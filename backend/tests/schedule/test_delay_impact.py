"""D10-BE-03 입고 지연 영향 탐색 시험."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from backend.app.services.delay_impact import (
    DelayImpactResult,
    FreshnessStatus,
    ImpactStatus,
    IncomingDateChange,
    IncomingDateEvidence,
    LaunchImpactCandidate,
    ReservationImpactCandidate,
    ScheduledTask,
    SourceClassification,
    SourceQuality,
    calculate_delay_impact,
)


SEOUL = ZoneInfo("Asia/Seoul")
BEFORE = datetime(2026, 10, 10, 10, 0, tzinfo=SEOUL)
AFTER_3D = BEFORE + timedelta(days=3)
AS_OF = datetime(2026, 10, 1, 9, 0, tzinfo=SEOUL)


def fixture_change() -> IncomingDateChange:
    return IncomingDateChange(
        incoming_id="incoming-demo-001",
        before_expected_at=BEFORE,
        after_expected_at=AFTER_3D,
        evidence=IncomingDateEvidence(
            source_id="fixture:incoming-delay-3d",
            source_classification=SourceClassification.FIXTURE,
            as_of=AS_OF,
            freshness=FreshnessStatus.FRESH,
            quality=SourceQuality.TENTATIVE,
            evidence_ids=("ev-fixture-incoming-001",),
        ),
    )


def sample_tasks() -> tuple[ScheduledTask, ...]:
    return (
        ScheduledTask(
            task_id="task-inspection",
            deadline=datetime(2026, 10, 10, 18, 0, tzinfo=SEOUL),
            depends_on_incoming=True,
            lag_hours=0,
        ),
        ScheduledTask(
            task_id="task-product-page",
            deadline=datetime(2026, 10, 11, 18, 0, tzinfo=SEOUL),
            depends_on_incoming=True,
            lag_hours=8,
        ),
        ScheduledTask(
            task_id="task-unrelated",
            deadline=datetime(2026, 10, 12, 18, 0, tzinfo=SEOUL),
            depends_on_incoming=False,
        ),
    )


def test_fixture_three_day_delay_calculates_impact_but_not_actual() -> None:
    result = calculate_delay_impact(
        change=fixture_change(),
        tasks=sample_tasks(),
        reservations=(
            ReservationImpactCandidate(
                reservation_id="reservation-001",
                incoming_id="incoming-demo-001",
            ),
        ),
        launch_events=(
            LaunchImpactCandidate(
                launch_event_id="launch-001",
                launch_at=datetime(
                    2026, 10, 15, 10, 0, tzinfo=SEOUL
                ),
                depends_on_incoming=True,
            ),
        ),
    )

    assert result.delay_hours == 72
    assert result.status == ImpactStatus.CONTRACT_ONLY
    assert result.actual_delay_confirmed is False

    assert result.impacted_task_ids == (
        "task-inspection",
        "task-product-page",
    )
    assert result.impacted_reservation_ids == ("reservation-001",)
    assert result.impacted_launch_event_ids == ("launch-001",)

    assert "task-unrelated" not in result.impacted_task_ids


def test_impact_path_preserves_source_and_before_after() -> None:
    result = calculate_delay_impact(
        change=fixture_change(),
        tasks=sample_tasks(),
        reservations=(),
        launch_events=(),
    )

    assert result.source_id == "fixture:incoming-delay-3d"
    assert (
        result.source_classification
        == SourceClassification.FIXTURE
    )
    assert result.as_of == AS_OF
    assert result.freshness == FreshnessStatus.FRESH
    assert result.quality == SourceQuality.TENTATIVE
    assert result.evidence_ids == ("ev-fixture-incoming-001",)

    first = result.impact_path[0]

    assert first.source_id == result.source_id
    assert first.before is not None
    assert first.after == first.before + timedelta(days=3)
    assert first.evidence_ids == result.evidence_ids


def test_task_lag_is_preserved_in_impact_path() -> None:
    result = calculate_delay_impact(
        change=fixture_change(),
        tasks=sample_tasks(),
        reservations=(),
        launch_events=(),
    )

    by_id = {
        item.target_id: item
        for item in result.impact_path
        if item.target_type == "TASK"
    }

    assert by_id["task-inspection"].lag_hours == 0
    assert by_id["task-product-page"].lag_hours == 8


@pytest.mark.parametrize(
    "classification",
    [
        SourceClassification.BLOCKED,
        SourceClassification.UNKNOWN,
        SourceClassification.SOURCE_QUALITY_BLOCKED,
    ],
)
def test_blocked_sources_do_not_confirm_actual_delay(
    classification: SourceClassification,
) -> None:
    change = IncomingDateChange(
        incoming_id="incoming-blocked",
        before_expected_at=BEFORE,
        after_expected_at=AFTER_3D,
        evidence=IncomingDateEvidence(
            source_id="ecount-or-gmail-unavailable",
            source_classification=classification,
            as_of=None,
            freshness=FreshnessStatus.UNKNOWN,
            quality=SourceQuality.BLOCKED,
            evidence_ids=(),
        ),
    )

    result = calculate_delay_impact(
        change=change,
        tasks=sample_tasks(),
        reservations=(),
        launch_events=(),
    )

    assert result.status == ImpactStatus.BLOCKED
    assert result.actual_delay_confirmed is False
    assert result.delay_hours is None
    assert result.impacted_task_ids == ()
    assert result.impact_path == ()


@pytest.mark.parametrize(
    ("before", "after"),
    [
        (None, AFTER_3D),
        (BEFORE, None),
        (None, None),
    ],
)
def test_null_expected_at_is_not_replaced_with_fake_date(
    before,
    after,
) -> None:
    change = IncomingDateChange(
        incoming_id="incoming-null",
        before_expected_at=before,
        after_expected_at=after,
        evidence=IncomingDateEvidence(
            source_id="gmail-not-connected",
            source_classification=SourceClassification.BLOCKED,
            as_of=None,
            freshness=FreshnessStatus.UNKNOWN,
            quality=SourceQuality.BLOCKED,
            evidence_ids=(),
        ),
    )

    result = calculate_delay_impact(
        change=change,
        tasks=sample_tasks(),
        reservations=(),
        launch_events=(),
    )

    assert result.status == ImpactStatus.BLOCKED
    assert result.delay_hours is None
    assert result.actual_delay_confirmed is False


def test_fixture_is_never_promoted_to_sanitized_real() -> None:
    result = calculate_delay_impact(
        change=fixture_change(),
        tasks=sample_tasks(),
        reservations=(),
        launch_events=(),
    )

    assert (
        result.source_classification
        == SourceClassification.FIXTURE
    )
    assert (
        result.source_classification
        != SourceClassification.SANITIZED_REAL
    )


def test_actual_requires_confirmed_fresh_evidence() -> None:
    change = IncomingDateChange(
        incoming_id="incoming-live",
        before_expected_at=BEFORE,
        after_expected_at=AFTER_3D,
        evidence=IncomingDateEvidence(
            source_id="verified-source-001",
            source_classification=SourceClassification.LIVE_READ,
            as_of=AS_OF,
            freshness=FreshnessStatus.FRESH,
            quality=SourceQuality.CONFIRMED,
            evidence_ids=("ev-live-001",),
        ),
    )

    result = calculate_delay_impact(
        change=change,
        tasks=sample_tasks(),
        reservations=(),
        launch_events=(),
    )

    assert result.status == ImpactStatus.CALCULATED
    assert result.actual_delay_confirmed is True
    assert result.delay_hours == 72


def test_same_input_is_deterministic() -> None:
    kwargs = dict(
        change=fixture_change(),
        tasks=sample_tasks(),
        reservations=(),
        launch_events=(),
    )

    first: DelayImpactResult = calculate_delay_impact(**kwargs)
    second: DelayImpactResult = calculate_delay_impact(**kwargs)

    assert first == second


def test_naive_expected_at_is_rejected() -> None:
    change = IncomingDateChange(
        incoming_id="incoming-invalid",
        before_expected_at=datetime(2026, 10, 10, 10, 0),
        after_expected_at=AFTER_3D,
        evidence=IncomingDateEvidence(
            source_id="fixture-invalid",
            source_classification=SourceClassification.FIXTURE,
            as_of=AS_OF,
            freshness=FreshnessStatus.FRESH,
            quality=SourceQuality.TENTATIVE,
            evidence_ids=("ev-001",),
        ),
    )

    with pytest.raises(ValueError, match="timezone-aware"):
        calculate_delay_impact(
            change=change,
            tasks=(),
            reservations=(),
            launch_events=(),
        )