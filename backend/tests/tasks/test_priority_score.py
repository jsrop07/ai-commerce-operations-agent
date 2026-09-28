"""D11-BE-01 공통 priority score 단독 시험."""

from datetime import UTC, datetime, timedelta

import pytest

from backend.app.services.task_priority import (
    CALIBRATION_STATUS,
    RULE_VERSION,
    priority_sort_key,
    score_task_priority,
)


AS_OF = datetime(
    2026,
    9,
    13,
    12,
    0,
    tzinfo=UTC,
)


def _score(**overrides):
    values = {
        "tenant_id": "tenant-001",
        "task_id": "task-001",
        "deadline": AS_OF + timedelta(hours=12),
        "risk_level": "HIGH",
        "affected_count": 5,
        "aging_hours": 48,
        "as_of": AS_OF,
        "source_classification": "FIXTURE",
    }

    values.update(overrides)

    return score_task_priority(**values)


def test_same_input_is_deterministic() -> None:
    first = _score()
    second = _score()

    assert first == second


def test_contributions_match_total_score() -> None:
    result = _score()

    contributions = (
        result.deadline.contribution,
        result.risk.contribution,
        result.business_impact.contribution,
        result.aging.contribution,
    )

    assert all(
        contribution is not None
        for contribution in contributions
    )

    expected = round(
        sum(
            contribution
            for contribution in contributions
            if contribution is not None
        ),
        4,
    )

    assert result.total_score == expected


def test_missing_value_is_not_zero() -> None:
    result = _score(
        deadline=None,
    )

    assert result.deadline.raw is None
    assert result.deadline.normalized is None
    assert result.deadline.contribution is None

    assert "deadline" in result.missing_features

    assert result.coverage_weight == 0.75


def test_unknown_risk_is_not_low_risk() -> None:
    unknown = _score(
        risk_level="UNKNOWN",
    )

    low = _score(
        risk_level="LOW",
    )

    assert unknown.risk.normalized is None
    assert unknown.risk.contribution is None

    assert low.risk.normalized == 20.0
    assert low.risk.contribution is not None


def test_blocked_source_can_preserve_missing_risk() -> None:
    result = _score(
        risk_level="BLOCKED",
        source_classification="BLOCKED",
    )

    assert result.risk.normalized is None
    assert result.source_classification == "BLOCKED"


def test_overdue_deadline_has_max_deadline_score() -> None:
    result = _score(
        deadline=AS_OF - timedelta(hours=1),
    )

    assert result.deadline.normalized == 100.0
    assert (
        result.deadline.reason
        == "DEADLINE_OVERDUE"
    )


def test_aging_increases_normalized_score() -> None:
    new = _score(
        aging_hours=0,
    )

    old = _score(
        aging_hours=72,
    )

    assert (
        old.aging.normalized
        > new.aging.normalized
    )


def test_business_impact_zero_is_real_zero() -> None:
    result = _score(
        affected_count=0,
    )

    assert result.business_impact.raw == 0
    assert result.business_impact.normalized == 0.0
    assert result.business_impact.contribution == 0.0

    assert (
        "business_impact"
        not in result.missing_features
    )


def test_business_impact_none_is_missing() -> None:
    result = _score(
        affected_count=None,
    )

    assert result.business_impact.normalized is None
    assert result.business_impact.contribution is None

    assert (
        "business_impact"
        in result.missing_features
    )


def test_negative_aging_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="aging_hours",
    ):
        _score(
            aging_hours=-1,
        )


def test_negative_impact_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="affected_count",
    ):
        _score(
            affected_count=-1,
        )


def test_naive_as_of_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        _score(
            as_of=datetime(
                2026,
                9,
                13,
                12,
                0,
            ),
        )


def test_rule_provenance_is_explicit() -> None:
    result = _score()

    assert result.provenance == "RULE"
    assert result.rule_version == RULE_VERSION
    assert (
        result.calibration_status
        == CALIBRATION_STATUS
    )


def test_different_tenant_is_preserved() -> None:
    result = _score(
        tenant_id="tenant-002",
    )

    assert result.tenant_id == "tenant-002"


def test_tie_break_is_stable_by_task_id() -> None:
    first = _score(
        task_id="task-a",
    )

    second = _score(
        task_id="task-b",
    )

    ordered = sorted(
        [second, first],
        key=priority_sort_key,
    )

    assert [
        item.task_id
        for item in ordered
    ] == [
        "task-a",
        "task-b",
    ]