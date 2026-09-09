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
from ai.retrieval.filters import (
    FilterConfidence,
    MetadataFilter,
)
from ai.services.retrieval_service import (
    RetrievalMethod,
    RetrievalRequest,
    RetrievalService,
)


def _bm25_documents() -> list[BM25Document]:
    return [
        BM25Document(
            chunk_id="chunk-001",
            source_id="product-001",
            source_type="PRODUCT",
            version="v1",
            text="워해머 스타터 세트 입문용 상품",
            metadata={
                "title": "워해머 스타터 세트",
                "name": "워해머 스타터 세트",
                "brand": "Games Workshop",
                "sku": "WH-STARTER",
                "category": "starter",
                "language": "ko",
                "as_of": "2026-09-09T00:00:00+09:00",
            },
        ),
        BM25Document(
            chunk_id="chunk-002",
            source_id="product-002",
            source_type="PRODUCT",
            version="v1",
            text="워해머 페인트 세트 도색용 상품",
            metadata={
                "title": "워해머 페인트 세트",
                "name": "워해머 페인트 세트",
                "brand": "Citadel",
                "sku": "WH-PAINT",
                "category": "paint",
                "language": "ko",
                "as_of": "2026-09-09T00:00:00+09:00",
            },
        ),
        BM25Document(
            chunk_id="chunk-003",
            source_id="product-003",
            source_type="PRODUCT",
            version="v1",
            text="보드게임 전략 확장 상품",
            metadata={
                "title": "전략 확장",
                "name": "전략 확장",
                "brand": "Example Brand",
                "sku": "BG-EXP",
                "category": "expansion",
                "language": "ko",
                "as_of": "2026-09-09T00:00:00+09:00",
            },
        ),
    ]


def _dense_documents() -> list[DenseDocument]:
    return [
        DenseDocument(
            chunk_id="chunk-001",
            source_id="product-001",
            source_type="PRODUCT",
            version="v1",
            text="워해머 스타터 세트 입문용 상품",
            metadata={
                "title": "워해머 스타터 세트",
                "name": "워해머 스타터 세트",
                "brand": "Games Workshop",
                "sku": "WH-STARTER",
                "category": "starter",
                "language": "ko",
                "as_of": "2026-09-09T00:00:00+09:00",
            },
        ),
        DenseDocument(
            chunk_id="chunk-002",
            source_id="product-002",
            source_type="PRODUCT",
            version="v1",
            text="워해머 페인트 세트 도색용 상품",
            metadata={
                "title": "워해머 페인트 세트",
                "name": "워해머 페인트 세트",
                "brand": "Citadel",
                "sku": "WH-PAINT",
                "category": "paint",
                "language": "ko",
                "as_of": "2026-09-09T00:00:00+09:00",
            },
        ),
        DenseDocument(
            chunk_id="chunk-003",
            source_id="product-003",
            source_type="PRODUCT",
            version="v1",
            text="보드게임 전략 확장 상품",
            metadata={
                "title": "전략 확장",
                "name": "전략 확장",
                "brand": "Example Brand",
                "sku": "BG-EXP",
                "category": "expansion",
                "language": "ko",
                "as_of": "2026-09-09T00:00:00+09:00",
            },
        ),
    ]


def _fake_embed_texts(
    texts: list[str],
) -> np.ndarray:
    vectors: list[list[float]] = []

    for text in texts:
        lowered = text.casefold()

        if "스타터" in lowered:
            vectors.append(
                [1.0, 0.0, 0.0]
            )
        elif "페인트" in lowered:
            vectors.append(
                [0.0, 1.0, 0.0]
            )
        elif "확장" in lowered:
            vectors.append(
                [0.0, 0.0, 1.0]
            )
        else:
            vectors.append(
                [0.33, 0.33, 0.33]
            )

    return np.asarray(
        vectors,
        dtype=np.float32,
    )


@pytest.fixture()
def retrieval_service() -> RetrievalService:
    bm25_index = BM25Index(
        _bm25_documents()
    )

    dense_index = DenseIndex(
        _dense_documents(),
        embed_texts=_fake_embed_texts,
    )

    return RetrievalService(
        bm25_index=bm25_index,
        dense_index=dense_index,
        bm25_index_version=(
            "bm25-day08-test-v1"
        ),
        dense_index_version=(
            "dense-day08-test-v1"
        ),
    )


def test_bm25_method_returns_contract_fields(
    retrieval_service: RetrievalService,
) -> None:
    response = retrieval_service.search(
        RetrievalRequest(
            query="워해머 스타터",
            top_k=2,
            method=RetrievalMethod.BM25,
        )
    )

    payload = response.to_dict()

    assert payload["method"] == "BM25"
    assert (
        payload["index_version"]
        == "bm25-day08-test-v1"
    )

    assert payload["request_id"].startswith(
        "req-"
    )

    assert payload["trace_id"].startswith(
        "trace-"
    )

    assert payload["query"] == (
        "워해머 스타터"
    )

    assert payload["confidence"] in {
        "HIGH",
        "MEDIUM",
        "LOW",
        "ABSTAIN",
    }

    assert payload["citations"]

    citation = payload["citations"][0]

    assert citation["source_type"] == (
        "PRODUCT"
    )

    assert citation["source_id"]
    assert citation["title"]
    assert citation["record_or_field"]
    assert citation["score"] >= 0.0

    assert citation[
        "excerpt_hash"
    ].startswith("sha256:")


def test_vector_method_uses_dense_index(
    retrieval_service: RetrievalService,
) -> None:
    response = retrieval_service.search(
        RetrievalRequest(
            query="페인트",
            top_k=1,
            method=RetrievalMethod.VECTOR,
        )
    )

    payload = response.to_dict()

    assert payload["method"] == "VECTOR"

    assert (
        payload["index_version"]
        == "dense-day08-test-v1"
    )

    assert len(
        payload["citations"]
    ) == 1

    assert (
        payload["citations"][0][
            "source_id"
        ]
        == "product-002"
    )


def test_top_k_limits_result_count(
    retrieval_service: RetrievalService,
) -> None:
    response = retrieval_service.search(
        RetrievalRequest(
            query="워해머",
            top_k=1,
            method=RetrievalMethod.BM25,
        )
    )

    assert len(
        response.citations
    ) <= 1


def test_exact_metadata_filter_is_passed_to_index(
    retrieval_service: RetrievalService,
) -> None:
    response = retrieval_service.search(
        RetrievalRequest(
            query="워해머",
            top_k=5,
            method=RetrievalMethod.BM25,
            filters=(
                MetadataFilter(
                    field="category",
                    value="paint",
                    confidence=(
                        FilterConfidence.EXACT
                    ),
                ),
            ),
        )
    )

    source_ids = {
        citation.source_id
        for citation in response.citations
    }

    assert "product-002" in source_ids
    assert "product-001" not in source_ids


def test_vector_filter_is_also_applied(
    retrieval_service: RetrievalService,
) -> None:
    response = retrieval_service.search(
        RetrievalRequest(
            query="확장",
            top_k=5,
            method=RetrievalMethod.VECTOR,
            filters=(
                MetadataFilter(
                    field="category",
                    value="expansion",
                    confidence=(
                        FilterConfidence.EXACT
                    ),
                ),
            ),
        )
    )

    source_ids = {
        citation.source_id
        for citation in response.citations
    }

    assert "product-003" in source_ids
    assert "product-001" not in source_ids
    assert "product-002" not in source_ids


def test_empty_query_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="query must not be empty",
    ):
        RetrievalRequest(
            query="   "
        )


def test_invalid_top_k_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "top_k must be greater than 0"
        ),
    ):
        RetrievalRequest(
            query="워해머",
            top_k=0,
        )


def test_excessive_top_k_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "top_k must not exceed 50"
        ),
    ):
        RetrievalRequest(
            query="워해머",
            top_k=51,
        )