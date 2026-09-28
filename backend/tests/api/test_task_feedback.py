from pathlib import Path

from fastapi.testclient import TestClient
import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

import backend.app.models  # noqa: F401
from backend.app.core.config import (
    Environment,
    Settings,
    WriteMode,
)
from backend.app.db.base import Base
from backend.app.main import create_app
from backend.app.services.reservation_projection import build_reservation_risk_projection
from backend.app.services.reservation_tasks import register_reservation_risk_projection
from datetime import UTC, datetime


def _app(
    tmp_path: Path,
    *,
    environment: Environment = (
        Environment.DEMO
    ),
):
    database_path = (
        tmp_path
        / "feedback-test.db"
    )

    settings = Settings(
        environment=environment,
        tenant_id="demo_store",
        write_mode=(
            WriteMode.DEMO_ONLY
            if environment
            != Environment.PRODUCTION_READ
            else WriteMode.DISABLED
        ),
        global_write_kill=True,
        database_url=(
            "sqlite+pysqlite:///"
            f"{database_path}"
        ),
    )

    app = create_app(settings)

    Base.metadata.create_all(
        app.state.db_engine
    )

    app.state.schedule_task_projections = [
        {
            "id": "task-001",
            "task_type": "INCOMING",
            "title": "입고 일정 확인",
            "deadline": None,
            "priority": 60,
            "status": "PROPOSED",
            "source_reason": "FIXTURE",
            "source_classification": (
                "FIXTURE"
            ),
            "evidence_ids": [],
        }
    ]

    return app


def test_feedback_post_and_readback(
    tmp_path: Path,
) -> None:
    app = _app(tmp_path)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/tasks/task-001/feedback",
            json={
                "decision": "EDIT",
                "target_field": "deadline",
                "after_value": (
                    "2026-09-20T12:00:00Z"
                ),
                "reason": "입고일 확인",
                "idempotency_key": (
                    "feedback-001"
                ),
                "expected_version": 0,
            },
        )

        assert response.status_code == 200

        row = response.json()["data"]

        assert row["actor"] == (
            "DEMO_OPERATOR"
        )

        assert (
            row["before_value"]
            is None
        )

        assert (
            row["feedback_version"]
            == 1
        )

        readback = client.get(
            "/api/v1/tasks/task-001/feedback"
        )

    assert readback.status_code == 200

    rows = readback.json()["data"]

    assert len(rows) == 1
    assert rows[0]["id"] == row["id"]


def test_feedback_replay_is_idempotent(
    tmp_path: Path,
) -> None:
    app = _app(tmp_path)

    payload = {
        "decision": "REJECT",
        "target_field": None,
        "after_value": None,
        "reason": "불필요한 Task",
        "idempotency_key": "feedback-001",
        "expected_version": 0,
    }

    with TestClient(app) as client:
        first = client.post(
            "/api/v1/tasks/task-001/feedback",
            json=payload,
        )

        second = client.post(
            "/api/v1/tasks/task-001/feedback",
            json=payload,
        )

        rows = client.get(
            "/api/v1/tasks/task-001/feedback"
        )

    assert first.status_code == 200
    assert second.status_code == 200

    assert (
        first.json()["data"]["id"]
        == second.json()["data"]["id"]
    )

    assert len(
        rows.json()["data"]
    ) == 1


def test_stale_version_returns_409(
    tmp_path: Path,
) -> None:
    app = _app(tmp_path)

    with TestClient(app) as client:
        first = client.post(
            "/api/v1/tasks/task-001/feedback",
            json={
                "decision": "EDIT",
                "target_field": "title",
                "after_value": "수정 제목",
                "reason": "첫 수정",
                "idempotency_key": "f-001",
                "expected_version": 0,
            },
        )

        assert first.status_code == 200

        stale = client.post(
            "/api/v1/tasks/task-001/feedback",
            json={
                "decision": "EDIT",
                "target_field": "title",
                "after_value": "또 수정",
                "reason": "stale",
                "idempotency_key": "f-002",
                "expected_version": 0,
            },
        )

    assert stale.status_code == 409

    assert (
        stale.json()["detail"]["code"]
        == "FEEDBACK_VERSION_CONFLICT"
    )


def test_unknown_task_returns_404(
    tmp_path: Path,
) -> None:
    app = _app(tmp_path)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/tasks/not-found/feedback",
            json={
                "decision": "REJECT",
                "target_field": None,
                "after_value": None,
                "reason": "not found",
                "idempotency_key": "f-001",
                "expected_version": 0,
            },
        )

    assert response.status_code == 404


def test_production_feedback_is_denied(
    tmp_path: Path,
) -> None:
    app = _app(
        tmp_path,
        environment=(
            Environment.PRODUCTION_READ
        ),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/tasks/task-001/feedback",
            json={
                "decision": "REJECT",
                "target_field": None,
                "after_value": None,
                "reason": "deny",
                "idempotency_key": "f-001",
                "expected_version": 0,
            },
        )

    assert response.status_code == 403
    assert (
        response.json()["detail"]["code"]
        == "POLICY_DENIED"
    )


def test_feedback_cors_preflight(
    tmp_path: Path,
) -> None:
    app = _app(tmp_path)

    with TestClient(app) as client:
        response = client.options(
            "/api/v1/tasks/task-001/feedback",
            headers={
                "Origin": (
                    "http://localhost:5173"
                ),
                "Access-Control-Request-Method": (
                    "POST"
                ),
                "Access-Control-Request-Headers": (
                    "content-type"
                ),
            },
        )

    assert response.status_code == 200

    assert (
        response.headers[
            "access-control-allow-origin"
        ]
        == "http://localhost:5173"
    )

    assert "POST" in response.headers[
        "access-control-allow-methods"
    ]


def test_generated_shortage_task_accepts_existing_feedback(tmp_path: Path) -> None:
    app = _app(tmp_path)
    risk = build_reservation_risk_projection(
        reservation_id="reservation-fixture-feedback",
        tenant_id=app.state.settings.tenant_id,
        sku_id="sku-fixture-001",
        required_qty=5,
        secured_qty=1,
        confirmed_incoming_qty=2,
        tentative_incoming_qty=0,
        shortage=2,
        affected_order_ids=(),
        aging_hours=0,
        priority=30,
        priority_reason="FIXTURE_PRIORITY",
        calculation_status="CONFIRMED",
        evidence=("reservation-evidence-001",),
        source_classification="FIXTURE",
        quality_status="CONFIRMED",
        as_of=datetime(2026, 9, 13, tzinfo=UTC),
    )
    task = register_reservation_risk_projection(app.state, risk)
    assert task is not None

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/tasks/{task['task_id']}/feedback",
            json={
                "decision": "EDIT",
                "target_field": "title",
                "after_value": "예약 부족 검토",
                "reason": "운영자 검토",
                "idempotency_key": "fixture-shortage-feedback-001",
                "expected_version": 0,
            },
        )
        history = client.get(f"/api/v1/tasks/{task['task_id']}/feedback")

    assert response.status_code == 200
    assert response.json()["data"]["decision"] == "EDIT"
    assert history.status_code == 200
    assert len(history.json()["data"]) == 1


@pytest.mark.parametrize("reason", ["", " "])
def test_blank_reason_returns_422(tmp_path: Path, reason: str) -> None:
    app = _app(tmp_path)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/tasks/task-001/feedback",
            json={
                "decision": "REJECT",
                "reason": reason,
                "idempotency_key": "blank-reason",
                "expected_version": 0,
            },
        )
    assert response.status_code == 422
    assert response.json()["detail"]


def test_reject_target_field_returns_422(tmp_path: Path) -> None:
    app = _app(tmp_path)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/tasks/task-001/feedback",
            json={
                "decision": "REJECT",
                "target_field": "title",
                "reason": "invalid",
                "idempotency_key": "reject-field",
                "expected_version": 0,
            },
        )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "REJECT_TARGET_FIELD_FORBIDDEN"


def test_actor_cannot_be_spoofed(tmp_path: Path) -> None:
    app = _app(tmp_path)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/tasks/task-001/feedback",
            json={
                "decision": "REJECT",
                "reason": "운영자 검토",
                "idempotency_key": "actor-spoof",
                "expected_version": 0,
                "actor": "CLIENT_ACTOR",
            },
        )
        history = client.get("/api/v1/tasks/task-001/feedback")
    assert response.status_code == 200
    assert response.json()["data"]["actor"] == "DEMO_OPERATOR"
    assert history.json()["data"][0]["actor"] == "DEMO_OPERATOR"


def test_storage_failure_is_not_reported_as_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = _app(tmp_path)

    def fail_commit(self: Session) -> None:
        raise OperationalError("COMMIT", {}, RuntimeError("storage unavailable"))

    monkeypatch.setattr(Session, "commit", fail_commit)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/v1/tasks/task-001/feedback",
            json={
                "decision": "REJECT",
                "reason": "운영자 검토",
                "idempotency_key": "storage-failure",
                "expected_version": 0,
            },
        )
        history = client.get("/api/v1/tasks/task-001/feedback")
    assert response.status_code == 500
    assert history.status_code == 200
    assert history.json()["data"] == []
