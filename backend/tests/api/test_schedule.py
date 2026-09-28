"""D10-BE-05 출시·일정·Task API 계약 시험."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from backend.app.core.config import (
    Environment,
    Settings,
    WriteMode,
)
from backend.app.main import create_app


SEOUL = ZoneInfo("Asia/Seoul")
AS_OF = datetime(2026, 10, 1, 9, 0, tzinfo=SEOUL)


def test_schedule_empty_read_contracts() -> None:
    app = create_app()

    with TestClient(app) as client:
        paths = (
            "/api/v1/launch-events",
            "/api/v1/tasks",
            "/api/v1/schedule/dependencies",
            "/api/v1/schedule/delay-impacts",
            "/api/v1/schedule/replan-proposals",
        )

        for path in paths:
            response = client.get(path)

            assert response.status_code == 200

            body = response.json()

            assert body["data"] == []
            assert body["request_id"]
            assert body["trace_id"]
            assert "schema_version" in body
            assert "evidence_ids" in body
            assert "warnings" in body
            assert body["as_of"] is not None


def test_launch_events_returns_projection() -> None:
    app = create_app()

    with TestClient(app) as client:
        client.app.state.schedule_launch_event_projections = [
            {
                "id": "launch-001",
                "product_id": "product-safe-001",
                "launch_at": (
                    "2026-10-20T10:00:00+09:00"
                ),
                "flow_template": "FLOW_A",
                "status": "PROPOSED",
                "source_classification": "FIXTURE",
                "as_of": AS_OF.isoformat(),
                "evidence_ids": [
                    "ev-launch-fixture-001"
                ],
            }
        ]

        response = client.get(
            "/api/v1/launch-events",
            headers={
                "x-request-id": "req-d10-launch",
                "x-trace-id": "tr-d10-launch",
            },
        )

    assert response.status_code == 200

    body = response.json()

    assert body["request_id"] == "req-d10-launch"
    assert body["trace_id"] == "tr-d10-launch"
    assert len(body["data"]) == 1

    item = body["data"][0]

    assert item["id"] == "launch-001"
    assert item["flow_template"] == "FLOW_A"
    assert (
        item["source_classification"]
        == "FIXTURE"
    )

    assert (
        "ev-launch-fixture-001"
        in body["evidence_ids"]
    )


def test_tasks_preserve_nullable_deadline() -> None:
    app = create_app()

    with TestClient(app) as client:
        client.app.state.schedule_task_projections = [
            {
                "id": "task-blocked-001",
                "task_type": "INCOMING",
                "title": "입고일 확인",
                "deadline": None,
                "priority": 60,
                "status": "PROPOSED",
                "source_reason": (
                    "AUTHORITATIVE_SOURCE_UNAVAILABLE"
                ),
                "source_classification": "BLOCKED",
                "as_of": None,
                "evidence_ids": [],
            }
        ]

        response = client.get(
            "/api/v1/tasks"
        )

    assert response.status_code == 200

    item = response.json()["data"][0]

    assert item["deadline"] is None
    assert item["as_of"] is None
    assert (
        item["source_classification"]
        == "BLOCKED"
    )


def test_dependencies_return_lag_contract() -> None:
    app = create_app()

    with TestClient(app) as client:
        client.app.state.schedule_dependency_projections = [
            {
                "predecessor_id": "task-a",
                "successor_id": "task-b",
                "lag_hours": 8,
                "source_classification": "FIXTURE",
                "evidence_ids": [
                    "ev-dependency-001"
                ],
            }
        ]

        response = client.get(
            "/api/v1/schedule/dependencies"
        )

    assert response.status_code == 200

    item = response.json()["data"][0]

    assert item["predecessor_id"] == "task-a"
    assert item["successor_id"] == "task-b"
    assert item["lag_hours"] == 8


def test_delay_impact_detail_not_found() -> None:
    app = create_app()

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/schedule/delay-impacts/missing"
        )

    assert response.status_code == 404

    detail = response.json()["detail"]

    assert (
        detail["code"]
        == "DELAY_IMPACT_NOT_FOUND"
    )


def test_replan_proposal_detail_not_found() -> None:
    app = create_app()

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/schedule/replan-proposals/missing"
        )

    assert response.status_code == 404

    detail = response.json()["detail"]

    assert (
        detail["code"]
        == "REPLAN_PROPOSAL_NOT_FOUND"
    )


def test_demo_replan_draft_is_idempotent() -> None:
    app = create_app()

    payload = {
        "current_schedule": [
            {
                "item_type": "TASK",
                "item_id": "task-inspection",
                "scheduled_at": (
                    "2026-10-10T18:00:00+09:00"
                ),
            },
            {
                "item_type": "LAUNCH_EVENT",
                "item_id": "launch-001",
                "scheduled_at": (
                    "2026-10-15T10:00:00+09:00"
                ),
            },
        ],
        "impact": {
            "status": "CONTRACT_ONLY",
            "actual_delay_confirmed": False,
            "incoming_id": "incoming-demo-001",
            "delay_hours": 72,
            "source_id": (
                "fixture:incoming-delay-3d"
            ),
            "source_classification": "FIXTURE",
            "as_of": (
                "2026-10-01T09:00:00+09:00"
            ),
            "freshness": "FRESH",
            "quality": "TENTATIVE",
            "evidence_ids": [
                "ev-fixture-001"
            ],
            "impacted_task_ids": [
                "task-inspection"
            ],
            "impacted_reservation_ids": [],
            "impacted_launch_event_ids": [
                "launch-001"
            ],
            "critical_path": [
                "task-inspection"
            ],
            "impact_path": [
                {
                    "target_type": "TASK",
                    "target_id": "task-inspection",
                    "source_id": (
                        "fixture:incoming-delay-3d"
                    ),
                    "before": (
                        "2026-10-10T18:00:00+09:00"
                    ),
                    "after": (
                        "2026-10-13T18:00:00+09:00"
                    ),
                    "lag_hours": 0,
                    "reason": (
                        "입고 72시간 지연 Fixture"
                    ),
                    "evidence_ids": [
                        "ev-fixture-001"
                    ],
                },
                {
                    "target_type": "LAUNCH_EVENT",
                    "target_id": "launch-001",
                    "source_id": (
                        "fixture:incoming-delay-3d"
                    ),
                    "before": (
                        "2026-10-15T10:00:00+09:00"
                    ),
                    "after": (
                        "2026-10-18T10:00:00+09:00"
                    ),
                    "lag_hours": 72,
                    "reason": (
                        "출시 일정 재검토 Fixture"
                    ),
                    "evidence_ids": [
                        "ev-fixture-001"
                    ],
                },
            ],
            "reason": (
                "Fixture 기반 입고 지연 영향"
            ),
        },
        "created_at": (
            "2026-10-02T09:00:00+09:00"
        ),
        "confidence": 0.8,
    }

    with TestClient(app) as client:
        first = client.post(
            "/api/v1/demo/schedule/"
            "replan-proposals/draft",
            json=payload,
        )

        second = client.post(
            "/api/v1/demo/schedule/"
            "replan-proposals/draft",
            json=payload,
        )

        assert first.status_code == 200
        assert second.status_code == 200

        first_id = first.json()["data"]["proposal_id"]
        second_id = second.json()["data"]["proposal_id"]

        assert first_id == second_id

        assert (
            len(
                client.app.state
                .schedule_replan_proposals
            )
            == 1
        )

        assert (
            first.json()["data"][
                "external_execution_allowed"
            ]
            is False
        )


def test_invalid_draft_confidence_returns_422() -> None:
    app = create_app()

    payload = {
        "current_schedule": [],
        "impact": {
            "status": "BLOCKED",
            "actual_delay_confirmed": False,
            "incoming_id": "incoming-001",
            "delay_hours": None,
            "source_id": "gmail-unavailable",
            "source_classification": "BLOCKED",
            "as_of": None,
            "freshness": "UNKNOWN",
            "quality": "BLOCKED",
            "evidence_ids": [],
            "impacted_task_ids": [],
            "impacted_reservation_ids": [],
            "impacted_launch_event_ids": [],
            "critical_path": [],
            "impact_path": [],
            "reason": "source unavailable",
        },
        "created_at": (
            "2026-10-02T09:00:00+09:00"
        ),
        "confidence": 1.5,
    }

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/demo/schedule/"
            "replan-proposals/draft",
            json=payload,
        )

    assert response.status_code == 422


def test_production_read_denies_demo_draft() -> None:
    settings = Settings(
        environment=Environment.PRODUCTION_READ,
        write_mode=WriteMode.DISABLED,
        global_write_kill=True,
    )

    app = create_app(settings)

    payload = {
        "current_schedule": [],
        "impact": {
            "status": "BLOCKED",
            "actual_delay_confirmed": False,
            "incoming_id": "incoming-blocked",
            "delay_hours": None,
            "source_id": "gmail-unavailable",
            "source_classification": "BLOCKED",
            "as_of": None,
            "freshness": "UNKNOWN",
            "quality": "BLOCKED",
            "evidence_ids": [],
            "impacted_task_ids": [],
            "impacted_reservation_ids": [],
            "impacted_launch_event_ids": [],
            "critical_path": [],
            "impact_path": [],
            "reason": "authoritative source unavailable",
        },
        "created_at": (
            "2026-10-02T09:00:00+09:00"
        ),
        "confidence": 0.0,
    }

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/demo/schedule/"
            "replan-proposals/draft",
            json=payload,
        )

    assert response.status_code == 403
    assert (
        response.json()["detail"]["code"]
        == "POLICY_DENIED"
    )


def test_openapi_contains_schedule_read_contract() -> None:
    app = create_app()

    with TestClient(app) as client:
        schema = client.get(
            "/openapi.json"
        ).json()

    paths = schema["paths"]

    assert "/api/v1/launch-events" in paths
    assert "/api/v1/tasks" in paths
    assert (
        "/api/v1/schedule/dependencies"
        in paths
    )
    assert (
        "/api/v1/schedule/delay-impacts"
        in paths
    )
    assert (
        "/api/v1/schedule/replan-proposals"
        in paths
    )

    assert (
        "/api/v1/demo/schedule/"
        "replan-proposals/draft"
        in paths
    )


def test_no_public_external_schedule_write_endpoint() -> None:
    app = create_app()

    with TestClient(app) as client:
        paths = client.get(
            "/openapi.json"
        ).json()["paths"]

    forbidden = (
        "/api/v1/schedule/apply",
        "/api/v1/calendar/write",
        "/api/v1/cafe24/schedule/write",
        "/api/v1/ecount/schedule/write",
    )

    for path in forbidden:
        assert path not in paths