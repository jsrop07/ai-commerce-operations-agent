from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from backend.app.api import cafe24_smoke
from backend.app.main import create_app
def test_cafe24_smoke_uses_read_only_adapter(monkeypatch) -> None:
    app = create_app()

    app.state.settings.cafe24_mall_id = "synthetic-mall"

    token_fixture_value = "synthetic-access-value"
    app.state.cafe24_access_token = token_fixture_value
    app.state.cafe24_authorized_mall_id = "synthetic-mall"
    app.state.cafe24_shop_no = "1"
    app.state.cafe24_access_token_expires_at = datetime.now(UTC) + timedelta(hours=1)

    app.state.cafe24_approved_scopes = frozenset(
        {
            "mall.read_product",
            "mall.read_order",
            "mall.read_category",
            "mall.read_community",
        }
    )

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

        if url.endswith("/categories"):
            return {
                "categories": [
                    {
                        "category_no": 1,
                        "category_name": "Synthetic Category",
                    }
                ]
            }

        if url.endswith("/boards"):
            return {
                "boards": [
                    {
                        "board_no": 6,
                        "board_name": "Synthetic Board",
                    }
                ]
            }

        raise AssertionError(
            f"예상하지 않은 URL입니다: {url}"
        )

    monkeypatch.setattr(
        cafe24_smoke,
        "_request_json",
        fake_request_json,
    )

    client = TestClient(app)

    response = client.get(
        "/internal/cafe24/smoke"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "LIVE_READ_OK"
    assert payload["provider"] == "CAFE24"
    assert payload["mall_id"] == "synthetic-mall"

    assert payload["products"]["count"] == 1
    assert payload["orders"]["count"] == 0
    assert payload["categories"]["count"] == 1
    assert payload["boards"]["count"] == 1

    assert payload["total_items"] == 3

    assert payload["read_call_count"] == 4
    assert payload["write_call_count"] == 0
    assert payload["token_exposed"] is False

    assert calls == [
        "GET",
        "GET",
        "GET",
        "GET",
    ]

    response_text = response.text

    assert token_fixture_value not in response_text

import pytest
import httpx
from backend.app.api.cafe24_oauth import REQUIRED_READ_SCOPES
from backend.app.adapters.providers.base import ProviderHttpError, ProviderTransientError, ProviderNonRetryableError


@pytest.mark.parametrize("missing", sorted(REQUIRED_READ_SCOPES))
def test_smoke_missing_any_scope_performs_zero_reads(monkeypatch, missing):
    app = create_app()
    app.state.settings.cafe24_mall_id = "synthetic-mall"
    app.state.cafe24_access_token = ("synthetic-access-secret")
    app.state.cafe24_approved_scopes = REQUIRED_READ_SCOPES - {missing}
    calls = []
    monkeypatch.setattr(cafe24_smoke, "_request_json", lambda **kw: calls.append(kw))
    response = TestClient(app).get("/internal/cafe24/smoke")
    assert response.status_code == 403
    assert calls == []
    assert "synthetic-access-secret" not in response.text


@pytest.mark.parametrize("field,value", [
    ("cafe24_authorized_mall_id", "another-synthetic-mall"),
    ("cafe24_shop_no", "2"), ("cafe24_access_token_expires_at", None),
    ("cafe24_access_token_expires_at", datetime(2000, 1, 1, tzinfo=UTC)),
])
def test_smoke_invalid_metadata_performs_zero_reads(monkeypatch, field, value):
    app = create_app()
    app.state.settings.cafe24_mall_id = "synthetic-mall"
    app.state.cafe24_access_token = ("synthetic-access-secret")
    app.state.cafe24_approved_scopes = REQUIRED_READ_SCOPES
    app.state.cafe24_authorized_mall_id = "synthetic-mall"
    app.state.cafe24_shop_no = "1"
    app.state.cafe24_access_token_expires_at = datetime.now(UTC) + timedelta(hours=1)
    setattr(app.state, field, value)
    calls = []
    monkeypatch.setattr(cafe24_smoke, "_request_json", lambda **kw: calls.append(kw))
    assert TestClient(app).get("/internal/cafe24/smoke").status_code == 403
    assert calls == []


@pytest.mark.parametrize("status_code", [429, 500, 502, 503, 504])
def test_request_json_status_errors_hide_response_body(monkeypatch, status_code):
    monkeypatch.setattr(httpx, "request", lambda **kw: httpx.Response(
        status_code, headers={"Retry-After": "0"}, text="synthetic-private-response"))
    with pytest.raises(ProviderHttpError) as caught:
        cafe24_smoke._request_json(method="GET", url="https://example.test/synthetic")
    assert caught.value.status_code == status_code
    assert "synthetic-private-response" not in str(caught.value)


def test_request_json_timeout_is_retryable_and_redacted(monkeypatch):
    def timeout(**kw):
        raise httpx.ReadTimeout("synthetic-private-response")
    monkeypatch.setattr(httpx, "request", timeout)
    with pytest.raises(ProviderTransientError) as caught:
        cafe24_smoke._request_json(method="GET", url="https://example.test/synthetic")
    assert "synthetic-private-response" not in str(caught.value)


def test_smoke_blocks_an_unexpected_fifth_read(monkeypatch):
    app = create_app()
    app.state.settings.cafe24_mall_id = "synthetic-mall"
    app.state.cafe24_access_token = ("synthetic-access-value")
    app.state.cafe24_approved_scopes = REQUIRED_READ_SCOPES
    app.state.cafe24_authorized_mall_id = "synthetic-mall"
    app.state.cafe24_shop_no = "1"
    app.state.cafe24_access_token_expires_at = datetime.now(UTC) + timedelta(hours=1)
    calls = []

    def fake_request_json(*, method, url, **kwargs):
        calls.append((method, url))
        return {
            "products": [],
            "orders": [],
            "categories": [],
            "boards": [],
        }

    original_read_boards = cafe24_smoke.Cafe24Adapter.read_boards

    def read_boards_then_unexpected_product(self, cursor=None):
        page = original_read_boards(self, cursor)
        self.read_products()
        return page

    monkeypatch.setattr(cafe24_smoke, "_request_json", fake_request_json)
    monkeypatch.setattr(
        cafe24_smoke.Cafe24Adapter,
        "read_boards",
        read_boards_then_unexpected_product,
    )

    response = TestClient(app).get("/internal/cafe24/smoke")

    assert response.status_code == 502
    assert len(calls) == 4
    assert all(method == "GET" for method, _ in calls)
