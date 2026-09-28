"""D11-BE-02 Task dedupe 단독 시험."""

from datetime import UTC, datetime, timedelta

import pytest

from backend.app.services.task_dedup import (
    TaskDedupService,
)


BASE = datetime(
    2026,
    9,
    13,
    0,
    0,
    tzinfo=UTC,
)


def _register(
    service: TaskDedupService,
    *,
    tenant_id: str = "tenant-001",
    sku_id: str = "sku-001",
    risk_type: str = "RESERVATION_SHORTAGE",
    occurred_at: datetime = BASE,
    evidence_ids: tuple[str, ...] = (
        "evidence-001",
    ),
    dedupe_window_hours: int = 24,
    cause_id: str = "reservation-001",
):
    return service.register(
        tenant_id=tenant_id,
        sku_id=sku_id,
        risk_type=risk_type,
        occurred_at=occurred_at,
        evidence_ids=evidence_ids,
        dedupe_window_hours=dedupe_window_hours,
        cause_id=cause_id,
    )


def test_same_cause_replay_has_one_effect() -> None:
    service = TaskDedupService()

    first = _register(service)

    second = _register(
        service,
        occurred_at=BASE + timedelta(hours=1),
    )

    assert first.dedupe_key == second.dedupe_key
    assert len(service.proposals) == 1
    assert second.replay_count == 1


def test_same_cause_ten_times_has_one_effect() -> None:
    service = TaskDedupService()

    for index in range(10):
        _register(
            service,
            occurred_at=(
                BASE + timedelta(hours=index)
            ),
        )

    assert len(service.proposals) == 1

    proposal = next(
        iter(service.proposals.values())
    )

    assert proposal.replay_count == 9


def test_evidence_is_merged_without_duplicates() -> None:
    service = TaskDedupService()

    _register(
        service,
        evidence_ids=(
            "evidence-001",
            "evidence-002",
        ),
    )

    result = _register(
        service,
        occurred_at=BASE + timedelta(hours=1),
        evidence_ids=(
            "evidence-002",
            "evidence-003",
        ),
    )

    assert result.evidence_ids == (
        "evidence-001",
        "evidence-002",
        "evidence-003",
    )


def test_different_tenant_is_separate() -> None:
    service = TaskDedupService()

    first = _register(
        service,
        tenant_id="tenant-001",
    )

    second = _register(
        service,
        tenant_id="tenant-002",
    )

    assert first.dedupe_key != second.dedupe_key
    assert len(service.proposals) == 2


def test_different_sku_is_separate() -> None:
    service = TaskDedupService()

    first = _register(
        service,
        sku_id="sku-001",
    )

    second = _register(
        service,
        sku_id="sku-002",
    )

    assert first.dedupe_key != second.dedupe_key


def test_different_risk_type_is_separate() -> None:
    service = TaskDedupService()

    first = _register(
        service,
        risk_type="RESERVATION_SHORTAGE",
    )

    second = _register(
        service,
        risk_type="INCOMING_DELAY",
    )

    assert first.dedupe_key != second.dedupe_key


def test_different_period_is_separate() -> None:
    service = TaskDedupService()

    first = _register(
        service,
        occurred_at=BASE,
        dedupe_window_hours=24,
    )

    second = _register(
        service,
        occurred_at=BASE + timedelta(hours=25),
        dedupe_window_hours=24,
    )

    assert first.dedupe_key != second.dedupe_key
    assert len(service.proposals) == 2


def test_naive_datetime_is_rejected() -> None:
    service = TaskDedupService()

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        _register(
            service,
            occurred_at=datetime(
                2026,
                9,
                13,
                0,
                0,
            ),
        )


def test_invalid_window_is_rejected() -> None:
    service = TaskDedupService()

    with pytest.raises(
        ValueError,
        match="dedupe_window_hours",
    ):
        _register(
            service,
            dedupe_window_hours=0,
        )

def test_different_cause_id_is_separate() -> None:
    service = TaskDedupService()

    first = _register(
        service,
        cause_id="reservation-001",
    )

    second = _register(
        service,
        cause_id="reservation-002",
    )

    assert first.dedupe_key != second.dedupe_key
    assert len(service.proposals) == 2

def test_missing_cause_id_is_rejected() -> None:
    service = TaskDedupService()

    with pytest.raises(
        ValueError,
        match="cause_id",
    ):
        _register(
            service,
            cause_id="",
        )