"""D09-BE-02 Inventory empty/blocked 계약."""

from fastapi.testclient import TestClient

from backend.app.main import app


def test_empty_inventory_has_explicit_reason() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/inventory"
        )

    assert response.status_code == 200

    body = response.json()

    assert body["data"] == []

    assert any(
        "INVENTORY_PROJECTION_EMPTY"
        in warning
        for warning in body["warnings"]
    )