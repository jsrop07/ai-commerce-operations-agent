from fastapi.testclient import TestClient

from backend.app.api import cafe24_oauth
from backend.app.main import create_app


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

    def fake_exchange_authorization_code(**kwargs):
        return {
            "access_token": "synthetic-access-value",
            "refresh_token": "synthetic-refresh-value",
            "scopes": [
                "mall.read_product",
                "mall.read_order",
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
    }

    # 실제 Token 값은 HTTP 응답에 노출되면 안 된다.
    assert "synthetic-access-value" not in response.text
    assert "synthetic-refresh-value" not in response.text

    assert app.state.cafe24_oauth_state is None
    assert app.state.cafe24_authorization_code is None
    assert app.state.cafe24_access_token == "synthetic-access-value"
    assert app.state.cafe24_refresh_token == "synthetic-refresh-value"


def test_cafe24_oauth_callback_rejects_wrong_state() -> None:
    app = create_app()
    app.state.cafe24_oauth_state = "expected-state-value"

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

    def fake_exchange_authorization_code(**kwargs):
        return {
            "access_token": "synthetic-access-value",
            "refresh_token": "synthetic-refresh-value",
            "scopes": [
                "mall.read_product",
                "mall.read_order",
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