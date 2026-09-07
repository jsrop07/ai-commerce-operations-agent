from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from ai.retrieval.freshness import (
    FreshnessState,
)


class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    ABSTAIN = "ABSTAIN"


@dataclass(frozen=True)
class ConfidenceThresholds:
    retriever: str

    # score > floor인 결과만
    # 실제 evidence 후보로 계산한다.
    evidence_score_floor: float

    # 최소한 이 score보다 낮으면
    # retrieval support가 약하다고 본다.
    medium_score: float

    # HIGH는 score와 gap을
    # 동시에 넘어야 한다.
    high_score: float
    high_gap: float


@dataclass(frozen=True)
class ConfidenceResult:
    level: ConfidenceLevel
    retriever: str

    top_score: float
    score_gap: float
    result_count: int
    effective_result_count: int

    freshness_state: FreshnessState

    answer_allowed: bool
    reasons: tuple[str, ...]


# Day 7의 16-query DEMO calibration 결과에서
# 관측한 no-answer score/gap을 기반으로 한
# 초기 baseline이다.
#
# Production SLA / 최종 threshold가 아니다.
DAY07_THRESHOLDS: dict[
    str,
    ConfidenceThresholds,
] = {
    "bm25": ConfidenceThresholds(
        retriever="bm25",
        evidence_score_floor=0.0,
        medium_score=3.10,
        high_score=11.00,
        high_gap=8.08,
    ),
    "dense": ConfidenceThresholds(
        retriever="dense",
        evidence_score_floor=0.0,
        medium_score=0.39,
        high_score=0.568,
        high_gap=0.185,
    ),
}


def summarize_freshness(
    states: Sequence[FreshnessState],
) -> FreshnessState:
    """
    검색 evidence의 freshness를 보수적으로 합친다.

    STALE이 하나라도 있으면 STALE.
    MISSING / POLICY_UNDEFINED도
    FRESH로 승격하지 않는다.
    """

    if not states:
        return FreshnessState.MISSING

    if FreshnessState.STALE in states:
        return FreshnessState.STALE

    if FreshnessState.MISSING in states:
        return FreshnessState.MISSING

    if (
        FreshnessState.POLICY_UNDEFINED
        in states
    ):
        return (
            FreshnessState
            .POLICY_UNDEFINED
        )

    return FreshnessState.FRESH


def evaluate_confidence(
    *,
    retriever: str,
    scores: Sequence[float],
    freshness_states: Sequence[
        FreshnessState
    ],
    no_relevant_evidence: bool = False,
) -> ConfidenceResult:
    """
    Day 7 retrieval confidence baseline.

    입력 signal:
    - top score
    - top1-top2 gap
    - result count
    - freshness

    no_relevant_evidence는 Golden/Eval 또는
    별도 verifier가 명시적으로 근거 없음으로
    판정한 경우 사용하는 hard guard이다.

    retriever score만으로는 semantic no-answer를
    완전히 판별할 수 없으므로 이를 추측하지 않는다.
    """

    normalized_retriever = (
        retriever.strip().lower()
    )

    thresholds = DAY07_THRESHOLDS.get(
        normalized_retriever
    )

    if thresholds is None:
        raise ValueError(
            "unsupported retriever for "
            f"confidence: {retriever}"
        )

    numeric_scores = [
        float(score)
        for score in scores
    ]

    result_count = len(
        numeric_scores
    )

    freshness_state = (
        summarize_freshness(
            freshness_states
        )
    )

    if not numeric_scores:
        return ConfidenceResult(
            level=ConfidenceLevel.ABSTAIN,
            retriever=(
                normalized_retriever
            ),
            top_score=0.0,
            score_gap=0.0,
            result_count=0,
            effective_result_count=0,
            freshness_state=(
                freshness_state
            ),
            answer_allowed=False,
            reasons=(
                "no_retrieval_results",
            ),
        )

    ordered = sorted(
        numeric_scores,
        reverse=True,
    )

    top_score = ordered[0]

    if len(ordered) >= 2:
        score_gap = (
            ordered[0]
            - ordered[1]
        )
    else:
        score_gap = ordered[0]

    effective_result_count = sum(
        1
        for score in ordered
        if (
            score
            > thresholds
            .evidence_score_floor
        )
    )

    reasons: list[str] = []

    # Evaluation/Verifier가 근거 없음으로
    # 명시한 경우 score가 높더라도 답하지 않는다.
    if no_relevant_evidence:
        return ConfidenceResult(
            level=ConfidenceLevel.ABSTAIN,
            retriever=(
                normalized_retriever
            ),
            top_score=top_score,
            score_gap=score_gap,
            result_count=result_count,
            effective_result_count=(
                effective_result_count
            ),
            freshness_state=(
                freshness_state
            ),
            answer_allowed=False,
            reasons=(
                "no_relevant_evidence",
            ),
        )

    # stale evidence는 score와 관계없이
    # definitive answer를 허용하지 않는다.
    if (
        freshness_state
        == FreshnessState.STALE
    ):
        return ConfidenceResult(
            level=ConfidenceLevel.LOW,
            retriever=(
                normalized_retriever
            ),
            top_score=top_score,
            score_gap=score_gap,
            result_count=result_count,
            effective_result_count=(
                effective_result_count
            ),
            freshness_state=(
                freshness_state
            ),
            answer_allowed=False,
            reasons=(
                "stale_evidence",
            ),
        )

    # freshness를 확인할 수 없는 경우도
    # HIGH/MEDIUM으로 승격하지 않는다.
    if freshness_state in {
        FreshnessState.MISSING,
        FreshnessState.POLICY_UNDEFINED,
    }:
        return ConfidenceResult(
            level=ConfidenceLevel.LOW,
            retriever=(
                normalized_retriever
            ),
            top_score=top_score,
            score_gap=score_gap,
            result_count=result_count,
            effective_result_count=(
                effective_result_count
            ),
            freshness_state=(
                freshness_state
            ),
            answer_allowed=False,
            reasons=(
                "freshness_unverified",
            ),
        )

    if effective_result_count == 0:
        return ConfidenceResult(
            level=ConfidenceLevel.ABSTAIN,
            retriever=(
                normalized_retriever
            ),
            top_score=top_score,
            score_gap=score_gap,
            result_count=result_count,
            effective_result_count=0,
            freshness_state=(
                freshness_state
            ),
            answer_allowed=False,
            reasons=(
                "no_effective_evidence",
            ),
        )

    # 현재 calibration set의 no-answer 최대값을
    # 동시에 넘어야 HIGH를 허용한다.
    if (
        top_score
        > thresholds.high_score
        and score_gap
        > thresholds.high_gap
        and effective_result_count >= 1
    ):
        reasons.append(
            "strong_score_and_gap"
        )

        return ConfidenceResult(
            level=ConfidenceLevel.HIGH,
            retriever=(
                normalized_retriever
            ),
            top_score=top_score,
            score_gap=score_gap,
            result_count=result_count,
            effective_result_count=(
                effective_result_count
            ),
            freshness_state=(
                freshness_state
            ),
            answer_allowed=True,
            reasons=tuple(reasons),
        )

    if (
        top_score
        >= thresholds.medium_score
    ):
        reasons.append(
            "retrieval_support_present"
        )

        # 후보 하나뿐인 경우 ranking 경쟁 근거가
        # 부족하므로 MEDIUM까지만 허용한다.
        if effective_result_count == 1:
            reasons.append(
                "single_effective_result"
            )
            
        reasons.append(
            "medium_requires_hold"
        )

        return ConfidenceResult(
            level=ConfidenceLevel.MEDIUM,
            retriever=(
                normalized_retriever
            ),
            top_score=top_score,
            score_gap=score_gap,
            result_count=result_count,
            effective_result_count=(
                effective_result_count
            ),
            freshness_state=(
                freshness_state
            ),
            answer_allowed=False,
            reasons=tuple(reasons),
        )

    return ConfidenceResult(
        level=ConfidenceLevel.LOW,
        retriever=(
            normalized_retriever
        ),
        top_score=top_score,
        score_gap=score_gap,
        result_count=result_count,
        effective_result_count=(
            effective_result_count
        ),
        freshness_state=(
            freshness_state
        ),
        answer_allowed=False,
        reasons=(
            "weak_retrieval_score",
        ),
    )