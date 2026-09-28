"""D09-BE-05 예약 위험 Read API."""

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.reservation_projection import (
    build_reservation_risk_projection,
)


def test_reservations_empty_contract() -> None:
    with TestClient(app) as client:
        client.app.state.reservation_risk_projections = []

        response = client.get(
            "/api/v1/reservations"
        )

    assert response.status_code == 200

    body = response.json()

    assert body["data"] == []

    assert any(
        "RESERVATION_RISK_EMPTY"
        in warning
        for warning in body["warnings"]
    )


def test_reservations_returns_risk_projection() -> None:
    projection = (
        build_reservation_risk_projection(
            reservation_id="res-safe-001",
            tenant_id="demo_store",
            sku_id="sku-safe-001",
            required_qty=5,
            secured_qty=1,
            confirmed_incoming_qty=2,
            tentative_incoming_qty=1,
            shortage=2,
            affected_order_ids=(
                "order-token-001",
            ),
            aging_hours=48,
            priority=70,
            priority_reason=(
                "AGING_48H_PLUS"
            ),
            calculation_status="CONFIRMED",
            evidence=(
                "ev-safe-001",
            ),
            source_classification=(
                "FIXTURE"
            ),
            quality_status="CONFIRMED",
        )
    )

    with TestClient(app) as client:
        client.app.state.reservation_risk_projections = [
            projection
        ]

        response = client.get(
            "/api/v1/reservations",
            headers={
                "x-request-id": (
                    "req-day09-test"
                ),
                "x-trace-id": (
                    "tr-day09-test"
                ),
            },
        )

    assert response.status_code == 200

    body = response.json()

    assert (
        body["request_id"]
        == "req-day09-test"
    )

    assert (
        body["trace_id"]
        == "tr-day09-test"
    )

    assert len(body["data"]) == 1

    item = body["data"][0]

    assert item["required_qty"] == 5
    assert item["secured_qty"] == 1

    assert (
        item["confirmed_incoming_qty"]
        == 2
    )

    assert (
        item["tentative_incoming_qty"]
        == 1
    )

    assert item["shortage"] == 2

    assert item["aging_hours"] == 48
    assert item["priority"] == 70

    assert (
        item["delivery_risk"]
        == "HIGH"
    )

    assert item["evidence"] == [
        "ev-safe-001"
    ]

    assert (
        item["source_classification"]
        == "FIXTURE"
    )


def test_reservation_api_preserves_nullable_quantities() -> None:
    projection = (
        build_reservation_risk_projection(
            reservation_id="res-null",
            tenant_id="demo_store",
            sku_id="sku-null",
            required_qty=5,
            secured_qty=None,
            confirmed_incoming_qty=None,
            tentative_incoming_qty=0,
            shortage=None,
            affected_order_ids=(),
            aging_hours=0,
            priority=30,
            priority_reason=(
                "NEW_RESERVATION_SHORTAGE"
            ),
            calculation_status=(
                "SECURED_QTY_UNKNOWN"
            ),
            evidence=(
                "ev-null",
            ),
            source_classification=(
                "BLOCKED"
            ),
            quality_status="BLOCKED",
        )
    )

    with TestClient(app) as client:
        client.app.state.reservation_risk_projections = [
            projection
        ]

        response = client.get(
            "/api/v1/reservations"
        )

    item = response.json()["data"][0]

    assert item["secured_qty"] is None

    assert (
        item["confirmed_incoming_qty"]
        is None
    )

    assert item["shortage"] is None

    assert (
        item["delivery_risk"]
        == "UNKNOWN"
    )