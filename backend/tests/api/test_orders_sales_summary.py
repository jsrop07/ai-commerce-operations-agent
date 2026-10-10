"""Synthetic Demo sales summary HTTP and isolation contract."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from hashlib import sha256

from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.api.catalog_v2 import DEMO_CATALOG_TENANT_ID
from backend.app.core.config import Environment
from backend.app.models_v2.ai import DemoSessionV2
from backend.app.models_v2.operations import OrderV2
from backend.app.models_v2.tenant import TenantV2
from backend.app.services.demo_session import COOKIE_NAME, issue_demo_session
from backend.tests.api.test_orders_list import (
    _client_with_session,
)
from backend.tests.api.test_orders_list import (
    orders_runtime as imported_orders_runtime,
)

orders_runtime = imported_orders_runtime


def test_full_period_daily_status_and_null_amounts(orders_runtime):
    app, factory = orders_runtime
    with factory() as db:
        first = db.scalar(select(OrderV2).where(OrderV2.external_order_id == "ORD-001"))
        second = db.scalar(select(OrderV2).where(OrderV2.external_order_id == "ORD-002"))
        first.total_order_amount = Decimal("0.10")
        first.total_paid_amount = Decimal("0.10")
        second.total_order_amount = Decimal("0.20")
        second.total_paid_amount = Decimal("0.20")
        db.commit()
    client = _client_with_session(app)
    response = client.get("/api/v1/orders/sales-summary")
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == "AVAILABLE"
    assert data["order_count"] == 3  # ORD-002 has two OrderItem rows.
    assert data["order_amount"] == {
        "amount": "0.30",
        "order_count": 2,
        "null_order_count": 1,
    }
    assert data["paid_amount"] == data["order_amount"]
    assert data["statuses"] == {
        "paid": {"T": 2, "F": 1},
        "canceled": {"T": 0, "F": 2, "M": 1},
        "shipping_status": {"T": 1, "F": 1, "M": 1},
    }
    assert [(day["order_date"], day["order_count"]) for day in data["daily"]] == [
        ("2026-10-04", 1),
        ("2026-10-05", 2),
    ]
    assert data["daily"][1]["order_amount"] == {
        "amount": "0.20",
        "order_count": 1,
        "null_order_count": 1,
    }
    assert data["currency"] is None
    assert data["currency_status"] == "UNSPECIFIED_IN_SOURCE"
    assert data["daily_gap_policy"] == "OMIT_DAYS_WITHOUT_ORDERS"
    assert data["paid_amount_semantics"] == "SOURCE_TOTAL_PAID_AMOUNT_NOT_SETTLED_REVENUE"
    assert data["undated_order_count"] == 0


def test_kst_period_empty_and_undated_order(orders_runtime):
    app, factory = orders_runtime
    client = _client_with_session(app)
    data = client.get(
        "/api/v1/orders/sales-summary",
        params={
            "from_date": "2026-10-05",
            "to_date": "2026-10-05",
        },
    ).json()["data"]
    assert data["order_count"] == 2
    assert data["order_amount"]["amount"] == "20.00"
    assert data["order_amount"]["null_order_count"] == 1
    assert [day["order_date"] for day in data["daily"]] == ["2026-10-05"]
    empty = client.get(
        "/api/v1/orders/sales-summary",
        params={
            "from_date": "2026-10-06",
            "to_date": "2026-10-07",
        },
    ).json()["data"]
    assert empty["status"] == "NO_DATA"
    assert empty["order_count"] == 0
    assert empty["order_amount"] == {
        "amount": None,
        "order_count": 0,
        "null_order_count": 0,
    }
    assert empty["daily"] == []
    with factory() as db:
        db.add(
            OrderV2(
                tenant_id=DEMO_CATALOG_TENANT_ID,
                external_order_id="UNDATED",
                source_system="SYNTHETIC_DEMO",
                source_order_at=None,
                paid="T",
                canceled="F",
                shipping_status="T",
                total_order_amount=None,
                total_paid_amount=None,
            )
        )
        db.commit()
    full = client.get("/api/v1/orders/sales-summary").json()["data"]
    assert full["order_count"] == 4
    assert full["undated_order_count"] == 1
    assert sum(day["order_count"] for day in full["daily"]) == 3


def test_all_null_amounts_remain_null(orders_runtime):
    app, factory = orders_runtime
    with factory() as db:
        for order in db.scalars(select(OrderV2).where(OrderV2.source_system == "SYNTHETIC_DEMO")):
            order.total_order_amount = None
            order.total_paid_amount = None
        db.commit()
    data = _client_with_session(app).get("/api/v1/orders/sales-summary").json()["data"]
    assert data["order_count"] == 3
    assert data["order_amount"] == {
        "amount": None,
        "order_count": 0,
        "null_order_count": 3,
    }
    assert all(day["order_amount"]["amount"] is None for day in data["daily"])


def test_session_tenant_environment_and_filter_validation(orders_runtime):
    app, factory = orders_runtime
    assert TestClient(app).get("/api/v1/orders/sales-summary").status_code == 401
    client = _client_with_session(app)
    for query in (
        "?from_date=bad",
        "?to_date=9999-12-31",
        "?unknown=1",
        "?from_date=2026-10-06&to_date=2026-10-05",
        "?from_date=2026-10-05&from_date=2026-10-06",
    ):
        assert client.get(f"/api/v1/orders/sales-summary{query}").status_code == 422, query
    other = TestClient(app)
    with factory() as db:
        other_tenant = db.scalar(select(TenantV2.id).where(TenantV2.id != DEMO_CATALOG_TENANT_ID))
        _, token = issue_demo_session(db, tenant_id=other_tenant, ttl_seconds=3600)
    other.cookies.set(COOKIE_NAME, token)
    assert other.get("/api/v1/orders/sales-summary").status_code == 401
    with factory() as db:
        row = db.scalar(
            select(DemoSessionV2).where(
                DemoSessionV2.token_hash
                == sha256(client.cookies.get(COOKIE_NAME).encode()).hexdigest(),
            )
        )
        row.created_at = datetime.now(UTC) - timedelta(seconds=10)
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    assert client.get("/api/v1/orders/sales-summary").status_code == 401
    app.state.settings.environment = Environment.LOCAL
    assert client.get("/api/v1/orders/sales-summary").status_code == 403
