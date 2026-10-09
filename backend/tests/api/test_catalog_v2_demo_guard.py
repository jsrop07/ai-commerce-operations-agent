"""Catalog V2 environment and tenant guards without database connections."""

from contextlib import nullcontext
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api import catalog_v2
from backend.app.core.config import Environment
from backend.app.services.catalog_v2_read import CatalogV2Summary

PATHS = (
    "/api/v1/catalog/summary",
    "/api/v1/catalog/products",
    "/api/v1/catalog/categories?depth=1",
)


def _client(monkeypatch, *, environment, tenant_id=None, row=None):
    tenant_id = tenant_id or catalog_v2.DEMO_CATALOG_TENANT_ID
    if row is None:
        row = SimpleNamespace(id=tenant_id, name="demo_store", environment="DEMO", status="ACTIVE")
    calls = []

    class FakeSession:
        def get(self, model, identity):
            calls.append(identity)
            return row

    app = FastAPI()
    app.include_router(catalog_v2.router)
    app.state.settings = SimpleNamespace(environment=environment, v2_tenant_id=tenant_id)
    app.state.v2_db_session_factory = lambda: nullcontext(FakeSession())
    monkeypatch.setattr(
        catalog_v2,
        "get_catalog_summary",
        lambda session, *, tenant_id: CatalogV2Summary(0, 0, 0),
    )
    monkeypatch.setattr(catalog_v2, "count_catalog_products", lambda *args, **kwargs: 0)
    monkeypatch.setattr(catalog_v2, "list_catalog_products", lambda *args, **kwargs: [])
    monkeypatch.setattr(catalog_v2, "list_catalog_categories", lambda *args, **kwargs: [])
    return TestClient(app), calls


@pytest.mark.parametrize("path", PATHS)
def test_demo_active_configured_tenant_allowed_without_name_pin(monkeypatch, path):
    tenant_id = catalog_v2.DEMO_CATALOG_TENANT_ID
    row = SimpleNamespace(
        id=tenant_id, name="renamed_demo_store", environment="DEMO", status="ACTIVE"
    )
    client, calls = _client(monkeypatch, environment=Environment.DEMO, row=row)
    response = client.get(path)
    assert response.status_code == 200, response.text
    assert response.json()["tenant_id"] == str(tenant_id)
    assert calls == [tenant_id]


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize(
    "row_environment,status",
    [
        ("LOCAL", "ACTIVE"),
        ("DEMO", "INACTIVE"),
    ],
)
def test_demo_rejects_wrong_tenant_environment_or_status(
    monkeypatch, path, row_environment, status
):
    tenant_id = catalog_v2.DEMO_CATALOG_TENANT_ID
    row = SimpleNamespace(
        id=tenant_id, name="demo_store", environment=row_environment, status=status
    )
    client, _ = _client(monkeypatch, environment=Environment.DEMO, row=row)
    response = client.get(path)
    assert response.status_code == 403
    assert response.json()["detail"] == "V2_TENANT_FORBIDDEN"


@pytest.mark.parametrize("path", PATHS)
def test_demo_rejects_other_configured_tenant_before_read(monkeypatch, path):
    client, calls = _client(monkeypatch, environment=Environment.DEMO, tenant_id=uuid4())
    response = client.get(path)
    assert response.status_code == 403
    assert response.json()["detail"] == "V2_TENANT_FORBIDDEN"
    assert calls == []


@pytest.mark.parametrize("path", PATHS)
def test_demo_rejects_mismatched_returned_tenant_identity(monkeypatch, path):
    row = SimpleNamespace(id=uuid4(), name="demo_store", environment="DEMO", status="ACTIVE")
    client, _ = _client(monkeypatch, environment=Environment.DEMO, row=row)
    response = client.get(path)
    assert response.status_code == 403
    assert response.json()["detail"] == "V2_TENANT_FORBIDDEN"


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("environment", [Environment.LOCAL, Environment.TEST])
def test_local_and_test_bootstrap_contract_remains_allowed(monkeypatch, path, environment):
    tenant_id = uuid4()
    row = SimpleNamespace(
        id=tenant_id, name="commerce_ops_local", environment="LOCAL", status="ACTIVE"
    )
    client, _ = _client(monkeypatch, environment=environment, tenant_id=tenant_id, row=row)
    assert client.get(path).status_code == 200


@pytest.mark.parametrize("path", PATHS)
def test_local_still_rejects_non_bootstrap_tenant(monkeypatch, path):
    tenant_id = uuid4()
    row = SimpleNamespace(id=tenant_id, name="other_local", environment="LOCAL", status="ACTIVE")
    client, _ = _client(monkeypatch, environment=Environment.LOCAL, tenant_id=tenant_id, row=row)
    response = client.get(path)
    assert response.status_code == 403
    assert response.json()["detail"] == "V2_TENANT_FORBIDDEN"


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize(
    "environment",
    [
        Environment.PRODUCTION_READ,
        Environment.PILOT_SHADOW,
        Environment.PILOT_APPROVED,
        "PRODUCTION",
    ],
)
def test_production_family_forbidden_before_tenant_read(monkeypatch, path, environment):
    client, calls = _client(monkeypatch, environment=environment)
    response = client.get(path)
    assert response.status_code == 403
    assert response.json()["detail"] == "V2_CATALOG_ENVIRONMENT_FORBIDDEN"
    assert calls == []
