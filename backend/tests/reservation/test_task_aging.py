"""D09-BE-04 예약 부족 Task dedupe/aging 테스트."""

from datetime import (
    UTC,
    datetime,
    timedelta,
)

from backend.app.services.reservation_tasks import (
    ReservationTaskService,
    register_reservation_risk_projection,
)
from types import SimpleNamespace
from backend.app.services.reservation_projection import build_reservation_risk_projection
from backend.app.services.reservation_shortage import (
    IncomingEvidence,
    calculate_reservation_shortage,
)


BASE = datetime(
    2026,
    9,
    10,
    0,
    0,
    tzinfo=UTC,
)


def _propose(
    service: ReservationTaskService,
    *,
    detected_at: datetime,
    tenant_id: str = "tenant-001",
    sku_id: str = "sku-001",
    cause: str = "RESERVATION_SHORTAGE",
    cause_id: str = "reservation-001",
):
    return service.propose_shortage_task(
        tenant_id=tenant_id,
        sku_id=sku_id,
        cause=cause,
        cause_id=cause_id,
        detected_at=detected_at,
        evidence_ids=(
            "evidence-001",
        ),
        source_classification=(
            "FIXTURE"
        ),
        dedupe_window_hours=168,
    )

def test_same_shortage_replay_creates_one_task() -> None:
    service = ReservationTaskService()

    first = _propose(
        service,
        detected_at=BASE,
    )

    second = _propose(
        service,
        detected_at=(
            BASE
            + timedelta(hours=1)
        ),
    )

    assert first.task_id == (
        second.task_id
    )

    assert len(service.tasks) == 1

    assert second.replay_count == 1

def test_different_cause_id_creates_different_task() -> None:
    service = ReservationTaskService()

    first = _propose(
        service,
        detected_at=BASE,
        cause_id="reservation-001",
    )

    second = _propose(
        service,
        detected_at=BASE + timedelta(hours=1),
        cause_id="reservation-002",
    )

    assert first.task_id != second.task_id
    assert len(service.tasks) == 2
    
def test_different_reservation_causes_create_separate_tasks() -> None:
    service = ReservationTaskService()

    first = service.propose_shortage_task(
        tenant_id="tenant-001",
        sku_id="sku-001",
        cause="RESERVATION_SHORTAGE",
        cause_id="reservation-001",
        detected_at=BASE,
        evidence_ids=("evidence-001",),
        source_classification="FIXTURE",
        dedupe_window_hours=168,
    )

    second = service.propose_shortage_task(
        tenant_id="tenant-001",
        sku_id="sku-001",
        cause="RESERVATION_SHORTAGE",
        cause_id="reservation-002",
        detected_at=BASE + timedelta(hours=1),
        evidence_ids=("evidence-002",),
        source_classification="FIXTURE",
        dedupe_window_hours=168,
    )

    assert first.task_id != second.task_id
    assert len(service.tasks) == 2

def test_replay_ten_times_has_one_business_effect() -> None:
    service = ReservationTaskService()

    for index in range(10):
        _propose(
            service,
            detected_at=(
                BASE
                + timedelta(
                    hours=index
                )
            ),
        )

    assert len(service.tasks) == 1

    task = next(
        iter(
            service.tasks.values()
        )
    )

    assert task.replay_count == 9


def test_different_sku_creates_different_task() -> None:
    service = ReservationTaskService()

    first = _propose(
        service,
        detected_at=BASE,
        sku_id="sku-001",
    )

    second = _propose(
        service,
        detected_at=BASE,
        sku_id="sku-002",
    )

    assert first.task_id != (
        second.task_id
    )

    assert len(service.tasks) == 2


def test_different_cause_creates_different_task() -> None:
    service = ReservationTaskService()

    first = _propose(
        service,
        detected_at=BASE,
        cause=(
            "RESERVATION_SHORTAGE"
        ),
    )

    second = _propose(
        service,
        detected_at=BASE,
        cause=(
            "INCOMING_DELAY"
        ),
    )

    assert first.task_id != (
        second.task_id
    )


def test_aging_24_hours_raises_priority() -> None:
    service = ReservationTaskService()

    _propose(
        service,
        detected_at=BASE,
    )

    result = _propose(
        service,
        detected_at=(
            BASE
            + timedelta(hours=24)
        ),
    )

    assert result.aging_hours == 24
    assert result.priority == 50

    assert (
        result.priority_reason
        == "AGING_24H_PLUS"
    )


def test_aging_48_hours_raises_priority() -> None:
    service = ReservationTaskService()

    _propose(
        service,
        detected_at=BASE,
    )

    result = _propose(
        service,
        detected_at=(
            BASE
            + timedelta(hours=48)
        ),
    )

    assert result.priority == 70

    assert (
        result.priority_reason
        == "AGING_48H_PLUS"
    )


def test_aging_72_hours_is_high_priority() -> None:
    service = ReservationTaskService()

    _propose(
        service,
        detected_at=BASE,
    )

    result = _propose(
        service,
        detected_at=(
            BASE
            + timedelta(hours=72)
        ),
    )

    assert result.priority == 90

    assert (
        result.priority_reason
        == "AGING_72H_PLUS"
    )


def test_task_is_proposed_only() -> None:
    service = ReservationTaskService()

    result = _propose(
        service,
        detected_at=BASE,
    )

    assert result.status == "PROPOSED"


def _risk_projection(*, reservation_id: str, shortage: int | None):
    return build_reservation_risk_projection(
        reservation_id=reservation_id,
        tenant_id="tenant-001",
        sku_id="sku-001",
        required_qty=5,
        secured_qty=1 if shortage is not None else None,
        confirmed_incoming_qty=2 if shortage is not None else None,
        tentative_incoming_qty=0,
        shortage=shortage,
        affected_order_ids=("order-fixture-001", "order-fixture-002"),
        aging_hours=12,
        priority=42,
        priority_reason="FIXTURE_PRIORITY",
        calculation_status="CONFIRMED" if shortage is not None else "SECURED_QTY_UNKNOWN",
        evidence=("reservation-evidence-001",),
        source_classification="FIXTURE",
        quality_status="CONFIRMED",
        as_of=BASE,
    )


def test_shortage_result_projects_to_deduped_task() -> None:
    shortage = calculate_reservation_shortage(
        required_qty=5,
        secured_qty=1,
        incoming=(IncomingEvidence(
            evidence_id="reservation-evidence-001",
            quantity=2,
            confirmation_status="CONFIRMED",
            quality_status="CONFIRMED",
            freshness="FRESH",
            source_classification="FIXTURE",
        ),),
        as_of=BASE,
    )
    assert shortage.shortage == 2

    service = ReservationTaskService()
    projection = _risk_projection(
        reservation_id="reservation-001",
        shortage=shortage.shortage,
    )
    first = service.project_shortage_task(projection)
    replay = service.project_shortage_task(projection)
    assert len(service.tasks) == 1
    other = service.project_shortage_task(_risk_projection(
        reservation_id="reservation-002",
        shortage=shortage.shortage,
    ))

    assert first is not None and replay is not None and other is not None
    assert first["id"] == replay["id"]
    assert first["reservation_id"] == "reservation-001"
    assert replay["reservation_id"] == "reservation-001"
    assert replay["replay_count"] == 1
    assert len(service.tasks) == 2
    assert other["id"] != first["id"]
    assert other["reservation_id"] == "reservation-002"
    assert first["status"] == "PROPOSED"
    assert first["priority"] == 42
    assert first["risk_level"] == "MEDIUM"
    assert first["deadline"] is None
    assert first["evidence_ids"] == ("reservation-evidence-001",)
    assert first["affected_count"] == 2
    assert "affected_order_ids" not in first


def test_unknown_or_zero_shortage_does_not_propose_task() -> None:
    service = ReservationTaskService()
    assert service.project_shortage_task(_risk_projection(
        reservation_id="reservation-unknown",
        shortage=None,
    )) is None
    assert service.project_shortage_task(_risk_projection(
        reservation_id="reservation-zero",
        shortage=0,
    )) is None
    assert service.tasks == {}


def test_registration_preserves_reservations_and_upserts_shortage_tasks() -> None:
    state = SimpleNamespace(
        reservation_risk_projections=[],
        reservation_task_service=ReservationTaskService(),
        schedule_task_projections=[],
    )
    risk = _risk_projection(reservation_id="reservation-001", shortage=2)
    first = register_reservation_risk_projection(state, risk)
    assert first is not None
    assert len(state.reservation_risk_projections) == 1
    assert len(state.schedule_task_projections) == 1

    replay = register_reservation_risk_projection(state, risk)
    assert replay is not None
    assert len(state.reservation_risk_projections) == 2
    assert len(state.schedule_task_projections) == 1
    assert replay["task_id"] == first["task_id"]
    assert replay["reservation_id"] == "reservation-001"
    assert state.schedule_task_projections[0]["replay_count"] == 1
    assert state.schedule_task_projections[0]["reservation_id"] == "reservation-001"

    other = register_reservation_risk_projection(
        state, _risk_projection(reservation_id="reservation-002", shortage=2)
    )
    assert other is not None
    assert other["task_id"] != first["task_id"]
    assert other["reservation_id"] == "reservation-002"
    assert len(state.schedule_task_projections) == 2
    assert {task["reservation_id"] for task in state.schedule_task_projections} == {
        "reservation-001", "reservation-002",
    }

    assert register_reservation_risk_projection(
        state, _risk_projection(reservation_id="reservation-unknown", shortage=None)
    ) is None
    assert register_reservation_risk_projection(
        state, _risk_projection(reservation_id="reservation-zero", shortage=0)
    ) is None
    assert len(state.reservation_risk_projections) == 5
    assert len(state.schedule_task_projections) == 2
    assert all("affected_order_ids" not in task for task in state.schedule_task_projections)
