"""Approved PRODUCT safe artifact -> commerce_ops V2 catalog.products importer."""

from __future__ import annotations

import argparse
import hashlib
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from sqlalchemy import select

from backend.app.core.config import get_settings
from backend.app.db.session_v2 import (
    build_v2_engine,
    build_v2_session_factory,
)
from backend.app.models_v2.catalog import ProductV2
from backend.app.models_v2.tenant import TenantV2


SNAPSHOT_PATH = Path(
    "artifacts/experiments/OPS-R07-PRE/private/product/"
    "product_safe_snapshot.jsonl"
)

MANIFEST_PATH = Path(
    "artifacts/experiments/OPS-R07-PRE/private/product/"
    "product_safe_manifest.json"
)

EXPECTED_SNAPSHOT_SHA256 = (
    "6438ad2ca5a21d4d30b1bf5bacbeb186679df1c16369fbc8eacc9cca3f1a9892"
)

EXPECTED_MANIFEST_SHA256 = (
    "4933b41ef73ca05714af08e5544c109e0502c043457e942f04ff976067539da9"
)

EXPECTED_SCHEMA_VERSION = "r07-pre-product-safe-candidate.v2"
EXPECTED_RECORD_COUNT = 2167


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def normalize_bool(value: Any, *, field_name: str) -> bool:
    if isinstance(value, bool):
        return value

    if isinstance(value, int) and value in (0, 1):
        return bool(value)

    if isinstance(value, str):
        normalized = value.strip().upper()

        if normalized in {"TRUE", "T", "Y", "YES", "1"}:
            return True

        if normalized in {"FALSE", "F", "N", "NO", "0"}:
            return False

    raise ValueError(
        f"unsupported boolean value for {field_name}"
    )


def normalize_price(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None

    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("invalid product price") from exc


def load_and_validate() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not SNAPSHOT_PATH.is_file():
        raise RuntimeError("PRODUCT snapshot file not found")

    if not MANIFEST_PATH.is_file():
        raise RuntimeError("PRODUCT manifest file not found")

    snapshot_hash = sha256_file(SNAPSHOT_PATH)
    manifest_hash = sha256_file(MANIFEST_PATH)

    if snapshot_hash != EXPECTED_SNAPSHOT_SHA256:
        raise RuntimeError("PRODUCT snapshot SHA256 mismatch")

    if manifest_hash != EXPECTED_MANIFEST_SHA256:
        raise RuntimeError("PRODUCT manifest SHA256 mismatch")

    with MANIFEST_PATH.open("r", encoding="utf-8") as file:
        manifest = json.load(file)

    if manifest.get("schema_version") != EXPECTED_SCHEMA_VERSION:
        raise RuntimeError("unexpected PRODUCT manifest schema version")

    counts = manifest.get("counts") or {}

    if counts.get("projected_records") != EXPECTED_RECORD_COUNT:
        raise RuntimeError("unexpected PRODUCT manifest record count")

    if counts.get("unique_products") != EXPECTED_RECORD_COUNT:
        raise RuntimeError("unexpected PRODUCT unique product count")

    if counts.get("observed_variant_sku_identifiers") != 0:
        raise RuntimeError("PRODUCT artifact unexpectedly contains SKU identity")

    rows: list[dict[str, Any]] = []

    with SNAPSHOT_PATH.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue

            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"invalid JSON at line {line_number}"
                ) from exc

            rows.append(row)

    if len(rows) != EXPECTED_RECORD_COUNT:
        raise RuntimeError("PRODUCT snapshot row count mismatch")

    required_fields = (
        "product_no",
        "product_name",
        "product_code",
        "display",
        "selling",
        "sold_out",
    )

    product_nos: set[int] = set()
    product_codes: set[str] = set()

    for row_number, row in enumerate(rows, start=1):
        for field_name in required_fields:
            if row.get(field_name) in (None, ""):
                raise RuntimeError(
                    f"missing {field_name} at row {row_number}"
                )

        product_no = int(row["product_no"])
        product_code = str(row["product_code"])

        if product_no in product_nos:
            raise RuntimeError(
                f"duplicate product_no at row {row_number}"
            )

        if product_code in product_codes:
            raise RuntimeError(
                f"duplicate product_code at row {row_number}"
            )

        product_nos.add(product_no)
        product_codes.add(product_code)

        if row.get("as_of") is not None:
            raise RuntimeError(
                "PRODUCT source as_of must remain null"
            )

        normalize_price(row.get("price"))
        normalize_bool(
            row.get("sold_out"),
            field_name="sold_out",
        )

    return manifest, rows


def build_product_values(row: dict[str, Any]) -> dict[str, Any]:
    custom_product_code = row.get("custom_product_code")

    if custom_product_code == "":
        custom_product_code = None

    return {
        "cafe24_product_no": int(row["product_no"]),
        "product_name": str(row["product_name"]),
        "product_code": str(row["product_code"]),
        "custom_product_code": (
            str(custom_product_code)
            if custom_product_code is not None
            else None
        ),
        "sale_price": normalize_price(row.get("price")),
        "display_status": str(row["display"]),
        "selling_status": str(row["selling"]),
        "sold_out": normalize_bool(
            row["sold_out"],
            field_name="sold_out",
        ),
        # Manifest explicitly states product updated_date is mutation time,
        # not observation time. Do not substitute it for source_as_of.
        "source_as_of": None,
    }


def run(*, apply: bool) -> None:
    settings = get_settings()

    if not settings.postgres_v2_url:
        raise RuntimeError("POSTGRES_V2_URL is not configured")

    if settings.v2_tenant_id is None:
        raise RuntimeError("V2_TENANT_ID is not configured")

    manifest, rows = load_and_validate()

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

            existing_products = session.scalars(
                select(ProductV2).where(
                    ProductV2.tenant_id == settings.v2_tenant_id
                )
            ).all()

            existing_by_product_no = {
                product.cafe24_product_no: product
                for product in existing_products
            }

            created = 0
            updated = 0
            unchanged = 0

            for row in rows:
                values = build_product_values(row)
                product_no = values["cafe24_product_no"]

                existing = existing_by_product_no.get(product_no)

                if existing is None:
                    session.add(
                        ProductV2(
                            tenant_id=settings.v2_tenant_id,
                            **values,
                        )
                    )
                    created += 1
                    continue

                if existing.product_code != values["product_code"]:
                    raise RuntimeError(
                        "existing product_code conflicts with product_no "
                        f"{product_no}"
                    )

                changed = False

                for field_name, new_value in values.items():
                    if getattr(existing, field_name) != new_value:
                        setattr(existing, field_name, new_value)
                        changed = True

                if changed:
                    updated += 1
                else:
                    unchanged += 1

            print(f"MODE={'APPLY' if apply else 'DRY_RUN'}")
            print(f"TENANT_ID={settings.v2_tenant_id}")
            print(f"MANIFEST_SCHEMA={manifest['schema_version']}")
            print(f"INPUT_ROWS={len(rows)}")
            print(f"EXISTING_ROWS={len(existing_products)}")
            print(f"WOULD_CREATE={created}")
            print(f"WOULD_UPDATE={updated}")
            print(f"UNCHANGED={unchanged}")

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

    mode = parser.add_mutually_exclusive_group(required=True)
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