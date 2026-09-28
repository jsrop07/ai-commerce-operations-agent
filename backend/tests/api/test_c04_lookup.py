"""C04 boundary tests using only explicitly wrapped synthetic records."""

from datetime import UTC, datetime, timedelta
from hashlib import sha256

import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import Environment, Settings
from backend.app.main import create_app
from backend.app.services.c04_lookup import C04LookupService, LookupFailure

PATH = "/api/v1/c04/lookup"
PARAMS = {"source_id": "product_demo_001", "version": "v1"}


def record(**changes):
    # Explicit wrapper metadata; no production corpus or final evaluation dataset.
    result = {
        "tenant_id": "demo_store", "source_id": "product_demo_001",
        "source_type": "PRODUCT", "title": "Synthetic board game",
        "version": "v1", "as_of": datetime.now(UTC), "pii_status": "CLEAN",
        "content": "합성 보드게임: 2–4명, 한국어판.",
        "data_mode": "SYNTHETIC_DEMO", "visibility": "DEMO_PUBLIC",
    }
    result.update(changes)
    return result


def client_for(records=()):
    settings = Settings(_env_file=None, environment=Environment.TEST, tenant_id="demo_store")
    return TestClient(create_app(settings, c04_lookup_service=C04LookupService(records)))


@pytest.mark.parametrize(
    "source_type", ["PRODUCT", "POLICY", "INVENTORY_SNAPSHOT", "INCOMING_STOCK"],
)
def test_safe_synthetic_http(source_type):
    item = record(source_type=source_type)
    client = client_for([item])
    response = client.get(PATH, params=PARAMS)
    assert response.status_code == 200
    body = response.json()
    data = body["data"]
    assert body["tenant_id"] == "demo_store"
    assert body["evidence_ids"] == []
    assert data["source_id"] == item["source_id"]
    assert data["source_type"] == source_type
    assert data["version"] == "v1"
    assert data["title"] == item["title"]
    assert data["data_mode"] == "SYNTHETIC_DEMO"
    assert data["visibility"] == "DEMO_PUBLIC"
    assert data["excerpt"] == item["content"]
    assert data["excerpt_hash"].startswith("sha256:")
    assert data["excerpt_hash"][len("sha256:"):] == sha256(
        data["excerpt"].encode("utf-8")
    ).hexdigest()
    assert data["as_of"] == body["as_of"]
    assert data["stale"] is False
    assert data["definitive_answer_allowed"] is False
    assert body["warnings"] == []
    assert data["chunk_id"] == "product_demo_001:v1:c04:0"
    exact = client.get(PATH, params={**PARAMS, "chunk_id": data["chunk_id"]})
    assert exact.status_code == 200
    assert exact.json()["data"] == data


@pytest.mark.parametrize("params", [
    {"source_id": "missing", "version": "v1"},
    {**PARAMS, "version": "v2"},
    {**PARAMS, "chunk_id": "product_demo_001:v1:semantic:0"},
    {**PARAMS, "chunk_id": "product_demo_001:v2:c04:0"},
    {**PARAMS, "chunk_id": "other:v1:c04:0"},
    {**PARAMS, "chunk_id": "product_demo_001:v1:c04:1"},
])
def test_exact_identity_required(params):
    assert client_for([record()]).get(PATH, params=params).status_code == 404


def test_foreign_tenant_cannot_be_selected_by_caller():
    client = client_for([record(tenant_id="other_demo")])
    response = client.get(
        PATH, params={**PARAMS, "tenant_id": "other_demo"},
        headers={"X-Tenant-ID": "other_demo"},
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "C04_NOT_FOUND"}


@pytest.mark.parametrize("changes", [
    {"source_type": value} for value in (
        "ORDER_STATUS", "order", "order_line", "customer", "shipping", "payment",
        "inquiry", "UNKNOWN",
    )
] + [
    {"pii_status": "REDACTED"}, {"pii_status": "UNKNOWN"},
    {"visibility": "PRIVATE"}, {"data_mode": "PRODUCTION"},
    {"as_of": "not-a-date"}, {"as_of": "2026-01-01T00:00:00"},
] + [
    {key: "synthetic-denied-value"} for key in (
        "order", "order_line", "customer", "shipping", "payment", "inquiry",
        "affected_order_ids", "reservation_id", "fields", "url", "file_path",
    )
] + [
    {"content": '{"affected_order_ids": ["synthetic"]}'},
    {"content": "reservation_id=synthetic"},
    {"content": '{"customer": {"name": "synthetic"}}'},
])
def test_unsafe_records_never_expose_content(changes):
    service = C04LookupService()
    with pytest.raises(LookupFailure) as error:
        service.register_demo_record(record(**changes), environment="DEMO", tenant_id="demo_store")
    assert error.value.status_code == 403
    with pytest.raises(LookupFailure) as missing:
        service.lookup(tenant_id="demo_store", **PARAMS)
    assert missing.value.status_code == 404
    response = client_for([record(**changes)]).get(PATH, params=PARAMS)
    assert response.status_code == 403
    assert response.json() == {"detail": "C04_RECORD_BLOCKED"}


@pytest.mark.parametrize("field", ["tenant_id", "as_of", "data_mode", "visibility"])
def test_missing_required_metadata_is_not_defaulted(field):
    item = record()
    del item[field]
    if field == "tenant_id":
        with pytest.raises(KeyError):
            C04LookupService([item])
    else:
        assert client_for([item]).get(PATH, params=PARAMS).status_code == 403


@pytest.mark.parametrize(("source_type", "seconds"), [
    ("INVENTORY_SNAPSHOT", 301), ("INCOMING_STOCK", 3601),
    ("INVENTORY_SNAPSHOT", -60),
])
def test_stale_live_http(source_type, seconds):
    item = record(source_type=source_type, as_of=datetime.now(UTC) - timedelta(seconds=seconds))
    response = client_for([item]).get(PATH, params=PARAMS)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["as_of"] == item["as_of"].isoformat().replace("+00:00", "Z")
    assert data["stale"] is True
    assert data["definitive_answer_allowed"] is False
    assert data["warnings"] == response.json()["warnings"]
    assert "C04_STALE" in data["warnings"][0]


def test_explicit_stale_and_exact_ttl_boundary():
    item = record(source_type="INVENTORY_SNAPSHOT")
    service = C04LookupService([item])
    assert service.lookup(tenant_id="demo_store", **PARAMS,
                          now=item["as_of"] + timedelta(seconds=300)).stale is False
    response = client_for([record(stale=True)]).get(PATH, params=PARAMS)
    assert response.json()["data"]["stale"] is True


def test_empty_and_unavailable_are_distinct():
    assert client_for().get(PATH, params=PARAMS).status_code == 404
    unavailable = client_for(None).get(PATH, params=PARAMS)
    assert unavailable.status_code == 503
    assert unavailable.json() == {"detail": "C04_REGISTRY_UNAVAILABLE"}
    client = client_for([record()])
    del client.app.state.c04_lookup_service
    assert client.get(PATH, params=PARAMS).status_code == 503


def test_default_app_restores_canonical_metadata():
    app = create_app(Settings(_env_file=None, environment=Environment.TEST))
    assert app.state.c04_corpus_restore.status == "READY"
    assert TestClient(app).get(PATH, params=PARAMS).status_code == 200


@pytest.mark.parametrize("source_type", ["PRODUCT", "POLICY"])
def test_static_null_as_of_http(source_type):
    response = client_for([record(source_type=source_type, as_of=None)]).get(PATH, params=PARAMS)
    assert response.status_code == 200
    assert response.json()["as_of"] is None
    assert response.json()["data"]["as_of"] is None
    assert response.json()["data"]["stale"] is False


@pytest.mark.parametrize("source_type", ["INVENTORY_SNAPSHOT", "INCOMING_STOCK"])
def test_live_null_as_of_blocked(source_type):
    response = client_for([record(source_type=source_type, as_of=None)]).get(PATH, params=PARAMS)
    assert response.status_code == 403


def test_demo_inventory_registration_http_regression():
    client = client_for()
    result = client.app.state.c04_lookup_service.register_demo_record(
        record(source_type="INVENTORY_SNAPSHOT"), environment="DEMO", tenant_id="demo_store",
    )
    response = client.get(PATH, params={**PARAMS, "chunk_id": result.chunk_id})
    assert response.status_code == 200
    assert response.json()["data"]["as_of"] is not None


def test_c04_nullable_schema_does_not_change_common_envelope():
    schema = client_for().get("/openapi.json").json()
    for name in ("C04Envelope", "LookupResult"):
        field = schema["components"]["schemas"][name]["properties"]["as_of"]
        assert {option["type"] for option in field["anyOf"]} == {"string", "null"}
    ref = schema["paths"]["/api/v1/insights"]["get"]["responses"]["200"][
        "content"
    ]["application/json"]["schema"]["$ref"].rsplit("/", 1)[-1]
    assert schema["components"]["schemas"][ref]["properties"]["as_of"]["type"] == "string"


def test_registry_is_snapshot_and_duplicates_fail():
    item = record()
    client = client_for([item])
    item["content"] = "mutated"
    assert client.get(PATH, params=PARAMS).json()["data"]["excerpt"] != "mutated"
    with pytest.raises(ValueError, match="Duplicate"):
        C04LookupService([item, item])


@pytest.mark.parametrize("params", [
    {}, {"source_id": "product_demo_001"}, {"version": "v1"},
    {**PARAMS, "source_id": "https://example.com/document"},
    {**PARAMS, "source_id": "../../secret"},
    {**PARAMS, "version": "C:\\private\\document"},
    {**PARAMS, "chunk_id": ""},
])
def test_invalid_http_input(params):
    assert client_for([record()]).get(PATH, params=params).status_code == 422


def test_read_only_and_openapi():
    client = client_for()
    for method in ("post", "put", "patch", "delete"):
        assert getattr(client, method)(PATH).status_code == 405
    operation = client.get("/openapi.json").json()["paths"][PATH]
    assert set(operation) == {"get"}
    get = operation["get"]
    assert set(get["responses"]) == {"200", "403", "404", "422", "503"}
    assert {p["name"] for p in get["parameters"] if p["required"]} == {"source_id", "version"}
    assert "security" not in get


def test_demo_registration_is_append_only_and_idempotent():
    service = C04LookupService()
    item = record()
    first = service.register_demo_record(item, environment="DEMO", tenant_id="demo_store")
    assert service.register_demo_record(
        item, environment="DEMO", tenant_id="demo_store",
    ) == first
    item["content"] = "Changed synthetic content"
    with pytest.raises(LookupFailure) as conflict:
        service.register_demo_record(item, environment="DEMO", tenant_id="demo_store")
    assert conflict.value.status_code == 409
    assert service.lookup(tenant_id="demo_store", **PARAMS) == first


@pytest.mark.parametrize("environment", ["PRODUCTION_READ", "PILOT_SHADOW", "TEST", "LOCAL"])
def test_registration_denied_outside_demo(environment):
    service = C04LookupService()
    with pytest.raises(LookupFailure) as error:
        service.register_demo_record(record(), environment=environment, tenant_id="demo_store")
    assert error.value.status_code == 403
    with pytest.raises(LookupFailure) as missing:
        service.lookup(tenant_id="demo_store", **PARAMS)
    assert missing.value.status_code == 404


def test_registration_denies_foreign_tenant_and_unavailable_registry():
    with pytest.raises(LookupFailure) as foreign:
        C04LookupService().register_demo_record(
            record(tenant_id="other_demo"), environment="DEMO", tenant_id="demo_store",
        )
    assert foreign.value.status_code == 403
    with pytest.raises(LookupFailure) as unavailable:
        C04LookupService(None).register_demo_record(
            record(), environment="DEMO", tenant_id="demo_store",
        )
    assert unavailable.value.status_code == 503
