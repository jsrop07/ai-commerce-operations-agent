from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ai.retrieval.freshness import FreshnessState


class HybridConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    ABSTAIN = "ABSTAIN"


@dataclass(frozen=True)
class HybridConfidenceThresholds:
    """
    Day 9 calibration 결과로 결정되는 threshold.

    threshold 값은 test set을 보고 수정하지 않는다.
    """

    high: float
    medium: float


@dataclass(frozen=True)
class HybridConfidenceFeatures:
    """
    Hybrid confidence 판정에 사용하는 입력 feature.
    """

    hybrid_score: float
    exact_match: bool
    freshness_state: FreshnessState
    result_count: int


@dataclass(frozen=True)
class HybridConfidenceResult:
    level: HybridConfidenceLevel

    confidence_score: float
    hybrid_score: float
    exact_match: bool
    freshness_state: FreshnessState
    result_count: int

    hold_required: bool
    answer_allowed: bool

    reasons: tuple[str, ...]


def normalize_rrf_score(
    score: float,
    *,
    rrf_k: int = 60,
    retriever_count: int = 2,
) -> float:
    """
    RRF raw score를 0~1 범위로 정규화한다.

    두 retriever 모두 rank=1일 때의 이론적 최대값을
    1.0으로 사용한다.
    """

    if rrf_k <= 0:
        raise ValueError(
            "rrf_k must be greater than 0"
        )

    if retriever_count <= 0:
        raise ValueError(
            "retriever_count must be greater than 0"
        )

    theoretical_max = (
        retriever_count
        / float(rrf_k + 1)
    )

    normalized = (
        float(score)
        / theoretical_max
    )

    return max(
        0.0,
        min(1.0, normalized),
    )


def normalize_weighted_score(
    score: float,
) -> float:
    """
    Weighted Hybrid는 이미 0~1 정규화 점수이므로
    범위만 안전하게 제한한다.
    """

    return max(
        0.0,
        min(1.0, float(score)),
    )


def build_confidence_score(
    *,
    hybrid_score: float,
    exact_match: bool,
) -> float:
    """
    Day 9 confidence feature score.

    Hybrid retrieval support를 주 신호로 사용하고
    exact match를 보조 신호로 사용한다.

    threshold 자체는 calibration set에서 결정한다.
    """

    normalized_score = max(
        0.0,
        min(1.0, float(hybrid_score)),
    )

    exact_match_value = (
        1.0
        if exact_match
        else 0.0
    )

    score = (
        normalized_score * 0.80
        + exact_match_value * 0.20
    )

    return max(
        0.0,
        min(1.0, score),
    )


def evaluate_hybrid_confidence(
    *,
    features: HybridConfidenceFeatures,
    thresholds: HybridConfidenceThresholds,
    no_relevant_evidence: bool = False,
) -> HybridConfidenceResult:
    """
    Day 9 Hybrid confidence 판정.

    freshness hard guard는 기존 Day7보다
    느슨하게 만들지 않는다.
    """

    if thresholds.high <= thresholds.medium:
        raise ValueError(
            "high threshold must be greater "
            "than medium threshold"
        )

    if not 0.0 <= thresholds.medium <= 1.0:
        raise ValueError(
            "medium threshold must be between 0 and 1"
        )

    if not 0.0 <= thresholds.high <= 1.0:
        raise ValueError(
            "high threshold must be between 0 and 1"
        )

    confidence_score = build_confidence_score(
        hybrid_score=features.hybrid_score,
        exact_match=features.exact_match,
    )

    if features.result_count <= 0:
        return HybridConfidenceResult(
            level=HybridConfidenceLevel.ABSTAIN,
            confidence_score=confidence_score,
            hybrid_score=features.hybrid_score,
            exact_match=features.exact_match,
            freshness_state=features.freshness_state,
            result_count=features.result_count,
            hold_required=True,
            answer_allowed=False,
            reasons=(
                "no_retrieval_results",
            ),
        )

    if no_relevant_evidence:
        return HybridConfidenceResult(
            level=HybridConfidenceLevel.ABSTAIN,
            confidence_score=confidence_score,
            hybrid_score=features.hybrid_score,
            exact_match=features.exact_match,
            freshness_state=features.freshness_state,
            result_count=features.result_count,
            hold_required=True,
            answer_allowed=False,
            reasons=(
                "no_relevant_evidence",
            ),
        )

    if (
        features.freshness_state
        == FreshnessState.STALE
    ):
        return HybridConfidenceResult(
            level=HybridConfidenceLevel.LOW,
            confidence_score=confidence_score,
            hybrid_score=features.hybrid_score,
            exact_match=features.exact_match,
            freshness_state=features.freshness_state,
            result_count=features.result_count,
            hold_required=True,
            answer_allowed=False,
            reasons=(
                "stale_evidence",
            ),
        )

    if features.freshness_state in {
        FreshnessState.MISSING,
        FreshnessState.POLICY_UNDEFINED,
    }:
        return HybridConfidenceResult(
            level=HybridConfidenceLevel.LOW,
            confidence_score=confidence_score,
            hybrid_score=features.hybrid_score,
            exact_match=features.exact_match,
            freshness_state=features.freshness_state,
            result_count=features.result_count,
            hold_required=True,
            answer_allowed=False,
            reasons=(
                "freshness_unverified",
            ),
        )

    if confidence_score >= thresholds.high:
        reasons = [
            "high_calibrated_support",
        ]

        if features.exact_match:
            reasons.append(
                "exact_match"
            )

        return HybridConfidenceResult(
            level=HybridConfidenceLevel.HIGH,
            confidence_score=confidence_score,
            hybrid_score=features.hybrid_score,
            exact_match=features.exact_match,
            freshness_state=features.freshness_state,
            result_count=features.result_count,
            hold_required=False,
            answer_allowed=True,
            reasons=tuple(reasons),
        )

    if confidence_score >= thresholds.medium:
        reasons = [
            "medium_calibrated_support",
            "medium_requires_hold",
        ]

        if features.exact_match:
            reasons.append(
                "exact_match"
            )

        return HybridConfidenceResult(
            level=HybridConfidenceLevel.MEDIUM,
            confidence_score=confidence_score,
            hybrid_score=features.hybrid_score,
            exact_match=features.exact_match,
            freshness_state=features.freshness_state,
            result_count=features.result_count,
            hold_required=True,
            answer_allowed=False,
            reasons=tuple(reasons),
        )

    return HybridConfidenceResult(
        level=HybridConfidenceLevel.LOW,
        confidence_score=confidence_score,
        hybrid_score=features.hybrid_score,
        exact_match=features.exact_match,
        freshness_state=features.freshness_state,
        result_count=features.result_count,
        hold_required=True,
        answer_allowed=False,
        reasons=(
            "weak_hybrid_support",
        ),
    )