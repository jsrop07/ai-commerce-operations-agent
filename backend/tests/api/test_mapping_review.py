"""D09-BE-01 Mapping Review API 테스트."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import (
    TestClient,
)

from backend.app.main import app


def test_mapping_review_endpoint_exists() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/mappings/review"
        )

    assert response.status_code == 200

    body = response.json()

    assert body["data"] == []


def test_single_candidate_is_not_auto_selected() -> None:
    with TestClient(app) as client:
        queue = (
            client
            .app
            .state
            .mapping_queue
        )

        queue.enqueue(
            tenant_id=(
                client
                .app
                .state
                .settings
                .tenant_id
            ),
            provider="CAFE24",
            object_type="SKU",
            external_id="external-001",
            external_text=None,
            source_identity_key=(
                "safe-source-001"
            ),
            reason=(
                "RESERVATION_SKU_"
                "MAPPING_REVIEW"
            ),
            candidate_ids=(
                "sku-candidate-001",
            ),
            confidence=0.91,
            matching_rule=(
                "PRODUCT_CODE_EXACT"
            ),
            evidence_ids=(
                "ev-map-001",
            ),
            quality_status=(
                "REVIEW_REQUIRED"
            ),
            source_classification=(
                "SANITIZED_REAL"
            ),
            as_of=datetime.now(UTC),
        )

        response = client.get(
            "/api/v1/mappings/review"
        )

    assert response.status_code == 200

    data = response.json()["data"]

    assert len(data) == 1

    item = data[0]

    assert item["candidates"] == [
        {
            "sku_id": (
                "sku-candidate-001"
            )
        }
    ]

    assert (
        item["selected_sku_id"]
        is None
    )

    assert (
        item["quality_status"]
        == "REVIEW_REQUIRED"
    )

    assert (
        item[
            "source_classification"
        ]
        == "SANITIZED_REAL"
    )


def test_mapping_review_does_not_expose_external_text() -> None:
    with TestClient(app) as client:
        queue = (
            client
            .app
            .state
            .mapping_queue
        )

        queue.enqueue(
            tenant_id=(
                client
                .app
                .state
                .settings
                .tenant_id
            ),
            provider="CAFE24",
            object_type="SKU",
            external_id="external-002",
            external_text=(
                "이 값은 review API에 "
                "노출되면 안 됨"
            ),
            source_identity_key=(
                "safe-source-002"
            ),
            reason="MAPPING_REQUIRED",
        )

        response = client.get(
            "/api/v1/mappings/review"
        )

    text = response.text

    assert (
        "이 값은 review API에"
        not in text
    )


def test_missing_candidate_is_explicitly_blocked() -> None:
    with TestClient(app) as client:
        queue = (
            client
            .app
            .state
            .mapping_queue
        )

        queue.enqueue(
            tenant_id=(
                client
                .app
                .state
                .settings
                .tenant_id
            ),
            provider="CAFE24",
            object_type="SKU",
            external_id="external-003",
            external_text=None,
            source_identity_key=(
                "safe-source-003"
            ),
            reason="MAPPING_REQUIRED",
        )

        response = client.get(
            "/api/v1/mappings/review"
        )

    data = response.json()["data"]

    item = next(
        item
        for item in data
        if (
            item["external_id"]
            == "external-003"
        )
    )

    assert item["candidates"] == []
    assert (
        item["quality_status"]
        == "BLOCKED"
    )

    assert (
        item["selected_sku_id"]
        is None
    )