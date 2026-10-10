"""Read-only HTTP contract for stored Synthetic Demo incoming schedules."""

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
from backend.app.api.schedule import router
from backend.app.core.config import Environment, Settings
from backend.app.db.base_v2 import BaseV2
from backend.app.models_v2.ai import DemoSessionV2
from backend.app.models_v2.catalog import ProductV2, ProductVariantV2
from backend.app.models_v2.operations import IncomingShipmentV2, TaskIncomingDependencyV2, TaskV2
from backend.app.models_v2.tenant import TenantV2
from backend.app.services.demo_session import COOKIE_NAME, issue_demo_session

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

PATH = "/api/v1/schedule/incoming-shipments"


@pytest.fixture
def runtime():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        execution_options={"schema_translate_map": {
            "public": None, "ai": None, "catalog": None, "operations": None,
        }},
    )
    BaseV2.metadata.create_all(engine, tables=[model.__table__ for model in (
        TenantV2, DemoSessionV2, ProductV2, ProductVariantV2,
        IncomingShipmentV2, TaskV2, TaskIncomingDependencyV2,
    )])
    factory = sessionmaker(engine, expire_on_commit=False)
    other_tenant = uuid4()
    product_id, variant_id, other_product_id = uuid4(), uuid4(), uuid4()
    incoming_a, incoming_b = uuid4(), uuid4()
    task_id = uuid4()
    with factory() as db:
        db.add_all([
            TenantV2(id=DEMO_CATALOG_TENANT_ID, name="demo", environment="DEMO", status="ACTIVE"),
            TenantV2(id=other_tenant, name="other", environment="DEMO", status="ACTIVE"),
            ProductV2(
                id=product_id, tenant_id=DEMO_CATALOG_TENANT_ID,
                cafe24_product_no=101, product_name="Synthetic product", product_code="SYN-101",
                sale_price=Decimal("10.00"), display_status="T", selling_status="T",
                sold_out=False, operational=True,
            ),
            ProductV2(
                id=other_product_id, tenant_id=other_tenant,
                cafe24_product_no=202, product_name="Other tenant product",
                product_code="OTHER-202", sale_price=Decimal("10.00"),
                display_status="T", selling_status="T", sold_out=False, operational=True,
            ),
            ProductVariantV2(
                id=variant_id, tenant_id=DEMO_CATALOG_TENANT_ID, product_id=product_id,
                option_name="Synthetic option",
            ),
            IncomingShipmentV2(
                id=incoming_a, tenant_id=DEMO_CATALOG_TENANT_ID, product_id=product_id,
                product_variant_id=variant_id, expected_quantity=3,
                expected_arrival_at=datetime(2026, 10, 9, 15, tzinfo=UTC),
                incoming_status="EXPECTED", confidence_status="TENTATIVE",
                source_system="SYNTHETIC_DEMO", external_reference="SYN-IN-1",
            ),
            IncomingShipmentV2(
                id=incoming_b, tenant_id=DEMO_CATALOG_TENANT_ID, product_id=product_id,
                expected_quantity=2, expected_arrival_at=None,
                incoming_status="EXPECTED", confidence_status="UNKNOWN",
                source_system="SYNTHETIC_DEMO", external_reference=None,
            ),
            IncomingShipmentV2(
                tenant_id=DEMO_CATALOG_TENANT_ID, product_id=product_id,
                expected_quantity=1, expected_arrival_at=datetime(2026, 10, 1, tzinfo=UTC),
                incoming_status="EXPECTED", confidence_status="UNKNOWN",
                source_system="CAFE24", external_reference="EXCLUDE",
            ),
            IncomingShipmentV2(
                tenant_id=other_tenant, product_id=other_product_id,
                expected_quantity=1, expected_arrival_at=datetime(2026, 10, 1, tzinfo=UTC),
                incoming_status="EXPECTED", confidence_status="UNKNOWN",
                source_system="SYNTHETIC_DEMO", external_reference="OTHER-TENANT",
            ),
            TaskV2(
                id=task_id, tenant_id=DEMO_CATALOG_TENANT_ID,
                task_type="RESERVATION_SHORTAGE", task_title="Synthetic shortage",
                task_status="PROPOSED", due_at=datetime(2026, 10, 10, tzinfo=UTC),
                priority=None,
            ),
            TaskIncomingDependencyV2(
                tenant_id=DEMO_CATALOG_TENANT_ID, task_id=task_id,
                incoming_shipment_id=incoming_a, dependency_type="AFFECTS_TASK",
            ),
        ])
        db.commit()
    app = FastAPI()
    app.state.settings = Settings(
        _env_file=None, environment=Environment.DEMO, database_url="sqlite://",
        v2_tenant_id=DEMO_CATALOG_TENANT_ID, demo_session_ttl_seconds=3600,
    )
    app.state.v2_db_session_factory = factory
    app.include_router(router)
    yield app, factory, other_tenant
    engine.dispose()


def client_with_session(app, factory, *, tenant_id=DEMO_CATALOG_TENANT_ID):
    client = TestClient(app)
    with factory() as db:
        _, token = issue_demo_session(db, tenant_id=tenant_id, ttl_seconds=3600)
    client.cookies.set(COOKIE_NAME, token)
    return client


def test_stored_incoming_and_explicit_task_relation(runtime):
    app, factory, _ = runtime
    client = client_with_session(app, factory)
    response = client.get(PATH)
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["total"] == 2
    first, second = body["data"]["items"]
    assert first["external_reference"] == "SYN-IN-1"
    assert first["expected_arrival_at"].startswith("2026-10-09T15:00:00")
    assert first["confidence_status"] == "TENTATIVE"
    assert first["source_as_of"] is None
    assert first["product_variant_id"] is not None
    assert len(first["related_tasks"]) == 1
    assert first["related_tasks"][0]["task_type"] == "RESERVATION_SHORTAGE"
    assert first["related_tasks"][0]["dependency_type"] == "AFFECTS_TASK"
    assert first["related_tasks"][0]["priority"] is None
    assert "flow" not in first["related_tasks"][0]
    assert second["expected_arrival_at"] is None
    assert second["external_reference"] is None
    assert second["product_variant_id"] is None
    assert second["related_tasks"] == []
    assert "EXCLUDE" not in str(body)
    assert "OTHER-TENANT" not in str(body)
    assert client.get(PATH, params={"from_date": "2026-10-09"}).status_code == 422


def test_session_tenant_and_environment_boundaries(runtime):
    app, factory, other_tenant = runtime
    assert TestClient(app).get(PATH).status_code == 401
    foreign = client_with_session(app, factory, tenant_id=other_tenant)
    assert foreign.get(PATH).status_code == 401
    valid = client_with_session(app, factory)
    with factory() as db:
        session = db.query(DemoSessionV2).filter(
            DemoSessionV2.tenant_id == DEMO_CATALOG_TENANT_ID
        ).order_by(DemoSessionV2.created_at.desc()).first()
        session.created_at = datetime.now(UTC) - timedelta(days=2)
        session.expires_at = datetime.now(UTC) - timedelta(days=1)
        db.commit()
    assert valid.get(PATH).status_code == 401
    app.state.settings.environment = Environment.LOCAL
    assert valid.get(PATH).status_code == 403
    app.state.settings.environment = Environment.DEMO
    app.state.settings.v2_tenant_id = other_tenant
    assert valid.get(PATH).status_code == 403


def test_empty_synthetic_result(runtime):
    app, factory, _ = runtime
    client = client_with_session(app, factory)
    with factory() as db:
        db.query(TaskIncomingDependencyV2).delete()
        db.query(TaskV2).delete()
        db.query(IncomingShipmentV2).delete()
        db.commit()
    response = client.get(PATH)
    assert response.status_code == 200
    assert response.json()["data"] == {"items": [], "total": 0}
    assert response.json()["warnings"] == ["SYNTHETIC_INCOMING_EMPTY"]
