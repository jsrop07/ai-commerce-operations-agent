from fastapi.testclient import TestClient

from backend.app.api import cafe24_smoke
from backend.app.main import create_app


def test_cafe24_smoke_uses_read_only_adapter(monkeypatch) -> None:
    app = create_app()

    app.state.settings.cafe24_mall_id = "synthetic-mall"

    token_fixture_value = "synthetic-access-value"
    app.state.cafe24_access_token = token_fixture_value

    calls: list[str] = []

    def fake_request_json(
        *,
        method,
        url,
        headers=None,
        params=None,
        timeout=10.0,
    ):
        calls.append(method)

        if url.endswith("/products"):
            return {
                "products": [
                    {
                        "product_no": 1,
                        "product_name": "Synthetic Product",
                    }
                ]
            }

        if url.endswith("/orders"):
            return {
                "orders": []
            }

        raise AssertionError("예상하지 않은 URL입니다.")

    monkeypatch.setattr(
        cafe24_smoke,
        "_request_json",
        fake_request_json,
    )

    client = TestClient(app)

    response = client.get("/internal/cafe24/smoke")

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "LIVE_READ_OK"
    assert body["products"]["count"] == 1
    assert body["orders"]["count"] == 0
    assert body["read_call_count"] == 2
    assert body["write_call_count"] == 0
    assert body["token_exposed"] is False

    assert calls == ["GET", "GET"]

    assert token_fixture_value not in response.text