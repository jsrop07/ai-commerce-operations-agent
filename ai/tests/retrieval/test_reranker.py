import time

import pytest

from ai.retrieval.reranker import (
    RerankCandidate,
    rerank_candidates,
)


def _candidate(
    rank: int,
    source_id: str,
    text: str,
) -> RerankCandidate:
    return RerankCandidate(
        original_rank=rank,
        source_id=source_id,
        source_type="PRODUCT",
        version="v1",
        text=text,
        metadata={
            "product_name": text,
        },
    )


def test_reranker_reorders_candidates() -> None:
    candidates = [
        _candidate(
            1,
            "A",
            "Kill Team Datacards",
        ),
        _candidate(
            2,
            "B",
            "Kill Team Starter Set",
        ),
    ]

    def scorer(pairs):
        return [
            0.1,
            0.9,
        ]

    result = rerank_candidates(
        "Kill Team Starter Set",
        candidates,
        scorer=scorer,
    )

    assert (
        result.results[0].source_id
        == "B"
    )

    assert (
        result.trace.status
        == "RERANKED"
    )


def test_source_id_is_deduplicated() -> None:
    candidates = [
        _candidate(
            1,
            "A",
            "first",
        ),
        _candidate(
            2,
            "A",
            "duplicate",
        ),
    ]

    result = rerank_candidates(
        "query",
        candidates,
        scorer=lambda pairs: [
            0.8
        ],
    )

    assert len(result.results) == 1


def test_candidate_top_30_cap() -> None:
    candidates = [
        _candidate(
            index,
            f"P-{index}",
            f"Product {index}",
        )
        for index in range(
            1,
            41,
        )
    ]

    seen = []

    def scorer(pairs):
        seen.extend(pairs)
        return [
            float(index)
            for index in range(
                len(pairs)
            )
        ]

    result = rerank_candidates(
        "query",
        candidates,
        scorer=scorer,
        candidate_top_k=30,
    )

    assert len(seen) == 30

    assert (
        result.trace.candidate_count
        == 30
    )


def test_top_5_output() -> None:
    candidates = [
        _candidate(
            index,
            f"P-{index}",
            f"Product {index}",
        )
        for index in range(
            1,
            11,
        )
    ]

    result = rerank_candidates(
        "query",
        candidates,
        scorer=lambda pairs: [
            float(index)
            for index in range(
                len(pairs)
            )
        ],
        output_top_k=5,
    )

    assert len(result.results) == 5


def test_top_10_output() -> None:
    candidates = [
        _candidate(
            index,
            f"P-{index}",
            f"Product {index}",
        )
        for index in range(
            1,
            21,
        )
    ]

    result = rerank_candidates(
        "query",
        candidates,
        scorer=lambda pairs: [
            float(index)
            for index in range(
                len(pairs)
            )
        ],
        output_top_k=10,
    )

    assert len(result.results) == 10


def test_timeout_falls_back() -> None:
    candidates = [
        _candidate(
            1,
            "A",
            "A",
        ),
        _candidate(
            2,
            "B",
            "B",
        ),
    ]

    def slow_scorer(pairs):
        time.sleep(0.2)
        return [
            0.1,
            0.9,
        ]

    result = rerank_candidates(
        "query",
        candidates,
        scorer=slow_scorer,
        timeout_seconds=0.01,
        max_retries=0,
    )

    assert (
        result.trace.status
        == "FALLBACK"
    )

    assert (
        result.trace.timeout_count
        == 1
    )

    assert (
        result.trace.fallback_count
        == 1
    )

    assert [
        item.source_id
        for item in result.results
    ] == [
        "A",
        "B",
    ]


def test_failure_retries_then_falls_back() -> None:
    calls = {
        "count": 0,
    }

    def broken_scorer(pairs):
        calls["count"] += 1
        raise RuntimeError(
            "simulated failure"
        )

    result = rerank_candidates(
        "query",
        [
            _candidate(
                1,
                "A",
                "A",
            )
        ],
        scorer=broken_scorer,
        max_retries=1,
    )

    assert calls["count"] == 2

    assert (
        result.trace.retry_count
        == 1
    )

    assert (
        result.trace.status
        == "FALLBACK"
    )


def test_no_candidates_is_safe() -> None:
    result = rerank_candidates(
        "query",
        [],
        scorer=lambda pairs: [],
    )

    assert result.results == ()

    assert (
        result.trace.status
        == "NO_CANDIDATES"
    )


def test_empty_query_rejected() -> None:
    with pytest.raises(
        ValueError
    ):
        rerank_candidates(
            "",
            [],
            scorer=lambda pairs: [],
        )


def test_invalid_top_k_rejected() -> None:
    with pytest.raises(
        ValueError
    ):
        rerank_candidates(
            "query",
            [],
            scorer=lambda pairs: [],
            output_top_k=0,
        )