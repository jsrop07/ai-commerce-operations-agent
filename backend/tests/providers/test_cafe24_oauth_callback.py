import logging

from fastapi.testclient import TestClient

from backend.app.api import cafe24_oauth
from backend.app.main import create_app
from datetime import UTC, datetime, timedelta

def test_cafe24_oauth_callback_accepts_matching_state(monkeypatch) -> None:
    app = create_app()

    # 실제 Cafe24 인증정보 대신 테스트 전용 값만 사용한다.
    app.state.settings.cafe24_mall_id = "synthetic-mall"
    app.state.settings.cafe24_client_id = "synthetic-client-id"
    oauth_fixture_value = "synthetic-client-secret"
    app.state.settings.cafe24_client_secret = oauth_fixture_value
    app.state.settings.cafe24_redirect_uri = (
        "https://example.test/internal/cafe24/oauth/callback"
    )

    app.state.cafe24_oauth_state = "synthetic-state-value"
    app.state.cafe24_oauth_state_created_at = datetime.now(UTC)

    def fake_exchange_authorization_code(**kwargs):
        return {
            "access_token": "synthetic-access-value",
            "expires_at": "2026-09-07T12:00:00+00:00",
            "refresh_token": "synthetic-refresh-value",
            "refresh_token_expires_at": (
                "2026-09-20T12:00:00+00:00"
            ),
            "mall_id": "synthetic-mall",
            "shop_no": "1",
            "scopes": [
                "mall.read_product",
                "mall.read_order",
                "mall.read_category",
                "mall.read_community",
            ],
        }

    monkeypatch.setattr(
        cafe24_oauth,
        "_exchange_authorization_code",
        fake_exchange_authorization_code,
    )

    client = TestClient(app)

    response = client.get(
        "/internal/cafe24/oauth/callback",
        params={
            "code": "synthetic-code-value",
            "state": "synthetic-state-value",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "authorized"
    assert body["provider"] == "CAFE24"
    assert body["token_received"] is True
    assert body["refresh_token_received"] is True
    assert set(body["scopes"]) == {
        "mall.read_product",
        "mall.read_order",
        "mall.read_category",
        "mall.read_community",
    }

    # 실제 Token 값은 HTTP 응답에 노출되면 안 된다.
    assert "synthetic-access-value" not in response.text
    assert "synthetic-refresh-value" not in response.text

    assert app.state.cafe24_oauth_state is None
    assert app.state.cafe24_authorization_code is None
    assert app.state.cafe24_access_token == "synthetic-access-value"
    assert app.state.cafe24_refresh_token == "synthetic-refresh-value"
    assert app.state.cafe24_access_token_expires_at is not None
    assert app.state.cafe24_refresh_token_expires_at is not None

    assert app.state.cafe24_authorized_mall_id == "synthetic-mall"
    assert app.state.cafe24_shop_no == "1"

    assert set(app.state.cafe24_approved_scopes) == {
        "mall.read_product",
        "mall.read_order",
        "mall.read_category",
        "mall.read_community",
    }

def test_cafe24_oauth_callback_rejects_wrong_state() -> None:
    app = create_app()
    app.state.cafe24_oauth_state = "expected-state-value"
    app.state.cafe24_oauth_state_created_at = datetime.now(UTC)
    client = TestClient(app)

    response = client.get(
        "/internal/cafe24/oauth/callback",
        params={
            "code": "synthetic-code-value",
            "state": "wrong-state-value",
        },
    )

    assert response.status_code == 403
    assert app.state.cafe24_authorization_code is None


def test_cafe24_oauth_callback_rejects_missing_code() -> None:
    app = create_app()
    app.state.cafe24_oauth_state = "synthetic-state-value"

    client = TestClient(app)

    response = client.get(
        "/internal/cafe24/oauth/callback",
        params={
            "state": "synthetic-state-value",
        },
    )

    assert response.status_code == 400


def test_cafe24_oauth_callback_rejects_missing_state() -> None:
    app = create_app()

    client = TestClient(app)

    response = client.get(
        "/internal/cafe24/oauth/callback",
        params={
            "code": "synthetic-code-value",
        },
    )

    assert response.status_code == 400

def test_cafe24_oauth_callback_rejects_unexpected_scope(monkeypatch) -> None:
    app = create_app()

    app.state.settings.cafe24_mall_id = "synthetic-mall"
    app.state.settings.cafe24_client_id = "synthetic-client-id"
    oauth_fixture_value = "synthetic-client-secret"
    app.state.settings.cafe24_client_secret = oauth_fixture_value
    app.state.settings.cafe24_redirect_uri = (
        "https://example.test/internal/cafe24/oauth/callback"
    )

    app.state.cafe24_oauth_state = "synthetic-state-value"
    app.state.cafe24_oauth_state_created_at = datetime.now(UTC)
    def fake_exchange_authorization_code(**kwargs):
        return {
            "access_token": "synthetic-access-value",
            "expires_at": "2026-09-07T12:00:00+00:00",
            "refresh_token": "synthetic-refresh-value",
            "refresh_token_expires_at": (
                "2026-09-20T12:00:00+00:00"
            ),
            "mall_id": "synthetic-mall",
            "shop_no": "1",
            "scopes": [
                "mall.read_product",
                "mall.read_order",
                "mall.read_category",
                "mall.read_community",
                "mall.write_product",
            ],
        }

    monkeypatch.setattr(
        cafe24_oauth,
        "_exchange_authorization_code",
        fake_exchange_authorization_code,
    )

    client = TestClient(app)

    response = client.get(
        "/internal/cafe24/oauth/callback",
        params={
            "code": "synthetic-code-value",
            "state": "synthetic-state-value",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "CAFE24_OAUTH_SCOPE_INVALID"

    assert app.state.cafe24_access_token is None
    assert app.state.cafe24_refresh_token is None

def test_cafe24_oauth_callback_rejects_expired_state() -> None:
    app = create_app()

    app.state.cafe24_oauth_state = "synthetic-state-value"
    app.state.cafe24_oauth_state_created_at = (
        datetime.now(UTC) - timedelta(minutes=11)
    )

    client = TestClient(app)

    response = client.get(
        "/internal/cafe24/oauth/callback",
        params={
            "code": "synthetic-code-value",
            "state": "synthetic-state-value",
        },
    )

    assert response.status_code == 403
    assert (
        response.json()["detail"]["code"]
        == "CAFE24_OAUTH_STATE_EXPIRED"
    )

    assert app.state.cafe24_oauth_state is None
    assert app.state.cafe24_oauth_state_created_at is None

def test_cafe24_oauth_start_requests_only_required_read_scopes() -> None:
    app = create_app()

    app.state.settings.cafe24_mall_id = "synthetic-mall"
    app.state.settings.cafe24_client_id = "synthetic-client-id"
    app.state.settings.cafe24_client_secret = (
        "synthetic-client-secret"
    )
    app.state.settings.cafe24_redirect_uri = (
        "https://example.test/internal/cafe24/oauth/callback"
    )

    client = TestClient(app)

    response = client.get(
        "/internal/cafe24/oauth/start"
    )

    assert response.status_code == 200

    authorization_url = response.json()[
        "authorization_url"
    ]

    assert "mall.read_product" in authorization_url
    assert "mall.read_order" in authorization_url
    assert "mall.read_category" in authorization_url
    assert "mall.read_community" in authorization_url

    assert "mall.write_" not in authorization_url

    assert app.state.cafe24_oauth_state is not None
    assert (
        app.state.cafe24_oauth_state_created_at
        is not None
    )

def test_cafe24_oauth_refresh_replaces_tokens(
    monkeypatch,
) -> None:
    app = create_app()

    app.state.settings.cafe24_mall_id = "synthetic-mall"
    app.state.settings.cafe24_client_id = "synthetic-client-id"
    app.state.settings.cafe24_client_secret = (
        "synthetic-client-secret"
    )
    app.state.settings.cafe24_redirect_uri = (
        "https://example.test/internal/cafe24/oauth/callback"
    )

    app.state.cafe24_refresh_token = "old-refresh-value"
    app.state.cafe24_refresh_token_expires_at = (
        datetime.now(UTC) + timedelta(days=1)
    )

    def fake_refresh_access_token(**kwargs):
        assert kwargs["refresh_token"] == "old-refresh-value"

        return {
            "access_token": "new-access-value",
            "expires_at": "2026-09-07T12:00:00+00:00",
            "refresh_token": "new-refresh-value",
            "refresh_token_expires_at": (
                "2026-09-20T12:00:00+00:00"
            ),
            "mall_id": "synthetic-mall",
            "shop_no": "1",
            "scopes": [
                "mall.read_product",
                "mall.read_order",
                "mall.read_category",
                "mall.read_community",
            ],
        }

    monkeypatch.setattr(
        cafe24_oauth,
        "_refresh_access_token",
        fake_refresh_access_token,
    )

    client = TestClient(app)

    response = client.post(
        "/internal/cafe24/oauth/refresh"
    )

    assert response.status_code == 200

    assert (
        app.state.cafe24_access_token
        == "new-access-value"
    )
    assert (
        app.state.cafe24_refresh_token
        == "new-refresh-value"
    )

    assert "new-access-value" not in response.text
    assert "new-refresh-value" not in response.text

def test_cafe24_oauth_refresh_rejects_expired_refresh_token() -> None:
    app = create_app()

    app.state.settings.cafe24_mall_id = "synthetic-mall"
    app.state.settings.cafe24_client_id = "synthetic-client-id"
    app.state.settings.cafe24_client_secret = (
        "synthetic-client-secret"
    )
    app.state.settings.cafe24_redirect_uri = (
        "https://example.test/internal/cafe24/oauth/callback"
    )

    app.state.cafe24_refresh_token = "expired-refresh-value"
    app.state.cafe24_refresh_token_expires_at = (
        datetime.now(UTC) - timedelta(seconds=1)
    )

    client = TestClient(app)

    response = client.post(
        "/internal/cafe24/oauth/refresh"
    )

    assert response.status_code == 403
    assert (
        response.json()["detail"]["code"]
        == "CAFE24_OAUTH_REFRESH_TOKEN_EXPIRED"
    )

import pytest
from fastapi import HTTPException
from starlette.requests import Request


@pytest.mark.parametrize("shop_no", [None, True, False, 0, -1, 1.5, "1.0", "-1", [], {}, "synthetic"])
def test_oauth_invalid_shop_metadata_is_not_stored(shop_no):
    app = create_app()
    app.state.settings.cafe24_mall_id = "synthetic-mall"
    data = {
        "access_token": "synthetic-access", "refresh_token": "synthetic-refresh",
        "scopes": list(cafe24_oauth.REQUIRED_READ_SCOPES), "mall_id": "synthetic-mall",
        "expires_at": "2099-01-01T00:00:00Z", "refresh_token_expires_at": "2099-02-01T00:00:00Z",
        "shop_no": shop_no,
    }
    with pytest.raises(HTTPException) as caught:
        cafe24_oauth._store_oauth_token_metadata(Request({"type": "http", "app": app}), data)
    assert caught.value.status_code == 502
    assert app.state.cafe24_access_token is None
    assert "synthetic-access" not in str(caught.value)


@pytest.mark.parametrize("missing", sorted(cafe24_oauth.REQUIRED_READ_SCOPES))
def test_oauth_each_required_scope_is_fail_closed(missing):
    with pytest.raises(HTTPException) as caught:
        cafe24_oauth._validate_scopes(list(cafe24_oauth.REQUIRED_READ_SCOPES - {missing}))
    assert caught.value.status_code == 403


def test_oauth_scopes_match_adapter_contract():
    from backend.app.adapters.providers.cafe24.adapter import Cafe24Adapter
    assert cafe24_oauth.REQUIRED_READ_SCOPES == {
        Cafe24Adapter.PRODUCT_SCOPE, Cafe24Adapter.ORDER_SCOPE,
        Cafe24Adapter.CATEGORY_SCOPE, Cafe24Adapter.COMMUNITY_SCOPE,
    }


def test_oauth_callback_query_values_are_not_logged(caplog) -> None:
    synthetic_code = "synthetic-oauth-code-for-log-test"
    synthetic_state = "synthetic-oauth-state-for-log-test"
    app = create_app()
    caplog.set_level(logging.INFO)
    # TestClient's bundled client logger is not the production httpx namespace.
    logging.getLogger("httpx2").setLevel(logging.WARNING)

    response = TestClient(app).get(
        "/internal/cafe24/oauth/callback",
        params={"code": synthetic_code, "state": synthetic_state},
    )

    assert response.status_code == 409
    assert synthetic_code not in caplog.text
    assert synthetic_state not in caplog.text