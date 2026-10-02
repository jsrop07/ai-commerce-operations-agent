"""Approved V2 category projection -> commerce_ops catalog importer."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

from backend.app.core.config import get_settings
from backend.app.db.session_v2 import (
    build_v2_engine,
    build_v2_session_factory,
)
from backend.app.models_v2.catalog import (
    CategoryV2,
    ProductCategoryV2,
    ProductV2,
)
from backend.app.models_v2.tenant import TenantV2


CATEGORY_SNAPSHOT_PATH = Path(
    "artifacts/experiments/V2-DB/private/category/"
    "category_v2_safe_snapshot.jsonl"
)

CATEGORY_MANIFEST_PATH = Path(
    "artifacts/experiments/V2-DB/private/category/"
    "category_v2_safe_manifest.json"
)

PRODUCT_SNAPSHOT_PATH = Path(
    "artifacts/experiments/OPS-R07-PRE/private/product/"
    "product_safe_snapshot.jsonl"
)

EXPECTED_CATEGORY_SNAPSHOT_SHA256 = (
    "bd18efd492e51dd0540f9394d96677df3f76b02ec07152dce30695bc07af9c0d"
)

EXPECTED_CATEGORY_MANIFEST_SHA256 = (
    "b74c3452d7555aec6024d77a634dd559cd5d3a0cf27917ebdb745dc849d6d5d4"
)

EXPECTED_PRODUCT_SNAPSHOT_SHA256 = (
    "6438ad2ca5a21d4d30b1bf5bacbeb186679df1c16369fbc8eacc9cca3f1a9892"
)

EXPECTED_CATEGORY_COUNT = 123
EXPECTED_PRODUCT_COUNT = 2167


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def parse_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None

    text = str(value)

    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    return datetime.fromisoformat(text)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue

            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"invalid JSON at {path}:{line_number}"
                ) from exc

    return rows


def load_and_validate() -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    for path in (
        CATEGORY_SNAPSHOT_PATH,
        CATEGORY_MANIFEST_PATH,
        PRODUCT_SNAPSHOT_PATH,
    ):
        if not path.is_file():
            raise RuntimeError(f"required file not found: {path}")

    if (
        sha256_file(CATEGORY_SNAPSHOT_PATH)
        != EXPECTED_CATEGORY_SNAPSHOT_SHA256
    ):
        raise RuntimeError("category snapshot SHA256 mismatch")

    if (
        sha256_file(CATEGORY_MANIFEST_PATH)
        != EXPECTED_CATEGORY_MANIFEST_SHA256
    ):
        raise RuntimeError("category manifest SHA256 mismatch")

    if (
        sha256_file(PRODUCT_SNAPSHOT_PATH)
        != EXPECTED_PRODUCT_SNAPSHOT_SHA256
    ):
        raise RuntimeError("product snapshot SHA256 mismatch")

    manifest = json.loads(
        CATEGORY_MANIFEST_PATH.read_text(encoding="utf-8")
    )

    if manifest.get("schema_version") != "v2-category-safe-candidate.v1":
        raise RuntimeError("unexpected category manifest schema")

    if manifest.get("category_count") != EXPECTED_CATEGORY_COUNT:
        raise RuntimeError("unexpected manifest category count")

    if manifest.get("unresolved_parent_count") != 0:
        raise RuntimeError("category manifest has unresolved parents")

    category_rows = load_jsonl(CATEGORY_SNAPSHOT_PATH)
    product_rows = load_jsonl(PRODUCT_SNAPSHOT_PATH)

    if len(category_rows) != EXPECTED_CATEGORY_COUNT:
        raise RuntimeError("category row count mismatch")

    if len(product_rows) != EXPECTED_PRODUCT_COUNT:
        raise RuntimeError("product row count mismatch")

    category_nos: set[int] = set()

    for row in category_rows:
        category_no = int(row["category_no"])

        if category_no in category_nos:
            raise RuntimeError(
                f"duplicate category_no: {category_no}"
            )

        category_nos.add(category_no)

        if not str(row.get("category_name") or "").strip():
            raise RuntimeError(
                f"missing category_name: {category_no}"
            )

        depth = int(row["category_depth"])

        if depth < 0:
            raise RuntimeError(
                f"invalid category_depth: {category_no}"
            )

        parent = row.get("parent_category_no")

        if parent is not None and int(parent) not in category_nos:
            # Full validation is performed below after all rows are known.
            pass

    unresolved = sorted(
        {
            int(row["parent_category_no"])
            for row in category_rows
            if row.get("parent_category_no") is not None
            and int(row["parent_category_no"]) not in category_nos
        }
    )

    if unresolved:
        raise RuntimeError(
            f"unresolved category parents: {unresolved}"
        )

    desired_relations: set[tuple[int, int]] = set()

    for row in product_rows:
        product_no = int(row["product_no"])

        for raw_category_no in row.get("category_nos") or []:
            category_no = int(raw_category_no)

            if category_no not in category_nos:
                raise RuntimeError(
                    "product references unknown category: "
                    f"product_no={product_no}, "
                    f"category_no={category_no}"
                )

            desired_relations.add(
                (product_no, category_no)
            )

    print(
        f"VALIDATED_RELATION_COUNT={len(desired_relations)}"
    )

    return category_rows, product_rows


def run(*, apply: bool) -> None:
    settings = get_settings()

    if not settings.postgres_v2_url:
        raise RuntimeError("POSTGRES_V2_URL is not configured")

    if settings.v2_tenant_id is None:
        raise RuntimeError("V2_TENANT_ID is not configured")

    category_rows, product_rows = load_and_validate()

    engine = build_v2_engine(settings.postgres_v2_url)
    session_factory = build_v2_session_factory(engine)

    try:
        with session_factory() as session:
            tenant = session.get(
                TenantV2,
                settings.v2_tenant_id,
            )

            if tenant is None:
                raise RuntimeError("configured V2 tenant not found")

            if tenant.status != "ACTIVE":
                raise RuntimeError("configured V2 tenant is not ACTIVE")

            products = session.scalars(
                select(ProductV2).where(
                    ProductV2.tenant_id
                    == settings.v2_tenant_id
                )
            ).all()

            if len(products) != EXPECTED_PRODUCT_COUNT:
                raise RuntimeError(
                    "V2 product count is not 2167"
                )

            products_by_no = {
                int(product.cafe24_product_no): product
                for product in products
            }

            existing_categories = session.scalars(
                select(CategoryV2).where(
                    CategoryV2.tenant_id
                    == settings.v2_tenant_id
                )
            ).all()

            categories_by_no = {
                int(category.cafe24_category_no): category
                for category in existing_categories
            }

            category_created = 0
            category_updated = 0
            category_unchanged = 0

            # Phase 1:
            # create/update category rows without parent FK first.
            for row in category_rows:
                category_no = int(row["category_no"])

                values = {
                    "category_name": str(
                        row["category_name"]
                    ).strip(),
                    "category_depth": int(
                        row["category_depth"]
                    ),
                    "source_as_of": parse_datetime(
                        row.get("as_of")
                    ),
                }

                category = categories_by_no.get(
                    category_no
                )

                if category is None:
                    category = CategoryV2(
                        tenant_id=settings.v2_tenant_id,
                        cafe24_category_no=category_no,
                        parent_category_id=None,
                        **values,
                    )

                    session.add(category)
                    categories_by_no[category_no] = category
                    category_created += 1
                    continue

                changed = False

                for field_name, value in values.items():
                    if getattr(category, field_name) != value:
                        setattr(category, field_name, value)
                        changed = True

                if changed:
                    category_updated += 1
                else:
                    category_unchanged += 1

            # Needed so every new CategoryV2 has a UUID.
            session.flush()

            # Phase 2:
            # resolve parent_category_no -> parent UUID.
            parent_changes = 0

            for row in category_rows:
                category_no = int(row["category_no"])
                category = categories_by_no[category_no]

                raw_parent = row.get("parent_category_no")

                desired_parent_id = None

                if raw_parent is not None:
                    parent_no = int(raw_parent)

                    parent = categories_by_no.get(parent_no)

                    if parent is None:
                        raise RuntimeError(
                            f"parent category missing: {parent_no}"
                        )

                    desired_parent_id = parent.id

                if category.parent_category_id != desired_parent_id:
                    category.parent_category_id = desired_parent_id
                    parent_changes += 1

            session.flush()

            desired_relation_keys: set[
                tuple[int, int]
            ] = set()

            for row in product_rows:
                product_no = int(row["product_no"])

                if product_no not in products_by_no:
                    raise RuntimeError(
                        f"V2 product missing: {product_no}"
                    )

                for raw_category_no in (
                    row.get("category_nos") or []
                ):
                    desired_relation_keys.add(
                        (
                            product_no,
                            int(raw_category_no),
                        )
                    )

            existing_relations = session.scalars(
                select(ProductCategoryV2).where(
                    ProductCategoryV2.tenant_id
                    == settings.v2_tenant_id
                )
            ).all()

            product_no_by_id = {
                product.id: int(
                    product.cafe24_product_no
                )
                for product in products
            }

            category_no_by_id = {
                category.id: int(
                    category.cafe24_category_no
                )
                for category in categories_by_no.values()
            }

            existing_relation_keys: set[
                tuple[int, int]
            ] = set()

            for relation in existing_relations:
                product_no = product_no_by_id.get(
                    relation.product_id
                )
                category_no = category_no_by_id.get(
                    relation.category_id
                )

                if product_no is None or category_no is None:
                    raise RuntimeError(
                        "existing relation references "
                        "unknown V2 entity"
                    )

                existing_relation_keys.add(
                    (product_no, category_no)
                )

            extra_existing = (
                existing_relation_keys
                - desired_relation_keys
            )

            if extra_existing:
                raise RuntimeError(
                    "existing product-category relations "
                    "are outside approved snapshot"
                )

            missing_relations = (
                desired_relation_keys
                - existing_relation_keys
            )

            for product_no, category_no in sorted(
                missing_relations
            ):
                session.add(
                    ProductCategoryV2(
                        tenant_id=settings.v2_tenant_id,
                        product_id=products_by_no[
                            product_no
                        ].id,
                        category_id=categories_by_no[
                            category_no
                        ].id,
                    )
                )

            print(
                f"MODE={'APPLY' if apply else 'DRY_RUN'}"
            )
            print(
                f"TENANT_ID={settings.v2_tenant_id}"
            )
            print(
                f"INPUT_CATEGORIES={len(category_rows)}"
            )
            print(
                f"EXISTING_CATEGORIES="
                f"{len(existing_categories)}"
            )
            print(
                f"WOULD_CREATE_CATEGORIES="
                f"{category_created}"
            )
            print(
                f"WOULD_UPDATE_CATEGORIES="
                f"{category_updated}"
            )
            print(
                f"UNCHANGED_CATEGORIES="
                f"{category_unchanged}"
            )
            print(
                f"PARENT_CHANGES={parent_changes}"
            )
            print(
                f"DESIRED_RELATIONS="
                f"{len(desired_relation_keys)}"
            )
            print(
                f"EXISTING_RELATIONS="
                f"{len(existing_relation_keys)}"
            )
            print(
                f"WOULD_CREATE_RELATIONS="
                f"{len(missing_relations)}"
            )

            if apply:
                session.commit()
                print("COMMITTED=True")
            else:
                session.rollback()
                print("COMMITTED=False")

    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()

    mode = parser.add_mutually_exclusive_group(
        required=True
    )

    mode.add_argument(
        "--dry-run",
        action="store_true",
    )

    mode.add_argument(
        "--apply",
        action="store_true",
    )

    args = parser.parse_args()

    run(apply=args.apply)


if __name__ == "__main__":
    main()