"""D10-BE-04 일정 Replan Proposal 시험."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from backend.app.services.delay_impact import (
    FreshnessStatus,
    IncomingDateChange,
    IncomingDateEvidence,
    LaunchImpactCandidate,
    ReservationImpactCandidate,
    ScheduledTask,
    SourceClassification,
    SourceQuality,
    calculate_delay_impact,
)
from backend.app.services.schedule_replan import (
    ReplanStatus,
    ScheduleItem,
    build_replan_proposal,
    decide_replan_proposal,
)


SEOUL = ZoneInfo("Asia/Seoul")
AS_OF = datetime(2026, 10, 1, 9, 0, tzinfo=SEOUL)
CREATED_AT = datetime(2026, 10, 2, 9, 0, tzinfo=SEOUL)
BEFORE_INCOMING = datetime(2026, 10, 10, 10, 0, tzinfo=SEOUL)
AFTER_INCOMING = BEFORE_INCOMING + timedelta(days=3)


def fixture_impact():
    change = IncomingDateChange(
        incoming_id="incoming-demo-001",
        before_expected_at=BEFORE_INCOMING,
        after_expected_at=AFTER_INCOMING,
        evidence=IncomingDateEvidence(
            source_id="fixture:incoming-delay-3d",
            source_classification=SourceClassification.FIXTURE,
            as_of=AS_OF,
            freshness=FreshnessStatus.FRESH,
            quality=SourceQuality.TENTATIVE,
            evidence_ids=("ev-fixture-001",),
        ),
    )

    return calculate_delay_impact(
        change=change,
        tasks=(
            ScheduledTask(
                task_id="task-inspection",
                deadline=datetime(
                    2026, 10, 10, 18, 0, tzinfo=SEOUL
                ),
                depends_on_incoming=True,
                lag_hours=0,
            ),
            ScheduledTask(
                task_id="task-product-page",
                deadline=datetime(
                    2026, 10, 11, 18, 0, tzinfo=SEOUL
                ),
                depends_on_incoming=True,
                lag_hours=8,
            ),
            ScheduledTask(
                task_id="task-unrelated",
                deadline=datetime(
                    2026, 10, 12, 18, 0, tzinfo=SEOUL
                ),
                depends_on_incoming=False,
            ),
        ),
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


def current_schedule() -> list[ScheduleItem]:
    return [
        ScheduleItem(
            item_type="TASK",
            item_id="task-inspection",
            scheduled_at=datetime(
                2026, 10, 10, 18, 0, tzinfo=SEOUL
            ),
        ),
        ScheduleItem(
            item_type="TASK",
            item_id="task-product-page",
            scheduled_at=datetime(
                2026, 10, 11, 18, 0, tzinfo=SEOUL
            ),
        ),
        ScheduleItem(
            item_type="TASK",
            item_id="task-unrelated",
            scheduled_at=datetime(
                2026, 10, 12, 18, 0, tzinfo=SEOUL
            ),
        ),
        ScheduleItem(
            item_type="LAUNCH_EVENT",
            item_id="launch-001",
            scheduled_at=datetime(
                2026, 10, 15, 10, 0, tzinfo=SEOUL
            ),
        ),
    ]


def test_builds_before_after_replan_diff() -> None:
    proposal = build_replan_proposal(
        current_schedule=current_schedule(),
        impact=fixture_impact(),
        created_at=CREATED_AT,
        confidence=0.8,
    )

    assert proposal.status == ReplanStatus.PROPOSED
    assert proposal.external_execution_allowed is False

    diff_by_id = {
        item.item_id: item
        for item in proposal.diff
    }

    assert (
        diff_by_id["task-inspection"].proposed_after
        == diff_by_id["task-inspection"].before
        + timedelta(days=3)
    )

    assert (
        diff_by_id["task-product-page"].proposed_after
        == diff_by_id["task-product-page"].before
        + timedelta(days=3)
    )

    assert (
        diff_by_id["launch-001"].proposed_after
        == diff_by_id["launch-001"].before
        + timedelta(days=3)
    )

    assert "task-unrelated" not in diff_by_id


def test_original_schedule_is_not_mutated() -> None:
    original = current_schedule()
    before = list(original)

    proposal = build_replan_proposal(
        current_schedule=original,
        impact=fixture_impact(),
        created_at=CREATED_AT,
        confidence=0.8,
    )

    assert original == before

    original_by_id = {
        item.item_id: item
        for item in original
    }
    proposed_by_id = {
        item.item_id: item
        for item in proposal.proposed_schedule
    }

    assert (
        original_by_id["task-inspection"].scheduled_at
        != proposed_by_id["task-inspection"].scheduled_at
    )


def test_replay_produces_same_proposal_id() -> None:
    kwargs = dict(
        current_schedule=current_schedule(),
        impact=fixture_impact(),
        created_at=CREATED_AT,
        confidence=0.8,
    )

    first = build_replan_proposal(**kwargs)
    second = build_replan_proposal(**kwargs)

    assert first.proposal_id == second.proposal_id
    assert first.diff == second.diff


@pytest.mark.parametrize(
    "decision",
    [
        ReplanStatus.APPROVED,
        ReplanStatus.REJECTED,
        ReplanStatus.EDITED,
        ReplanStatus.EXPIRED,
    ],
)
def test_decision_changes_proposal_state_only(
    decision: ReplanStatus,
) -> None:
    proposal = build_replan_proposal(
        current_schedule=current_schedule(),
        impact=fixture_impact(),
        created_at=CREATED_AT,
        confidence=0.8,
    )

    decided = decide_replan_proposal(
        proposal,
        decision,
    )

    assert decided.status == decision

    assert (
        decided.before_schedule
        == proposal.before_schedule
    )
    assert (
        decided.proposed_schedule
        == proposal.proposed_schedule
    )
    assert decided.diff == proposal.diff

    assert decided.external_execution_allowed is False


def test_approve_does_not_apply_to_original_schedule() -> None:
    original = current_schedule()
    before = list(original)

    proposal = build_replan_proposal(
        current_schedule=original,
        impact=fixture_impact(),
        created_at=CREATED_AT,
        confidence=0.9,
    )

    approved = decide_replan_proposal(
        proposal,
        ReplanStatus.APPROVED,
    )

    assert approved.status == ReplanStatus.APPROVED

    # 승인 상태와 실제 schedule mutation은 별개다.
    assert original == before
    assert approved.external_execution_allowed is False


def test_downstream_impact_and_evidence_are_preserved() -> None:
    proposal = build_replan_proposal(
        current_schedule=current_schedule(),
        impact=fixture_impact(),
        created_at=CREATED_AT,
        confidence=0.8,
    )

    assert proposal.evidence_ids == ("ev-fixture-001",)

    assert "task-inspection" in proposal.downstream_impact
    assert "task-product-page" in proposal.downstream_impact
    assert "reservation-001" in proposal.downstream_impact
    assert "launch-001" in proposal.downstream_impact


def test_invalid_confidence_is_rejected() -> None:
    with pytest.raises(ValueError, match="confidence"):
        build_replan_proposal(
            current_schedule=current_schedule(),
            impact=fixture_impact(),
            created_at=CREATED_AT,
            confidence=1.1,
        )


def test_naive_created_at_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        build_replan_proposal(
            current_schedule=current_schedule(),
            impact=fixture_impact(),
            created_at=datetime(2026, 10, 2, 9, 0),
            confidence=0.8,
        )