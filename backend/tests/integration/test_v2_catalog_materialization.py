"""Integration checks for the fixed V2 catalog materialization."""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.core.config import get_settings
from backend.app.db.session_v2 import (
    build_v2_engine,
    build_v2_session_factory,
)
from backend.app.main import app
from backend.app.services.catalog_v2_read import (
    get_catalog_summary,
    list_catalog_products,
)


EXPECTED_PRODUCTS = 2167
EXPECTED_CATEGORIES = 123
EXPECTED_RELATIONS = 2165


def test_v2_catalog_summary_matches_materialized_snapshot() -> None:
    client = TestClient(app)

    response = client.get(
        "/api/v1/catalog/summary"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["data"]["product_count"] == EXPECTED_PRODUCTS
    assert body["data"]["category_count"] == EXPECTED_CATEGORIES
    assert (
        body["data"]["product_category_count"]
        == EXPECTED_RELATIONS
    )
    assert body["data"]["source"] == "commerce_ops_v2"
    assert body["as_of"] is not None


def test_v2_catalog_products_returns_paginated_rows() -> None:
    client = TestClient(app)

    response = client.get(
        "/api/v1/catalog/products",
        params={
            "limit": 3,
            "offset": 0,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert len(body["data"]) == 3

    first = body["data"][0]

    assert isinstance(
        first["cafe24_product_no"],
        int,
    )
    assert first["product_code"]
    assert first["product_name"]
    assert isinstance(
        first["category_nos"],
        list,
    )


def test_v2_catalog_products_rejects_limit_over_200() -> None:
    client = TestClient(app)

    response = client.get(
        "/api/v1/catalog/products",
        params={
            "limit": 201,
            "offset": 0,
        },
    )

    assert response.status_code == 422


def test_v2_catalog_service_is_tenant_scoped() -> None:
    settings = get_settings()

    assert settings.postgres_v2_url
    assert settings.v2_tenant_id

    engine = build_v2_engine(
        settings.postgres_v2_url
    )
    session_factory = build_v2_session_factory(
        engine
    )

    other_tenant_id = uuid4()

    try:
        with session_factory() as session:
            real_summary = get_catalog_summary(
                session,
                tenant_id=settings.v2_tenant_id,
            )

            other_summary = get_catalog_summary(
                session,
                tenant_id=other_tenant_id,
            )

            other_products = list_catalog_products(
                session,
                tenant_id=other_tenant_id,
                limit=10,
            )

        assert real_summary.product_count == EXPECTED_PRODUCTS

        assert other_summary.product_count == 0
        assert other_summary.category_count == 0
        assert other_summary.product_category_count == 0

        assert other_products == []

    finally:
        engine.dispose()