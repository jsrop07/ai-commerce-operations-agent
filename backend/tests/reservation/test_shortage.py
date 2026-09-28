"""D09-BE-02 예약 부족수량 계산 테스트."""

from __future__ import annotations

from backend.app.services.reservation_shortage import (
    IncomingEvidence,
    calculate_reservation_shortage,
)


def _incoming(
    *,
    evidence_id: str,
    quantity: int | None,
    confirmation_status: str = "CONFIRMED",
    quality_status: str = "CONFIRMED",
    freshness: str = "FRESH",
) -> IncomingEvidence:
    return IncomingEvidence(
        evidence_id=evidence_id,
        quantity=quantity,
        confirmation_status=(
            confirmation_status
        ),
        quality_status=quality_status,
        freshness=freshness,
        source_classification=(
            "FIXTURE"
        ),
    )


def test_required_5_secured_1_confirmed_2_shortage_2() -> None:
    result = calculate_reservation_shortage(
        required_qty=5,
        secured_qty=1,
        incoming=(
            _incoming(
                evidence_id="incoming-001",
                quantity=2,
            ),
        ),
    )

    assert result.confirmed_incoming_qty == 2
    assert result.shortage == 2
    assert (
        result.calculation_status
        == "CONFIRMED"
    )


def test_tentative_incoming_is_not_deducted() -> None:
    result = calculate_reservation_shortage(
        required_qty=5,
        secured_qty=1,
        incoming=(
            _incoming(
                evidence_id="incoming-002",
                quantity=3,
                confirmation_status=(
                    "TENTATIVE"
                ),
            ),
        ),
    )

    assert result.confirmed_incoming_qty == 0
    assert result.tentative_incoming_qty == 3
    assert result.shortage == 4

    assert (
        result.excluded_incoming[0].reason
        == "TENTATIVE"
    )


def test_stale_incoming_is_not_deducted() -> None:
    result = calculate_reservation_shortage(
        required_qty=5,
        secured_qty=1,
        incoming=(
            _incoming(
                evidence_id="incoming-003",
                quantity=2,
                freshness="STALE",
            ),
        ),
    )

    assert result.confirmed_incoming_qty == 0
    assert result.shortage == 4

    assert (
        result.excluded_incoming[0].reason
        == "STALE"
    )


def test_source_quality_blocked_is_not_deducted() -> None:
    result = calculate_reservation_shortage(
        required_qty=5,
        secured_qty=1,
        incoming=(
            _incoming(
                evidence_id="incoming-004",
                quantity=2,
                quality_status=(
                    "SOURCE_QUALITY_BLOCKED"
                ),
            ),
        ),
    )

    assert result.confirmed_incoming_qty == 0
    assert result.shortage == 4


def test_confirmed_null_quantity_is_not_converted_to_zero() -> None:
    result = calculate_reservation_shortage(
        required_qty=5,
        secured_qty=1,
        incoming=(
            _incoming(
                evidence_id="incoming-005",
                quantity=None,
            ),
        ),
    )

    assert (
        result.confirmed_incoming_qty
        is None
    )

    assert result.shortage is None

    assert (
        result.calculation_status
        == "CONFIRMED_INCOMING_UNKNOWN"
    )


def test_null_secured_quantity_blocks_shortage_calculation() -> None:
    result = calculate_reservation_shortage(
        required_qty=5,
        secured_qty=None,
    )

    assert result.secured_qty is None
    assert result.shortage is None

    assert (
        result.calculation_status
        == "SECURED_QTY_UNKNOWN"
    )


def test_shortage_does_not_go_negative() -> None:
    result = calculate_reservation_shortage(
        required_qty=3,
        secured_qty=2,
        incoming=(
            _incoming(
                evidence_id="incoming-006",
                quantity=5,
            ),
        ),
    )

    assert result.shortage == 0