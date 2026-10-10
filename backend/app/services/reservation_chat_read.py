"""Read-only, Product-scoped reservation facts for the operations conversation.

Does not modify reservations, stock, Task or external systems.
"""
from __future__ import annotations

from datetime import UTC, datetime, time
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models_v2.operations import IncomingShipmentV2, ReservationV2
from backend.app.services.reservation_shortage import IncomingEvidence, calculate_reservation_shortage

_KST = ZoneInfo("Asia/Seoul")


def read_product_reservation_facts(
    session: Session, *, tenant_id: UUID, product_id: UUID
) -> dict:
    """Return scoped, conditional facts; never interpret missing data as zero."""
    reservations = session.scalars(
        select(ReservationV2).where(
            ReservationV2.tenant_id == tenant_id,
            ReservationV2.product_id == product_id,
        ).limit(2)
    ).all()
    if not reservations:
        return {"status": "HOLD", "reason": "NO_RESERVATION_DATA"}
    if len(reservations) != 1:
        return {"status": "HOLD", "reason": "MULTIPLE_RESERVATIONS_NOT_AGGREGATED"}

    reservation = reservations[0]
    if reservation.source_quality_status != "CONFIRMED":
        return {"status": "HOLD", "reason": "RESERVATION_QUALITY_UNCONFIRMED"}
    if reservation.required_quantity is None or reservation.secured_quantity is None:
        return {"status": "HOLD", "reason": "RESERVATION_QUANTITY_MISSING"}

    baseline = calculate_reservation_shortage(
        required_qty=reservation.required_quantity,
        secured_qty=reservation.secured_quantity,
    ).shortage

    promised_end = (
        datetime.combine(reservation.promised_date, time.max, tzinfo=_KST)
        if reservation.promised_date is not None else None
    )
    arrivals = session.scalars(
        select(IncomingShipmentV2).where(
            IncomingShipmentV2.tenant_id == tenant_id,
            IncomingShipmentV2.product_id == product_id,
            IncomingShipmentV2.product_variant_id == reservation.product_variant_id,
            IncomingShipmentV2.source_system == "SYNTHETIC_DEMO",
        ).order_by(IncomingShipmentV2.expected_arrival_at, IncomingShipmentV2.id)
    ).all()

    candidates: list[IncomingEvidence] = []
    incoming_refs: list[str] = []
    for item in arrivals:
        arrival = item.expected_arrival_at
        if arrival is not None and arrival.tzinfo is None:
            arrival = arrival.replace(tzinfo=UTC)
        if (
            promised_end is not None
            and arrival is not None
            and arrival.astimezone(_KST) <= promised_end
            and item.incoming_status in {"EXPECTED", "CONFIRMED"}
            and item.confidence_status == "CONFIRMED"
        ):
            candidates.append(IncomingEvidence(
                evidence_id=str(item.id),
                quantity=item.expected_quantity,
                confirmation_status="CONFIRMED",
                quality_status="CONFIRMED",
                freshness="FRESH",  # hypothetical input, not a freshness assertion
                source_classification="SYNTHETIC_DEMO",
            ))
            incoming_refs.append(item.external_reference or str(item.id))

    conditional = None
    if candidates:
        conditional = calculate_reservation_shortage(
            required_qty=reservation.required_quantity,
            secured_qty=reservation.secured_quantity,
            incoming=tuple(candidates),
        ).shortage

    return {
        "status": "CONDITIONAL" if conditional is not None else "BASELINE_ONLY",
        "reservation_id": str(reservation.id),
        "required_quantity": reservation.required_quantity,
        "secured_quantity": reservation.secured_quantity,
        "baseline_unsecured_quantity": baseline,
        "conditional_shortage_quantity": conditional,
        "conditional_incoming_quantity": sum(item.quantity for item in candidates),
        "incoming_references": incoming_refs,
        "promised_date": reservation.promised_date.isoformat() if reservation.promised_date else None,
        "allocation_verified": False,
        "receipt_verified": False,
    }
