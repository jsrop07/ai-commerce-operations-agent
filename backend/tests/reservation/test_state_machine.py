"""D09-BE-03 예약 상태 전이 테스트."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from backend.app.services.reservation_state import (
    ReservationFlowState,
    ReservationStateMachine,
    ReservationTransitionError,
)


NOW = datetime(
    2026,
    9,
    10,
    6,
    40,
    tzinfo=UTC,
)


def _transition(
    machine: ReservationStateMachine,
    current: ReservationFlowState,
    target: ReservationFlowState,
    *,
    source_system: str = "BACKEND",
    source_classification: str = "FIXTURE",
):
    return machine.transition(
        reservation_id="reservation-001",
        current_state=current,
        target_state=target,
        actor="operator-fixture",
        evidence_ids=(
            "evidence-001",
        ),
        occurred_at=NOW,
        as_of=NOW,
        source_system=source_system,
        source_classification=(
            source_classification
        ),
    )


def test_valid_reservation_to_purchase_pending() -> None:
    machine = ReservationStateMachine()

    result = _transition(
        machine,
        ReservationFlowState
        .RESERVATION_CONFIRMED,
        ReservationFlowState
        .PURCHASE_ORDER_PENDING,
    )

    assert (
        result.current_state
        == ReservationFlowState
        .PURCHASE_ORDER_PENDING
    )

    assert result.audit.outcome == "ALLOWED"


def test_full_fixture_transition_path() -> None:
    machine = ReservationStateMachine()

    path = (
        ReservationFlowState
        .RESERVATION_CONFIRMED,
        ReservationFlowState
        .PURCHASE_ORDER_PENDING,
        ReservationFlowState
        .PURCHASE_ORDER_CONFIRMED,
        ReservationFlowState
        .INCOMING_CONFIRMED,
        ReservationFlowState
        .RECEIVED,
        ReservationFlowState
        .READY_TO_SHIP,
        ReservationFlowState
        .SHIPPED,
    )

    current = path[0]

    for target in path[1:]:
        result = _transition(
            machine,
            current,
            target,
        )

        current = (
            result.current_state
        )

    assert (
        current
        == ReservationFlowState.SHIPPED
    )

    assert len(machine.audit) == 6

    assert all(
        audit.outcome == "ALLOWED"
        for audit in machine.audit
    )


def test_invalid_jump_is_denied_and_audited() -> None:
    machine = ReservationStateMachine()

    with pytest.raises(
        ReservationTransitionError,
        match="INVALID_STATE_TRANSITION",
    ):
        _transition(
            machine,
            ReservationFlowState
            .RESERVATION_CONFIRMED,
            ReservationFlowState.SHIPPED,
        )

    assert len(machine.audit) == 1

    audit = machine.audit[0]

    assert audit.outcome == "DENIED"
    assert (
        audit.reason
        == "INVALID_STATE_TRANSITION"
    )


def test_ecount_contract_only_cannot_confirm_purchase_order() -> None:
    machine = ReservationStateMachine()

    with pytest.raises(
        ReservationTransitionError,
        match=(
            "ECOUNT_PURCHASE_ORDER_"
            "NOT_ACTUALLY_INTEGRATED"
        ),
    ):
        _transition(
            machine,
            ReservationFlowState
            .PURCHASE_ORDER_PENDING,
            ReservationFlowState
            .PURCHASE_ORDER_CONFIRMED,
            source_system="ECOUNT",
            source_classification=(
                "CONTRACT_ONLY"
            ),
        )

    assert machine.audit[-1].outcome == (
        "DENIED"
    )


def test_gmail_contract_only_cannot_confirm_incoming() -> None:
    machine = ReservationStateMachine()

    with pytest.raises(
        ReservationTransitionError,
        match=(
            "GMAIL_REPLY_"
            "NOT_ACTUALLY_INTEGRATED"
        ),
    ):
        _transition(
            machine,
            ReservationFlowState
            .PURCHASE_ORDER_CONFIRMED,
            ReservationFlowState
            .INCOMING_CONFIRMED,
            source_system="GMAIL",
            source_classification=(
                "CONTRACT_ONLY"
            ),
        )

    assert machine.audit[-1].outcome == (
        "DENIED"
    )


def test_audit_contains_required_provenance() -> None:
    machine = ReservationStateMachine()

    result = _transition(
        machine,
        ReservationFlowState
        .RESERVATION_CONFIRMED,
        ReservationFlowState
        .PURCHASE_ORDER_PENDING,
        source_classification="SANITIZED_REAL",
    )

    audit = result.audit

    assert audit.actor == (
        "operator-fixture"
    )

    assert audit.evidence_ids == (
        "evidence-001",
    )

    assert audit.occurred_at == NOW
    assert audit.as_of == NOW

    assert (
        audit.source_classification
        == "SANITIZED_REAL"
    )


def test_transition_requires_evidence() -> None:
    machine = ReservationStateMachine()

    with pytest.raises(
        ValueError,
        match="evidence_ids are required",
    ):
        machine.transition(
            reservation_id=(
                "reservation-001"
            ),
            current_state=(
                ReservationFlowState
                .RESERVATION_CONFIRMED
            ),
            target_state=(
                ReservationFlowState
                .PURCHASE_ORDER_PENDING
            ),
            actor="operator-fixture",
            evidence_ids=(),
            occurred_at=NOW,
            source_system="BACKEND",
            source_classification=(
                "FIXTURE"
            ),
        )