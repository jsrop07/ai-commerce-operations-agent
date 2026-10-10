"""HTTP contract for the read-only Synthetic Demo order list."""

import asyncio
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.catalog_v2 import DEMO_CATALOG_TENANT_ID
from backend.app.api.orders_summary import router as orders_router
from backend.app.core.config import Environment, Settings
from backend.app.db.base_v2 import BaseV2
from backend.app.models_v2.ai import DemoSessionV2
from backend.app.models_v2.catalog import ProductV2, ProductVariantV2
from backend.app.models_v2.operations import OrderItemV2, OrderV2
from backend.app.models_v2.tenant import TenantV2
from backend.app.services.demo_session import COOKIE_NAME, issue_demo_session

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest.fixture
def orders_runtime():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        execution_options={
            "schema_translate_map": {
                "public": None,
                "ai": None,
                "catalog": None,
                "operations": None,
            }
        },
    )
    BaseV2.metadata.create_all(
        engine,
        tables=[
            model.__table__
            for model in (
                TenantV2,
                DemoSessionV2,
                ProductV2,
                ProductVariantV2,
                OrderV2,
                OrderItemV2,
            )
        ],
    )
    factory = sessionmaker(engine, expire_on_commit=False)
    other_tenant = uuid4()
    product_id, variant_id = uuid4(), uuid4()
    with factory() as db:
        db.add_all(
            [
                TenantV2(
                    id=DEMO_CATALOG_TENANT_ID,
                    name="demo_store",
                    environment="DEMO",
                    status="ACTIVE",
                ),
                TenantV2(id=other_tenant, name="other", environment="DEMO", status="ACTIVE"),
                ProductV2(
                    id=product_id,
                    tenant_id=DEMO_CATALOG_TENANT_ID,
                    cafe24_product_no=101,
                    product_name="테스트 상품",
                    product_code="TEST",
                    custom_product_code=None,
                    sale_price=Decimal("10.00"),
                    display_status="T",
                    selling_status="T",
                    sold_out=False,
                    operational=True,
                    source_as_of=None,
                ),
                ProductVariantV2(
                    id=variant_id,
                    tenant_id=DEMO_CATALOG_TENANT_ID,
                    product_id=product_id,
                    option_name="빨강",
                ),
            ]
        )
        order_specs = [
            (
                "ORD-001",
                datetime(2026, 10, 4, 14, 59, 59, tzinfo=UTC),
                "T",
                "F",
                "T",
                "SYNTHETIC_DEMO",
            ),
            ("ORD-002", datetime(2026, 10, 4, 15, 0, tzinfo=UTC), "T", "M", "M", "SYNTHETIC_DEMO"),
            ("ORD-003", datetime(2026, 10, 4, 15, 0, tzinfo=UTC), "F", "F", "F", "SYNTHETIC_DEMO"),
            ("REAL-001", datetime(2026, 10, 4, 15, 0, tzinfo=UTC), "T", "F", "T", "CAFE24"),
        ]
        for number, at, paid, canceled, shipping, source in order_specs:
            order_id = uuid4()
            db.add(
                OrderV2(
                    id=order_id,
                    tenant_id=DEMO_CATALOG_TENANT_ID,
                    external_order_id=number,
                    source_system=source,
                    source_order_at=at,
                    paid=paid,
                    canceled=canceled,
                    shipping_status=shipping,
                    total_order_amount=None if number == "ORD-003" else Decimal("20.00"),
                    total_paid_amount=None if number == "ORD-003" else Decimal("20.00"),
                )
            )
            if source == "SYNTHETIC_DEMO":
                for index in range(2 if number == "ORD-002" else 1):
                    db.add(
                        OrderItemV2(
                            tenant_id=DEMO_CATALOG_TENANT_ID,
                            order_id=order_id,
                            external_order_item_id=f"{number}-{index}",
                            external_product_no=101,
                            product_id=product_id,
                            product_variant_id=variant_id,
                            source_product_name="테스트 상품",
                            quantity=1,
                            source_sale_price=Decimal("10.00"),
                        )
                    )
        db.add(
            OrderV2(
                tenant_id=other_tenant,
                external_order_id="OTHER-001",
                source_system="SYNTHETIC_DEMO",
                source_order_at=datetime.now(UTC),
                paid="T",
                canceled="F",
                shipping_status="T",
            )
        )
        db.commit()
    settings = Settings(
        _env_file=None,
        environment=Environment.DEMO,
        database_url="sqlite://",
        v2_tenant_id=DEMO_CATALOG_TENANT_ID,
        demo_session_ttl_seconds=3600,
        demo_session_cookie_secure=False,
    )
    app = FastAPI()
    app.state.settings = settings
    app.state.v2_db_session_factory = factory
    app.include_router(orders_router)
    app.state.test_factory = factory
    yield app, factory
    engine.dispose()


def _client_with_session(app):
    client = TestClient(app)
    with app.state.test_factory() as db:
        _, token = issue_demo_session(
            db,
            tenant_id=DEMO_CATALOG_TENANT_ID,
            ttl_seconds=3600,
        )
    client.cookies.set(COOKIE_NAME, token)
    return client


def test_list_contract_filters_and_stable_paging(orders_runtime):
    app, _ = orders_runtime
    client = _client_with_session(app)
    first = client.get(
        "/api/v1/orders",
        params={
            "from_date": "2026-10-05",
            "to_date": "2026-10-05",
            "sort_by": "order_date",
            "sort_order": "asc",
            "limit": 1,
        },
    )
    assert first.status_code == 200, first.text
    data = first.json()["data"]
    assert (data["total"], data["limit"], data["offset"]) == (2, 1, 0)
    assert len(data["items"]) == 1
    second = client.get(
        "/api/v1/orders",
        params={
            "from_date": "2026-10-05",
            "to_date": "2026-10-05",
            "sort_by": "order_date",
            "sort_order": "asc",
            "limit": 1,
            "offset": 1,
        },
    )
    assert second.status_code == 200
    numbers = {data["items"][0]["order_number"], second.json()["data"]["items"][0]["order_number"]}
    assert numbers == {"ORD-002", "ORD-003"}
    assert (
        client.get("/api/v1/orders", params={"to_date": "2026-10-04"}).json()["data"]["total"] == 1
    )
    filtered = client.get(
        "/api/v1/orders",
        params={
            "order_number": "002",
            "product_name": "테스트",
            "paid": "T",
            "canceled": "M",
            "shipping_status": "M",
        },
    )
    assert filtered.status_code == 200, filtered.text
    assert filtered.json()["data"]["total"] == 1
    item = filtered.json()["data"]["items"][0]
    assert len(item["items"]) == 2
    assert item["items"][0]["option_name"] == "빨강"
    assert set(item) == {
        "order_number",
        "order_date",
        "total_order_amount",
        "total_paid_amount",
        "paid",
        "canceled",
        "shipping_status",
        "source_system",
        "items",
    }
    null_item = client.get("/api/v1/orders", params={"paid": "F"}).json()["data"]["items"][0]
    assert null_item["total_order_amount"] is None
    assert null_item["total_paid_amount"] is None


def test_session_tenant_environment_and_validation(orders_runtime):
    app, factory = orders_runtime
    anonymous = TestClient(app)
    assert anonymous.get("/api/v1/orders").status_code == 401
    a = _client_with_session(app)
    b = _client_with_session(app)
    assert a.get("/api/v1/orders").json()["data"]["total"] == 3
    assert b.get("/api/v1/orders").json()["data"]["total"] == 3
    other = TestClient(app)
    with factory() as db:
        other_tenant = db.query(TenantV2.id).filter(TenantV2.id != DEMO_CATALOG_TENANT_ID).scalar()
        _, other_token = issue_demo_session(db, tenant_id=other_tenant, ttl_seconds=3600)
    other.cookies.set(COOKIE_NAME, other_token)
    assert other.get("/api/v1/orders").status_code == 401
    assert (
        a.get("/api/v1/orders", params={"sort_by": "order_number"}).json()["data"]["items"][0][
            "order_number"
        ]
        == "ORD-003"
    )
    assert a.get("/api/v1/orders", params={"order_number": "%"}).json()["data"]["total"] == 0
    for query in (
        "?paid=X",
        "?canceled=X",
        "?shipping_status=X",
        "?limit=101",
        "?offset=-1",
        "?sort_by=amount",
        "?from_date=bad",
        "?unknown=1",
        "?paid=T&paid=F",
        "?from_date=2026-10-06&to_date=2026-10-05",
    ):
        assert a.get(f"/api/v1/orders{query}").status_code == 422, query
    with factory() as db:
        from hashlib import sha256

        from sqlalchemy import select

        row = db.scalar(
            select(DemoSessionV2).where(
                DemoSessionV2.token_hash == sha256(a.cookies.get(COOKIE_NAME).encode()).hexdigest(),
            )
        )
        row.created_at = datetime.now(UTC) - timedelta(seconds=10)
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    assert a.get("/api/v1/orders").status_code == 401
    app.state.settings.v2_tenant_id = uuid4()
    assert b.get("/api/v1/orders").status_code == 403
    app.state.settings.environment = Environment.LOCAL
    assert b.get("/api/v1/orders").status_code == 403
