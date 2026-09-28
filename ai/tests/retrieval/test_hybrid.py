from ai.retrieval.bm25 import (
    BM25SearchResult,
)
from ai.retrieval.dense import (
    DenseSearchResult,
)
from ai.retrieval.hybrid import (
    reciprocal_rank_fusion,
    weighted_hybrid,
)

import pytest


def _bm25(
    *,
    rank: int,
    source_id: str,
    score: float,
) -> BM25SearchResult:
    return BM25SearchResult(
        rank=rank,
        chunk_id=f"{source_id}-chunk",
        source_id=source_id,
        source_type="PRODUCT",
        version="v1",
        score=score,
        metadata={
            "title": source_id,
        },
    )


def _vector(
    *,
    rank: int,
    source_id: str,
    score: float,
) -> DenseSearchResult:
    return DenseSearchResult(
        rank=rank,
        chunk_id=f"{source_id}-chunk",
        source_id=source_id,
        source_type="PRODUCT",
        version="v1",
        score=score,
        metadata={
            "title": source_id,
        },
    )


def test_rrf_rewards_overlap() -> None:
    bm25 = [
        _bm25(
            rank=1,
            source_id="A",
            score=10.0,
        ),
        _bm25(
            rank=2,
            source_id="B",
            score=8.0,
        ),
    ]

    vector = [
        _vector(
            rank=1,
            source_id="B",
            score=0.95,
        ),
        _vector(
            rank=2,
            source_id="C",
            score=0.90,
        ),
    ]

    result = reciprocal_rank_fusion(
        bm25,
        vector,
        candidate_top_k=2,
    )

    assert result[0].source_id == "B"

    assert (
        result[0].fusion_method
        == "RRF"
    )


def test_rrf_keeps_single_retriever_candidate() -> None:
    result = reciprocal_rank_fusion(
        [
            _bm25(
                rank=1,
                source_id="A",
                score=9.0,
            )
        ],
        [],
    )

    assert len(result) == 1
    assert result[0].source_id == "A"

    assert result[0].vector_rank is None


def test_weighted_normalizes_different_score_scales() -> None:
    bm25 = [
        _bm25(
            rank=1,
            source_id="A",
            score=100.0,
        ),
        _bm25(
            rank=2,
            source_id="B",
            score=10.0,
        ),
    ]

    vector = [
        _vector(
            rank=1,
            source_id="B",
            score=0.99,
        ),
        _vector(
            rank=2,
            source_id="A",
            score=0.10,
        ),
    ]

    result = weighted_hybrid(
        bm25,
        vector,
        candidate_top_k=2,
    )

    by_source = {
        item.source_id: item
        for item in result
    }

    assert (
        by_source["A"]
        .bm25_normalized
        == pytest.approx(1.0)
    )

    assert (
        by_source["B"]
        .vector_normalized
        == pytest.approx(1.0)
    )


def test_weighted_respects_configured_weights() -> None:
    bm25 = [
        _bm25(
            rank=1,
            source_id="A",
            score=10.0,
        ),
        _bm25(
            rank=2,
            source_id="B",
            score=0.0,
        ),
    ]

    vector = [
        _vector(
            rank=1,
            source_id="B",
            score=1.0,
        ),
        _vector(
            rank=2,
            source_id="A",
            score=0.0,
        ),
    ]

    result = weighted_hybrid(
        bm25,
        vector,
        bm25_weight=0.8,
        vector_weight=0.2,
    )

    assert result[0].source_id == "A"


def test_candidate_top_k_is_applied_to_both() -> None:
    bm25 = [
        _bm25(
            rank=1,
            source_id="A",
            score=3.0,
        ),
        _bm25(
            rank=2,
            source_id="B",
            score=2.0,
        ),
    ]

    vector = [
        _vector(
            rank=1,
            source_id="C",
            score=0.9,
        ),
        _vector(
            rank=2,
            source_id="D",
            score=0.8,
        ),
    ]

    result = reciprocal_rank_fusion(
        bm25,
        vector,
        candidate_top_k=1,
    )

    source_ids = {
        item.source_id
        for item in result
    }

    assert source_ids == {
        "A",
        "C",
    }


def test_duplicate_source_is_collapsed() -> None:
    bm25 = [
        _bm25(
            rank=1,
            source_id="A",
            score=10.0,
        ),
        BM25SearchResult(
            rank=2,
            chunk_id="A-second-chunk",
            source_id="A",
            source_type="PRODUCT",
            version="v1",
            score=9.0,
            metadata={
                "title": "A",
            },
        ),
    ]

    result = reciprocal_rank_fusion(
        bm25,
        [],
    )

    assert len(result) == 1
    assert result[0].source_id == "A"
    assert result[0].bm25_rank == 1


def test_rrf_is_deterministic() -> None:
    bm25 = [
        _bm25(
            rank=1,
            source_id="B",
            score=5.0,
        ),
    ]

    vector = [
        _vector(
            rank=1,
            source_id="A",
            score=0.8,
        ),
    ]

    first = reciprocal_rank_fusion(
        bm25,
        vector,
    )

    second = reciprocal_rank_fusion(
        bm25,
        vector,
    )

    assert [
        item.source_id
        for item in first
    ] == [
        item.source_id
        for item in second
    ]


def test_invalid_candidate_top_k() -> None:
    with pytest.raises(
        ValueError
    ):
        reciprocal_rank_fusion(
            [],
            [],
            candidate_top_k=0,
        )


def test_invalid_rrf_k() -> None:
    with pytest.raises(
        ValueError
    ):
        reciprocal_rank_fusion(
            [],
            [],
            rrf_k=0,
        )


def test_negative_weight_is_rejected() -> None:
    with pytest.raises(
        ValueError
    ):
        weighted_hybrid(
            [],
            [],
            bm25_weight=-1.0,
            vector_weight=1.0,
        )


def test_zero_total_weight_is_rejected() -> None:
    with pytest.raises(
        ValueError
    ):
        weighted_hybrid(
            [],
            [],
            bm25_weight=0.0,
            vector_weight=0.0,
        )