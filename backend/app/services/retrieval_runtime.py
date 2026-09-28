"""Read-only retrieval over validated synthetic v3 rows. No model/provider imports."""

import re
import unicodedata
from threading import Lock
from typing import Literal

import anyio
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.services.c04_lookup import SENSITIVE_REFERENCE, LookupFailure, SourceType
from backend.app.services.corpus_restore import SNAPSHOT_VERSION, RestoredCorpus
from backend.app.worker.privacy.text_redaction import (
    EMAIL_PATTERN,
    ORDER_ID_PATTERN,
    PHONE_PATTERN,
)

PRIVATE_QUERY = re.compile(
    r"\b(?:order_line|affected_order_ids|reservation_id)\b|"
    r"\b(?:order|customer|reservation|payment|inquiry)[ _-]?(?:id|number|ref)\b|"
    r"\b(?:order|ord|customer|cust|reservation|res)[_#-][A-Za-z0-9-]+|"
    r"\b(?:order|customer)\s+(?:#[A-Za-z0-9-]+|\d+)|"
    r"(?:주문|예약|고객)\s*(?:번호|아이디)|배송지|결제정보|카드번호|계좌번호|"
    r"문의\s*원문|(?:feedback|자유메모)\s*[:=]|"
    r"(?:shipping\s+address|payment\s+details|inquiry\s+text|feedback\s+memo)|"
    r"\b(?:\d[ -]?){13,19}\b|[가-힣]+(?:로|길)\s*\d+",
    re.IGNORECASE,
)


class SearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=2000, strict=True)
    top_k: int = Field(default=5, ge=1, le=50, strict=True)
    method: Literal["BM25", "VECTOR"] | None = None
    source_type: SourceType | None = None

    @field_validator("query")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("query must not be empty")
        return value.strip()


class RetrievalFailure(Exception):
    def __init__(self, status: int, code: str):
        self.status, self.code = status, code
        super().__init__(code)


def validate_query(query: str) -> None:
    normalized = unicodedata.normalize("NFKC", query)
    normalized = "".join(c for c in normalized if unicodedata.category(c) != "Cf")
    if any(pattern.search(normalized) for pattern in (
        SENSITIVE_REFERENCE, PRIVATE_QUERY, EMAIL_PATTERN, PHONE_PATTERN, ORDER_ID_PATTERN,
    )):
        raise RetrievalFailure(403, "RETRIEVAL_SAFETY_BLOCKED")


class RetrievalRuntime:
    def __init__(self, *, corpus: RestoredCorpus | None, tenant_id: str,
                 method: str | None = None, timeout_seconds: float = 5.0):
        self.corpus = corpus
        self.tenant_id = tenant_id
        self.method = (method or (corpus.selection_method if corpus else "") or "").upper()
        self.selection_status = (
            corpus.selection_status
            if corpus and self.method == (corpus.selection_method or "").upper()
            else "CONFIG_OVERRIDE"
        )
        self.timeout_seconds = timeout_seconds
        self._busy = Lock()

    async def search(self, request: SearchInput):
        validate_query(request.query)  # Before AI imports, index construction, or search.
        if request.method is not None and request.method != self.method:
            raise RetrievalFailure(422, "RETRIEVAL_METHOD_MISMATCH")
        if self.corpus is None or self.corpus.status != "READY":
            raise RetrievalFailure(503, "RETRIEVAL_RUNTIME_UNAVAILABLE")
        if self.method != "BM25" or not self.corpus.search_rows:
            raise RetrievalFailure(503, "RETRIEVAL_INDEX_UNAVAILABLE")
        try:
            with anyio.fail_after(self.timeout_seconds):
                return await anyio.to_thread.run_sync(self._search, request, abandon_on_cancel=True)
        except TimeoutError:
            # A timed-out worker retains _busy until it finishes; its output is discarded.
            raise RetrievalFailure(504, "RETRIEVAL_TIMEOUT") from None
        except RetrievalFailure:
            raise
        except Exception:
            raise RetrievalFailure(503, "RETRIEVAL_RUNTIME_UNAVAILABLE") from None

    def _search(self, request: SearchInput):
        if not self._busy.acquire(blocking=False):
            raise RetrievalFailure(503, "RETRIEVAL_RUNTIME_BUSY")
        try:
            return self._execute(request)
        finally:
            self._busy.release()

    def _execute(self, request: SearchInput):
        from ai.retrieval.bm25 import BM25Document, BM25Index
        from ai.retrieval.citation import build_excerpt_hash
        from ai.retrieval.filters import FilterConfidence, MetadataFilter
        from ai.services.retrieval_service import (
            RetrievalMethod,
            RetrievalRequest,
            RetrievalService,
        )

        corpus = self.corpus
        documents = []
        verified = {}
        for row in corpus.search_rows:
            if row["tenant_id"] != self.tenant_id or row["data_mode"] != "SYNTHETIC_DEMO":
                raise RetrievalFailure(503, "RETRIEVAL_INDEX_UNAVAILABLE")
            exact = corpus.lookup_service.lookup(
                tenant_id=self.tenant_id, source_id=row["source_id"], version=row["version"],
            )
            if exact.visibility != "DEMO_PUBLIC" or exact.data_mode != "SYNTHETIC_DEMO":
                raise RetrievalFailure(503, "RETRIEVAL_INDEX_UNAVAILABLE")
            metadata = dict(row["metadata"])
            metadata.update(
                source_type=exact.source_type, tenant_id=self.tenant_id,
                visibility=exact.visibility, data_mode=exact.data_mode,
                as_of=exact.as_of.isoformat() if exact.as_of else "",
                freshness_state="STALE" if exact.stale else "FRESH",
            )
            documents.append(BM25Document(
                chunk_id=row["chunk_id"], source_id=row["source_id"],
                source_type=row["source_type"], version=row["version"],
                text=row["text"], metadata=metadata,
            ))
            verified[row["chunk_id"]] = row
        # All documents have source_type; reject no-match rather than AI filter fallback.
        if request.source_type and not any(d.source_type == request.source_type for d in documents):
            raise RetrievalFailure(503, "RETRIEVAL_INDEX_UNAVAILABLE")
        filters = (() if request.source_type is None else (
            MetadataFilter("source_type", request.source_type, FilterConfidence.EXACT),
        ))
        try:
            index = BM25Index(documents)
        except (TypeError, ValueError):
            raise RetrievalFailure(503, "RETRIEVAL_INDEX_UNAVAILABLE") from None
        service = RetrievalService(bm25_index=index, bm25_index_version=SNAPSHOT_VERSION)
        result = service.search(RetrievalRequest(
            query=request.query, top_k=request.top_k, method=RetrievalMethod(self.method),
            filters=filters,
        ))
        citations = []
        for rank, citation in enumerate(result.citations, 1):
            row = verified.get(citation.semantic_chunk_id)
            if (row is None or row["source_id"] != citation.source_id
                    or row["version"] != citation.version or row["text"] != citation.excerpt
                    or row["source_type"] != citation.source_type
                    or citation.excerpt_hash != build_excerpt_hash(citation.excerpt)
                    or (request.source_type and citation.source_type != request.source_type)):
                raise RetrievalFailure(503, "RETRIEVAL_CITATION_INVALID")
            key, c04_hash = None, None
            try:
                mapping = corpus.resolve(
                    tenant_id=self.tenant_id, source_id=citation.source_id,
                    version=citation.version, semantic_chunk_id=citation.semantic_chunk_id,
                    semantic_excerpt_hash=citation.excerpt_hash,
                )
                key = dict(source_id=mapping.source_id, version=mapping.version,
                           chunk_id=mapping.c04_chunk_id)
                c04_hash = mapping.c04_excerpt_hash
            except LookupFailure as exc:
                if exc.status_code != 404:
                    raise
            citations.append(dict(
                rank=rank, score=citation.score, source_type=citation.source_type,
                source_id=citation.source_id, title=citation.title, version=citation.version,
                semantic_chunk_id=citation.semantic_chunk_id, semantic_excerpt=citation.excerpt,
                semantic_excerpt_hash=citation.excerpt_hash, as_of=citation.as_of,
                c04_lookup=key, c04_excerpt_hash=c04_hash,
                mapping_status="MAPPED" if key else "MAPPING_MISSING",
            ))
        return result, dict(
            method=result.method, selection_status=self.selection_status,
            data_mode="SYNTHETIC_DEMO", index_version=result.index_version,
            actual_retrieval_executed=True, citations=citations,
            result_status="RESULTS" if citations else "ZERO_CITATIONS",
            answer_status=result.answer_status, warnings=list(result.warnings),
            required_lookup=list(result.required_lookup),
            human_review_required=result.human_review_required,
            human_review_reason=list(result.human_review_reason),
        )
