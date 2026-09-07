from __future__ import annotations

import numpy as np
import pytest

from ai.retrieval.dense import (
    DenseDocument,
    DenseIndex,
    cosine_similarity,
    snapshot_to_dense_documents,
)

from ai.retrieval.filters import (
    FilterConfidence,
    MetadataFilter,
)

def _fake_embed(
    texts: list[str],
) -> np.ndarray:
    vectors = []

    for text in texts:
        lowered = text.lower()

        if "별빛" in lowered:
            vector = [1.0, 0.0, 0.0]

        elif "왕국" in lowered:
            vector = [0.0, 1.0, 0.0]

        elif "배송" in lowered:
            vector = [0.0, 0.0, 1.0]

        else:
            vector = [
                0.3,
                0.3,
                0.3,
            ]

        values = np.asarray(
            vector,
            dtype=np.float32,
        )

        norm = np.linalg.norm(
            values
        )

        if norm > 0:
            values = values / norm

        vectors.append(
            values
        )

    return np.stack(
        vectors
    )


def _documents() -> list[DenseDocument]:
    return [
        DenseDocument(
            chunk_id="chunk_1",
            source_id="product_demo_001",
            source_type="PRODUCT",
            version="v1",
            text="별빛 항해자 전략 게임",
            metadata={
                "name": "별빛 항해자",
            },
        ),
        DenseDocument(
            chunk_id="chunk_2",
            source_id="product_demo_002",
            source_type="PRODUCT",
            version="v1",
            text="왕국의 상인들 경제 전략 게임",
            metadata={
                "name": "왕국의 상인들",
            },
        ),
        DenseDocument(
            chunk_id="chunk_3",
            source_id="policy_shipping_demo",
            source_type="POLICY",
            version="v1",
            text="배송 및 예약상품 정책",
            metadata={
                "title": "배송 정책",
            },
        ),
    ]


def test_cosine_similarity_identical_vectors() -> None:
    left = np.asarray(
        [1.0, 0.0],
        dtype=np.float32,
    )

    right = np.asarray(
        [1.0, 0.0],
        dtype=np.float32,
    )

    assert cosine_similarity(
        left,
        right,
    ) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal_vectors() -> None:
    left = np.asarray(
        [1.0, 0.0],
        dtype=np.float32,
    )

    right = np.asarray(
        [0.0, 1.0],
        dtype=np.float32,
    )

    assert cosine_similarity(
        left,
        right,
    ) == pytest.approx(0.0)


def test_cosine_rejects_dimension_mismatch() -> None:
    with pytest.raises(ValueError):
        cosine_similarity(
            np.asarray([1.0, 0.0]),
            np.asarray([1.0, 0.0, 0.0]),
        )


def test_dense_index_reports_vector_dimension() -> None:
    index = DenseIndex(
        _documents(),
        embed_texts=_fake_embed,
    )

    assert (
        index.vector_dimension
        == 3
    )


def test_dense_exact_product_query_ranks_first() -> None:
    index = DenseIndex(
        _documents(),
        embed_texts=_fake_embed,
    )

    results = index.search(
        "별빛 항해자 알려줘",
        top_k=3,
    )

    assert (
        results[0].source_id
        == "product_demo_001"
    )

    assert results[0].score == pytest.approx(
        1.0
    )


def test_dense_policy_query_ranks_policy_first() -> None:
    index = DenseIndex(
        _documents(),
        embed_texts=_fake_embed,
    )

    results = index.search(
        "배송 기준 알려줘",
        top_k=3,
    )

    assert (
        results[0].source_id
        == "policy_shipping_demo"
    )


def test_dense_top_k_limits_results() -> None:
    index = DenseIndex(
        _documents(),
        embed_texts=_fake_embed,
    )

    results = index.search(
        "별빛",
        top_k=2,
    )

    assert len(results) == 2


def test_dense_invalid_top_k_is_rejected() -> None:
    index = DenseIndex(
        _documents(),
        embed_texts=_fake_embed,
    )

    with pytest.raises(ValueError):
        index.search(
            "별빛",
            top_k=0,
        )


def test_dense_rejects_empty_documents() -> None:
    with pytest.raises(ValueError):
        DenseIndex(
            [],
            embed_texts=_fake_embed,
        )


def test_dense_rejects_embedding_count_mismatch() -> None:
    def broken_embed(
        texts: list[str],
    ) -> np.ndarray:
        return np.asarray(
            [[1.0, 0.0]],
            dtype=np.float32,
        )

    with pytest.raises(ValueError):
        DenseIndex(
            _documents(),
            embed_texts=broken_embed,
        )


def test_snapshot_to_dense_documents_preserves_version() -> None:
    rows = [
        {
            "chunk_id": "chunk_v1",
            "source_id": "policy_shipping_demo",
            "source_type": "POLICY",
            "version": "v1",
            "text": "기존 배송 정책",
            "metadata": {
                "title": "배송 정책",
            },
        },
        {
            "chunk_id": "chunk_v2",
            "source_id": "policy_shipping_demo",
            "source_type": "POLICY",
            "version": "v2",
            "text": "개정 배송 정책",
            "metadata": {
                "title": "배송 정책",
            },
        },
    ]

    documents = (
        snapshot_to_dense_documents(
            rows
        )
    )

    assert [
        document.version
        for document in documents
    ] == [
        "v1",
        "v2",
    ]


def test_dense_search_is_deterministic() -> None:
    index = DenseIndex(
        _documents(),
        embed_texts=_fake_embed,
    )

    first = index.search(
        "알 수 없는 질문",
        top_k=3,
    )

    second = index.search(
        "알 수 없는 질문",
        top_k=3,
    )

    assert [
        (
            result.source_id,
            result.version,
            result.score,
        )
        for result in first
    ] == [
        (
            result.source_id,
            result.version,
            result.score,
        )
        for result in second
    ]

def test_dense_exact_filter_is_applied_before_scoring() -> None:
    index = DenseIndex(
        _documents(),
        embed_texts=_fake_embed,
    )

    results = index.search(
        "별빛",
        top_k=3,
        filters=[
            MetadataFilter(
                field="name",
                value="왕국의 상인들",
                confidence=(
                    FilterConfidence.EXACT
                ),
            )
        ],
    )

    source_ids = [
        result.source_id
        for result in results
    ]

    assert "product_demo_002" in source_ids
    assert "product_demo_001" not in source_ids


def test_dense_uncertain_filter_does_not_block_top_result() -> None:
    index = DenseIndex(
        _documents(),
        embed_texts=_fake_embed,
    )

    results = index.search(
        "별빛",
        top_k=3,
        filters=[
            MetadataFilter(
                field="name",
                value="왕국의 상인들",
                confidence=(
                    FilterConfidence.UNCERTAIN
                ),
            )
        ],
    )

    assert (
        results[0].source_id
        == "product_demo_001"
    )


def test_dense_no_match_filter_falls_back() -> None:
    index = DenseIndex(
        _documents(),
        embed_texts=_fake_embed,
    )

    results = index.search(
        "별빛",
        top_k=3,
        filters=[
            MetadataFilter(
                field="language",
                value="jp",
                confidence=(
                    FilterConfidence.EXACT
                ),
            )
        ],
    )

    assert (
        results[0].source_id
        == "product_demo_001"
    )