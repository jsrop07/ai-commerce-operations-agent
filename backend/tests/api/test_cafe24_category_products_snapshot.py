"""Day 9 Cafe24 current category-product snapshot API tests."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from backend.app.api import cafe24_bootstrap
from backend.app.core.config import Settings
from backend.app.main import create_app

TOKEN = "synthetic-access-secret"
PATH = (
    "/internal/cafe24/bootstrap/"
    "category-products/snapshot"
)


def app_with_oauth(tmp_path):
    app = create_app(
        Settings(
            cafe24_protected_data_dir=(
                str(tmp_path)
            ),
        )
    )
    app.state.cafe24_access_token = TOKEN
    app.state.cafe24_authorized_mall_id = (
        "synthetic-mall"
    )
    app.state.cafe24_shop_no = "1"
    app.state.cafe24_access_token_expires_at = (
        datetime.now(UTC)
        + timedelta(hours=1)
    )
    app.state.cafe24_approved_scopes = {
        "mall.read_product",
    }
    return app


def test_category_products_snapshot_rejects_missing_token(
    tmp_path,
) -> None:
    app = app_with_oauth(tmp_path)
    app.state.cafe24_access_token = None

    response = TestClient(app).post(
        PATH,
        params={"category_no": 56},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == (
        "CAFE24_ACCESS_TOKEN_MISSING"
    )


def test_category_products_snapshot_rejects_missing_mall_id(
    tmp_path,
) -> None:
    app = app_with_oauth(tmp_path)
    app.state.cafe24_authorized_mall_id = None

    response = TestClient(app).post(
        PATH,
        params={"category_no": 56},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == (
        "CAFE24_MALL_ID_MISSING"
    )


def test_category_products_snapshot_requires_read_product_scope(
    tmp_path,
) -> None:
    app = app_with_oauth(tmp_path)
    app.state.cafe24_approved_scopes = {
        "mall.read_order",
    }

    response = TestClient(app).post(
        PATH,
        params={"category_no": 56},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == (
        "CAFE24_READ_PRODUCT_SCOPE_MISSING"
    )


def test_category_products_snapshot_uses_mocked_get_and_returns_aggregate_only(
    tmp_path,
    monkeypatch,
) -> None:
    app = app_with_oauth(tmp_path)
    calls: list[dict[str, object]] = []

    def request_json(**kwargs: object) -> dict[str, object]:
        calls.append(kwargs)
        return {
            "products": [
                {
                    "product_no": 101,
                    "product_name": (
                        "RAW PRODUCT DATA"
                    ),
                    "customer_name": (
                        "RAW CUSTOMER DATA"
                    ),
                },
                {
                    "product_no": 202,
                    "product_name": (
                        "RAW PRODUCT DATA 2"
                    ),
                },
            ]
        }

    monkeypatch.setattr(
        cafe24_bootstrap,
        "_request_json",
        request_json,
    )

    response = TestClient(app).post(
        PATH,
        params={
            "category_no": 56,
            "display_group": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["category_no"] == 56
    assert payload["display_group"] == 1
    assert payload[
        "product_relation_count"
    ] == 2
    assert payload["sanitized_count"] == 2
    assert payload[
        "source_classification"
    ] == "LIVE_READ"
    assert payload["evidence_type"] == (
        "CURRENT_CATEGORY_EVIDENCE"
    )
    assert payload["as_of"]
    assert payload["read_succeeded"] is True
    assert payload["batch_id"].startswith(
        "category-products-snapshot-"
    )
    assert payload[
        "external_write_count"
    ] == 0
    assert payload["warning"] is None
    assert payload["reason"] == (
        "CURRENT_CATEGORY_PRODUCT_"
        "SNAPSHOT_CAPTURED"
    )

    assert len(calls) == 1
    assert calls[0]["method"] == "GET"
    assert calls[0]["params"] == {
        "display_group": 1,
        "limit": 50_000,
    }
    response_text = response.text
    for forbidden in (
        TOKEN,
        "Authorization",
        "RAW PRODUCT DATA",
        "RAW CUSTOMER DATA",
        '\"products\":',
    ):
        assert forbidden not in response_text


def test_category_products_snapshot_rejects_invalid_category_no(
    tmp_path,
) -> None:
    app = app_with_oauth(tmp_path)

    response = TestClient(app).post(
        PATH,
        params={"category_no": 0},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == (
        "CAFE24_CATEGORY_NO_INVALID"
    )
