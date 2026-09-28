"""D11-BE-03 Task priority contribution API."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.services.reservation_projection import build_reservation_risk_projection
from backend.app.services.reservation_tasks import register_reservation_risk_projection


NOW = datetime(
    2026,
    9,
    13,
    12,
    0,
    tzinfo=UTC,
)


def test_tasks_expose_priority_breakdown() -> None:
    app = create_app()

    with TestClient(app) as client:
        client.app.state.schedule_task_projections = [
            {
                "id": "task-001",
                "task_type": "INCOMING",
                "title": "입고 확인",
                "deadline": (
                    NOW
                    + timedelta(hours=12)
                ),
                "risk_level": "HIGH",
                "affected_count": 5,
                "aging_hours": 48,
                "status": "PROPOSED",
                "source_reason": "FIXTURE",
                "source_classification": "FIXTURE",
                "evidence_ids": [
                    "evidence-001"
                ],
            }
        ]

        response = client.get(
            "/api/v1/tasks"
        )

    assert response.status_code == 200

    item = response.json()["data"][0]

    assert "priority" in item
    assert "priority_breakdown" in item

    breakdown = item[
        "priority_breakdown"
    ]

    assert set(
        breakdown.keys()
    ) == {
        "deadline",
        "risk",
        "business_impact",
        "aging",
    }

    assert (
        item["priority_provenance"]
        == "RULE"
    )

    assert (
        item["priority_rule_version"]
        == "task-priority.v0.1"
    )

    assert item["priority"] == (
        item["priority_rule_score"]
    )

    assert (
        item["priority_coverage_weight"]
        > 0
    )
def test_tasks_preserve_missing_values() -> None:
    app = create_app()

    with TestClient(app) as client:
        client.app.state.schedule_task_projections = [
            {
                "id": "task-002",
                "task_type": "INCOMING",
                "title": "입고일 확인",
                "deadline": None,
                "risk_level": "UNKNOWN",
                "affected_count": None,
                "aging_hours": None,
                "status": "PROPOSED",
                "source_reason": (
                    "AUTHORITATIVE_SOURCE_UNAVAILABLE"
                ),
                "source_classification": "BLOCKED",
                "evidence_ids": [],
            }
        ]

        response = client.get(
            "/api/v1/tasks"
        )

    assert response.status_code == 200

    item = response.json()["data"][0]

    breakdown = item[
        "priority_breakdown"
    ]

    assert (
        breakdown["deadline"]["normalized"]
        is None
    )
    assert (
        breakdown["risk"]["normalized"]
        is None
    )
    assert (
        breakdown["business_impact"][
            "normalized"
        ]
        is None
    )
    assert (
        breakdown["aging"]["normalized"]
        is None
    )

    assert set(
        item[
            "priority_missing_features"
        ]
    ) == {
        "deadline",
        "risk",
        "business_impact",
        "aging",
    }


def test_tasks_are_sorted_by_priority() -> None:
    app = create_app()

    with TestClient(app) as client:
        client.app.state.schedule_task_projections = [
            {
                "id": "task-low",
                "task_type": "INCOMING",
                "title": "낮은 위험",
                "deadline": (
                    NOW
                    + timedelta(days=14)
                ),
                "risk_level": "LOW",
                "affected_count": 0,
                "aging_hours": 0,
                "status": "PROPOSED",
                "source_reason": "FIXTURE",
                "source_classification": "FIXTURE",
                "evidence_ids": [],
            },
            {
                "id": "task-high",
                "task_type": "INCOMING",
                "title": "높은 위험",
                "deadline": (
                    NOW
                    - timedelta(hours=1)
                ),
                "risk_level": "HIGH",
                "affected_count": 10,
                "aging_hours": 72,
                "status": "PROPOSED",
                "source_reason": "FIXTURE",
                "source_classification": "FIXTURE",
                "evidence_ids": [],
            },
        ]

        response = client.get(
            "/api/v1/tasks"
        )

    assert response.status_code == 200

    data = response.json()["data"]

    assert data[0]["id"] == "task-high"
    assert data[1]["id"] == "task-low"


def test_tasks_preserve_evidence_and_source() -> None:
    app = create_app()

    with TestClient(app) as client:
        client.app.state.schedule_task_projections = [
            {
                "id": "task-003",
                "task_type": "INCOMING",
                "title": "근거 확인",
                "deadline": None,
                "risk_level": None,
                "affected_count": None,
                "aging_hours": None,
                "status": "PROPOSED",
                "source_reason": "FIXTURE",
                "source_classification": "BLOCKED",
                "evidence_ids": [
                    "evidence-001",
                ],
            }
        ]

        response = client.get(
            "/api/v1/tasks"
        )

    body = response.json()
    item = body["data"][0]

    assert (
        item["source_classification"]
        == "BLOCKED"
    )

    assert (
        "evidence-001"
        in body["evidence_ids"]
    )

def test_tasks_preserve_existing_priority_when_all_rule_inputs_missing() -> None:
    app = create_app()

    with TestClient(app) as client:
        client.app.state.schedule_task_projections = [
            {
                "id": "task-legacy-001",
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

    assert item["priority"] == 60
    assert item["priority_rule_score"] == 0
    assert (
        item["priority_coverage_weight"]
        == 0
    )

    assert set(
        item["priority_missing_features"]
    ) == {
        "deadline",
        "risk",
        "business_impact",
        "aging",
    }


def test_reservation_shortage_projection_is_scored_by_tasks_api() -> None:
    app = create_app()
    risk = build_reservation_risk_projection(
        reservation_id="reservation-001",
        tenant_id=app.state.settings.tenant_id,
        sku_id="sku-fixture-001",
        required_qty=5,
        secured_qty=1,
        confirmed_incoming_qty=2,
        tentative_incoming_qty=0,
        shortage=2,
        affected_order_ids=("order-fixture-001",),
        aging_hours=12,
        priority=42,
        priority_reason="FIXTURE_PRIORITY",
        calculation_status="CONFIRMED",
        evidence=("reservation-evidence-001",),
        source_classification="FIXTURE",
        quality_status="CONFIRMED",
        as_of=NOW,
    )
    task = register_reservation_risk_projection(app.state, risk)
    assert task is not None
    assert len(app.state.reservation_risk_projections) == 1
    assert len(app.state.schedule_task_projections) == 1

    with TestClient(app) as client:
        response = client.get("/api/v1/tasks")

    assert response.status_code == 200
    item = response.json()["data"][0]
    assert item["id"] == task["task_id"]
    assert item["reservation_id"] == "reservation-001"
    assert item["task_type"] == "RESERVATION_SHORTAGE"
    assert item["priority_rule_version"] == "task-priority.v0.1"
    assert item["priority_calibration_status"] == "DAY11_BASELINE_UNVALIDATED"
    assert set(item["priority_breakdown"]) == {
        "deadline", "risk", "business_impact", "aging",
    }
    assert "deadline" in item["priority_missing_features"]
    assert item["priority_breakdown"]["deadline"]["normalized"] is None
    assert item["priority"] == item["priority_rule_score"]
    assert item["affected_count"] == 1
    assert "affected_order_ids" not in item
