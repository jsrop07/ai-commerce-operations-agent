import re
from collections import Counter, defaultdict
from datetime import timedelta
from types import SimpleNamespace
from uuid import UUID

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.core.config import Settings
from backend.app.db.base_v2 import BaseV2
from backend.app.models_v2.catalog import CategoryV2, ProductCategoryV2, ProductV2, ProductVariantV2
from backend.app.models_v2.operations import OrderItemV2, OrderV2
from backend.app.models_v2.tenant import TenantV2
from backend.app.services.c09_order_aggregate import safe_product_demand_aggregate
from backend.app.services.c15_synthetic_seed import (
    AS_OF,
    DEPARTMENT_COUNTS,
    LEAVES,
    SEED_VERSION,
    TENANT_ID,
    generate_seed,
    identity,
)
from backend.app.services.product_demand_projection import project_product_demand
from scripts import c15_synthetic_seed as seed_script
from scripts.c15_synthetic_seed import apply_seed


def test_c15_url_guard_uses_settings_and_exact_database(monkeypatch):
    monkeypatch.setattr(seed_script, "Settings", lambda: Settings(_env_file=None))
    monkeypatch.setenv(
        "POSTGRES_V2_URL", "postgresql+psycopg://user:secret@localhost/commerce_ops_db"
    )
    assert seed_script._database_url().endswith("/commerce_ops_db")

    monkeypatch.setenv("POSTGRES_V2_URL", "postgresql+psycopg://user:secret@localhost/commerce_ops")
    with pytest.raises(RuntimeError, match="^C15_REQUIRES_COMMERCE_OPS_DB$") as exc:
        seed_script._database_url()
    assert "secret" not in str(exc.value)

    monkeypatch.delenv("POSTGRES_V2_URL")
    with pytest.raises(RuntimeError, match="^C15_REQUIRES_COMMERCE_OPS_DB$"):
        seed_script._database_url()


@pytest.mark.parametrize(
    ("environment", "status", "tenant_id", "allowed"),
    [
        ("DEMO", "ACTIVE", TENANT_ID, True),
        ("LOCAL", "ACTIVE", TENANT_ID, False),
        ("PRODUCTION_READ", "ACTIVE", TENANT_ID, False),
        ("DEMO", "INACTIVE", TENANT_ID, False),
        ("DEMO", "ACTIVE", None, False),
    ],
)
def test_c15_tenant_guard(environment, status, tenant_id, allowed):
    class FakeSession:
        def get(self, model, key):
            assert model is TenantV2 and key == TENANT_ID
            if tenant_id != key:
                return None
            return SimpleNamespace(environment=environment, status=status)

    if allowed:
        seed_script._check_tenant(FakeSession())
    else:
        with pytest.raises(RuntimeError, match="^C15_DEMO_TENANT_NOT_DEMO_ACTIVE$"):
            seed_script._check_tenant(FakeSession())


def test_c15_bundle_exact_contract():
    bundle = generate_seed()
    assert bundle.manifest == generate_seed().manifest
    assert bundle.manifest["seed_version"] == SEED_VERSION
    assert (
        bundle.manifest["seed_hash"]
        == "02195b5dc7352f48554640b8fe276323343b5e33d0644865def2f00323d01a4f"
    )
    assert bundle.manifest["as_of"] == AS_OF.isoformat()
    assert bundle.manifest["counts"] == {
        "categories": 41,
        "products": 150,
        "product_categories": 157,
        "variants": 176,
        "orders": 600,
        "order_items": 1700,
    }
    assert Counter(c["category_depth"] for c in bundle.categories) == {1: 7, 2: 10, 3: 24}
    by_category = {c["id"]: c for c in bundle.categories}
    identity_paths = dict.fromkeys(
        path
        for _, root, branch, leaf, _ in LEAVES
        for path in ((root,), (root, branch), (root, branch, leaf))
    )
    identity_paths[("PRE-ORDER",)] = None
    assert [c["id"] for c in bundle.categories] == [
        identity("category", "/".join(path)) for path in identity_paths
    ]
    for category in bundle.categories:
        depth = category["category_depth"]
        parent = category["parent_category_id"]
        assert (parent is None) == (depth == 1)
        if parent:
            assert by_category[parent]["category_depth"] == depth - 1
    assert len({tuple(sorted(r.items())) for r in bundle.product_categories}) == 157
    by_product = {p["id"]: p for p in bundle.products}
    memberships = defaultdict(list)
    department_counts = Counter()
    preorder_id = next(c["id"] for c in bundle.categories if c["category_name"] == "예약 판매")
    for relation in bundle.product_categories:
        memberships[relation["product_id"]].append(by_category[relation["category_id"]])
    for product in bundle.products:
        cats = memberships[product["id"]]
        normal = [c for c in cats if c["id"] != preorder_id]
        if normal:
            current = normal[0]
            assert current["category_depth"] == 3
            while current["parent_category_id"]:
                current = by_category[current["parent_category_id"]]
            department_counts[current["category_name"]] += 1
    assert department_counts == {
        "보드게임": 35,
        "카드 게임": 20,
        "테이블탑 게임": 32,
        "취미·도색 용품": 28,
        "게임 용품": 25,
        "선물·퍼즐": 7,
    }
    assert sum(DEPARTMENT_COUNTS.values()) == 147
    assert all(any("가" <= char <= "힣" for char in p["product_name"]) for p in bundle.products)
    assert all(any("가" <= char <= "힣" for char in c["category_name"]) for c in bundle.categories)
    assert all(not re.search(r"[A-Za-z]", p["product_name"]) for p in bundle.products)
    assert all(not re.search(r"[A-Za-z]", c["category_name"]) for c in bundle.categories)
    assert len({p["product_name"] for p in bundle.products}) == 150
    hero = next(p for p in bundle.products if p["product_code"] == "DEMO-P-0009")
    assert hero["product_name"] == "아침 시장"
    assert hero["id"] == UUID("dd5e08e7-a9a7-5a91-a34b-e9e0bf3b9e09")
    assert hero["cafe24_product_no"] == 9_150_000_009
    assert all(
        p["id"] == identity("product", str(index))
        and p["product_code"] == f"DEMO-P-{index:04d}"
        and p["cafe24_product_no"] == 9_150_000_000 + index
        for index, p in enumerate(bundle.products, 1)
    )
    assert preorder_id == identity("category", "PRE-ORDER")
    assert Counter(len(memberships[p["id"]]) for p in bundle.products) == {1: 137, 2: 10, 0: 3}
    assert sum(preorder_id in {c["id"] for c in memberships[p["id"]]} for p in bundle.products) == 7
    prices = Counter(
        "UNDER_20K"
        if p["sale_price"] < 20000
        else "20K_50K"
        if p["sale_price"] < 50000
        else "50K_100K"
        if p["sale_price"] < 100000
        else "100K_200K"
        if p["sale_price"] < 200000
        else "200K_PLUS"
        for p in bundle.products
    )
    assert prices == {
        "UNDER_20K": 26,
        "20K_50K": 16,
        "50K_100K": 71,
        "100K_200K": 21,
        "200K_PLUS": 16,
    }
    assert Counter(
        (p["display_status"], p["selling_status"], p["sold_out"]) for p in bundle.products
    ) == {
        ("T", "T", False): 104,
        ("T", "T", True): 36,
        ("F", "F", True): 7,
        ("F", "T", True): 2,
        ("F", "T", False): 1,
    }
    assert all(p["operational"] for p in bundle.products)
    assert sum(p["custom_product_code"] is not None for p in bundle.products) == 146
    assert len({p["product_code"] for p in bundle.products}) == 150
    assert all(p["product_code"].startswith("DEMO-P-") for p in bundle.products)
    canaries = ("Warhammer", "Orks", "Aeldari", "Necromunda", "Kill Team")
    assert not any(
        token.lower() in p["product_name"].lower() for p in bundle.products for token in canaries
    )
    assert all(p["cafe24_product_no"] >= 9_150_000_000 for p in bundle.products)
    assert all(p["tenant_id"] == TENANT_ID for p in bundle.products)
    assert all(v["product_id"] in by_product for v in bundle.variants)
    assert all(v["id"] == identity("variant", v["variant_code"]) for v in bundle.variants)
    assert {v["option_name"] for v in bundle.variants} == {"기본형", "다른 구성", "고급형"}
    assert Counter(o["paid"] for o in bundle.orders) == {"T": 567, "F": 33}
    assert Counter(o["shipping_status"] for o in bundle.orders) == {"F": 97, "T": 449, "M": 54}
    assert Counter(o["canceled"] for o in bundle.orders) == {"T": 33, "F": 553, "M": 14}
    assert all(
        o["shipping_status"] == "F"
        for o in bundle.orders
        if o["paid"] == "F" or o["canceled"] == "T"
    )
    assert all(o["shipping_status"] == "M" for o in bundle.orders if o["canceled"] == "M")
    assert all(AS_OF - timedelta(days=89) <= o["source_order_at"] <= AS_OF for o in bundle.orders)
    assert sum(i["quantity"] for i in bundle.order_items) == 1792
    assert all(i["product_id"] in by_product for i in bundle.order_items)
    assert all(
        i["source_product_name"] == by_product[i["product_id"]]["product_name"]
        for i in bundle.order_items
    )
    assert all(
        i["external_product_no"] == by_product[i["product_id"]]["cafe24_product_no"]
        for i in bundle.order_items
    )
    order_ids = {o["id"] for o in bundle.orders}
    assert all(i["order_id"] in order_ids for i in bundle.order_items)
    assert all(o["source_system"] == "SYNTHETIC_DEMO" for o in bundle.orders)
    assert (
        sum(
            by_product[i["product_id"]]["id"]
            in {
                r["product_id"]
                for r in bundle.product_categories
                if r["category_id"] == preorder_id
            }
            for i in bundle.order_items
        )
        == 100
    )
    preorder_products = {
        r["product_id"] for r in bundle.product_categories if r["category_id"] == preorder_id
    }
    assert (
        len({i["order_id"] for i in bundle.order_items if i["product_id"] in preorder_products})
        == 100
    )
    sorted_prices = sorted(p["sale_price"] for p in bundle.products)
    assert 40000 <= sorted_prices[37] <= 50000
    assert 68000 <= sorted_prices[74] <= 75000
    assert 90000 <= sorted_prices[112] <= 100000
    demand = Counter()
    for item in bundle.order_items:
        demand[item["product_id"]] += item["quantity"]
    ranked = sorted(demand.values(), reverse=True)
    assert 0.40 <= sum(ranked[:15]) / 1792 <= 0.45
    assert 0.35 <= sum(ranked[15:60]) / 1792 <= 0.40
    assert 0.15 <= sum(ranked[60:]) / 1792 <= 0.25


def test_c15_sqlite_seed_twice_and_existing_demand_projection():
    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        execution_options={
            "schema_translate_map": {"public": None, "catalog": None, "operations": None}
        },
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    tables = [
        TenantV2.__table__,
        ProductV2.__table__,
        CategoryV2.__table__,
        ProductCategoryV2.__table__,
        ProductVariantV2.__table__,
        OrderV2.__table__,
        OrderItemV2.__table__,
    ]
    BaseV2.metadata.create_all(engine, tables=tables)
    with Session(engine) as session:
        session.add(TenantV2(id=TENANT_ID, name="demo_store", environment="DEMO", status="ACTIVE"))
        session.commit()
        first = apply_seed(session)
        session.commit()
        second = apply_seed(session)
        session.commit()
        assert first == {
            "categories": 41,
            "products": 150,
            "product_categories": 157,
            "variants": 176,
            "orders": 600,
            "order_items": 1700,
        }
        assert all(value == 0 for value in second.values())
        bundle = generate_seed()
        projection = project_product_demand(
            session, tenant_id=TENANT_ID, product_id=bundle.products[0]["id"]
        )
        safe = safe_product_demand_aggregate(projection)
        assert safe.product_no == bundle.products[0]["cafe24_product_no"]
        assert safe.ordered_quantity > 0
        assert safe.effective_quantity <= safe.ordered_quantity
        assert safe.data_mode == "SYNTHETIC_DEMO"
        product = session.get(ProductV2, bundle.products[0]["id"])
        product.product_name = "이전 표시명"
        category = session.get(CategoryV2, bundle.categories[0]["id"])
        category.category_name = "이전 카테고리명"
        item = session.get(OrderItemV2, bundle.order_items[0]["id"])
        item.source_product_name = "이전 주문 상품명"
        variant = session.get(ProductVariantV2, bundle.variants[0]["id"])
        variant.option_name = "이전 옵션명"
        session.flush()
        assert all(value == 0 for value in apply_seed(session).values())
        assert product.product_name == bundle.products[0]["product_name"]
        assert category.category_name == bundle.categories[0]["category_name"]
        assert item.source_product_name == bundle.order_items[0]["source_product_name"]
        assert variant.option_name == bundle.variants[0]["option_name"]
        product.sale_price += 1
        session.flush()
        with pytest.raises(RuntimeError, match="C15_EXISTING_ROW_DRIFT"):
            apply_seed(session)
        session.rollback()
    engine.dispose()
