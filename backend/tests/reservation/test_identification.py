"""D09-BE-01 예약주문 식별 테스트."""

from __future__ import annotations

from backend.app.services.reservation_service import (
    ReservationIdentification,
    ReservationIdentificationInput,
    identify_reservation,
)


def test_current_preorder_category_does_not_confirm_history() -> None:
    result = identify_reservation(
        ReservationIdentificationInput(
            order_id="order-001",
            current_category=(
                "pre-order"
            ),
            source_classification=(
                "SANITIZED_REAL"
            ),
        )
    )

    assert (
        result.status
        == ReservationIdentification.UNKNOWN
    )

    assert (
        "CURRENT_CATEGORY_ONLY_"
        "NOT_VALID_TIME_EVIDENCE"
        in result.reasons
    )

    assert (
        result.mapping_review_required
        is False
    )

    assert result.selected_sku_id is None


def test_missing_evidence_without_candidates_does_not_require_mapping_review() -> None:
    result = identify_reservation(
        ReservationIdentificationInput(
            order_id="order-no-evidence",
            source_classification=(
                "SANITIZED_REAL"
            ),
        )
    )

    assert (
        result.status
        == ReservationIdentification.UNKNOWN
    )
    assert (
        "RESERVATION_EVIDENCE_MISSING"
        in result.reasons
    )
    assert (
        result.mapping_review_required
        is False
    )
    assert result.selected_sku_id is None


def test_order_time_category_snapshot_can_confirm() -> None:
    result = identify_reservation(
        ReservationIdentificationInput(
            order_id="order-002",
            order_category_snapshot=(
                "예약판매"
            ),
            mapping_approved=True,
            selected_sku_id="sku-002",
            source_classification=(
                "SANITIZED_REAL"
            ),
        )
    )

    assert (
        result.status
        == (
            ReservationIdentification
            .CONFIRMED_RESERVATION
        )
    )

    assert (
        result.selected_sku_id
        == "sku-002"
    )


def test_explicit_reservation_evidence_can_confirm() -> None:
    result = identify_reservation(
        ReservationIdentificationInput(
            order_id="order-003",
            reservation_evidence_ids=(
                "ev-reservation-001",
            ),
            mapping_approved=True,
            selected_sku_id="sku-003",
            source_classification=(
                "SANITIZED_REAL"
            ),
        )
    )

    assert (
        result.status
        == (
            ReservationIdentification
            .CONFIRMED_RESERVATION
        )
    )


def test_single_candidate_is_not_auto_selected() -> None:
    result = identify_reservation(
        ReservationIdentificationInput(
            order_id="order-004",
            order_category_snapshot=(
                "PREORDER"
            ),
            mapping_candidates=(
                "sku-only-candidate",
            ),
            mapping_approved=False,
            source_classification=(
                "SANITIZED_REAL"
            ),
        )
    )

    assert (
        result.status
        == (
            ReservationIdentification
            .AMBIGUOUS
        )
    )

    assert (
        result.selected_sku_id
        is None
    )

    assert (
        result.mapping_review_required
        is True
    )


def test_multiple_candidates_are_ambiguous() -> None:
    result = identify_reservation(
        ReservationIdentificationInput(
            order_id="order-005",
            reservation_evidence_ids=(
                "ev-005",
            ),
            mapping_candidates=(
                "sku-a",
                "sku-b",
            ),
            mapping_approved=False,
        )
    )

    assert (
        result.status
        == (
            ReservationIdentification
            .AMBIGUOUS
        )
    )

    assert (
        result.mapping_review_required
        is True
    )


def test_valid_evidence_without_candidates_requires_unapproved_mapping_review() -> None:
    result = identify_reservation(
        ReservationIdentificationInput(
            order_id="order-valid-evidence",
            reservation_evidence_ids=(
                "ev-valid-reservation",
            ),
            mapping_approved=False,
        )
    )

    assert (
        result.status
        == ReservationIdentification.UNKNOWN
    )
    assert (
        result.mapping_review_required
        is True
    )
    assert result.selected_sku_id is None


def test_selected_sku_requires_explicit_approval() -> None:
    try:
        identify_reservation(
            ReservationIdentificationInput(
                order_id="order-006",
                selected_sku_id="sku-006",
                mapping_approved=False,
            )
        )
    except ValueError as exc:
        assert (
            "without approved mapping"
            in str(exc)
        )
    else:
        raise AssertionError(
            "ValueError expected"
        )


def test_approved_mapping_requires_selected_sku() -> None:
    try:
        identify_reservation(
            ReservationIdentificationInput(
                order_id="order-approved",
                mapping_approved=True,
            )
        )
    except ValueError as exc:
        assert (
            "approved mapping requires"
            in str(exc)
        )
    else:
        raise AssertionError(
            "ValueError expected"
        )
