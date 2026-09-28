"""D09-BE-05 예약 위험 Projection 테스트."""

from backend.app.services.reservation_projection import (
    build_reservation_risk_projection,
)


def test_shortage_is_medium_delivery_risk() -> None:
    result = (
        build_reservation_risk_projection(
            reservation_id="res-001",
            tenant_id="demo_store",
            sku_id="sku-001",
            required_qty=5,
            secured_qty=1,
            confirmed_incoming_qty=2,
            tentative_incoming_qty=0,
            shortage=2,
            affected_order_ids=(
                "order-001",
            ),
            aging_hours=12,
            priority=30,
            priority_reason=(
                "NEW_RESERVATION_SHORTAGE"
            ),
            calculation_status="CONFIRMED",
            evidence=(
                "ev-001",
            ),
            source_classification=(
                "FIXTURE"
            ),
            quality_status="CONFIRMED",
        )
    )

    assert result.shortage == 2
    assert (
        result.delivery_risk
        == "MEDIUM"
    )


def test_aged_shortage_is_high_risk() -> None:
    result = (
        build_reservation_risk_projection(
            reservation_id="res-002",
            tenant_id="demo_store",
            sku_id="sku-002",
            required_qty=5,
            secured_qty=1,
            confirmed_incoming_qty=2,
            tentative_incoming_qty=1,
            shortage=2,
            affected_order_ids=(
                "order-002",
            ),
            aging_hours=48,
            priority=70,
            priority_reason=(
                "AGING_48H_PLUS"
            ),
            calculation_status="CONFIRMED",
            evidence=(
                "ev-002",
            ),
            source_classification=(
                "SANITIZED_REAL"
            ),
            quality_status="CONFIRMED",
        )
    )

    assert result.delivery_risk == "HIGH"


def test_unknown_shortage_does_not_become_low() -> None:
    result = (
        build_reservation_risk_projection(
            reservation_id="res-003",
            tenant_id="demo_store",
            sku_id="sku-003",
            required_qty=5,
            secured_qty=None,
            confirmed_incoming_qty=None,
            tentative_incoming_qty=2,
            shortage=None,
            affected_order_ids=(
                "order-003",
            ),
            aging_hours=10,
            priority=30,
            priority_reason=(
                "NEW_RESERVATION_SHORTAGE"
            ),
            calculation_status=(
                "SECURED_QTY_UNKNOWN"
            ),
            evidence=(
                "ev-003",
            ),
            source_classification=(
                "BLOCKED"
            ),
            quality_status="BLOCKED",
        )
    )

    assert (
        result.delivery_risk
        == "UNKNOWN"
    )