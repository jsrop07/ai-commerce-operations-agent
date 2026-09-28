"""D11-BE-01 공통 Task priority Rule 계산.

이 모듈의 점수/가중치는 Day11 구현 검증용 baseline이다.
실제 운영 효과가 검증된 업무 기준으로 간주하지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


RULE_VERSION = "task-priority.v0.1"
CALIBRATION_STATUS = "DAY11_BASELINE_UNVALIDATED"


@dataclass(frozen=True)
class PriorityRuleConfig:
    """버전으로 고정하는 우선순위 Rule 설정."""

    deadline_weight: float = 0.25
    risk_weight: float = 0.25
    business_impact_weight: float = 0.25
    aging_weight: float = 0.25

    deadline_urgent_hours: int = 24
    deadline_near_hours: int = 72
    deadline_watch_hours: int = 168

    impact_medium_count: int = 2
    impact_high_count: int = 5
    impact_critical_count: int = 10

    aging_watch_hours: int = 24
    aging_high_hours: int = 48
    aging_critical_hours: int = 72

    rule_version: str = RULE_VERSION


DEFAULT_CONFIG = PriorityRuleConfig()


@dataclass(frozen=True)
class PriorityFeatureContribution:
    """한 feature가 최종 priority에 기여한 근거."""

    raw: object | None
    normalized: float | None
    weight: float
    contribution: float | None
    reason: str


@dataclass(frozen=True)
class PriorityScore:
    """Frontend/API로 Projection 가능한 Rule 계산 결과."""

    tenant_id: str
    task_id: str

    total_score: float

    deadline: PriorityFeatureContribution
    risk: PriorityFeatureContribution
    business_impact: PriorityFeatureContribution
    aging: PriorityFeatureContribution

    coverage_weight: float
    missing_features: tuple[str, ...]

    rule_version: str
    calibration_status: str
    provenance: str

    as_of: datetime
    source_classification: str


def _validate_aware_datetime(
    value: datetime,
    *,
    field_name: str,
) -> None:
    if (
        value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(
            f"{field_name} must be timezone-aware"
        )


def _normalize_deadline(
    *,
    deadline: datetime | None,
    as_of: datetime,
    config: PriorityRuleConfig,
) -> tuple[float | None, str]:
    if deadline is None:
        return None, "DEADLINE_UNKNOWN"

    _validate_aware_datetime(
        deadline,
        field_name="deadline",
    )

    hours_remaining = (
        deadline - as_of
    ).total_seconds() / 3600

    if hours_remaining <= 0:
        return 100.0, "DEADLINE_OVERDUE"

    if hours_remaining <= config.deadline_urgent_hours:
        return 80.0, "DEADLINE_WITHIN_24H"

    if hours_remaining <= config.deadline_near_hours:
        return 60.0, "DEADLINE_WITHIN_72H"

    if hours_remaining <= config.deadline_watch_hours:
        return 40.0, "DEADLINE_WITHIN_168H"

    return 20.0, "DEADLINE_LATER"


def _normalize_risk(
    risk_level: str | None,
) -> tuple[float | None, str]:
    if risk_level is None:
        return None, "RISK_UNKNOWN"

    normalized_risk = risk_level.upper()

    mapping = {
        "LOW": (20.0, "RISK_LOW"),
        "MEDIUM": (60.0, "RISK_MEDIUM"),
        "HIGH": (100.0, "RISK_HIGH"),
    }

    if normalized_risk in {
        "UNKNOWN",
        "BLOCKED",
        "SOURCE_QUALITY_BLOCKED",
    }:
        return None, f"RISK_{normalized_risk}"

    if normalized_risk not in mapping:
        raise ValueError(
            f"unsupported risk_level: {risk_level}"
        )

    return mapping[normalized_risk]


def _normalize_business_impact(
    *,
    affected_count: int | None,
    config: PriorityRuleConfig,
) -> tuple[float | None, str]:
    if affected_count is None:
        return None, "BUSINESS_IMPACT_UNKNOWN"

    if affected_count < 0:
        raise ValueError(
            "affected_count must be >= 0"
        )

    if affected_count >= config.impact_critical_count:
        return 100.0, "BUSINESS_IMPACT_10_PLUS"

    if affected_count >= config.impact_high_count:
        return 75.0, "BUSINESS_IMPACT_5_PLUS"

    if affected_count >= config.impact_medium_count:
        return 50.0, "BUSINESS_IMPACT_2_PLUS"

    if affected_count == 1:
        return 25.0, "BUSINESS_IMPACT_1"

    return 0.0, "BUSINESS_IMPACT_NONE"


def _normalize_aging(
    *,
    aging_hours: int | None,
    config: PriorityRuleConfig,
) -> tuple[float | None, str]:
    if aging_hours is None:
        return None, "AGING_UNKNOWN"

    if aging_hours < 0:
        raise ValueError(
            "aging_hours must be >= 0"
        )

    if aging_hours >= config.aging_critical_hours:
        return 100.0, "AGING_72H_PLUS"

    if aging_hours >= config.aging_high_hours:
        return 70.0, "AGING_48H_PLUS"

    if aging_hours >= config.aging_watch_hours:
        return 40.0, "AGING_24H_PLUS"

    return 0.0, "AGING_UNDER_24H"


def _feature(
    *,
    raw: object | None,
    normalized: float | None,
    weight: float,
    reason: str,
) -> PriorityFeatureContribution:
    contribution = (
        None
        if normalized is None
        else round(normalized * weight, 4)
    )

    return PriorityFeatureContribution(
        raw=raw,
        normalized=normalized,
        weight=weight,
        contribution=contribution,
        reason=reason,
    )


def score_task_priority(
    *,
    tenant_id: str,
    task_id: str,
    deadline: datetime | None,
    risk_level: str | None,
    affected_count: int | None,
    aging_hours: int | None,
    as_of: datetime,
    source_classification: str,
    config: PriorityRuleConfig = DEFAULT_CONFIG,
) -> PriorityScore:
    """Task priority를 결정론적 Rule로 계산한다."""

    if not tenant_id:
        raise ValueError("tenant_id is required")

    if not task_id:
        raise ValueError("task_id is required")

    if not source_classification:
        raise ValueError(
            "source_classification is required"
        )

    _validate_aware_datetime(
        as_of,
        field_name="as_of",
    )

    weights = (
        config.deadline_weight,
        config.risk_weight,
        config.business_impact_weight,
        config.aging_weight,
    )

    if any(weight < 0 for weight in weights):
        raise ValueError(
            "priority weights must be >= 0"
        )

    if round(sum(weights), 10) != 1.0:
        raise ValueError(
            "priority weights must sum to 1.0"
        )

    deadline_value, deadline_reason = (
        _normalize_deadline(
            deadline=deadline,
            as_of=as_of,
            config=config,
        )
    )

    risk_value, risk_reason = (
        _normalize_risk(risk_level)
    )

    impact_value, impact_reason = (
        _normalize_business_impact(
            affected_count=affected_count,
            config=config,
        )
    )

    aging_value, aging_reason = (
        _normalize_aging(
            aging_hours=aging_hours,
            config=config,
        )
    )

    deadline_feature = _feature(
        raw=deadline,
        normalized=deadline_value,
        weight=config.deadline_weight,
        reason=deadline_reason,
    )

    risk_feature = _feature(
        raw=risk_level,
        normalized=risk_value,
        weight=config.risk_weight,
        reason=risk_reason,
    )

    impact_feature = _feature(
        raw=affected_count,
        normalized=impact_value,
        weight=config.business_impact_weight,
        reason=impact_reason,
    )

    aging_feature = _feature(
        raw=aging_hours,
        normalized=aging_value,
        weight=config.aging_weight,
        reason=aging_reason,
    )

    features = {
        "deadline": deadline_feature,
        "risk": risk_feature,
        "business_impact": impact_feature,
        "aging": aging_feature,
    }

    contributions = [
        feature.contribution
        for feature in features.values()
        if feature.contribution is not None
    ]

    total_score = round(
        min(
            max(sum(contributions), 0.0),
            100.0,
        ),
        4,
    )

    missing_features = tuple(
        name
        for name, feature in features.items()
        if feature.normalized is None
    )

    coverage_weight = round(
        sum(
            feature.weight
            for feature in features.values()
            if feature.normalized is not None
        ),
        4,
    )

    return PriorityScore(
        tenant_id=tenant_id,
        task_id=task_id,
        total_score=total_score,
        deadline=deadline_feature,
        risk=risk_feature,
        business_impact=impact_feature,
        aging=aging_feature,
        coverage_weight=coverage_weight,
        missing_features=missing_features,
        rule_version=config.rule_version,
        calibration_status=CALIBRATION_STATUS,
        provenance="RULE",
        as_of=as_of,
        source_classification=source_classification,
    )


def priority_sort_key(
    result: PriorityScore,
) -> tuple[float, float, str]:
    """높은 점수 → 높은 정보 coverage → task_id 순으로 안정 정렬한다."""

    return (
        -result.total_score,
        -result.coverage_weight,
        result.task_id,
    )