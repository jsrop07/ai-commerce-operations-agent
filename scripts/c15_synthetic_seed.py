"""C15 preview by default. Database writes require a later explicit --apply run."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.models_v2.catalog import CategoryV2, ProductCategoryV2, ProductV2, ProductVariantV2
from backend.app.models_v2.operations import OrderItemV2, OrderV2
from backend.app.models_v2.tenant import TenantV2
from backend.app.services.c15_synthetic_seed import TENANT_ID, generate_seed


def _database_url() -> str:
    url = Settings().postgres_v2_url
    try:
        database = make_url(url).database if url else None
    except (ArgumentError, ValueError):
        database = None
    if database != "commerce_ops_db":
        raise RuntimeError("C15_REQUIRES_COMMERCE_OPS_DB")
    return url


def _check_tenant(session: Session) -> None:
    tenant = session.get(TenantV2, TENANT_ID)
    if tenant is None or tenant.environment != "DEMO" or tenant.status != "ACTIVE":
        raise RuntimeError("C15_DEMO_TENANT_NOT_DEMO_ACTIVE")


def _synchronize(
    session: Session, model, rows: list[dict], *, display_fields: frozenset[str] = frozenset()
) -> int:
    """Insert owned identities; update only approved display fields on existing rows."""
    current = {
        row.id: row
        for row in session.scalars(
            select(model).where(
                model.tenant_id == TENANT_ID, model.id.in_([row["id"] for row in rows])
            )
        ).all()
    }
    inserted = 0
    for row in rows:
        old = current.get(row["id"])
        if old is None:
            session.add(model(**row))
            inserted += 1
            continue
        _assert_owned_row(old, row, model.__tablename__, display_fields=display_fields)
        for field in display_fields:
            setattr(old, field, row[field])
    session.flush()
    return inserted


def _assert_owned_row(
    existing_row, expected: dict, table_name: str, *, display_fields: frozenset[str] = frozenset()
) -> None:
    for key, value in expected.items():
        if key in display_fields:
            continue
        actual = getattr(existing_row, key)
        if isinstance(actual, datetime) and isinstance(value, datetime):
            actual = actual.replace(tzinfo=actual.tzinfo or UTC)
            value = value.replace(tzinfo=value.tzinfo or UTC)
        if actual != value:
            raise RuntimeError(f"C15_EXISTING_ROW_DRIFT:{table_name}:{expected['id']}:{key}")


def _synchronize_relations(session: Session, rows: list[dict]) -> int:
    product_ids = {row["product_id"] for row in rows}
    current = {
        (row.product_id, row.category_id)
        for row in session.scalars(
            select(ProductCategoryV2).where(
                ProductCategoryV2.tenant_id == TENANT_ID,
                ProductCategoryV2.product_id.in_(product_ids),
            )
        ).all()
    }
    desired = {(row["product_id"], row["category_id"]) for row in rows}
    if current - desired:
        raise RuntimeError("C15_FOREIGN_PRODUCT_CATEGORY_RELATION")
    missing = desired - current
    for row in rows:
        if (row["product_id"], row["category_id"]) in missing:
            session.add(ProductCategoryV2(**row))
    session.flush()
    return len(missing)


def apply_seed(session: Session) -> dict[str, int]:
    """Caller owns the transaction; generated identities make a second call a no-op."""
    _check_tenant(session)
    bundle = generate_seed()
    owned_order_ids = {row["id"] for row in bundle.orders}
    other_demo_order = session.scalar(
        select(OrderV2.id)
        .where(
            OrderV2.tenant_id == TENANT_ID,
            OrderV2.source_system == "SYNTHETIC_DEMO",
            OrderV2.id.not_in(owned_order_ids),
        )
        .limit(1)
    )
    if other_demo_order is not None:
        raise RuntimeError("C15_OTHER_SYNTHETIC_ORDERS_PRESENT")
    result = {"categories": 0}
    for depth in (1, 2, 3):
        rows = [row for row in bundle.categories if row["category_depth"] == depth]
        result["categories"] += _synchronize(
            session, CategoryV2, rows, display_fields=frozenset({"category_name"})
        )
    for name, model in (
        ("products", ProductV2),
        ("variants", ProductVariantV2),
        ("orders", OrderV2),
        ("order_items", OrderItemV2),
    ):
        if name == "variants":
            result["product_categories"] = _synchronize_relations(
                session, bundle.product_categories
            )
        display_fields = {
            "products": frozenset({"product_name"}),
            "variants": frozenset({"option_name"}),
            "order_items": frozenset({"source_product_name"}),
        }.get(name, frozenset())
        result[name] = _synchronize(
            session, model, getattr(bundle, name), display_fields=display_fields
        )
    return result


def reset_seed(session: Session) -> dict[str, int]:
    """Delete only generated C15 identities, with database FKs protecting other data."""
    _check_tenant(session)
    bundle = generate_seed()
    result = {}
    for name, model in (
        ("order_items", OrderItemV2),
        ("orders", OrderV2),
        ("variants", ProductVariantV2),
    ):
        expected = {row["id"]: row for row in getattr(bundle, name)}
        ids = list(expected)
        existing = session.scalars(
            select(model).where(model.tenant_id == TENANT_ID, model.id.in_(ids))
        ).all()
        for row in existing:
            _assert_owned_row(row, expected[row.id], model.__tablename__)
            session.delete(row)
        session.flush()
        result[name] = len(existing)
    pairs = {(row["product_id"], row["category_id"]) for row in bundle.product_categories}
    relations = session.scalars(
        select(ProductCategoryV2).where(
            ProductCategoryV2.tenant_id == TENANT_ID,
            ProductCategoryV2.product_id.in_([p["id"] for p in bundle.products]),
        )
    ).all()
    if {(r.product_id, r.category_id) for r in relations} - pairs:
        raise RuntimeError("C15_FOREIGN_PRODUCT_CATEGORY_RELATION")
    for relation in relations:
        session.delete(relation)
    session.flush()
    result["product_categories"] = len(relations)
    for name, model in (("products", ProductV2),):
        expected = {row["id"]: row for row in getattr(bundle, name)}
        ids = list(expected)
        existing = session.scalars(
            select(model).where(model.tenant_id == TENANT_ID, model.id.in_(ids))
        ).all()
        for row in existing:
            _assert_owned_row(row, expected[row.id], model.__tablename__)
            session.delete(row)
        session.flush()
        result[name] = len(existing)
    result["categories"] = 0
    for depth in (3, 2, 1):
        expected = {row["id"]: row for row in bundle.categories if row["category_depth"] == depth}
        existing = session.scalars(
            select(CategoryV2).where(CategoryV2.tenant_id == TENANT_ID, CategoryV2.id.in_(expected))
        ).all()
        for row in existing:
            _assert_owned_row(row, expected[row.id], CategoryV2.__tablename__)
            session.delete(row)
        session.flush()
        result["categories"] += len(existing)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--reset-seed", action="store_true")
    args = parser.parse_args()
    bundle = generate_seed()
    print(json.dumps(bundle.manifest, indent=2, sort_keys=True))
    if not args.apply and not args.reset_seed:
        print("DB_CONNECTIONS=0 DB_WRITES=0 VALIDATION=PASS")
        return
    engine = create_engine(_database_url(), pool_pre_ping=True)
    try:
        with Session(engine) as session, session.begin():
            changes = apply_seed(session) if args.apply else reset_seed(session)
        print(
            json.dumps(
                {"operation": "apply" if args.apply else "reset-seed", "changes": changes},
                sort_keys=True,
            )
        )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
