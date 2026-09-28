import pytest

from ai.retrieval.freshness import FreshnessState
from ai.retrieval.hybrid_confidence import (
    HybridConfidenceFeatures,
    HybridConfidenceLevel,
    HybridConfidenceThresholds,
    build_confidence_score,
    evaluate_hybrid_confidence,
    normalize_rrf_score,
    normalize_weighted_score,
)


THRESHOLDS = HybridConfidenceThresholds(
    medium=0.50,
    high=0.80,
)


def test_rrf_score_is_normalized() -> None:
    raw_max = 2 / 61

    assert normalize_rrf_score(
        raw_max,
        rrf_k=60,
    ) == pytest.approx(1.0)


def test_rrf_score_is_clamped() -> None:
    assert normalize_rrf_score(
        999.0
    ) == 1.0


def test_weighted_score_is_clamped() -> None:
    assert normalize_weighted_score(
        1.5
    ) == 1.0

    assert normalize_weighted_score(
        -1.0
    ) == 0.0


def test_exact_match_increases_confidence() -> None:
    without_exact = build_confidence_score(
        hybrid_score=0.5,
        exact_match=False,
    )

    with_exact = build_confidence_score(
        hybrid_score=0.5,
        exact_match=True,
    )

    assert with_exact > without_exact


def test_fresh_high_support_can_be_high() -> None:
    result = evaluate_hybrid_confidence(
        features=HybridConfidenceFeatures(
            hybrid_score=0.9,
            exact_match=True,
            freshness_state=FreshnessState.FRESH,
            result_count=10,
        ),
        thresholds=THRESHOLDS,
    )

    assert (
        result.level
        == HybridConfidenceLevel.HIGH
    )

    assert result.answer_allowed is True
    assert result.hold_required is False


def test_medium_requires_hold() -> None:
    result = evaluate_hybrid_confidence(
        features=HybridConfidenceFeatures(
            hybrid_score=0.65,
            exact_match=False,
            freshness_state=FreshnessState.FRESH,
            result_count=10,
        ),
        thresholds=THRESHOLDS,
    )

    assert (
        result.level
        == HybridConfidenceLevel.MEDIUM
    )

    assert result.answer_allowed is False
    assert result.hold_required is True


def test_stale_is_always_hold() -> None:
    result = evaluate_hybrid_confidence(
        features=HybridConfidenceFeatures(
            hybrid_score=1.0,
            exact_match=True,
            freshness_state=FreshnessState.STALE,
            result_count=10,
        ),
        thresholds=THRESHOLDS,
    )

    assert (
        result.level
        == HybridConfidenceLevel.LOW
    )

    assert result.answer_allowed is False
    assert result.hold_required is True
    assert "stale_evidence" in result.reasons


def test_missing_freshness_is_hold() -> None:
    result = evaluate_hybrid_confidence(
        features=HybridConfidenceFeatures(
            hybrid_score=1.0,
            exact_match=True,
            freshness_state=FreshnessState.MISSING,
            result_count=10,
        ),
        thresholds=THRESHOLDS,
    )

    assert (
        result.level
        == HybridConfidenceLevel.LOW
    )

    assert result.answer_allowed is False


def test_no_results_abstains() -> None:
    result = evaluate_hybrid_confidence(
        features=HybridConfidenceFeatures(
            hybrid_score=0.0,
            exact_match=False,
            freshness_state=FreshnessState.FRESH,
            result_count=0,
        ),
        thresholds=THRESHOLDS,
    )

    assert (
        result.level
        == HybridConfidenceLevel.ABSTAIN
    )

    assert result.answer_allowed is False


def test_no_relevant_evidence_abstains() -> None:
    result = evaluate_hybrid_confidence(
        features=HybridConfidenceFeatures(
            hybrid_score=1.0,
            exact_match=True,
            freshness_state=FreshnessState.FRESH,
            result_count=5,
        ),
        thresholds=THRESHOLDS,
        no_relevant_evidence=True,
    )

    assert (
        result.level
        == HybridConfidenceLevel.ABSTAIN
    )

    assert result.answer_allowed is False


def test_invalid_threshold_order_rejected() -> None:
    with pytest.raises(ValueError):
        evaluate_hybrid_confidence(
            features=HybridConfidenceFeatures(
                hybrid_score=0.5,
                exact_match=False,
                freshness_state=FreshnessState.FRESH,
                result_count=1,
            ),
            thresholds=HybridConfidenceThresholds(
                medium=0.8,
                high=0.7,
            ),
        )