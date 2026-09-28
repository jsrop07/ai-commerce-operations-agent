import json
from copy import deepcopy
from datetime import UTC, datetime
from hashlib import sha256

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.adapters.providers import TossPosMockProvider
from backend.app.core.config import Environment, Settings
from backend.app.db.base import Base
from backend.app.main import create_app
from backend.app.models.commerce import InventoryLedger
from backend.app.services.c04_lookup import C04LookupService
from backend.app.services.demo import DEMO_SCENARIOS
from backend.app.services.offline_sale import OfflineSalePipeline


def _runtime_sale(
    *,
    event_id: str,
    business_key: str,
    occurred_at: str,
    tenant_id: str = "demo_store",
    quantity: int = 1,
    sku_id: str = "sku_demo_001",
) -> dict[str, object]:
    payload = deepcopy(DEMO_SCENARIOS["offline_sale"])
    payload["event_id"] = event_id
    payload["source_event_id"] = event_id
    payload["idempotency_key"] = f"TOSS_POS:{event_id}:1.0"
    payload["tenant_id"] = tenant_id
    payload["occurred_at"] = occurred_at
    payload["ingested_at"] = occurred_at
    payload["payload"] = {
        **payload["payload"],
        "sku_id": sku_id,
        "quantity": quantity,
        "business_identity_key": business_key,
    }
    return payload


def _demo_app():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return create_app(
        Settings(environment=Environment.DEMO),
        db_engine=engine,
    )


def _persistent_pipeline(
    *,
    snapshot_as_of: datetime,
    snapshot_reserved: int | None = 0,
):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    pipeline = OfflineSalePipeline(
        snapshot_as_of=snapshot_as_of,
        snapshot_reserved=snapshot_reserved,
        db_session_factory=lambda: Session(engine),
    )
    return pipeline, engine


def test_day04_offline_sale_e2e_duplicate_effect_once() -> None:
    app = _demo_app()
    client = TestClient(app)
    provider_page = TossPosMockProvider().read_offline_sales()
    assert provider_page.resource == "offline_sales"
    payload = provider_page.items[0]
    first = client.post("/api/v1/demo/events", json=payload)
    second = client.post("/api/v1/demo/events", json=payload)
    assert first.status_code == second.status_code == 202
    assert first.json()["status"] == "ACCEPTED"
    assert second.json()["status"] == "REPLAYED"

    response = client.get(
        "/api/v1/insights",
        headers={"x-request-id": "req_e2e", "x-trace-id": payload["correlation_id"]},
    )
    body = response.json()
    insight = body["data"][0]
    assert insight["calculation"]["expected_inventory"] == 7
    assert insight["correlation_id"] == payload["correlation_id"]
    assert app.state.pipeline.inbox.accepted_count == 1
    assert app.state.pipeline.inbox.replayed_count == 1
    assert app.state.pipeline.effects.business_effect_count == 1
    assert app.state.pipeline.external_write_count == 0
    assert all(payload["correlation_id"] in record for record in app.state.pipeline.trace)

    inventory = client.get("/api/v1/inventory").json()["data"]
    assert len(inventory) == 1
    assert inventory[0]["sku_id"] == "sku_demo_001"
    assert inventory[0]["expected_inventory"] == 7
    assert inventory[0]["available_inventory"] == 7


def test_demo_insight_c04_handoff_uses_registered_safe_projection():
    app = _demo_app()
    client = TestClient(app)
    event = deepcopy(DEMO_SCENARIOS["offline_sale"])
    # Synthetic sentinels prove the payload is not copied into C04.
    forbidden = {
        "order_id": "synthetic-order-sentinel", "customer_id": "synthetic-customer-sentinel",
        "reservation_id": "synthetic-reservation-sentinel",
        "feedback_memo": "synthetic-memo-sentinel",
    }
    event["payload"].update(forbidden)
    assert client.post("/api/v1/demo/events", json=event).status_code == 202
    response = client.get("/api/v1/insights")
    assert response.status_code == 200
    insight = response.json()["data"][0]
    assert insight["evidence_ids"] == response.json()["evidence_ids"] == [event["event_id"]]
    key = insight["c04_lookup"]
    assert set(key) == {"source_id", "version", "chunk_id"}
    assert key["version"] == "v1"
    assert key["chunk_id"] == f"{key['source_id']}:v1:c04:0"
    for sentinel in [event["event_id"], event["payload"]["sku_id"], *forbidden.values()]:
        assert sentinel not in key["source_id"]
    lookup = client.get("/api/v1/c04/lookup", params=key)
    assert lookup.status_code == 200
    data = lookup.json()["data"]
    assert data["source_type"] == "INVENTORY_SNAPSHOT"
    assert data["data_mode"] == "SYNTHETIC_DEMO"
    assert data["visibility"] == "DEMO_PUBLIC"
    assert data["excerpt_hash"] == f"sha256:{sha256(data['excerpt'].encode('utf-8')).hexdigest()}"
    assert json.loads(data["excerpt"]) == {
        "starting_inventory": 8, "sold": 1, "expected_inventory": 7,
        "rule_version": "shadow-inventory-v1",
    }
    # Replay never regenerates as_of, changes lineage, or issues a different key.
    assert client.post("/api/v1/demo/events", json=event).json()["status"] == "REPLAYED"
    assert client.get("/api/v1/insights").json()["data"][0] == insight
    assert client.get("/api/v1/c04/lookup", params=key).json()["data"] == data
    assert app.state.pipeline.external_write_count == 0


@pytest.mark.parametrize("failure", ["unavailable", "exception", "missing"])
def test_c04_registration_failure_preserves_demo_ingestion(failure, monkeypatch):
    app = _demo_app()
    if failure == "unavailable":
        app.state.c04_lookup_service = C04LookupService(None)
    elif failure == "missing":
        del app.state.c04_lookup_service
    else:
        def fail(*args, **kwargs):
            raise RuntimeError("synthetic registration failure")
        monkeypatch.setattr(app.state.c04_lookup_service, "register_demo_record", fail)
    client = TestClient(app)
    event = DEMO_SCENARIOS["offline_sale"]
    response = client.post("/api/v1/demo/events", json=event)
    assert response.status_code == 202
    assert response.json()["status"] == "ACCEPTED"
    insights = client.get("/api/v1/insights")
    assert insights.status_code == 200
    item = insights.json()["data"][0]
    assert item["evidence_ids"] == [event["event_id"]]
    assert "c04_lookup" not in item
    assert app.state.pipeline.external_write_count == 0


@pytest.mark.parametrize("change", ["tenant", "version", "chunk", "registry", "production"])
def test_insights_omits_unresolvable_or_non_demo_keys(change):
    app = _demo_app()
    client = TestClient(app)
    client.post("/api/v1/demo/events", json=DEMO_SCENARIOS["offline_sale"])
    item = app.state.pipeline.insights[0]
    original = dict(item["c04_lookup"])
    if change == "tenant":
        app.state.settings.tenant_id = "another_demo"
        assert client.get("/api/v1/c04/lookup", params=original).status_code == 404
    elif change == "registry":
        app.state.c04_lookup_service = C04LookupService(None)
    elif change == "production":
        app.state.settings.environment = Environment.PRODUCTION_READ
    else:
        field = "version" if change == "version" else "chunk_id"
        item["c04_lookup"][field] = "invalid"
        assert client.get("/api/v1/c04/lookup", params=item["c04_lookup"]).status_code == 404
    response = client.get("/api/v1/insights")
    assert response.status_code == 200
    assert "c04_lookup" not in response.json()["data"][0]
    assert response.json()["data"][0]["evidence_ids"] == item["evidence_ids"]


def test_foreign_tenant_demo_sale_never_registers_c04():
    app = _demo_app()
    client = TestClient(app)
    event = deepcopy(DEMO_SCENARIOS["offline_sale"])
    event["tenant_id"] = "foreign_demo"
    assert client.post("/api/v1/demo/events", json=event).status_code == 202
    assert "c04_lookup" not in client.get("/api/v1/insights").json()["data"][0]


def test_demo_event_api_denied_outside_demo(monkeypatch) -> None:
    app = create_app(Settings(environment=Environment.PRODUCTION_READ))
    registrations = []
    monkeypatch.setattr(app.state.c04_lookup_service, "register_demo_record",
                        lambda *args, **kwargs: registrations.append(True))
    response = TestClient(app).post("/api/v1/demo/events", json=DEMO_SCENARIOS["offline_sale"])
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "POLICY_DENIED"
    assert TestClient(app).get("/api/v1/insights").json()["data"] == []
    assert registrations == []

def test_day04_inquiry_http_keeps_ai_disabled() -> None:
    app = _demo_app()
    client = TestClient(app)

    payload = DEMO_SCENARIOS["product_inquiry"]

    response = client.post(
        "/api/v1/demo/events",
        json=payload,
        headers={
            "x-request-id": "req_day04_inquiry_http",
            "x-trace-id": "trace_day04_inquiry_http",
        },
    )

    assert response.status_code == 202

    body = response.json()

    assert body["status"] == "ACCEPTED"
    assert body["request_id"] == "req_day04_inquiry_http"
    assert body["trace_id"] == "trace_day04_inquiry_http"

    assert (
        body["correlation_id"]
        == payload["correlation_id"]
    )

    assert app.state.pipeline.ai_results == []

    disabled_trace = next(
        json.loads(record)
        for record in app.state.pipeline.trace
        if json.loads(record)["message"] == "INQUIRY_AI_DISABLED"
    )
    assert disabled_trace["request_id"] == "req_day04_inquiry_http"
    assert disabled_trace["trace_id"] == "trace_day04_inquiry_http"
    assert disabled_trace["correlation_id"] == payload["correlation_id"]

def test_day04_prohibited_inquiry_http_does_not_call_ai() -> None:
    app = _demo_app()
    client = TestClient(app)

    payload = DEMO_SCENARIOS["risk_inquiry"]

    response = client.post(
        "/api/v1/demo/events",
        json=payload,
        headers={
            "x-request-id": "req_day04_prohibited_http",
            "x-trace-id": "trace_day04_prohibited_http",
        },
    )

    assert response.status_code == 202

    assert app.state.pipeline.ai_results == []

    counters = app.state.pipeline.ai_consumer.runtime.counters

    assert counters.external_model_calls == 0
    assert counters.tool_calls == 0
    assert counters.provider_calls == 0
    assert counters.auto_send_count == 0

    assert app.state.pipeline.external_write_count == 0


def test_demo_sale_writes_inventory_projection_once() -> None:
    app = _demo_app()
    snapshot_as_of = datetime(2026, 9, 23, 10, 0, tzinfo=UTC)
    app.state.pipeline.snapshot_as_of = snapshot_as_of
    client = TestClient(app)

    payload = deepcopy(DEMO_SCENARIOS["offline_sale"])
    payload["event_id"] = "evt_runtime_sale_001"
    payload["source_event_id"] = "runtime-sale-001"
    payload["idempotency_key"] = "TOSS_POS:runtime-sale-001:1.0"
    payload["occurred_at"] = "2026-09-23T10:10:00Z"
    payload["ingested_at"] = "2026-09-23T10:10:01Z"
    payload["payload"] = {
        **payload["payload"],
        "business_identity_key": "business-runtime-sale-001",
    }

    first = client.post("/api/v1/demo/events", json=payload)
    second = client.post("/api/v1/demo/events", json=payload)
    inventory = client.get("/api/v1/inventory").json()["data"]

    assert first.status_code == second.status_code == 202
    assert first.json()["status"] == "ACCEPTED"
    assert second.json()["status"] == "REPLAYED"
    assert app.state.inventory_projections is app.state.pipeline.inventory_projections
    with Session(app.state.db_engine) as session:
        assert session.query(InventoryLedger).count() == 1
    assert len(inventory) == 1
    assert inventory[0]["expected_inventory"] == 7
    assert inventory[0]["available_inventory"] == 7
    assert inventory[0]["provider"] == "DEMO"
    assert inventory[0]["as_of"] == "2026-09-23T10:00:00Z"


def test_demo_db_replay_with_new_source_event_keeps_one_row() -> None:
    pipeline, engine = _persistent_pipeline(
        snapshot_as_of=datetime(2026, 9, 23, 10, 0, tzinfo=UTC),
    )
    first = _runtime_sale(
        event_id="evt-db-first",
        business_key="business-db-replay",
        occurred_at="2026-09-23T10:10:00Z",
    )
    replay = _runtime_sale(
        event_id="evt-db-replay",
        business_key="business-db-replay",
        occurred_at="2026-09-23T10:10:00Z",
    )

    assert pipeline.process(first).status == "ACCEPTED"
    assert pipeline.process(replay).status == "ACCEPTED"
    assert pipeline.inventory_projections[0].expected_inventory == 7
    with Session(engine) as session:
        assert session.query(InventoryLedger).count() == 1


def test_demo_db_restart_rebuilds_projection_from_snapshot_and_ledger() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    settings = Settings(environment=Environment.DEMO)
    first_app = create_app(settings, db_engine=engine)
    first_app.state.pipeline.snapshot_as_of = datetime(
        2026, 9, 23, 10, 0, tzinfo=UTC
    )
    first_client = TestClient(first_app)
    first = _runtime_sale(
        event_id="evt-db-restart",
        business_key="business-db-restart",
        occurred_at="2026-09-23T10:10:00Z",
    )
    assert first_client.post("/api/v1/demo/events", json=first).status_code == 202

    second_app = create_app(settings, db_engine=engine)
    second_client = TestClient(second_app)
    inventory = second_client.get("/api/v1/inventory").json()["data"]

    assert len(inventory) == 1
    assert inventory[0]["expected_inventory"] == 7
    assert inventory[0]["available_inventory"] == 7
    assert inventory[0]["as_of"] == "2026-09-23T10:00:00Z"


@pytest.mark.parametrize(
    "occurred_at",
    ["2026-09-23T09:59:00Z", "2026-09-23T10:00:00Z"],
)
def test_demo_db_cutoff_excludes_before_and_equal_events(occurred_at: str) -> None:
    pipeline, _ = _persistent_pipeline(
        snapshot_as_of=datetime(2026, 9, 23, 10, 0, tzinfo=UTC),
    )
    pipeline.process(
        _runtime_sale(
            event_id=f"evt-db-cutoff-{occurred_at}",
            business_key=f"business-db-cutoff-{occurred_at}",
            occurred_at=occurred_at,
        )
    )

    projection = pipeline.inventory_projections[0]
    assert projection.ledger_delta == 0
    assert projection.expected_inventory == 8
    assert projection.available_inventory == 8


def test_demo_db_reserved_only_reduces_available_inventory() -> None:
    pipeline, _ = _persistent_pipeline(
        snapshot_as_of=datetime(2026, 9, 23, 10, 0, tzinfo=UTC),
        snapshot_reserved=2,
    )
    pipeline.process(
        _runtime_sale(
            event_id="evt-db-reserved",
            business_key="business-db-reserved",
            occurred_at="2026-09-23T10:10:00Z",
        )
    )

    projection = pipeline.inventory_projections[0]
    assert projection.expected_inventory == 7
    assert projection.available_inventory == 5


def test_demo_db_tenants_remain_isolated() -> None:
    pipeline, engine = _persistent_pipeline(
        snapshot_as_of=datetime(2026, 9, 23, 10, 0, tzinfo=UTC),
    )
    for tenant_id, sku_id in (
        ("store-a", "sku-demo-a"),
        ("store-b", "sku-demo-b"),
    ):
        pipeline.process(
            _runtime_sale(
                event_id=f"evt-db-{tenant_id}",
                business_key=f"business-db-{tenant_id}",
                occurred_at="2026-09-23T10:10:00Z",
                tenant_id=tenant_id,
                sku_id=sku_id,
            )
        )

    assert {
        (projection.tenant_id, projection.expected_inventory)
        for projection in pipeline.inventory_projections
    } == {("store-a", 7), ("store-b", 7)}
    with Session(engine) as session:
        assert session.query(InventoryLedger).count() == 2


def test_demo_db_failure_does_not_create_success_projection() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    pipeline = OfflineSalePipeline(
        db_session_factory=lambda: Session(engine),
    )

    with pytest.raises(OperationalError):
        pipeline.process(
            _runtime_sale(
                event_id="evt-db-failure",
                business_key="business-db-failure",
                occurred_at="2026-09-23T10:10:00Z",
            )
        )
    assert pipeline.inventory_projections == []


@pytest.mark.parametrize(
    "occurred_at",
    ["2026-09-23T09:59:00Z", "2026-09-23T10:00:00Z"],
)
def test_demo_sale_at_or_before_snapshot_is_not_reapplied(
    occurred_at: str,
) -> None:
    pipeline = OfflineSalePipeline(
        snapshot_as_of=datetime(2026, 9, 23, 10, 0, tzinfo=UTC)
    )

    pipeline.process(
        _runtime_sale(
            event_id=f"evt-cutoff-{occurred_at}",
            business_key=f"business-cutoff-{occurred_at}",
            occurred_at=occurred_at,
        )
    )

    assert len(pipeline.inventory_ledger.entries) == 1
    assert pipeline.inventory_projections[0].ledger_delta == 0
    assert pipeline.inventory_projections[0].expected_inventory == 8
    assert pipeline.inventory_projections[0].available_inventory == 8


def test_two_distinct_demo_sales_update_one_sku_projection() -> None:
    pipeline = OfflineSalePipeline(
        snapshot_as_of=datetime(2026, 9, 23, 10, 0, tzinfo=UTC)
    )

    for number, minute in ((1, 10), (2, 20)):
        pipeline.process(
            _runtime_sale(
                event_id=f"evt-distinct-{number}",
                business_key=f"business-distinct-{number}",
                occurred_at=f"2026-09-23T10:{minute:02d}:00Z",
            )
        )

    assert len(pipeline.inventory_ledger.entries) == 2
    assert len(pipeline.inventory_projections) == 1
    assert pipeline.inventory_projections[0].expected_inventory == 6
    assert pipeline.inventory_projections[0].available_inventory == 6


def test_demo_reserved_is_deducted_only_from_available_inventory() -> None:
    pipeline = OfflineSalePipeline(
        snapshot_reserved=2,
        snapshot_as_of=datetime(2026, 9, 23, 10, 0, tzinfo=UTC),
    )

    pipeline.process(
        _runtime_sale(
            event_id="evt-reserved-001",
            business_key="business-reserved-001",
            occurred_at="2026-09-23T10:10:00Z",
        )
    )

    projection = pipeline.inventory_projections[0]
    assert projection.expected_inventory == 7
    assert projection.available_inventory == 5


def test_demo_inventory_projections_are_isolated_by_tenant() -> None:
    pipeline = OfflineSalePipeline(
        snapshot_as_of=datetime(2026, 9, 23, 10, 0, tzinfo=UTC)
    )

    for tenant_id in ("store-a", "store-b"):
        pipeline.process(
            _runtime_sale(
                event_id=f"evt-{tenant_id}",
                business_key=f"business-{tenant_id}",
                occurred_at="2026-09-23T10:10:00Z",
                tenant_id=tenant_id,
            )
        )

    assert len(pipeline.inventory_projections) == 2
    assert {
        (item.tenant_id, item.expected_inventory)
        for item in pipeline.inventory_projections
    } == {("store-a", 7), ("store-b", 7)}
