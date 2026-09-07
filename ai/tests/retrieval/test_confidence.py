from __future__ import annotations

import pytest

from ai.retrieval.confidence import (
    ConfidenceLevel,
    evaluate_confidence,
    summarize_freshness,
)
from ai.retrieval.freshness import (
    FreshnessState,
)


def test_empty_results_abstain() -> None:
    result = evaluate_confidence(
        retriever="bm25",
        scores=[],
        freshness_states=[],
    )

    assert (
        result.level
        == ConfidenceLevel.ABSTAIN
    )

    assert (
        result.answer_allowed
        is False
    )


def test_known_no_relevant_evidence_abstains_even_with_high_bm25_score() -> None:
    result = evaluate_confidence(
        retriever="bm25",
        scores=[
            10.999,
            2.9208,
            1.0,
        ],
        freshness_states=[
            FreshnessState.FRESH,
        ],
        no_relevant_evidence=True,
    )

    assert (
        result.level
        == ConfidenceLevel.ABSTAIN
    )


def test_known_no_relevant_evidence_abstains_even_with_dense_similarity() -> None:
    result = evaluate_confidence(
        retriever="dense",
        scores=[
            0.5607,
            0.3758,
            0.31,
        ],
        freshness_states=[
            FreshnessState.FRESH,
        ],
        no_relevant_evidence=True,
    )

    assert (
        result.level
        == ConfidenceLevel.ABSTAIN
    )


def test_stale_evidence_caps_confidence_at_low() -> None:
    result = evaluate_confidence(
        retriever="bm25",
        scores=[
            30.0,
            5.0,
        ],
        freshness_states=[
            FreshnessState.STALE,
        ],
    )

    assert (
        result.level
        == ConfidenceLevel.LOW
    )

    assert (
        result.answer_allowed
        is False
    )


def test_missing_freshness_is_low() -> None:
    result = evaluate_confidence(
        retriever="dense",
        scores=[
            0.9,
            0.1,
        ],
        freshness_states=[
            FreshnessState.MISSING,
        ],
    )

    assert (
        result.level
        == ConfidenceLevel.LOW
    )


def test_policy_undefined_freshness_is_low() -> None:
    result = evaluate_confidence(
        retriever="dense",
        scores=[
            0.9,
            0.1,
        ],
        freshness_states=[
            (
                FreshnessState
                .POLICY_UNDEFINED
            ),
        ],
    )

    assert (
        result.level
        == ConfidenceLevel.LOW
    )


def test_strong_bm25_score_and_gap_can_be_high() -> None:
    result = evaluate_confidence(
        retriever="bm25",
        scores=[
            25.624,
            3.7637,
            1.0,
        ],
        freshness_states=[
            FreshnessState.FRESH,
        ],
    )

    assert (
        result.level
        == ConfidenceLevel.HIGH
    )


def test_bm25_abstain_boundary_is_not_high() -> None:
    result = evaluate_confidence(
        retriever="bm25",
        scores=[
            10.999,
            2.9208,
        ],
        freshness_states=[
            FreshnessState.FRESH,
        ],
    )

    assert (
        result.level
        != ConfidenceLevel.HIGH
    )


def test_strong_dense_score_and_gap_can_be_high() -> None:
    result = evaluate_confidence(
        retriever="dense",
        scores=[
            0.7298,
            0.4468,
            0.2,
        ],
        freshness_states=[
            FreshnessState.FRESH,
        ],
    )

    assert (
        result.level
        == ConfidenceLevel.HIGH
    )


def test_dense_false_high_boundary_is_blocked() -> None:
    result = evaluate_confidence(
        retriever="dense",
        scores=[
            0.5607,
            0.3758,
        ],
        freshness_states=[
            FreshnessState.FRESH,
        ],
    )

    assert (
        result.level
        != ConfidenceLevel.HIGH
    )


def test_medium_support_is_not_called_high() -> None:
    result = evaluate_confidence(
        retriever="dense",
        scores=[
            0.6414,
            0.6338,
        ],
        freshness_states=[
            FreshnessState.FRESH,
        ],
    )

    assert (
        result.level
        == ConfidenceLevel.MEDIUM
    )

    assert (
        result.answer_allowed
        is False
    )

def test_medium_never_allows_definitive_answer() -> None:
    result = evaluate_confidence(
        retriever="dense",
        scores=[
            0.5607,
            0.3758,
        ],
        freshness_states=[
            FreshnessState.FRESH,
        ],
    )

    assert (
        result.level
        == ConfidenceLevel.MEDIUM
    )

    assert (
        result.answer_allowed
        is False
    )

    assert (
        "medium_requires_hold"
        in result.reasons
    )

def test_weak_dense_score_is_low() -> None:
    result = evaluate_confidence(
        retriever="dense",
        scores=[
            0.20,
            0.10,
        ],
        freshness_states=[
            FreshnessState.FRESH,
        ],
    )

    assert (
        result.level
        == ConfidenceLevel.LOW
    )


def test_zero_bm25_scores_abstain() -> None:
    result = evaluate_confidence(
        retriever="bm25",
        scores=[
            0.0,
            0.0,
            0.0,
        ],
        freshness_states=[
            FreshnessState.FRESH,
        ],
    )

    assert (
        result.level
        == ConfidenceLevel.ABSTAIN
    )


def test_freshness_summary_prefers_stale() -> None:
    state = summarize_freshness(
        [
            FreshnessState.FRESH,
            FreshnessState.STALE,
        ]
    )

    assert (
        state
        == FreshnessState.STALE
    )


def test_unknown_retriever_is_rejected() -> None:
    with pytest.raises(ValueError):
        evaluate_confidence(
            retriever="hybrid",
            scores=[1.0],
            freshness_states=[
                FreshnessState.FRESH,
            ],
        )