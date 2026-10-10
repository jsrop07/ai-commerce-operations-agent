"""Isolated SQLite contract for the read-only Synthetic reservation analysis."""

import asyncio
import sys
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.catalog_v2 import DEMO_CATALOG_TENANT_ID
from backend.app.api.dashboard_queue import router as queue_router
from backend.app.api.reservations import router
from backend.app.core.config import Environment, Settings
from backend.app.db.base_v2 import BaseV2
from backend.app.models_v2.ai import DemoSessionV2
from backend.app.models_v2.catalog import ProductV2, ProductVariantV2
from backend.app.models_v2.operations import (
    IncomingShipmentV2, InventorySnapshotV2, ReservationV2, TaskIncomingDependencyV2, TaskV2,
)
from backend.app.models_v2.tenant import TenantV2
from backend.app.services.c15_synthetic_seed import identity
from backend.app.services.demo_session import COOKIE_NAME, issue_demo_session

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

PATH = "/api/v1/reservations/shortage-analysis"


def test_conditional_calculation_and_guards():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        execution_options={"schema_translate_map": {
            "public": None, "ai": None, "catalog": None, "operations": None,
        }},
    )
    BaseV2.metadata.create_all(engine, tables=[model.__table__ for model in (
        TenantV2, DemoSessionV2, ProductV2, ProductVariantV2,
        ReservationV2, IncomingShipmentV2, InventorySnapshotV2, TaskV2, TaskIncomingDependencyV2,
    )])
    factory = sessionmaker(engine, expire_on_commit=False)
    product_id = identity("product", "9")
    variant_id = identity("variant", "DEMO-SKU-0009-01")
    with factory() as db:
        db.add_all([
            TenantV2(id=DEMO_CATALOG_TENANT_ID, name="demo", environment="DEMO", status="ACTIVE"),
            ProductV2(id=product_id, tenant_id=DEMO_CATALOG_TENANT_ID,
                      cafe24_product_no=9150000009, product_name="Synthetic Hero", product_code="DEMO-P-0009",
                      sale_price=Decimal("10"), display_status="T", selling_status="T",
                      sold_out=False, operational=True),
            ProductVariantV2(id=variant_id, tenant_id=DEMO_CATALOG_TENANT_ID,
                         product_id=product_id, variant_code="DEMO-SKU-0009-01", option_name="Hero option"),
            ReservationV2(id=uuid4(), tenant_id=DEMO_CATALOG_TENANT_ID,
                          product_id=product_id, product_variant_id=variant_id,
                          required_quantity=5, secured_quantity=1, promised_date=date(2026, 10, 10),
                          reservation_status="CONFIRMED", source_quality_status="CONFIRMED"),
            InventorySnapshotV2(id=uuid4(), tenant_id=DEMO_CATALOG_TENANT_ID,
                                product_id=product_id, product_variant_id=variant_id,
                                on_hand_quantity=1, reserved_quantity=0,
                                data_as_of=datetime(2026, 10, 4, tzinfo=UTC),
                                source_system="SYNTHETIC_DEMO", data_quality_status="CONFIRMED"),
        ])
        first_incoming = None
        for day in (8, 9):
            incoming_id = uuid4()
            if first_incoming is None:
                first_incoming = incoming_id
            db.add(IncomingShipmentV2(
                id=incoming_id, tenant_id=DEMO_CATALOG_TENANT_ID,
                product_id=product_id, product_variant_id=variant_id,
                expected_quantity=1, expected_arrival_at=datetime(2026, 10, day, 9, tzinfo=UTC),
                incoming_status="CONFIRMED", confidence_status="CONFIRMED",
                source_system="SYNTHETIC_DEMO", external_reference=f"SYN-{day}",
            ))
        task_id = uuid4()
        db.add(TaskV2(id=task_id, tenant_id=DEMO_CATALOG_TENANT_ID,
                      product_id=product_id, task_type="RESERVATION_SHORTAGE",
                      task_title="Scenario task", task_status="PROPOSED"))
        db.add(TaskIncomingDependencyV2(
            tenant_id=DEMO_CATALOG_TENANT_ID, task_id=task_id,
            incoming_shipment_id=first_incoming, dependency_type="AFFECTS_TASK",
        ))
        db.commit()
        _, token = issue_demo_session(db, tenant_id=DEMO_CATALOG_TENANT_ID, ttl_seconds=3600)
    app = FastAPI()
    app.state.settings = Settings(_env_file=None, environment=Environment.DEMO,
                                  database_url="sqlite://", v2_tenant_id=DEMO_CATALOG_TENANT_ID)
    app.state.v2_db_session_factory = factory
    app.include_router(router)
    app.include_router(queue_router)
    client = TestClient(app)
    assert client.get(PATH).status_code == 401
    assert client.get("/api/v1/dashboard/urgent-queue").status_code == 401
    client.cookies.set(COOKIE_NAME, token)
    assert client.get(PATH + "?unexpected=1").status_code == 422
    response = client.get(PATH)
    assert response.status_code == 200
    data = response.json()["data"]
    assert (data["status"], data["baseline_unsecured_quantity"],
            data["conditional_shortage_quantity"], data["conditional_incoming_quantity"]) == (
                "CONDITIONAL", 4, 2, 2,
            )
    assert data["allocation_verified"] is False and data["receipt_verified"] is False
    assert all(item["treatment"] == "CONDITIONAL_UNRECEIVED" for item in data["incoming"])
    queue = client.get("/api/v1/dashboard/urgent-queue")
    assert queue.status_code == 200
    queue_data = queue.json()["data"]
    assert queue_data["status"] == "READY"
    assert queue_data["calculation_mode"] == "ON_REQUEST"
    assert queue_data["source_counts"] == {"reservations": 1, "inventory_snapshots": 1, "linked_tasks": 1}
    assert {item["kind"] for item in queue_data["items"]} == {
        "CONDITIONAL_RESERVATION", "INVENTORY_STALE", "TASK_REVIEW",
    }
    assert "현재 미확보 4개" in next(item["reason"] for item in queue_data["items"]
                                      if item["kind"] == "CONDITIONAL_RESERVATION")
    assert client.get("/api/v1/dashboard/urgent-queue?unexpected=1").status_code == 422
    with factory() as db:
        incoming = db.query(IncomingShipmentV2).first()
        incoming.incoming_status = "RECEIVED"
        db.commit()
    changed = client.get(PATH).json()["data"]
    assert changed["conditional_shortage_quantity"] == 3
    assert any(item["treatment"] == "EXCLUDED_RECEIVED_MAY_ALREADY_BE_SECURED"
               for item in changed["incoming"])
    with factory() as db:
        reservation = db.query(ReservationV2).first()
        reservation.source_quality_status = "UNKNOWN"
        db.commit()
    uncertain = client.get(PATH).json()["data"]
    assert uncertain["status"] == "HOLD"
    assert uncertain["baseline_unsecured_quantity"] is None
    assert uncertain["conditional_shortage_quantity"] is None
    with factory() as db:
        reservation = db.query(ReservationV2).first()
        reservation.source_quality_status = "CONFIRMED"
        reservation.secured_quantity = reservation.required_quantity
        db.query(TaskIncomingDependencyV2).delete()
        db.query(TaskV2).delete()
        db.query(IncomingShipmentV2).delete()
        db.query(InventorySnapshotV2).delete()
        db.commit()
    clear = client.get("/api/v1/dashboard/urgent-queue").json()["data"]
    assert clear["status"] == "CLEAR" and clear["items"] == []
    with factory() as db:
        db.query(ReservationV2).delete()
        db.commit()
    no_data = client.get("/api/v1/dashboard/urgent-queue").json()["data"]
    assert no_data["status"] == "NO_DATA" and no_data["items"] == []
    app.state.settings = Settings(_env_file=None, environment=Environment.DEMO,
                                  database_url="sqlite://", v2_tenant_id=uuid4())
    assert client.get(PATH).status_code == 403
    assert client.get("/api/v1/dashboard/urgent-queue").status_code == 403
    app.state.settings = Settings(_env_file=None, environment=Environment.LOCAL,
                                  database_url="sqlite://", v2_tenant_id=DEMO_CATALOG_TENANT_ID)
    assert client.get(PATH).status_code == 403
    assert client.get("/api/v1/dashboard/urgent-queue").status_code == 403
    engine.dispose()
