"""Explicit Synthetic Demo reservation caller; no live server or provider."""

import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import Settings
from backend.app.main import create_app
from backend.app.services.demo import prepare_synthetic_reservations

PREPARE = "/api/v1/demo/reservations/prepare"
READ = "/api/v1/reservations"


def demo_client(*, tenant_id="demo_store"):
    app = create_app(Settings(
        _env_file=None, environment="DEMO", tenant_id=tenant_id,
        database_url="sqlite://",
    ))
    return TestClient(app)


def test_explicit_preparation_uses_domain_calculation_and_is_idempotent(monkeypatch):
    import backend.app.services.demo as demo

    client = demo_client()
    app = client.app
    calls = []
    original = demo.calculate_reservation_shortage

    def counted(**kwargs):
        calls.append(kwargs)
        return original(**kwargs)

    monkeypatch.setattr(demo, "calculate_reservation_shortage", counted)
    before = client.get(READ)
    assert before.status_code == 200 and before.json()["data"] == []
    assert app.state.reservation_risk_projections == []

    first = client.post(PREPARE)
    assert first.status_code == 200
    assert first.json()["status"] == "READY"
    assert first.json()["data_mode"] == "SYNTHETIC_DEMO"
    assert first.json()["created_count"] == 2
    assert first.json()["row_count"] == 2
    assert len(calls) == 2

    rows = client.get(READ).json()["data"]
    assert len(rows) == 2
    known = next(row for row in rows if row["calculation_status"] == "CONFIRMED")
    unknown = next(row for row in rows if row["shortage"] is None)
    assert known["required_qty"] == 6
    assert known["secured_qty"] == 2
    assert known["confirmed_incoming_qty"] == 1
    assert known["tentative_incoming_qty"] == 3
    assert known["shortage"] == 3
    assert known["delivery_risk"] == "MEDIUM"
    assert unknown["secured_qty"] is None
    assert unknown["confirmed_incoming_qty"] is None
    assert unknown["shortage"] is None
    assert unknown["delivery_risk"] == "UNKNOWN"
    assert unknown["quality_status"] == "UNKNOWN"
    assert len(app.state.schedule_task_projections) == 1

    for row in rows:
        assert row["tenant_id"] == "demo_store"
        assert row["data_mode"] == "SYNTHETIC_DEMO"
        assert row["source_classification"] == "SYNTHETIC_DEMO"
        assert row["affected_order_ids"] == []
        assert row["as_of"].endswith("Z") or row["as_of"].endswith("+00:00")
        assert not {"order_id", "order_line_id", "customer_id"} & row.keys()

    second = client.post(PREPARE)
    assert second.status_code == 200
    assert second.json()["status"] == "ALREADY_READY"
    assert second.json()["created_count"] == 0
    assert second.json()["row_count"] == 2
    assert len(client.get(READ).json()["data"]) == 2
    assert len(calls) == 2
    assert len(app.state.schedule_task_projections) == 1
    assert app.state.schedule_task_projections[0]["replay_count"] == 0


def test_tenant_isolation_and_direct_caller_guard():
    first = demo_client(tenant_id="demo_store")
    second = demo_client(tenant_id="other_demo_tenant")
    assert first.post(PREPARE).status_code == 200
    assert second.get(READ).json()["data"] == []
    result = second.post(PREPARE)
    assert result.status_code == 200
    assert all(row["tenant_id"] == "other_demo_tenant"
               for row in second.get(READ).json()["data"])
    assert all(row["tenant_id"] == "demo_store"
               for row in first.get(READ).json()["data"])
    try:
        prepare_synthetic_reservations(first.app.state, tenant_id="foreign")
    except ValueError:
        pass
    else:
        raise AssertionError("foreign tenant must be rejected")


def test_non_demo_and_client_supplied_input_are_rejected():
    app = create_app(Settings(
        _env_file=None, environment="PRODUCTION_READ", database_url="sqlite://",
    ))
    client = TestClient(app)
    assert client.post(PREPARE).status_code == 403
    assert client.get(READ).json()["data"] == []

    demo = demo_client()
    assert demo.post(PREPARE, json={"required_qty": 100}).status_code == 422
    assert demo.post(PREPARE, params={"tenant_id": "foreign"}).status_code == 422
    assert demo.get(READ).json()["data"] == []


def test_prepare_does_not_use_event_pipeline_db_or_llm(monkeypatch):
    import backend.app.services.grounded_explanation_bridge as bridge

    client = demo_client()

    def forbidden(*_, **__):
        pytest.fail("Demo reservation preparation must stay in memory")

    monkeypatch.setattr(client.app.state.pipeline, "process", forbidden)
    monkeypatch.setattr(bridge, "run_grounded_explanation", forbidden)
    client.app.state.db_session_factory = forbidden
    assert client.post(PREPARE).status_code == 200
    assert len(client.get(READ).json()["data"]) == 2
