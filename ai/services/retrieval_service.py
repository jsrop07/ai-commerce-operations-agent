from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Mapping, Sequence
from uuid import uuid4

from ai.retrieval.bm25 import BM25Index
from ai.retrieval.citation import build_citation
from ai.retrieval.confidence import (
    ConfidenceLevel,
    evaluate_confidence,
)
from ai.retrieval.dense import DenseIndex
from ai.retrieval.filters import MetadataFilter
from ai.retrieval.freshness import FreshnessState


class RetrievalMethod(str, Enum):
    """Day 8에서 허용하는 단일 Retriever."""

    BM25 = "BM25"
    VECTOR = "VECTOR"


@dataclass(frozen=True)
class RetrievalSafetyContext:
    """
    Retrieval 결과만으로 확답하면 안 되는
    운영 조건을 전달한다.

    외부 Provider 실행은 수행하지 않는다.
    """

    live_order_lookup_required: bool = False
    delivery_address_change: bool = False
    cancel_refund: bool = False
    incoming_date_unconfirmed: bool = False
    policy_source_unconfirmed: bool = False
    mapping_ambiguous: bool = False
    source_conflict: bool = False
    
@dataclass(frozen=True)
class RetrievalRequest:
    """AI Retrieval service의 입력 계약."""

    query: str
    filters: tuple[MetadataFilter, ...] = ()
    top_k: int = 5
    method: RetrievalMethod = RetrievalMethod.BM25
    safety: RetrievalSafetyContext = (
        RetrievalSafetyContext()
    )

    def __post_init__(self) -> None:
        if not self.query.strip():
            raise ValueError("query must not be empty")

        if self.top_k <= 0:
            raise ValueError(
                "top_k must be greater than 0"
            )

        if self.top_k > 50:
            raise ValueError(
                "top_k must not exceed 50"
            )

@dataclass(frozen=True)
class RetrievalCitation:
    """
    Backend Retrieval Consumer Projection에 전달할
    citation 최소 필드.

    기존 citation.py의 검증 규칙을 재사용하되,
    Backend가 필요한 source_type/score를 추가한다.
    """

    source_type: str
    source_id: str
    title: str
    record_or_field: str
    as_of: str | None
    score: float
    excerpt_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RetrievalResponse:
    """D08-AI-01~03 Retrieval service 결과."""

    request_id: str
    trace_id: str
    query: str
    method: str
    citations: tuple[RetrievalCitation, ...]
    confidence: str
    index_version: str
    warnings: tuple[str, ...]

    answer_status: str
    required_lookup: tuple[str, ...]
    human_review_required: bool
    human_review_reason: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "trace_id": self.trace_id,
            "query": self.query,
            "method": self.method,
            "citations": [
                citation.to_dict()
                for citation in self.citations
            ],
            "confidence": self.confidence,
            "index_version": self.index_version,
            "warnings": list(self.warnings),
            "answer_status": self.answer_status,
            "required_lookup": list(
                self.required_lookup
            ),
            "human_review_required": (
                self.human_review_required
            ),
            "human_review_reason": list(
                self.human_review_reason
            ),
        }


class RetrievalService:
    """
    Day 7에서 검증한 BM25/Dense Index를
    Day 8 공통 서비스 계약으로 연결한다.

    Hybrid/RRF/query rewrite는 Day 9 범위이므로
    이 서비스에서는 구현하지 않는다.
    """

    def __init__(
        self,
        *,
        bm25_index: BM25Index,
        dense_index: DenseIndex,
        bm25_index_version: str,
        dense_index_version: str,
    ) -> None:
        self._bm25_index = bm25_index
        self._dense_index = dense_index

        self._index_versions = {
            RetrievalMethod.BM25: (
                bm25_index_version
            ),
            RetrievalMethod.VECTOR: (
                dense_index_version
            ),
        }

    def search(
        self,
        request: RetrievalRequest,
    ) -> RetrievalResponse:
        method = RetrievalMethod(
            request.method
        )

        if method == RetrievalMethod.BM25:
            results = self._bm25_index.search(
                request.query,
                top_k=request.top_k,
                filters=request.filters,
            )
            documents = (
                self._bm25_index.documents
            )
            confidence_retriever = "bm25"

        elif method == RetrievalMethod.VECTOR:
            results = self._dense_index.search(
                request.query,
                top_k=request.top_k,
                filters=request.filters,
            )
            documents = (
                self._dense_index.documents
            )
            confidence_retriever = "dense"

        else:
            raise ValueError(
                f"unsupported retrieval method: {method}"
            )

        documents_by_chunk_id = {
            document.chunk_id: document
            for document in documents
        }

        citations: list[
            RetrievalCitation
        ] = []

        warnings: list[str] = []

        freshness_states: list[
            FreshnessState
        ] = []

        scores: list[float] = []

        for result in results:
            document = documents_by_chunk_id.get(
                result.chunk_id
            )

            if document is None:
                warnings.append(
                    "RESULT_DOCUMENT_NOT_FOUND"
                )
                continue

            scores.append(float(result.score))

            freshness_state = (
                self._resolve_freshness_state(
                    source_type=(
                        result.source_type
                    ),
                    metadata=result.metadata,
                )
            )

            freshness_states.append(
                freshness_state
            )

            try:
                citation = (
                    self._build_retrieval_citation(
                        result=result,
                        document=document,
                    )
                )
            except ValueError:
                warnings.append(
                    "INVALID_CITATION_EVIDENCE"
                )
                continue

            citations.append(citation)

        confidence_result = evaluate_confidence(
            retriever=confidence_retriever,
            scores=scores,
            freshness_states=(
                freshness_states
            ),
        )
        (
            answer_status,
            required_lookup,
            human_review_required,
            human_review_reason,
        ) = self._resolve_answer_policy(
            confidence_level=(
                confidence_result.level
            ),
            citation_count=len(citations),
            freshness_states=(
                freshness_states
            ),
            safety=request.safety,
        )
        if (
            confidence_result.level
            in {
                ConfidenceLevel.LOW,
                ConfidenceLevel.ABSTAIN,
            }
        ):
            warnings.append(
                "LOW_OR_INSUFFICIENT_CONFIDENCE"
            )

        if not confidence_result.answer_allowed:
            warnings.append(
                "ANSWER_NOT_ALLOWED"
            )

        return RetrievalResponse(
            request_id=(
                "req-"
                + uuid4().hex
            ),
            trace_id=(
                "trace-"
                + uuid4().hex
            ),
            query=request.query,
            method=method.value,
            citations=tuple(citations),
            confidence=(
                confidence_result.level.value
            ),
            index_version=(
                self._index_versions[method]
            ),
            warnings=tuple(
                dict.fromkeys(warnings)
            ),
            answer_status=answer_status,
            required_lookup=required_lookup,
            human_review_required=(
                human_review_required
            ),
            human_review_reason=(
                human_review_reason
            ),
        )
    @staticmethod
    def _resolve_freshness_state(
        *,
        source_type: str,
        metadata: Mapping[str, str],
    ) -> FreshnessState:
        """
        Product처럼 live fact가 아닌 Corpus는
        현재 index snapshot 내부에서 FRESH로 취급한다.

        Inventory/Incoming/Order 같은 live source는
        freshness_state가 명시되지 않으면
        확정 근거로 쓰지 않는다.
        """

        live_source_types = {
            "INVENTORY_SNAPSHOT",
            "INCOMING_STOCK",
            "ORDER_STATUS",
        }

        if source_type not in live_source_types:
            return FreshnessState.FRESH

        raw_state = (
            metadata.get("freshness_state")
            or ""
        ).strip().upper()

        if not raw_state:
            return FreshnessState.MISSING

        try:
            return FreshnessState(raw_state)
        except ValueError:
            return FreshnessState.MISSING

    @staticmethod
    def _build_retrieval_citation(
        *,
        result: Any,
        document: Any,
    ) -> RetrievalCitation:
        metadata = result.metadata

        title = (
            metadata.get("title")
            or metadata.get("name")
            or result.source_id
        )

        as_of = (
            metadata.get("as_of")
            or None
        )

        validated = build_citation(
            {
                "source_id": result.source_id,
                "title": title,
                "record_id": result.chunk_id,
                "source_type": result.source_type,
                "as_of": as_of,
                "field_or_path": "text",
                "excerpt": document.text,
            }
        )

        return RetrievalCitation(
            source_type=result.source_type,
            source_id=validated.source_id,
            title=validated.title,
            record_or_field=(
                validated.field_or_path
            ),
            as_of=validated.as_of,
            score=float(result.score),
            excerpt_hash=(
                validated.excerpt_hash
            ),
        )

    @staticmethod
    def _resolve_answer_policy(
        *,
        confidence_level: ConfidenceLevel,
        citation_count: int,
        freshness_states: Sequence[
            FreshnessState
        ],
        safety: RetrievalSafetyContext,
    ) -> tuple[
        str,
        tuple[str, ...],
        bool,
        tuple[str, ...],
    ]:
        """
        Retrieval 결과를 운영 안전 상태로 변환한다.

        반환:
        - answer_status
        - required_lookup
        - human_review_required
        - human_review_reason
        """

        required_lookup: list[str] = []

        if citation_count == 0:
            return (
                "INSUFFICIENT_EVIDENCE",
                (),
                False,
                ("NO_VALID_CITATION",),
            )

        if (
            FreshnessState.STALE
            in freshness_states
        ):
            return (
                "HOLD",
                (),
                False,
                ("STALE_EVIDENCE",),
            )

        if any(
            state
            in {
                FreshnessState.MISSING,
                FreshnessState.POLICY_UNDEFINED,
            }
            for state in freshness_states
        ):
            return (
                "HOLD",
                (),
                False,
                ("FRESHNESS_UNVERIFIED",),
            )

        if safety.source_conflict:
            return (
                "HOLD",
                (),
                True,
                ("SOURCE_CONFLICT",),
            )

        if safety.mapping_ambiguous:
            return (
                "HOLD",
                (),
                True,
                ("MAPPING_AMBIGUOUS",),
            )

        if safety.policy_source_unconfirmed:
            return (
                "HOLD",
                (),
                True,
                ("POLICY_SOURCE_UNCONFIRMED",),
            )

        if safety.incoming_date_unconfirmed:
            required_lookup.append(
                "CONFIRMED_INCOMING_STOCK"
            )

            return (
                "HOLD",
                tuple(required_lookup),
                True,
                ("INCOMING_DATE_UNCONFIRMED",),
            )

        if safety.live_order_lookup_required:
            required_lookup.append(
                "ORDER_STATUS"
            )

            return (
                "HUMAN_REVIEW",
                tuple(required_lookup),
                True,
                ("LIVE_ORDER_LOOKUP_REQUIRED",),
            )

        if safety.delivery_address_change:
            required_lookup.append(
                "AUTHORIZED_ORDER_REFERENCE"
            )

            return (
                "HUMAN_REVIEW",
                tuple(required_lookup),
                True,
                ("DELIVERY_ADDRESS_CHANGE",),
            )

        if safety.cancel_refund:
            required_lookup.append(
                "AUTHORIZED_ORDER_REFERENCE"
            )

            return (
                "HUMAN_REVIEW",
                tuple(required_lookup),
                True,
                ("CANCEL_REFUND_HIGH_RISK",),
            )

        if confidence_level in {
            ConfidenceLevel.LOW,
            ConfidenceLevel.ABSTAIN,
        }:
            return (
                "HOLD",
                (),
                False,
                ("LOW_RETRIEVAL_CONFIDENCE",),
            )

        if (
            confidence_level
            == ConfidenceLevel.MEDIUM
        ):
            return (
                "HOLD",
                (),
                False,
                ("MEDIUM_REQUIRES_HOLD",),
            )

        return (
            "DRAFT_AVAILABLE",
            (),
            False,
            (),
        )
