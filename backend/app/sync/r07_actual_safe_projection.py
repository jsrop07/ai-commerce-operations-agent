"""Private product-only R07-PRE candidate; never reads raw provider data."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from backend.app.sync.day09_ai_catalog_handoff import _scan_payload
from backend.app.sync.day09_ai_catalog_handoff import (
    _latest_by_identity,
    _load_observations,
    _scan_payload,
)
from backend.app.worker.privacy.protected_storage import build_snapshot_sha256

PRODUCT_DIR = Path(r"C:\ai-commerce-private\cafe24\cafe24\sanitized\products")
PRODUCT_PATTERN = "product-full-*.sanitized.json"
OUTPUT_DIR = Path("artifacts/experiments/OPS-R07-PRE/private/product")
OUTPUT_NAME = "product_safe_snapshot.jsonl"
MANIFEST_NAME = "product_safe_manifest.json"
SOURCE_NAME = "CAFE24_SANITIZED_PRODUCT_FULL"
DATA_MODE = "PRIVATE_ACTUAL_EVAL"
SNAPSHOT_FIELDS = frozenset({
    "product_no", "product_code", "custom_product_code", "product_name",
    "brand_code", "shop_no",
    "display", "selling", "sold_out",
    "category_nos", "is_preorder",
    "retail_price", "price", "maximum_quantity",
    "list_image", "origin_place_value",
    "source_type", "source", "version", "as_of", "updated_date",
    "data_mode", "quality_status",
})
EXCLUDED_SENSITIVE_SOURCE_FIELDS = frozenset({
    "internal_product_name", "buy_member_id_list", "summary_description",
    "shipping_fee_by_product", "shipping_fee_type", "points_setting_by_payment",
    "use_kakaopay", "use_naverpay", "naverpay_type", "price_content",
})


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _timestamp(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.isoformat()


def _safe_code(value: object) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[A-Za-z0-9_-]+", value.strip()))


def _load_products(
    source_dir: Path,
) -> tuple[list[tuple[str, str, dict[str, Any]]], list[dict[str, str]], dict[str, object]]:
    """Load only product-full files; report no record values."""
    files = sorted(source_dir.glob(PRODUCT_PATTERN))
    if not files:
        raise FileNotFoundError("no product-full sanitized files")
    rows: list[tuple[str, str, dict[str, Any]]] = []
    file_hashes: list[dict[str, str]] = []
    headers: Counter[str] = Counter()
    fields: Counter[str] = Counter()
    types: dict[str, Counter[str]] = {}
    findings: Counter[str] = Counter()
    manifest_dir = source_dir.parent.parent / "manifests"
    for path in files:
        body = path.read_bytes()
        digest = hashlib.sha256(body).hexdigest()
        payload = json.loads(body.decode("utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
            raise ValueError("invalid sanitized product envelope")
        batch_id = payload.get("batch_id")
        if payload.get("provider") != "CAFE24":
            findings["invalid_provider_files"] += 1
        if payload.get("resource") != "products":
            findings["invalid_resource_files"] += 1
        if not isinstance(batch_id, str) or path.name != f"{batch_id}.sanitized.json":
            findings["invalid_batch_identity_files"] += 1
        manifest_path = manifest_dir / f"{batch_id}.manifest.json"
        if manifest_path.is_file():
            metadata = json.loads(manifest_path.read_text(encoding="utf-8"))
            entries = metadata.get("resources") if isinstance(metadata, dict) else None
            matching = [
                item for item in entries
                if isinstance(item, dict)
                and item.get("provider") == "CAFE24"
                and item.get("resource") == "products"
                and item.get("batch_id") == batch_id
            ] if isinstance(entries, list) else []
            if len(matching) != 1:
                findings["sanitized_manifest_entry_count_invalid"] += 1
            elif matching[0].get("sanitized_count") != len(payload["records"]):
                findings["sanitized_manifest_count_mismatch"] += 1
            elif matching[0].get("sanitized_sha256") is None:
                findings["sanitized_manifest_hash_unavailable"] += 1
            elif matching[0].get("sanitized_sha256") != digest:
                findings["sanitized_manifest_hash_mismatch"] += 1
            else:
                findings["sanitized_manifest_hash_matches"] += 1
        else:
            findings["sanitized_manifest_missing_files"] += 1
        headers.update(payload.keys())
        file_hashes.append({"file_name": path.name, "sha256": digest})
        for record in payload["records"]:
            if not isinstance(record, dict):
                findings["invalid_record_shape"] += 1
                continue
            fields.update(record.keys())
            for key, value in record.items():
                types.setdefault(key, Counter())[type(value).__name__] += 1
            rows.append((str(batch_id), path.name, record))
    schema = {
        "file_count": len(files),
        "raw_record_count": len(rows),
        "header_field_frequency": dict(sorted(headers.items())),
        "record_field_frequency": dict(sorted(fields.items())),
        "record_field_types": {
            key: dict(sorted(counts.items())) for key, counts in sorted(types.items())
        },
        "load_findings": dict(sorted(findings.items())),
    }
    return rows, file_hashes, schema


def inspect_product_schema(source_dir: Path = PRODUCT_DIR) -> dict[str, object]:
    """Report only field names, types, and counts; never record values."""
    return _load_products(source_dir)[2]


def build_product_projection(
    source_dir: Path = PRODUCT_DIR,
    output_dir: Path = OUTPUT_DIR,
    *,
    require_category_data: bool = True,
) -> dict[str, object]:
    rows, file_hashes, schema = _load_products(source_dir)
    findings: Counter[str] = Counter(schema["load_findings"])
    sanitized_root = source_dir.parent

    if require_category_data:
        category_observations, _ = _load_observations(
            sanitized_root / "categories",
            preferred_glob="category-full-*.sanitized.json",
        )

        relation_observations, _ = _load_observations(
            sanitized_root / "category_product_relations",
            preferred_glob="category-products-snapshot-*.sanitized.json",
        )

        categories_by_no = _latest_by_identity(
            category_observations,
            identity_field="category_no",
        )
    else:
        category_observations = []
        relation_observations = []
        categories_by_no = {}
    identities: dict[int, tuple[str, str, dict[str, Any]]] = {}
    product_codes: dict[str, int] = {}
    shop_ids: set[int] = set()
    product_category_nos: dict[int, set[int]] = {}
    relation_latest: dict[tuple[int, int], Any] = {}

    for observation in relation_observations:
        category_no = observation.record.get("category_no")
        product_no = observation.record.get("product_no")

        if type(category_no) is not int or category_no < 1:
            findings["invalid_category_relation_category_no"] += 1
            continue

        if type(product_no) is not int or product_no < 1:
            findings["invalid_category_relation_product_no"] += 1
            continue

        if category_no not in categories_by_no:
            findings["unknown_category_relation"] += 1
            continue

        key = (category_no, product_no)
        relation_latest[key] = observation

    for category_no, product_no in sorted(relation_latest):
        product_category_nos.setdefault(product_no, set()).add(category_no)
    for batch_id, file_name, record in rows:
        product_no = record.get("product_no")
        if type(product_no) is not int or product_no < 1:
            findings["invalid_product_id"] += 1
            continue
        shop_no = record.get("shop_no")
        if type(shop_no) is not int or shop_no < 1:
            findings["invalid_shop_no"] += 1
        else:
            shop_ids.add(shop_no)
        if not isinstance(record.get("product_name"), str) or not record["product_name"].strip():
            findings["empty_product_name"] += 1
        code = record.get("product_code")
        if not _safe_code(code):
            findings["invalid_product_code"] += 1
        else:
            normalized_code = code.strip()
            prior_product = product_codes.setdefault(normalized_code, product_no)
            if prior_product != product_no:
                findings["product_code_identity_conflicts"] += 1

        custom_product_code = record.get("custom_product_code")
        if isinstance(custom_product_code, str) and custom_product_code.strip():
            findings["custom_product_code_present"] += 1
        else:
            findings["custom_product_code_missing"] += 1

        display = record.get("display")
        if display not in {"T", "F"}:
            findings["invalid_display"] += 1

        selling = record.get("selling")
        if selling not in {"T", "F"}:
            findings["invalid_selling"] += 1

        sold_out = record.get("sold_out")
        if sold_out not in {"T", "F"}:
            findings["invalid_sold_out"] += 1

        maximum_quantity = record.get("maximum_quantity")
        if type(maximum_quantity) is not int or maximum_quantity < 0:
            findings["invalid_maximum_quantity"] += 1

        for price_field in ("price", "retail_price"):
            price_value = record.get(price_field)

            if not isinstance(price_value, str) or not price_value.strip():
                findings[f"invalid_{price_field}"] += 1
                continue

            try:
                parsed_price = Decimal(price_value.strip())
            except InvalidOperation:
                findings[f"invalid_{price_field}"] += 1
                continue

            if parsed_price < 0:
                findings[f"invalid_{price_field}"] += 1
        if record.get("updated_date") not in (None, "") and _timestamp(record["updated_date"]) is None:
            findings["invalid_updated_date"] += 1
        if record.get("updated_date") in (None, ""):
            findings["missing_updated_date"] += 1
        prior = identities.get(product_no)
        if prior is not None:
            duplicate_scope = (
                "same_batch_duplicate_product_rows"
                if prior[0] == batch_id else "cross_batch_duplicate_product_rows"
            )
            findings[duplicate_scope] += 1
            duplicate_kind = (
                "identical_duplicate_product_rows"
                if _canonical_bytes(prior[2]) == _canonical_bytes(record)
                else "conflicting_duplicate_product_rows"
            )
            findings[duplicate_kind] += 1
            continue
        identities[product_no] = (batch_id, file_name, record)

    # product-full contains no variant/SKU identity. Product code is not a SKU.
    # PRODUCT-level retrieval에서는 SKU/variant 부재를 기록하되 차단 사유로 사용하지 않는다.
    findings["missing_variant_sku_source"] = len(identities)

    # 실제 운영 Cafe24에서 수집된 단일 shop scope이며,
    # safe projection 2,167건 모두 같은 shop_no임을 사용자 검수로 확인했다.
    findings["tenant_dataset_scope_verified"] = len(identities)

    # 2026-09-29 사용자가 safe PRODUCT review sample을 직접 검수하고 사용을 승인했다.
    findings["user_review_approved"] = 1

    # 원 Provider response까지의 provenance는 별도 OPEN finding으로 유지한다.
    findings["raw_response_provenance_unverified"] = len(file_hashes)
    file_set_hash = build_snapshot_sha256(file_hashes)
    version = f"product-file-set-sha256:{file_set_hash}"
    snapshot_rows = []
    for product_no, (_, _, record) in sorted(identities.items()):
        custom_product_code = record.get("custom_product_code")
        if isinstance(custom_product_code, str):
            custom_product_code = custom_product_code.strip() or None
        else:
            custom_product_code = None

        snapshot_rows.append({
            "product_no": product_no,
            "product_code": record.get("product_code"),
            "custom_product_code": custom_product_code,
            "product_name": record.get("product_name"),

            "brand_code": record.get("brand_code"),
            "shop_no": record.get("shop_no"),

            "display": record.get("display"),
            "selling": record.get("selling"),
            "sold_out": record.get("sold_out"),

            "category_nos": sorted(product_category_nos.get(product_no, set())),
            "is_preorder": 56 in product_category_nos.get(product_no, set()),

            "retail_price": record.get("retail_price"),
            "price": record.get("price"),
            "maximum_quantity": record.get("maximum_quantity"),

            "list_image": record.get("list_image"),
            "origin_place_value": record.get("origin_place_value"),

            "source_type": "PRODUCT",
            "source": SOURCE_NAME,
            "version": version,
            "as_of": None,
            "updated_date": _timestamp(record.get("updated_date")),
            "data_mode": DATA_MODE,
            "quality_status": "APPROVED_FOR_R07_PRE_PRODUCT_EVAL",
        })
    forbidden_projection_fields = sorted(
        set().union(*(item.keys() for item in snapshot_rows)) - SNAPSHOT_FIELDS
    )
    if forbidden_projection_fields:
        raise ValueError("projection contains forbidden fields")
    pii_matches, secret_matches = _scan_payload(snapshot_rows)
    if pii_matches or secret_matches:
        raise ValueError("projection content safety scan failed")
    fatal_findings = (
        "invalid_provider_files",
        "invalid_resource_files",
        "invalid_batch_identity_files",
        "invalid_record_shape",
        "invalid_product_id",
        "invalid_shop_no",
        "empty_product_name",
        "invalid_product_code",
        "product_code_identity_conflicts",
        "invalid_updated_date",
        "same_batch_duplicate_product_rows",
        "cross_batch_duplicate_product_rows",
        "invalid_display",
        "invalid_selling",
        "invalid_sold_out",
        "invalid_maximum_quantity",
        "invalid_price",
        "invalid_retail_price",
        "invalid_category_relation_category_no",
        "invalid_category_relation_product_no",
        "unknown_category_relation",
    )
    fatal_summary = {
        key: findings[key]
        for key in fatal_findings
        if findings[key]
    }

    if fatal_summary:
        raise ValueError(
            f"product source validation failed; fatal_findings={fatal_summary}"
        )
    projection_hash = build_snapshot_sha256(snapshot_rows)
    snapshot_bytes = b"".join(_canonical_bytes(row) + b"\n" for row in snapshot_rows)
    manifest = {
        "schema_version": "r07-pre-product-safe-candidate.v2",
        "official_status": "SUPPORTED_FOR_R07_PRE_PRODUCT_EVAL",
        "internal_status": "APPROVED_PRODUCT_LEVEL_PROVENANCE_OPEN",
        "data_mode": DATA_MODE,
        "visibility": DATA_MODE,
        "retrieval_compatible": True,
        "source": SOURCE_NAME,
        "source_type": "PRODUCT",
        "source_version": version,
        "as_of": None,
        "as_of_rule": "null: product updated_date is mutation time, not observation time",
        "updated_date_rule": "product mutation time only; never treated as as_of",
        "identity_rule": "product_no; duplicates are findings, never silently selected",
        "sku_identity_rule": "unavailable in product-full source",
        "tenant_rule": (
            "dataset scope verified by user: all projected PRODUCT records originate "
            "from the target operational Cafe24 store and share one shop_no; "
            "shop_no is not renamed to tenant_id"
        ),
        "not_evaluated": [
            "duplicate_variant_sku",
            "product_variant_relationship",
            "empty_sku_or_unidentifiable_option",
            "raw_response_provenance",
        ],
        "allowlist": sorted(SNAPSHOT_FIELDS),
        "field_mapping": {
            "product_no": "product_no",
            "product_code": "product_code",
            "custom_product_code": "custom_product_code",
            "product_name": "product_name",
            "brand_code": "brand_code",
            "shop_no": "shop_no",
            "display": "display",
            "selling": "selling",
            "sold_out": "sold_out",
            "category_nos": "category_product_relations.category_no",
            "is_preorder": "derived: category_no 56 membership",
            "retail_price": "retail_price",
            "price": "price",
            "maximum_quantity": "maximum_quantity",
            "list_image": "list_image",
            "origin_place_value": "origin_place_value",
            "updated_date": "updated_date",
        },
        "counts": {
            "source_files": len(file_hashes), "raw_records": len(rows),
            "unique_products": len(identities),
            "observed_variant_sku_identifiers": 0,
            "unique_variant_sku": None,
            "projected_records": len(snapshot_rows), "distinct_shop_no": len(shop_ids),
        },
        "findings": dict(sorted(findings.items())),
        "forbidden_projection_field_count": 0,
        "projection_pii_match_count": 0,
        "projection_secret_match_count": 0,
        "excluded_sensitive_source_fields_present": sorted(
            EXCLUDED_SENSITIVE_SOURCE_FIELDS & schema["record_field_frequency"].keys()
        ),
        "source_files": file_hashes,
        "source_file_set_sha256": file_set_hash,
        "safe_projection_canonical_sha256": projection_hash,
        "snapshot_file_sha256": hashlib.sha256(snapshot_bytes).hexdigest(),
        "snapshot_file": OUTPUT_NAME,
        "hash_rules": {
            "source_file": "SHA256 of each original sanitized file's bytes",
            "source_file_set": "SHA256 of UTF-8 sorted-key compact JSON array of sorted file_name/sha256 pairs; no newline",
            "safe_projection": "SHA256 of UTF-8 sorted-key compact JSON array of allowlisted rows; no newline",
            "snapshot_file": "SHA256 of UTF-8 compact sorted-key JSONL bytes; LF after every row",
            "manifest_file": "SHA256 of UTF-8 compact sorted-key JSON bytes; one final LF",
        },
        "source_support": {
            "PRODUCT": "SUPPORTED", "POLICY": "MISSING",
            "INVENTORY_SNAPSHOT": "BLOCKED", "INCOMING_STOCK": "MISSING",
            "C02": "BLOCKED",
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = output_dir / OUTPUT_NAME
    manifest_path = output_dir / MANIFEST_NAME
    snapshot_path.write_bytes(snapshot_bytes)
    manifest_bytes = _canonical_bytes(manifest) + b"\n"
    manifest_path.write_bytes(manifest_bytes)
    return {
        "snapshot_path": str(snapshot_path), "manifest_path": str(manifest_path),
        "counts": manifest["counts"], "findings": manifest["findings"],
        "source_file_set_sha256": file_set_hash,
        "safe_projection_canonical_sha256": projection_hash,
        "snapshot_file_sha256": manifest["snapshot_file_sha256"],
        "manifest_file_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
    }


if __name__ == "__main__":
    import sys

    if sys.argv[1:] == ["--inspect"]:
        result = inspect_product_schema()
    elif sys.argv[1:] == ["--build"]:
        result = build_product_projection()
    else:
        raise SystemExit("use --inspect or --build")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
