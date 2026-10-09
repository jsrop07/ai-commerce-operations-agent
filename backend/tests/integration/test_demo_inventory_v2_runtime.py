"""Public DEMO inventory reads only the synthetic V2 PostgreSQL source."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from backend.app.core.config import Environment, Settings


@pytest.mark.postgres
def test_demo_inventory_uses_v2_with_legacy_port_unavailable() -> None:
    configured = Settings()
    if not configured.postgres_v2_url or make_url(configured.postgres_v2_url).port != 55433:
        pytest.skip("isolated 55433 Demo V2 PostgreSQL is not configured")
    engine = create_engine(configured.postgres_v2_url)
    try:
        with engine.connect() as connection:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        pytest.skip("isolated 55433 Demo V2 PostgreSQL is unavailable")
    finally:
        engine.dispose()

    settings = Settings(
        _env_file=None, environment=Environment.DEMO,
        tenant_id=str(configured.v2_tenant_id), v2_tenant_id=configured.v2_tenant_id,
        postgres_v2_url=configured.postgres_v2_url,
        database_url="postgresql+psycopg://blocked:blocked@127.0.0.1:55432/forbidden",
        demo_session_ttl_seconds=3600, demo_session_cookie_secure=False,
    )
    # Search models are outside this read-only Inventory test's scope.
    with patch("backend.app.services.c18_product_search.ProductSearchService", return_value=None):
        from backend.app.main import create_app

        app = create_app(settings)
    assert app.state.db_engine is None
    assert app.state.db_session_factory is None

    with TestClient(app) as client:
        health = client.get("/api/v1/health")
        summary = client.get("/api/v1/catalog/summary")
        products = client.get("/api/v1/catalog/products?limit=3&offset=0")
        inventory = client.get("/api/v1/inventory")
        demo_session = client.post("/api/v1/demo/session")
        assert client.get("/api/v1/tasks/any/feedback").status_code == 403
        assert client.get("/api/v1/workflows/any/threads/any/state").status_code == 403

    assert health.status_code == 200
    assert health.json()["environment"] == "DEMO"
    assert summary.status_code == 200
    assert summary.json()["data"]["product_count"] == 150
    assert summary.json()["data"]["category_count"] == 41
    assert summary.json()["tenant_id"] == str(configured.v2_tenant_id)
    assert products.status_code == 200
    assert len(products.json()["data"]["items"]) == 3
    assert inventory.status_code == 200
    assert demo_session.status_code in {200, 201}
    assert demo_session.json()["status"] == "ACTIVE"
    hero = next(row for row in inventory.json()["data"] if row["sku_id"] == "DEMO-SKU-0009-01")
    assert hero["source_on_hand"] == 1
    assert hero["provider"] == "SYNTHETIC_DEMO"
    assert hero["confirmed_for_total"] is False  # historical snapshot has no V2 TTL
