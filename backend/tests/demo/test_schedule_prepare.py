"""Explicit C08 Synthetic Demo schedule preparation through the existing API."""

import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import Settings
from backend.app.main import create_app
from backend.app.services.demo import prepare_synthetic_schedule_c08

PREPARE = "/api/v1/demo/schedule/prepare"
LIST = "/api/v1/schedule/delay-impacts"
DETAIL = f"{LIST}/incoming-demo-001"
DRAFT = "/api/v1/demo/schedule/replan-proposals/draft"


def demo_client(*, tenant_id: str = "demo_store") -> TestClient:
    return TestClient(create_app(Settings(
        _env_file=None, environment="DEMO", tenant_id=tenant_id,
        database_url="sqlite://",
    )))


def test_prepare_exposes_fixed_calculated_snapshot_and_is_idempotent(monkeypatch) -> None:
    import backend.app.services.demo as demo

    client = demo_client()
    original = demo.calculate_delay_impact
    calls = []

    def counted(**kwargs):
        calls.append(kwargs)
        return original(**kwargs)

    monkeypatch.setattr(demo, "calculate_delay_impact", counted)
    assert client.get(LIST).json()["data"] == []
    assert client.app.state.schedule_replan_proposals == []

    first = client.post(PREPARE, headers={"x-request-id": "req-c08"})
    assert first.status_code == 200
    ready = first.json()
    assert ready["status"] == "READY"
    assert ready["data_mode"] == "SYNTHETIC_DEMO"
    assert ready["created_count"] == ready["row_count"] == 1
    assert ready["tenant_id"] == "demo_store"
    assert ready["request_id"] == "req-c08"
    assert ready["snapshot_id"] == "c08-r08-synthetic-v1"
    assert len(ready["snapshot_sha256"]) == 64
    assert len(calls) == 1

    listed = client.get(LIST)
    detailed = client.get(DETAIL)
    assert listed.status_code == detailed.status_code == 200
    assert len(listed.json()["data"]) == 1
    data = detailed.json()["data"]
    assert listed.json()["data"][0] == data
    assert data["data_mode"] == "SYNTHETIC_DEMO"
    assert data["source_classification"] == "FIXTURE"
    assert data["actual_delay_confirmed"] is False
    assert data["delay_hours"] == 72
    assert data["snapshot_id"] == ready["snapshot_id"]
    assert data["snapshot_sha256"] == ready["snapshot_sha256"]
    assert data["impacted_task_ids"] == ["task-inspection", "task-product-page"]
    assert data["impacted_reservation_ids"] == ["reservation-001"]
    assert data["impacted_launch_event_ids"] == ["launch-001"]
    assert {item["target_id"] for item in data["impact_path"]} == {
        "task-inspection", "task-product-page", "reservation-001", "launch-001"
    }
    assert client.app.state.schedule_replan_proposals == []

    second = client.post(PREPARE)
    assert second.status_code == 200
    assert second.json()["status"] == "ALREADY_READY"
    assert second.json()["created_count"] == 0
    assert second.json()["row_count"] == 1
    assert second.json()["snapshot_sha256"] == ready["snapshot_sha256"]
    assert len(client.app.state.schedule_delay_impact_projections) == 1

    other = demo_client()
    assert other.post(PREPARE).json()["snapshot_sha256"] == ready["snapshot_sha256"]
    assert len(calls) == 3


def test_prepare_then_existing_draft_keeps_other_incoming_out_and_original_unchanged() -> None:
    client = demo_client()
    assert client.post(PREPARE).status_code == 200
    impact = client.get(DETAIL).json()["data"]
    current_schedule = [
        {"item_type": "TASK", "item_id": "task-inspection",
         "scheduled_at": "2026-10-10T18:00:00+09:00"},
        {"item_type": "TASK", "item_id": "task-product-page",
         "scheduled_at": "2026-10-11T18:00:00+09:00"},
        {"item_type": "TASK", "item_id": "task-unrelated",
         "scheduled_at": "2026-10-12T18:00:00+09:00"},
        {"item_type": "TASK", "item_id": "task-other-incoming",
         "scheduled_at": "2026-10-10T10:00:00+09:00"},
        {"item_type": "LAUNCH_EVENT", "item_id": "launch-001",
         "scheduled_at": "2026-10-15T10:00:00+09:00"},
        {"item_type": "LAUNCH_EVENT", "item_id": "launch-other-incoming",
         "scheduled_at": "2026-10-10T10:00:00+09:00"},
    ]
    before = [dict(item) for item in current_schedule]
    draft = client.post(DRAFT, json={
        "current_schedule": current_schedule,
        "impact": impact,
        "created_at": "2026-10-02T09:00:00+09:00",
        "confidence": 0.8,
    })
    assert draft.status_code == 200
    proposal = draft.json()["data"]
    assert proposal["source_incoming_id"] == "incoming-demo-001"
    assert proposal["external_execution_allowed"] is False
    assert {item["item_id"] for item in proposal["diff"]} == {
        "task-inspection", "task-product-page", "launch-001"
    }
    assert set(proposal["downstream_impact"]) == {
        "task-inspection", "task-product-page", "reservation-001", "launch-001"
    }
    assert current_schedule == before
    assert len(client.get("/api/v1/schedule/replan-proposals").json()["data"]) == 1


@pytest.mark.parametrize("environment", ["PRODUCTION_READ", "LOCAL"])
def test_prepare_denies_non_demo(environment: str) -> None:
    production = TestClient(create_app(Settings(
        _env_file=None, environment=environment, database_url="sqlite://",
    )))
    denied = production.post(PREPARE)
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "POLICY_DENIED"
    assert production.get(LIST).json()["data"] == []


def test_prepare_denies_client_input_and_foreign_tenant() -> None:
    demo = demo_client()
    assert demo.post(PREPARE, json={"incoming_id": "incoming-demo-002"}).status_code == 422
    assert demo.post(PREPARE, params={"incoming_id": "incoming-demo-002"}).status_code == 422
    assert demo.get(LIST).json()["data"] == []
    with pytest.raises(ValueError, match="DEMO_ONLY"):
        prepare_synthetic_schedule_c08(demo.app.state, tenant_id="other-tenant")


def test_prepare_conflict_preserves_existing_projection_and_avoids_providers(monkeypatch) -> None:
    client = demo_client()

    def forbidden(*_, **__):
        pytest.fail("C08 preparation must stay in memory")

    monkeypatch.setattr(client.app.state.pipeline, "process", forbidden)
    client.app.state.db_session_factory = forbidden
    existing = {"incoming_id": "incoming-demo-001", "data_mode": "ACTUAL"}
    client.app.state.schedule_delay_impact_projections.append(existing)
    conflict = client.post(PREPARE)
    assert conflict.status_code == 409
    assert client.app.state.schedule_delay_impact_projections == [existing]
    assert client.app.state.schedule_replan_proposals == []

    clean = demo_client()
    monkeypatch.setattr(clean.app.state.pipeline, "process", forbidden)
    clean.app.state.db_session_factory = forbidden
    assert clean.post(PREPARE).status_code == 200

    synthetic_conflict = dict(clean.app.state.schedule_delay_impact_projections[0])
    synthetic_conflict["snapshot_sha256"] = "different-contract"
    clean.app.state.schedule_delay_impact_projections[:] = [synthetic_conflict]
    assert clean.post(PREPARE).status_code == 409
    assert clean.app.state.schedule_delay_impact_projections == [synthetic_conflict]
