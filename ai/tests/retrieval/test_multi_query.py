import pytest

from ai.retrieval.hybrid import (
    HybridSearchResult,
)
from ai.retrieval.multi_query import (
    generate_multi_queries,
    merge_multi_query_results,
    run_multi_query,
)


def _result(
    *,
    rank: int,
    source_id: str,
) -> HybridSearchResult:
    return HybridSearchResult(
        rank=rank,
        source_id=source_id,
        source_type="PRODUCT",
        version="v1",
        chunk_id=f"{source_id}-chunk",
        score=1.0 / rank,
        metadata={
            "title": source_id,
        },
        bm25_rank=rank,
        vector_rank=None,
        bm25_score=1.0 / rank,
        vector_score=None,
        bm25_normalized=1.0,
        vector_normalized=0.0,
        fusion_method="RRF",
    )


def test_exact_product_skips_multi_query() -> None:
    candidates = generate_multi_queries(
        "아크 노바 한국어판 찾아줘",
        slice_name="product_exact",
    )

    assert len(candidates) == 1
    assert (
        candidates[0].query
        == "아크 노바 한국어판 찾아줘"
    )
    assert (
        candidates[0].reason
        == "MULTI_QUERY_NOT_REQUIRED"
    )


def test_policy_generates_at_most_three_queries() -> None:
    candidates = generate_multi_queries(
        "배송 정책 알려줘?",
        slice_name="policy",
    )

    assert 1 <= len(candidates) <= 3


def test_compatibility_generates_candidates() -> None:
    candidates = generate_multi_queries(
        "윙스팬 유럽 확장은 본판 없이 플레이할 수 있어?",
        slice_name="compatibility",
    )

    assert len(candidates) >= 2

    assert candidates[0].query == (
        "윙스팬 유럽 확장은 "
        "본판 없이 플레이할 수 있어?"
    )


def test_candidate_generation_does_not_invent_alias() -> None:
    candidates = generate_multi_queries(
        "아크 노바 확장팩 호환 여부 알려줘?",
        slice_name="compatibility",
    )

    joined = " ".join(
        item.query
        for item in candidates
    )

    assert "아크 노바" in joined
    assert "아크노바" not in joined


def test_candidate_generation_does_not_invent_language() -> None:
    candidates = generate_multi_queries(
        "Kill Team expansion 호환 여부 알려줘?",
        slice_name="compatibility",
    )

    joined = " ".join(
        item.query
        for item in candidates
    )

    assert "한국어판" not in joined
    assert "English" not in joined


def test_candidate_generation_preserves_edition() -> None:
    candidates = generate_multi_queries(
        "Kill Team 3rd Edition "
        "확장 호환 여부 알려줘?",
        slice_name="compatibility",
    )

    for candidate in candidates:
        assert "3rd Edition" in (
            candidate.query
        )


def test_source_id_is_deduplicated() -> None:
    candidates = generate_multi_queries(
        "배송 정책 알려줘?",
        slice_name="policy",
    )

    batches = [
        [
            _result(
                rank=1,
                source_id="policy-A",
            ),
            _result(
                rank=2,
                source_id="policy-B",
            ),
        ],
        [
            _result(
                rank=1,
                source_id="policy-A",
            ),
        ],
    ]

    merged = merge_multi_query_results(
        candidates[:2],
        batches,
    )

    assert [
        result.source_id
        for result in merged
    ].count(
        "policy-A"
    ) == 1


def test_overlap_gets_multi_query_reason() -> None:
    candidates = generate_multi_queries(
        "배송 정책 알려줘?",
        slice_name="policy",
    )

    merged = merge_multi_query_results(
        candidates[:2],
        [
            [
                _result(
                    rank=1,
                    source_id="policy-A",
                ),
            ],
            [
                _result(
                    rank=2,
                    source_id="policy-A",
                ),
            ],
        ],
    )

    assert (
        merged[0].combine_reason
        == "MATCHED_MULTIPLE_QUERIES"
    )

    assert len(
        merged[0].matched_queries
    ) == 2


def test_multi_query_can_increase_recall() -> None:
    def search_fn(
        query: str,
    ) -> list[HybridSearchResult]:
        if query.endswith("?"):
            return [
                _result(
                    rank=1,
                    source_id="A",
                )
            ]

        return [
            _result(
                rank=1,
                source_id="A",
            ),
            _result(
                rank=2,
                source_id="B",
            ),
        ]

    result = run_multi_query(
        "배송 정책 알려줘?",
        slice_name="policy",
        search_fn=search_fn,
        relevant_source_ids={
            "A",
            "B",
        },
    )

    assert (
        result.trace.single_query_recall
        == pytest.approx(0.5)
    )

    assert (
        result.trace.multi_query_recall
        == pytest.approx(1.0)
    )

    assert (
        result.trace.recall_change
        == pytest.approx(0.5)
    )


def test_trace_records_counts_and_dedupe() -> None:
    def search_fn(
        query: str,
    ) -> list[HybridSearchResult]:
        return [
            _result(
                rank=1,
                source_id="A",
            ),
            _result(
                rank=2,
                source_id="B",
            ),
        ]

    result = run_multi_query(
        "배송 정책 알려줘?",
        slice_name="policy",
        search_fn=search_fn,
    )

    assert result.trace.query_count >= 2

    assert (
        result.trace.retrieval_count
        == result.trace.query_count * 2
    )

    assert (
        result.trace.unique_result_count
        == 2
    )

    assert (
        result.trace.dedupe_count
        == result.trace.retrieval_count - 2
    )


def test_exact_product_trace_is_skipped() -> None:
    result = run_multi_query(
        "아크 노바 한국어판 찾아줘",
        slice_name="product_exact",
        search_fn=lambda query: [
            _result(
                rank=1,
                source_id="product-A",
            )
        ],
    )

    assert result.trace.skipped is True

    assert (
        result.trace.skip_reason
        == "SLICE_NOT_MULTI_QUERY_ELIGIBLE"
    )

    assert result.trace.query_count == 1


def test_api_cost_defaults_to_zero() -> None:
    result = run_multi_query(
        "배송 정책 알려줘?",
        slice_name="policy",
        search_fn=lambda query: [],
    )

    assert (
        result.trace.api_cost_usd
        == 0.0
    )


def test_negative_api_cost_is_rejected() -> None:
    with pytest.raises(
        ValueError
    ):
        run_multi_query(
            "배송 정책 알려줘?",
            slice_name="policy",
            search_fn=lambda query: [],
            api_cost_usd=-1.0,
        )


def test_max_query_count_is_hard_capped_at_three() -> None:
    candidates = generate_multi_queries(
        "배송 정책 알려줘?",
        slice_name="policy",
        max_queries=10,
    )

    assert len(candidates) <= 3


def test_invalid_max_query_count_is_rejected() -> None:
    with pytest.raises(
        ValueError
    ):
        generate_multi_queries(
            "배송 정책 알려줘?",
            slice_name="policy",
            max_queries=0,
        )