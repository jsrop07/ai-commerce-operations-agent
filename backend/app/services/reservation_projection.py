"""D09-BE-05 예약 위험 Read Projection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class ReservationRiskProjection:
    reservation_id: str
    tenant_id: str
    sku_id: str

    required_qty: int
    secured_qty: int | None

    confirmed_incoming_qty: int | None
    tentative_incoming_qty: int

    shortage: int | None

    affected_order_ids: tuple[str, ...]

    aging_hours: int
    priority: int
    priority_reason: str

    delivery_risk: str

    calculation_status: str

    evidence: tuple[str, ...]

    source_classification: str
    quality_status: str

    as_of: datetime


def build_reservation_risk_projection(
    *,
    reservation_id: str,
    tenant_id: str,
    sku_id: str,
    required_qty: int,
    secured_qty: int | None,
    confirmed_incoming_qty: int | None,
    tentative_incoming_qty: int,
    shortage: int | None,
    affected_order_ids: tuple[str, ...],
    aging_hours: int,
    priority: int,
    priority_reason: str,
    calculation_status: str,
    evidence: tuple[str, ...],
    source_classification: str,
    quality_status: str,
    as_of: datetime | None = None,
) -> ReservationRiskProjection:
    if not reservation_id:
        raise ValueError(
            "reservation_id is required"
        )

    if not tenant_id:
        raise ValueError(
            "tenant_id is required"
        )

    if not sku_id:
        raise ValueError(
            "sku_id is required"
        )

    if required_qty <= 0:
        raise ValueError(
            "required_qty must be > 0"
        )

    if aging_hours < 0:
        raise ValueError(
            "aging_hours must be >= 0"
        )

    # 실제 계산이 불가능한 경우 위험도를
    # 임의 LOW로 만들지 않는다.
    if shortage is None:
        delivery_risk = "UNKNOWN"

    elif shortage > 0 and aging_hours >= 48:
        delivery_risk = "HIGH"

    elif shortage > 0:
        delivery_risk = "MEDIUM"

    else:
        delivery_risk = "LOW"

    return ReservationRiskProjection(
        reservation_id=reservation_id,
        tenant_id=tenant_id,
        sku_id=sku_id,
        required_qty=required_qty,
        secured_qty=secured_qty,
        confirmed_incoming_qty=(
            confirmed_incoming_qty
        ),
        tentative_incoming_qty=(
            tentative_incoming_qty
        ),
        shortage=shortage,
        affected_order_ids=(
            affected_order_ids
        ),
        aging_hours=aging_hours,
        priority=priority,
        priority_reason=priority_reason,
        delivery_risk=delivery_risk,
        calculation_status=(
            calculation_status
        ),
        evidence=evidence,
        source_classification=(
            source_classification
        ),
        quality_status=quality_status,
        as_of=as_of or datetime.now(UTC),
    )