from fastapi.testclient import TestClient

from backend.app.core.config import (
    Environment,
    Settings,
    WriteMode,
)
from backend.app.main import create_app
from backend.app.services.inventory_projection import (
    build_inventory_projection,
)


def _client_with_projection():
    settings = Settings(
        environment=Environment.PRODUCTION_READ,
        write_mode=WriteMode.DISABLED,
        global_write_kill=True,
    )

    app = create_app(settings)

    projection = build_inventory_projection(
        tenant_id=settings.tenant_id,
        sku_id="sku-001",
        source_on_hand=10,
        ledger_delta=-2,
        reserved=1,
        confirmed_incoming=3,
        quality_status="CONFIRMED",
        ttl_seconds=300,
        age_seconds=120,
        risk_level="LOW",
        evidence=(
            "snapshot-001",
            "ledger-sale-001",
        ),
    )

    app.state.inventory_projections.append(projection)

    return TestClient(app)


def test_inventory_projection_api_returns_backend_calculation() -> None:
    client = _client_with_projection()

    response = client.get("/api/v1/inventory")

    assert response.status_code == 200

    body = response.json()
    item = body["data"][0]

    assert item["sku_id"] == "sku-001"
    assert item["source_on_hand"] == 10
    assert item["ledger_delta"] == -2
    assert item["reserved"] == 1
    assert item["expected_inventory"] == 7
    assert item["confirmed_incoming"] == 3

    assert item["risk_level"] == "LOW"
    assert item["quality_status"] == "CONFIRMED"

    assert item["ttl_seconds"] == 300
    assert item["age_seconds"] == 120
    assert item["freshness_reason"] == "FRESH"
    assert item["confirmed_for_total"] is True

    assert item["calculation"] == {
        "source_on_hand": 10,
        "ledger_delta": -2,
        "reserved": 1,
        "expected_inventory": 7,
    }

    assert item["evidence"] == [
        "snapshot-001",
        "ledger-sale-001",
    ]


def test_inventory_projection_api_preserves_unknown_as_null() -> None:
    settings = Settings(
        environment=Environment.PRODUCTION_READ,
        write_mode=WriteMode.DISABLED,
        global_write_kill=True,
    )

    app = create_app(settings)

    projection = build_inventory_projection(
        tenant_id=settings.tenant_id,
        sku_id="sku-unknown",
        source_on_hand=None,
        ledger_delta=0,
        reserved=None,
        confirmed_incoming=None,
        quality_status="UNKNOWN",
        ttl_seconds=300,
        age_seconds=10,
        evidence=("source-unknown",),
    )

    app.state.inventory_projections.append(projection)

    client = TestClient(app)
    response = client.get("/api/v1/inventory")

    assert response.status_code == 200

    item = response.json()["data"][0]

    assert item["source_on_hand"] is None
    assert item["reserved"] is None
    assert item["expected_inventory"] is None
    assert item["confirmed_incoming"] is None

    assert item["confirmed_for_total"] is False
    assert item["freshness_reason"] == "SOURCE_ON_HAND_UNKNOWN"


def test_stale_inventory_is_excluded_from_confirmed_total() -> None:
    settings = Settings(
        environment=Environment.PRODUCTION_READ,
        write_mode=WriteMode.DISABLED,
        global_write_kill=True,
    )

    app = create_app(settings)

    projection = build_inventory_projection(
        tenant_id=settings.tenant_id,
        sku_id="sku-stale",
        source_on_hand=10,
        ledger_delta=-1,
        reserved=0,
        confirmed_incoming=2,
        quality_status="CONFIRMED",
        ttl_seconds=300,
        age_seconds=301,
        evidence=("snapshot-stale",),
    )

    app.state.inventory_projections.append(projection)

    client = TestClient(app)
    item = client.get("/api/v1/inventory").json()["data"][0]

    assert item["expected_inventory"] == 9
    assert item["freshness_reason"] == "STALE"
    assert item["confirmed_for_total"] is False
