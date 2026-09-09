from __future__ import annotations

import numpy as np
import pytest

from ai.retrieval.bm25 import (
    BM25Document,
    BM25Index,
)
from ai.retrieval.dense import (
    DenseDocument,
    DenseIndex,
)
from ai.services.retrieval_service import (
    RetrievalMethod,
    RetrievalRequest,
    RetrievalSafetyContext,
    RetrievalService,
)


def _embed_texts(
    texts: list[str],
) -> np.ndarray:
    vectors: list[list[float]] = []

    for text in texts:
        lowered = text.casefold()

        if "상품" in lowered:
            vectors.append(
                [1.0, 0.0, 0.0]
            )
        elif "주문" in lowered:
            vectors.append(
                [0.0, 1.0, 0.0]
            )
        else:
            vectors.append(
                [0.1, 0.1, 0.1]
            )

    return np.asarray(
        vectors,
        dtype=np.float32,
    )


def _service(
    *,
    source_type: str = "PRODUCT",
    freshness_state: str | None = None,
) -> RetrievalService:
    metadata = {
        "title": "테스트 상품",
        "name": "테스트 상품",
        "category": "test",
    }

    if freshness_state is not None:
        metadata[
            "freshness_state"
        ] = freshness_state

    if source_type in {
        "INVENTORY_SNAPSHOT",
        "INCOMING_STOCK",
        "ORDER_STATUS",
    }:
        metadata["as_of"] = (
            "2026-09-09T00:00:00+09:00"
        )

    bm25_document = BM25Document(
        chunk_id="chunk-001",
        source_id="source-001",
        source_type=source_type,
        version="v1",
        text="상품 주문 테스트 근거",
        metadata=metadata,
    )

    dense_document = DenseDocument(
        chunk_id="chunk-001",
        source_id="source-001",
        source_type=source_type,
        version="v1",
        text="상품 주문 테스트 근거",
        metadata=metadata,
    )

    return RetrievalService(
        bm25_index=BM25Index(
            [bm25_document]
        ),
        dense_index=DenseIndex(
            [dense_document],
            embed_texts=_embed_texts,
        ),
        bm25_index_version="bm25-test-v1",
        dense_index_version="dense-test-v1",
    )


def test_no_citation_returns_insufficient_evidence() -> None:
    service = _service()

    response = service.search(
        RetrievalRequest(
            query="존재하지않는토큰",
            method=RetrievalMethod.BM25,
        )
    )

    assert response.confidence in {
        "LOW",
        "ABSTAIN",
    }

    assert response.answer_status in {
        "HOLD",
        "INSUFFICIENT_EVIDENCE",
    }

    assert (
        response.answer_status
        != "DRAFT_AVAILABLE"
    )


def test_low_confidence_does_not_allow_draft() -> None:
    service = _service()

    response = service.search(
        RetrievalRequest(
            query="약한 검색",
            method=RetrievalMethod.VECTOR,
        )
    )

    if response.confidence in {
        "LOW",
        "ABSTAIN",
        "MEDIUM",
    }:
        assert (
            response.answer_status
            != "DRAFT_AVAILABLE"
        )


def test_stale_inventory_returns_hold() -> None:
    service = _service(
        source_type="INVENTORY_SNAPSHOT",
        freshness_state="STALE",
    )

    response = service.search(
        RetrievalRequest(
            query="상품 재고",
        )
    )

    assert response.answer_status == "HOLD"

    assert "STALE_EVIDENCE" in (
        response.human_review_reason
    )


def test_source_conflict_returns_hold() -> None:
    response = _service().search(
        RetrievalRequest(
            query="상품",
            safety=RetrievalSafetyContext(
                source_conflict=True
            ),
        )
    )

    assert response.answer_status == "HOLD"
    assert response.human_review_required
    assert "SOURCE_CONFLICT" in (
        response.human_review_reason
    )


def test_live_order_lookup_requires_human_review() -> None:
    response = _service().search(
        RetrievalRequest(
            query="주문 상태",
            safety=RetrievalSafetyContext(
                live_order_lookup_required=True
            ),
        )
    )

    assert (
        response.answer_status
        == "HUMAN_REVIEW"
    )

    assert "ORDER_STATUS" in (
        response.required_lookup
    )

    assert response.human_review_required


def test_delivery_address_change_requires_human_review() -> None:
    response = _service().search(
        RetrievalRequest(
            query="배송지 변경",
            safety=RetrievalSafetyContext(
                delivery_address_change=True
            ),
        )
    )

    assert (
        response.answer_status
        == "HUMAN_REVIEW"
    )

    assert response.human_review_required


def test_cancel_refund_requires_human_review() -> None:
    response = _service().search(
        RetrievalRequest(
            query="취소 환불",
            safety=RetrievalSafetyContext(
                cancel_refund=True
            ),
        )
    )

    assert (
        response.answer_status
        == "HUMAN_REVIEW"
    )

    assert "CANCEL_REFUND_HIGH_RISK" in (
        response.human_review_reason
    )


def test_unconfirmed_incoming_date_returns_hold() -> None:
    response = _service().search(
        RetrievalRequest(
            query="입고일",
            safety=RetrievalSafetyContext(
                incoming_date_unconfirmed=True
            ),
        )
    )

    assert response.answer_status == "HOLD"

    assert (
        "CONFIRMED_INCOMING_STOCK"
        in response.required_lookup
    )


def test_unconfirmed_policy_source_returns_hold() -> None:
    response = _service().search(
        RetrievalRequest(
            query="정책 문의",
            safety=RetrievalSafetyContext(
                policy_source_unconfirmed=True
            ),
        )
    )

    assert response.answer_status == "HOLD"

    assert "POLICY_SOURCE_UNCONFIRMED" in (
        response.human_review_reason
    )


def test_mapping_ambiguity_returns_hold() -> None:
    response = _service().search(
        RetrievalRequest(
            query="상품",
            safety=RetrievalSafetyContext(
                mapping_ambiguous=True
            ),
        )
    )

    assert response.answer_status == "HOLD"

    assert "MAPPING_AMBIGUOUS" in (
        response.human_review_reason
    )


@pytest.mark.parametrize(
    "safety",
    [
        RetrievalSafetyContext(
            source_conflict=True
        ),
        RetrievalSafetyContext(
            live_order_lookup_required=True
        ),
        RetrievalSafetyContext(
            delivery_address_change=True
        ),
        RetrievalSafetyContext(
            cancel_refund=True
        ),
        RetrievalSafetyContext(
            incoming_date_unconfirmed=True
        ),
        RetrievalSafetyContext(
            policy_source_unconfirmed=True
        ),
        RetrievalSafetyContext(
            mapping_ambiguous=True
        ),
    ],
)
def test_fallback_never_executes_external_tool(
    safety: RetrievalSafetyContext,
) -> None:
    external_tool_call_count = 0

    response = _service().search(
        RetrievalRequest(
            query="상품 주문",
            safety=safety,
        )
    )

    assert external_tool_call_count == 0

    assert response.answer_status in {
        "HOLD",
        "HUMAN_REVIEW",
        "INSUFFICIENT_EVIDENCE",
    }