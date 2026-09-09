from __future__ import annotations

import numpy as np

from ai.retrieval.bm25 import (
    BM25Document,
    BM25Index,
)
from ai.retrieval.dense import (
    DenseDocument,
    DenseIndex,
)
from ai.retrieval.filters import (
    FilterConfidence,
    MetadataFilter,
)
from ai.retrieval.trace import (
    TRACE_SCHEMA_VERSION,
    build_query_hash,
    build_retrieval_trace,
    validate_retrieval_trace,
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

        if "스타터" in lowered:
            vectors.append(
                [1.0, 0.0]
            )
        elif "페인트" in lowered:
            vectors.append(
                [0.0, 1.0]
            )
        else:
            vectors.append(
                [0.5, 0.5]
            )

    return np.asarray(
        vectors,
        dtype=np.float32,
    )


def _indexes() -> tuple[
    BM25Index,
    DenseIndex,
]:
    bm25_documents = [
        BM25Document(
            chunk_id="chunk-001",
            source_id="product-001",
            source_type="PRODUCT",
            version="v1",
            text="워해머 스타터 세트",
            metadata={
                "title": "워해머 스타터 세트",
                "category": "starter",
                "language": "ko",
            },
        ),
        BM25Document(
            chunk_id="chunk-002",
            source_id="product-002",
            source_type="PRODUCT",
            version="v1",
            text="워해머 페인트 세트",
            metadata={
                "title": "워해머 페인트 세트",
                "category": "paint",
                "language": "ko",
            },
        ),
    ]

    dense_documents = [
        DenseDocument(
            chunk_id=document.chunk_id,
            source_id=document.source_id,
            source_type=document.source_type,
            version=document.version,
            text=document.text,
            metadata=document.metadata,
        )
        for document in bm25_documents
    ]

    return (
        BM25Index(
            bm25_documents
        ),
        DenseIndex(
            dense_documents,
            embed_texts=_embed_texts,
        ),
    )


def test_query_hash_is_deterministic() -> None:
    left = build_query_hash(
        "워해머   스타터"
    )

    right = build_query_hash(
        "워해머 스타터"
    )

    assert left == right
    assert left.startswith("sha256:")


def test_trace_preserves_request_and_trace_id() -> None:
    bm25_index, dense_index = _indexes()

    service = RetrievalService(
        bm25_index=bm25_index,
        dense_index=dense_index,
        bm25_index_version=(
            "bm25-trace-test-v1"
        ),
        dense_index_version=(
            "dense-trace-test-v1"
        ),
    )

    request = RetrievalRequest(
        query="워해머 스타터",
        method=RetrievalMethod.BM25,
        top_k=1,
    )

    response = service.search(
        request
    )

    results = bm25_index.search(
        request.query,
        top_k=request.top_k,
        filters=request.filters,
    )

    trace = build_retrieval_trace(
        request=request,
        response=response,
        search_results=results,
        sanitized_query=(
            "워해머 스타터"
        ),
    )

    assert trace.request_id == (
        response.request_id
    )

    assert trace.trace_id == (
        response.trace_id
    )

    assert (
        trace.schema_version
        == TRACE_SCHEMA_VERSION
    )


def test_trace_records_filter_and_candidate() -> None:
    bm25_index, dense_index = _indexes()

    service = RetrievalService(
        bm25_index=bm25_index,
        dense_index=dense_index,
        bm25_index_version="bm25-v1",
        dense_index_version="dense-v1",
    )

    request = RetrievalRequest(
        query="워해머",
        method=RetrievalMethod.BM25,
        top_k=2,
        filters=(
            MetadataFilter(
                field="category",
                value="starter",
                confidence=(
                    FilterConfidence.EXACT
                ),
            ),
        ),
    )

    response = service.search(
        request
    )

    results = bm25_index.search(
        request.query,
        top_k=request.top_k,
        filters=request.filters,
    )

    trace = build_retrieval_trace(
        request=request,
        response=response,
        search_results=results,
        sanitized_query="워해머",
    )

    payload = trace.to_dict()

    assert payload[
        "retrieval"
    ]["filters"] == [
        {
            "field": "category",
            "value": "starter",
            "confidence": "EXACT",
        }
    ]

    assert payload[
        "retrieval"
    ]["candidates_before_rerank"]

    candidate = payload[
        "retrieval"
    ]["candidates_before_rerank"][0]

    assert candidate["source_id"]
    assert candidate["chunk_id"]
    assert candidate["score"] >= 0.0


def test_trace_records_decision_fields() -> None:
    bm25_index, dense_index = _indexes()

    service = RetrievalService(
        bm25_index=bm25_index,
        dense_index=dense_index,
        bm25_index_version="bm25-v1",
        dense_index_version="dense-v1",
    )

    request = RetrievalRequest(
        query="주문 상태",
        safety=RetrievalSafetyContext(
            live_order_lookup_required=True
        ),
    )

    response = service.search(
        request
    )

    results = bm25_index.search(
        request.query,
        top_k=request.top_k,
        filters=request.filters,
    )

    trace = build_retrieval_trace(
        request=request,
        response=response,
        search_results=results,
        sanitized_query="주문 상태",
    )

    payload = trace.to_dict()

    assert payload[
        "decision"
    ]["answer_status"] == (
        response.answer_status
    )

    assert payload[
        "decision"
    ]["required_lookup"] == list(
        response.required_lookup
    )

    assert payload[
        "decision"
    ][
        "human_review_required"
    ] == response.human_review_required


def test_trace_does_not_claim_raw_pii() -> None:
    bm25_index, dense_index = _indexes()

    service = RetrievalService(
        bm25_index=bm25_index,
        dense_index=dense_index,
        bm25_index_version="bm25-v1",
        dense_index_version="dense-v1",
    )

    request = RetrievalRequest(
        query="상품 문의"
    )

    response = service.search(
        request
    )

    results = bm25_index.search(
        request.query,
        top_k=request.top_k,
        filters=request.filters,
    )

    trace = build_retrieval_trace(
        request=request,
        response=response,
        search_results=results,
        sanitized_query="상품 문의",
    )

    errors = validate_retrieval_trace(
        trace
    )

    assert errors == []

    payload = trace.to_dict()

    assert (
        payload["safety"][
            "raw_pii_included"
        ]
        is False
    )

    assert (
        payload["safety"][
            "raw_customer_text_included"
        ]
        is False
    )

    assert (
        payload["safety"][
            "production_write"
        ]
        is False
    )

    assert (
        payload["safety"][
            "provider_calls"
        ]
        == 0
    )

    assert (
        payload["safety"][
            "tool_calls"
        ]
        == 0
    )


def test_day8_has_no_query_rewrite() -> None:
    bm25_index, dense_index = _indexes()

    service = RetrievalService(
        bm25_index=bm25_index,
        dense_index=dense_index,
        bm25_index_version="bm25-v1",
        dense_index_version="dense-v1",
    )

    request = RetrievalRequest(
        query="워해머 스타터"
    )

    response = service.search(
        request
    )

    results = bm25_index.search(
        request.query
    )

    trace = build_retrieval_trace(
        request=request,
        response=response,
        search_results=results,
        sanitized_query=(
            "워해머 스타터"
        ),
        rewritten_query=None,
    )

    assert (
        trace.rewrite_applied
        is False
    )

    assert (
        trace.rewritten_query
        is None
    )