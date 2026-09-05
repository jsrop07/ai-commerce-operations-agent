import pytest

from ai.evaluation.compare_chunking_candidates import (
    lexical_score,
    recall_at_k,
    reciprocal_rank,
    ndcg_at_k,
    search_sources,
)


def test_lexical_score_prefers_related_text() -> None:
    query = "예약상품 배송"

    related = lexical_score(
        query,
        "예약상품은 입고 후 배송됩니다.",
    )

    unrelated = lexical_score(
        query,
        "전략 게임 구성품 안내",
    )

    assert related > unrelated


def test_recall_at_k_finds_relevant_source() -> None:
    ranked = [
        {
            "source_id": "wrong",
        },
        {
            "source_id": "correct",
        },
    ]

    relevant = {
        "correct": 3,
    }

    assert recall_at_k(
        ranked,
        relevant,
        k=1,
    ) == 0.0

    assert recall_at_k(
        ranked,
        relevant,
        k=2,
    ) == 1.0


def test_reciprocal_rank_uses_first_relevant_result() -> None:
    ranked = [
        {
            "source_id": "wrong",
        },
        {
            "source_id": "correct",
        },
    ]

    relevant = {
        "correct": 3,
    }

    assert reciprocal_rank(
        ranked,
        relevant,
    ) == pytest.approx(0.5)


def test_ndcg_rewards_high_grade_result_near_top() -> None:
    relevant = {
        "high": 3,
        "medium": 2,
    }

    good = [
        {
            "source_id": "high",
        },
        {
            "source_id": "medium",
        },
    ]

    bad = [
        {
            "source_id": "medium",
        },
        {
            "source_id": "high",
        },
    ]

    assert ndcg_at_k(
        good,
        relevant,
        k=5,
    ) > ndcg_at_k(
        bad,
        relevant,
        k=5,
    )

def test_search_sources_collapses_duplicate_source_chunks() -> None:
    chunks = [
        {
            "chunk_id": "a:0",
            "source_id": "source_a",
            "source_type": "PRODUCT",
            "version": "v1",
            "text": "예약상품 배송 안내",
        },
        {
            "chunk_id": "a:1",
            "source_id": "source_a",
            "source_type": "PRODUCT",
            "version": "v1",
            "text": "예약상품 입고 배송",
        },
        {
            "chunk_id": "b:0",
            "source_id": "source_b",
            "source_type": "PRODUCT",
            "version": "v1",
            "text": "전략 게임 구성품",
        },
    ]

    ranked = search_sources(
        "예약상품 배송",
        chunks,
        top_k=5,
    )

    source_ids = [
        item["source_id"]
        for item in ranked
    ]

    assert source_ids.count("source_a") == 1


def test_ndcg_never_exceeds_one_for_unique_sources() -> None:
    relevant = {
        "high": 3,
        "medium": 2,
    }

    ranked = [
        {"source_id": "high"},
        {"source_id": "medium"},
    ]

    score = ndcg_at_k(
        ranked,
        relevant,
        k=5,
    )

    assert 0.0 <= score <= 1.0