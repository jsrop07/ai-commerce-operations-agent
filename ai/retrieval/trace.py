from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

from ai.retrieval.filters import MetadataFilter
from ai.services.retrieval_service import (
    RetrievalRequest,
    RetrievalResponse,
)


TRACE_SCHEMA_VERSION = "retrieval-trace.v1"


def build_query_hash(
    query: str,
) -> str:
    """
    Trace 비교용 query hash.

    공백을 정규화한 뒤 SHA256을 생성한다.
    """
    normalized = " ".join(
        query.split()
    )

    digest = hashlib.sha256(
        normalized.encode("utf-8")
    ).hexdigest()

    return f"sha256:{digest}"


@dataclass(frozen=True)
class TraceFilter:
    field: str
    value: str
    confidence: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TraceCandidate:
    """
    검색 후보 기록.

    고객 원문이나 document text는 저장하지 않는다.
    """

    rank: int
    chunk_id: str
    source_id: str
    source_type: str
    version: str
    score: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RetrievalTrace:
    schema_version: str

    request_id: str
    trace_id: str

    query_hash: str
    sanitized_query: str

    rewrite_applied: bool
    rewritten_query: str | None

    method: str
    top_k: int
    filters: tuple[TraceFilter, ...]

    candidates_before_rerank: tuple[
        TraceCandidate,
        ...
    ]

    citations: tuple[
        Mapping[str, Any],
        ...
    ]

    confidence: str
    answer_status: str

    required_lookup: tuple[str, ...]
    human_review_required: bool
    human_review_reason: tuple[str, ...]

    index_version: str

    raw_pii_included: bool
    raw_customer_text_included: bool
    production_write: bool
    provider_calls: int
    tool_calls: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": (
                self.schema_version
            ),
            "request_id": self.request_id,
            "trace_id": self.trace_id,
            "query": {
                "hash": self.query_hash,
                "sanitized": (
                    self.sanitized_query
                ),
                "rewrite_applied": (
                    self.rewrite_applied
                ),
                "rewritten": (
                    self.rewritten_query
                ),
            },
            "retrieval": {
                "method": self.method,
                "top_k": self.top_k,
                "filters": [
                    item.to_dict()
                    for item in self.filters
                ],
                "candidates_before_rerank": [
                    item.to_dict()
                    for item
                    in (
                        self
                        .candidates_before_rerank
                    )
                ],
                "index_version": (
                    self.index_version
                ),
            },
            "citations": [
                dict(item)
                for item in self.citations
            ],
            "decision": {
                "confidence": (
                    self.confidence
                ),
                "answer_status": (
                    self.answer_status
                ),
                "required_lookup": list(
                    self.required_lookup
                ),
                "human_review_required": (
                    self
                    .human_review_required
                ),
                "human_review_reason": list(
                    self.human_review_reason
                ),
            },
            "safety": {
                "raw_pii_included": (
                    self.raw_pii_included
                ),
                "raw_customer_text_included": (
                    self
                    .raw_customer_text_included
                ),
                "production_write": (
                    self.production_write
                ),
                "provider_calls": (
                    self.provider_calls
                ),
                "tool_calls": (
                    self.tool_calls
                ),
            },
        }


def _filter_to_trace(
    metadata_filter: MetadataFilter,
) -> TraceFilter:
    confidence = (
        metadata_filter.confidence.value
        if hasattr(
            metadata_filter.confidence,
            "value",
        )
        else str(
            metadata_filter.confidence
        )
    )

    return TraceFilter(
        field=metadata_filter.field,
        value=metadata_filter.value,
        confidence=confidence,
    )


def build_retrieval_trace(
    *,
    request: RetrievalRequest,
    response: RetrievalResponse,
    search_results: Sequence[Any],
    sanitized_query: str,
    rewritten_query: str | None = None,
) -> RetrievalTrace:
    """
    D08-AI-04 Retrieval Trace 생성.

    search_results는 Retriever가 반환한
    ranking 결과이며 raw document text는
    Trace에 저장하지 않는다.
    """

    if not sanitized_query.strip():
        raise ValueError(
            "sanitized_query must not be empty"
        )

    if (
        response.request_id.strip()
        == ""
    ):
        raise ValueError(
            "request_id must not be empty"
        )

    if response.trace_id.strip() == "":
        raise ValueError(
            "trace_id must not be empty"
        )

    candidates = tuple(
        TraceCandidate(
            rank=int(result.rank),
            chunk_id=str(
                result.chunk_id
            ),
            source_id=str(
                result.source_id
            ),
            source_type=str(
                result.source_type
            ),
            version=str(
                result.version
            ),
            score=float(
                result.score
            ),
        )
        for result in search_results
    )

    citation_dicts = tuple(
        citation.to_dict()
        for citation
        in response.citations
    )

    return RetrievalTrace(
        schema_version=(
            TRACE_SCHEMA_VERSION
        ),
        request_id=(
            response.request_id
        ),
        trace_id=response.trace_id,
        query_hash=build_query_hash(
            sanitized_query
        ),
        sanitized_query=(
            sanitized_query
        ),
        rewrite_applied=(
            rewritten_query is not None
            and rewritten_query
            != sanitized_query
        ),
        rewritten_query=(
            rewritten_query
        ),
        method=response.method,
        top_k=request.top_k,
        filters=tuple(
            _filter_to_trace(item)
            for item in request.filters
        ),
        candidates_before_rerank=(
            candidates
        ),
        citations=citation_dicts,
        confidence=(
            response.confidence
        ),
        answer_status=(
            response.answer_status
        ),
        required_lookup=(
            response.required_lookup
        ),
        human_review_required=(
            response.human_review_required
        ),
        human_review_reason=(
            response.human_review_reason
        ),
        index_version=(
            response.index_version
        ),
        raw_pii_included=False,
        raw_customer_text_included=False,
        production_write=False,
        provider_calls=0,
        tool_calls=0,
    )


def validate_retrieval_trace(
    trace: RetrievalTrace,
) -> list[str]:
    """
    D08 Retrieval Trace 최소 안전 검증.
    """
    errors: list[str] = []

    if (
        trace.schema_version
        != TRACE_SCHEMA_VERSION
    ):
        errors.append(
            "invalid schema_version"
        )

    if not trace.request_id:
        errors.append(
            "request_id is empty"
        )

    if not trace.trace_id:
        errors.append(
            "trace_id is empty"
        )

    if not trace.query_hash.startswith(
        "sha256:"
    ):
        errors.append(
            "invalid query_hash"
        )

    if not trace.sanitized_query:
        errors.append(
            "sanitized_query is empty"
        )

    if trace.raw_pii_included:
        errors.append(
            "raw_pii_included must be false"
        )

    if trace.raw_customer_text_included:
        errors.append(
            "raw_customer_text_included "
            "must be false"
        )

    if trace.production_write:
        errors.append(
            "production_write must be false"
        )

    if trace.provider_calls != 0:
        errors.append(
            "provider_calls must be zero"
        )

    if trace.tool_calls != 0:
        errors.append(
            "tool_calls must be zero"
        )

    return errors