from fastapi.testclient import TestClient

from backend.app.core.config import (
    Environment,
    Settings,
    WriteMode,
)
from backend.app.main import create_app


def _app():
    settings = Settings(
        environment=Environment.PRODUCTION_READ,
        write_mode=WriteMode.DISABLED,
        global_write_kill=True,
    )
    return create_app(settings)


def test_pending_mapping_is_exposed_as_read_projection() -> None:
    app = _app()

    item = app.state.mapping_queue.enqueue(
        tenant_id=app.state.settings.tenant_id,
        provider="TOSS_POS",
        object_type="SKU",
        external_id="TOSS-P999",
        external_text="미매핑 테스트 상품",
        source_identity_key="source-key-001",
        reason="UNKNOWN_PRODUCT_CODE",
    )

    client = TestClient(app)
    response = client.get("/api/v1/mappings")

    assert response.status_code == 200

    body = response.json()
    assert len(body["data"]) == 1

    result = body["data"][0]

    assert result["queue_id"] == item.queue_id
    assert result["provider"] == "TOSS_POS"
    assert result["external_id"] == "TOSS-P999"
    assert result["review_status"] == "PENDING"
    assert result["reason"] == "UNKNOWN_PRODUCT_CODE"

    assert result["approved"] is False
    assert result["canonical_id"] is None
    assert result["confidence"] is None
    assert result["matching_rule"] is None


def test_resolved_mapping_moves_out_of_pending_projection() -> None:
    app = _app()

    item = app.state.mapping_queue.enqueue(
        tenant_id=app.state.settings.tenant_id,
        provider="TOSS_POS",
        object_type="SKU",
        external_id="TOSS-P999",
        external_text="미매핑 테스트 상품",
        source_identity_key="source-key-002",
        reason="UNKNOWN_PRODUCT_CODE",
    )

    app.state.mapping_queue.resolve(item.queue_id)

    client = TestClient(app)
    result = client.get("/api/v1/mappings").json()["data"][0]

    assert result["queue_id"] == item.queue_id
    assert result["review_status"] == "RESOLVED"
    assert result["approved"] is False  # Resolution alone is not DB approval.


def test_mapping_projection_is_read_only() -> None:
    client = TestClient(_app())

    assert client.post("/api/v1/mappings").status_code == 405
    assert client.put("/api/v1/mappings").status_code == 405
    assert client.patch("/api/v1/mappings").status_code == 405
    assert client.delete("/api/v1/mappings").status_code == 405
