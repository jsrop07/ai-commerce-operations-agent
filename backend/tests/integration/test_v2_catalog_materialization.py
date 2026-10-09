"""Integration checks for the fixed V2 catalog materialization."""

from __future__ import annotations

from contextlib import nullcontext
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.app.core.config import Environment, get_settings
from backend.app.db.session_v2 import (
    build_v2_engine,
    build_v2_session_factory,
)
from backend.app.main import create_app
from backend.app.models_v2.catalog import CategoryV2, ProductCategoryV2, ProductV2
from backend.app.services.catalog_v2_read import (
    CatalogProductFilters,
    CatalogV2Product,
    get_catalog_summary,
    list_catalog_categories,
    list_catalog_products,
)

EXPECTED_PRODUCTS = 150
EXPECTED_CATEGORIES = 41
EXPECTED_RELATIONS = 157

# This snapshot belongs to the active DEMO V2 tenant. The process default is LOCAL.
app = create_app(get_settings().model_copy(update={"environment": Environment.DEMO}))


@pytest.fixture(scope="module")
def catalog_session():
    settings = get_settings()
    engine = build_v2_engine(settings.postgres_v2_url)
    try:
        with build_v2_session_factory(engine)() as session:
            yield session
    finally:
        engine.dispose()


def products_data(**params):
    response = TestClient(app).get("/api/v1/catalog/products", params=params)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def categories_data(**params):
    response = TestClient(app).get("/api/v1/catalog/categories", params=params)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def hierarchy_branch(session):
    tenant_id = get_settings().v2_tenant_id
    leaf = session.scalars(
        select(CategoryV2)
        .join(ProductCategoryV2,
              (ProductCategoryV2.tenant_id == CategoryV2.tenant_id)
              & (ProductCategoryV2.category_id == CategoryV2.id))
        .where(CategoryV2.tenant_id == tenant_id, CategoryV2.category_depth == 3)
        .limit(1)
    ).one()
    middle = session.get(CategoryV2, leaf.parent_category_id)
    root = session.get(CategoryV2, middle.parent_category_id)
    assert (root.category_depth, middle.category_depth, leaf.category_depth) == (1, 2, 3)
    return root, middle, leaf


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
    assert body["data"]["source_as_of"] is None
    assert datetime.fromisoformat(body["as_of"]).tzinfo is not None


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

    assert body["data"]["total"] == EXPECTED_PRODUCTS
    assert body["data"]["limit"] == 3
    assert body["data"]["offset"] == 0
    assert body["data"]["source_as_of"] is None
    assert datetime.fromisoformat(body["as_of"]).tzinfo is not None
    assert len(body["data"]["items"]) == 3

    numbers = [item["cafe24_product_no"] for item in body["data"]["items"]]
    assert numbers == sorted(numbers, reverse=True)
    first = body["data"]["items"][0]

    assert isinstance(
        first["cafe24_product_no"],
        int,
    )
    assert first["product_code"]
    assert first["product_name"]
    assert isinstance(first["operational"], bool)
    assert isinstance(
        first["category_nos"],
        list,
    )
    assert [category["cafe24_category_no"] for category in first["categories"]] == first["category_nos"]


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


def test_v2_catalog_products_beyond_total_is_empty() -> None:
    response = TestClient(app).get(
        "/api/v1/catalog/products", params={"limit": 7, "offset": EXPECTED_PRODUCTS}
    )
    assert response.status_code == 200
    assert response.json()["data"] == {
        "items": [], "total": EXPECTED_PRODUCTS, "limit": 7,
        "offset": EXPECTED_PRODUCTS, "source_as_of": None,
    }


def test_v2_catalog_desc_limit_offset_and_last_page() -> None:
    first = products_data(limit=50, offset=0)
    second = products_data(limit=50, offset=50)
    last = products_data(limit=50, offset=EXPECTED_PRODUCTS - 17)
    assert len(first["items"]) == len(second["items"]) == 50
    assert first["items"][0]["cafe24_product_no"] > first["items"][-1]["cafe24_product_no"]
    assert first["items"][-1]["cafe24_product_no"] > second["items"][0]["cafe24_product_no"]
    assert len(last["items"]) == 17
    assert last["total"] == EXPECTED_PRODUCTS


def test_v2_catalog_searches_product_fields(catalog_session) -> None:
    tenant_id = get_settings().v2_tenant_id
    product = catalog_session.scalars(
        select(ProductV2).where(ProductV2.tenant_id == tenant_id, ProductV2.custom_product_code.is_not(None))
        .order_by(ProductV2.cafe24_product_no.desc()).limit(1)
    ).one()
    for query in (
        product.product_name[:100], product.product_code,
        product.product_code.lower(),
        product.custom_product_code, str(product.cafe24_product_no),
    ):
        data = products_data(q=query, product_no_min=product.cafe24_product_no,
                             product_no_max=product.cafe24_product_no)
        assert data["total"] == 1
        assert data["items"][0]["id"] == str(product.id)


def test_v2_catalog_searches_category_number_and_name(catalog_session) -> None:
    tenant_id = get_settings().v2_tenant_id
    rows = catalog_session.execute(
        select(ProductV2, CategoryV2)
        .join(ProductCategoryV2,
              (ProductCategoryV2.tenant_id == ProductV2.tenant_id)
              & (ProductCategoryV2.product_id == ProductV2.id))
        .join(CategoryV2,
              (CategoryV2.tenant_id == ProductCategoryV2.tenant_id)
              & (CategoryV2.id == ProductCategoryV2.category_id))
        .where(ProductV2.tenant_id == tenant_id)
    ).all()
    number_row = next((product, category) for product, category in rows
                      if str(category.cafe24_category_no) not in
                      f"{product.cafe24_product_no} {product.product_name} {product.product_code} {product.custom_product_code}")
    name_row = next((product, category) for product, category in rows
                    if category.category_name.lower() not in
                    f"{product.product_name} {product.product_code} {product.custom_product_code}".lower())
    for product, category, query in (
        (*number_row, str(number_row[1].cafe24_category_no)),
        (*name_row, name_row[1].category_name),
    ):
        data = products_data(q=query, product_no_min=product.cafe24_product_no,
                             product_no_max=product.cafe24_product_no)
        assert data["total"] == 1
        assert {item["cafe24_category_no"] for item in data["items"][0]["categories"]} >= {
            category.cafe24_category_no
        }


@pytest.mark.parametrize("field", ["display_status", "selling_status", "sold_out"])
def test_v2_catalog_status_filters_and_filtered_total(catalog_session, field: str) -> None:
    tenant_id = get_settings().v2_tenant_id
    column = getattr(ProductV2, field)
    for value in ((False, True) if field == "sold_out" else ("F", "T")):
        data = products_data(**{field: value}, limit=20)
        expected = catalog_session.scalar(
            select(func.count()).select_from(ProductV2)
            .where(ProductV2.tenant_id == tenant_id, column == value)
        )
        assert data["total"] == expected
        assert all(item[field] == value for item in data["items"])


def test_v2_catalog_price_and_product_number_ranges(catalog_session) -> None:
    tenant_id = get_settings().v2_tenant_id
    price = catalog_session.scalar(
        select(ProductV2.sale_price).where(ProductV2.tenant_id == tenant_id,
                                           ProductV2.sale_price.is_not(None)).limit(1)
    )
    assert isinstance(price, Decimal)
    priced = products_data(price_min=price, price_max=price, limit=200)
    expected_price_count = catalog_session.scalar(
        select(func.count()).select_from(ProductV2)
        .where(ProductV2.tenant_id == tenant_id, ProductV2.sale_price == price)
    )
    assert priced["total"] == expected_price_count
    assert all(Decimal(item["sale_price"]) == price for item in priced["items"])

    number = catalog_session.scalar(
        select(func.max(ProductV2.cafe24_product_no)).where(ProductV2.tenant_id == tenant_id)
    )
    one = products_data(product_no_min=number, product_no_max=number)
    assert one["total"] == 1
    assert one["items"][0]["cafe24_product_no"] == number
    empty = products_data(product_no_min=number + 1)
    assert empty["total"] == 0 and empty["items"] == []


def test_v2_catalog_combined_search_and_filters(catalog_session) -> None:
    tenant_id = get_settings().v2_tenant_id
    product = catalog_session.scalars(
        select(ProductV2).where(ProductV2.tenant_id == tenant_id, ProductV2.sale_price.is_not(None))
        .order_by(ProductV2.cafe24_product_no.desc()).limit(1)
    ).one()
    data = products_data(
        q=product.product_code, display_status=product.display_status,
        selling_status=product.selling_status, sold_out=product.sold_out,
        price_min=product.sale_price, price_max=product.sale_price,
        product_no_min=product.cafe24_product_no,
        product_no_max=product.cafe24_product_no,
    )
    assert data["total"] == 1
    assert data["items"][0]["id"] == str(product.id)


@pytest.mark.parametrize("params", [
    {"price_min": 20, "price_max": 10},
    {"product_no_min": 20, "product_no_max": 10},
    {"display_status": "UNKNOWN"},
    {"selling_status": "UNKNOWN"},
    {"sold_out": "maybe"},
    {"q": "   "},
])
def test_v2_catalog_rejects_invalid_filters(params: dict) -> None:
    assert TestClient(app).get("/api/v1/catalog/products", params=params).status_code == 422


def test_v2_catalog_categories_follow_real_relations(catalog_session) -> None:
    tenant_id = get_settings().v2_tenant_id
    relation_counts = (
        select(ProductCategoryV2.product_id)
        .where(ProductCategoryV2.tenant_id == tenant_id)
        .group_by(ProductCategoryV2.product_id)
        .having(func.count() > 1)
    )
    multi_id = catalog_session.scalar(relation_counts.limit(1))
    assert multi_id is not None
    multi_product = catalog_session.get(ProductV2, multi_id)
    multi = products_data(product_no_min=multi_product.cafe24_product_no,
                          product_no_max=multi_product.cafe24_product_no)["items"][0]
    expected_categories = catalog_session.execute(
        select(CategoryV2.cafe24_category_no, CategoryV2.category_name)
        .join(ProductCategoryV2,
              (ProductCategoryV2.tenant_id == CategoryV2.tenant_id)
              & (ProductCategoryV2.category_id == CategoryV2.id))
        .where(ProductCategoryV2.tenant_id == tenant_id,
               ProductCategoryV2.product_id == multi_id)
        .order_by(CategoryV2.cafe24_category_no)
    ).all()
    assert len(expected_categories) > 1
    assert multi["categories"] == [
        {"cafe24_category_no": number, "category_name": name}
        for number, name in expected_categories
    ]
    assert multi["category_nos"] == [number for number, _ in expected_categories]

    no_relation = ~select(ProductCategoryV2.product_id).where(
        ProductCategoryV2.tenant_id == ProductV2.tenant_id,
        ProductCategoryV2.product_id == ProductV2.id,
    ).exists()
    unlinked = catalog_session.scalars(
        select(ProductV2).where(ProductV2.tenant_id == tenant_id, no_relation).limit(1)
    ).one()
    item = products_data(product_no_min=unlinked.cafe24_product_no,
                         product_no_max=unlinked.cafe24_product_no)["items"][0]
    assert item["categories"] == []
    assert item["category_nos"] == []


def test_v2_catalog_hierarchy_lists_only_real_children(catalog_session) -> None:
    tenant_id = get_settings().v2_tenant_id
    root, middle, leaf = hierarchy_branch(catalog_session)
    roots = categories_data(depth=1)
    assert len(roots) == 7
    assert all(item["category_depth"] == 1 and item["parent_category_id"] is None for item in roots)
    assert str(root.id) in {item["id"] for item in roots}

    second = categories_data(depth=2, parent_category_id=str(root.id))
    actual_second = catalog_session.scalars(
        select(CategoryV2).where(CategoryV2.tenant_id == tenant_id,
                                 CategoryV2.parent_category_id == root.id,
                                 CategoryV2.category_depth == 2)
    ).all()
    assert {item["id"] for item in second} == {str(item.id) for item in actual_second}
    assert all(item["parent_category_id"] == str(root.id) for item in second)
    assert str(middle.id) in {item["id"] for item in second}

    third = categories_data(depth=3, parent_category_id=str(middle.id))
    actual_third = catalog_session.scalars(
        select(CategoryV2).where(CategoryV2.tenant_id == tenant_id,
                                 CategoryV2.parent_category_id == middle.id,
                                 CategoryV2.category_depth == 3)
    ).all()
    assert {item["id"] for item in third} == {str(item.id) for item in actual_third}
    assert all(item["parent_category_id"] == str(middle.id) for item in third)
    assert str(leaf.id) in {item["id"] for item in third}
    assert categories_data(depth=3, parent_category_id=str(leaf.id)) == []
    assert categories_data(depth=2, parent_category_id=str(uuid4())) == []


@pytest.mark.parametrize("params", [
    {"depth": 0}, {"depth": 4}, {"depth": 2}, {"depth": 3},
    {"depth": 1, "parent_category_id": str(uuid4())},
    {"depth": 2, "parent_category_id": "not-a-uuid"},
])
def test_v2_catalog_hierarchy_rejects_invalid_queries(params: dict) -> None:
    assert TestClient(app).get("/api/v1/catalog/categories", params=params).status_code == 422


def test_v2_catalog_category_filter_includes_actual_descendants(catalog_session) -> None:
    tenant_id = get_settings().v2_tenant_id
    root, middle, leaf = hierarchy_branch(catalog_session)
    categories = catalog_session.scalars(
        select(CategoryV2).where(CategoryV2.tenant_id == tenant_id)
    ).all()
    by_id = {category.id: category for category in categories}
    for selected in (root, middle, leaf):
        descendant_ids = {
            category.id for category in categories
            if category.id == selected.id
            or category.parent_category_id == selected.id
            or (category.parent_category_id is not None
                and by_id[category.parent_category_id].parent_category_id == selected.id)
        }
        descendant_nos = {by_id[category_id].cafe24_category_no for category_id in descendant_ids}
        expected_total = catalog_session.scalar(
            select(func.count(func.distinct(ProductCategoryV2.product_id)))
            .where(ProductCategoryV2.tenant_id == tenant_id,
                   ProductCategoryV2.category_id.in_(descendant_ids))
        )
        data = products_data(category_no=selected.cafe24_category_no, limit=200)
        assert data["total"] == expected_total
        assert all(descendant_nos.intersection(item["category_nos"]) for item in data["items"])
    assert products_data(category_no=999999999)["total"] == 0
    assert products_data(category_no=999999999)["items"] == []


def test_v2_catalog_numeric_q_matches_exact_price_and_product_number(catalog_session) -> None:
    tenant_id = get_settings().v2_tenant_id
    product = catalog_session.scalars(
        select(ProductV2).where(ProductV2.tenant_id == tenant_id,
                                ProductV2.sale_price.is_not(None))
        .order_by(ProductV2.cafe24_product_no.desc()).limit(1)
    ).one()
    for query in (f"00{product.sale_price}", f"0{product.cafe24_product_no}"):
        data = products_data(q=query, product_no_min=product.cafe24_product_no,
                             product_no_max=product.cafe24_product_no)
        assert data["total"] == 1
        assert data["items"][0]["id"] == str(product.id)


@pytest.mark.parametrize("sort_by", ["cafe24_product_no", "sale_price"])
@pytest.mark.parametrize("sort_dir", ["asc", "desc"])
def test_v2_catalog_sort_is_stable_before_pagination(catalog_session, sort_by: str, sort_dir: str) -> None:
    first = products_data(sort_by=sort_by, sort_dir=sort_dir, limit=50, offset=0)
    second = products_data(sort_by=sort_by, sort_dir=sort_dir, limit=50, offset=50)
    assert first["total"] == second["total"] == EXPECTED_PRODUCTS
    assert len(first["items"]) == len(second["items"]) == 50
    assert not ({item["id"] for item in first["items"]} & {item["id"] for item in second["items"]})
    values = [item[sort_by] for item in first["items"] + second["items"]]
    if sort_by == "sale_price":
        nonnull = [Decimal(value) for value in values if value is not None]
        assert nonnull == sorted(nonnull, reverse=sort_dir == "desc")
        assert all(value is not None for value in values[:len(nonnull)])
        rows = first["items"] + second["items"]
        for left, right in zip(rows, rows[1:]):
            if left["sale_price"] == right["sale_price"]:
                assert left["cafe24_product_no"] > right["cafe24_product_no"]
    else:
        assert values == sorted(values, reverse=sort_dir == "desc")


@pytest.mark.parametrize("sort_dir", ["asc", "desc"])
def test_v2_catalog_null_prices_are_last(catalog_session, sort_dir: str) -> None:
    tenant_id = get_settings().v2_tenant_id
    largest_no = catalog_session.scalar(
        select(func.max(ProductV2.cafe24_product_no)).where(ProductV2.tenant_id == tenant_id)
    )
    with catalog_session.begin_nested() as savepoint:
        catalog_session.add(ProductV2(
            id=uuid4(), tenant_id=tenant_id, cafe24_product_no=largest_no + 1,
            product_name="C13 null price sort test", product_code="C13_NULL_PRICE_SORT_TEST",
            custom_product_code=None, sale_price=None, display_status="T",
            selling_status="T", sold_out=False, operational=True, source_as_of=None,
        ))
        catalog_session.flush()
        first = list_catalog_products(
            catalog_session, tenant_id=tenant_id, limit=1,
            sort_by="sale_price", sort_dir=sort_dir,
        )
        last = list_catalog_products(
            catalog_session, tenant_id=tenant_id, limit=1, offset=EXPECTED_PRODUCTS,
            sort_by="sale_price", sort_dir=sort_dir,
        )
        assert first[0].sale_price is not None
        assert last[0].sale_price is None
        savepoint.rollback()


def test_v2_catalog_combines_q_category_and_status_filters(catalog_session) -> None:
    root, _, leaf = hierarchy_branch(catalog_session)
    tenant_id = get_settings().v2_tenant_id
    product = catalog_session.scalars(
        select(ProductV2)
        .join(ProductCategoryV2,
              (ProductCategoryV2.tenant_id == ProductV2.tenant_id)
              & (ProductCategoryV2.product_id == ProductV2.id))
        .where(ProductV2.tenant_id == tenant_id, ProductCategoryV2.category_id == leaf.id)
        .limit(1)
    ).one()
    data = products_data(
        q=product.product_code, category_no=root.cafe24_category_no,
        display_status=product.display_status, selling_status=product.selling_status,
        sold_out=product.sold_out,
        product_no_min=product.cafe24_product_no,
        product_no_max=product.cafe24_product_no,
    )
    assert data["total"] == 1
    assert data["items"][0]["id"] == str(product.id)


@pytest.mark.parametrize("params", [
    {"sort_by": "product_name"}, {"sort_dir": "up"},
    {"category_no": -1},
])
def test_v2_catalog_rejects_invalid_sort_and_category(params: dict) -> None:
    assert TestClient(app).get("/api/v1/catalog/products", params=params).status_code == 422


def test_v2_catalog_hierarchy_and_category_filter_are_tenant_scoped(catalog_session) -> None:
    root, _, _ = hierarchy_branch(catalog_session)
    other_tenant_id = uuid4()
    assert list_catalog_categories(catalog_session, tenant_id=other_tenant_id, depth=1) == []
    assert list_catalog_products(
        catalog_session, tenant_id=other_tenant_id,
        filters=CatalogProductFilters(category_no=root.cafe24_category_no),
    ) == []


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 201}, {"offset": -1}])
def test_v2_catalog_products_rejects_invalid_pagination(params: dict) -> None:
    assert TestClient(app).get("/api/v1/catalog/products", params=params).status_code == 422


@pytest.mark.parametrize("environment", [Environment.LOCAL, Environment.TEST])
def test_v2_catalog_local_and_test_reject_demo_tenant(
    monkeypatch, environment: Environment,
) -> None:
    monkeypatch.setattr(app.state.settings, "environment", environment)
    response = TestClient(app).get("/api/v1/catalog/summary")
    assert response.status_code == 403
    assert response.json()["detail"] == "V2_TENANT_FORBIDDEN"


@pytest.mark.parametrize("path", ["summary", "products"])
@pytest.mark.parametrize("environment", [
    Environment.PRODUCTION_READ, Environment.PILOT_SHADOW, Environment.PILOT_APPROVED,
])
def test_v2_catalog_rejects_other_environments(
    monkeypatch, path: str, environment: Environment
) -> None:
    monkeypatch.setattr(app.state.settings, "environment", environment)
    response = TestClient(app).get(
        f"/api/v1/catalog/{path}", params={"environment": "LOCAL", "mode": "LOCAL"}
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "V2_CATALOG_ENVIRONMENT_FORBIDDEN"


@pytest.mark.parametrize("path", ["summary", "products"])
def test_v2_catalog_requires_database(monkeypatch, path: str) -> None:
    monkeypatch.setattr(app.state, "v2_db_session_factory", None)
    response = TestClient(app).get(f"/api/v1/catalog/{path}")
    assert response.status_code == 503
    assert response.json()["detail"] == "V2_DATABASE_NOT_CONFIGURED"


@pytest.mark.parametrize("path", ["summary", "products"])
def test_v2_catalog_requires_configured_tenant(monkeypatch, path: str) -> None:
    monkeypatch.setattr(app.state.settings, "v2_tenant_id", None)
    response = TestClient(app).get(f"/api/v1/catalog/{path}")
    assert response.status_code == 503
    assert response.json()["detail"] == "V2_TENANT_NOT_CONFIGURED"


@pytest.mark.parametrize("path", ["summary", "products"])
def test_v2_catalog_unknown_tenant_cannot_read(monkeypatch, path: str) -> None:
    monkeypatch.setattr(app.state.settings, "environment", Environment.LOCAL)
    monkeypatch.setattr(app.state.settings, "v2_tenant_id", uuid4())
    response = TestClient(app).get(f"/api/v1/catalog/{path}")
    assert response.status_code == 503
    assert response.json()["detail"] == "V2_TENANT_NOT_FOUND"


def test_v2_catalog_preserves_nullable_product_fields(monkeypatch) -> None:
    from backend.app.api import catalog_v2

    product = CatalogV2Product(
        id=uuid4(), cafe24_product_no=1, product_name="test", product_code="P1",
        custom_product_code=None, sale_price=None, display_status="T",
        selling_status="T", sold_out=False, operational=True, category_nos=(), categories=(),source_as_of=None,
    )
    monkeypatch.setattr(catalog_v2, "count_catalog_products", lambda *args, **kwargs: 1)
    monkeypatch.setattr(catalog_v2, "list_catalog_products", lambda *args, **kwargs: [product])
    response = TestClient(app).get("/api/v1/catalog/products", params={"limit": 1})
    assert response.status_code == 200
    item = response.json()["data"]["items"][0]
    assert item["custom_product_code"] is None
    assert item["sale_price"] is None


@pytest.mark.parametrize("tenant_fields", [
    {"name": "other"}, {"environment": "DEMO"}, {"status": "INACTIVE"},
])
def test_v2_catalog_rejects_non_bootstrap_tenant(monkeypatch, tenant_fields: dict) -> None:
    monkeypatch.setattr(app.state.settings, "environment", Environment.LOCAL)
    tenant = SimpleNamespace(
        id=app.state.settings.v2_tenant_id,
        name="commerce_ops_local", environment="LOCAL", status="ACTIVE",
    )
    for field, value in tenant_fields.items():
        setattr(tenant, field, value)
    session = SimpleNamespace(get=lambda *args: tenant)
    monkeypatch.setattr(app.state, "v2_db_session_factory", lambda: nullcontext(session))
    response = TestClient(app).get("/api/v1/catalog/summary")
    assert response.status_code == 403
    assert response.json()["detail"] == "V2_TENANT_FORBIDDEN"


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
