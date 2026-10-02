"""Synthetic-only checks for the private R07-PRE product boundary."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from backend.app.sync.r07_actual_safe_projection import (
    SNAPSHOT_FIELDS,
    build_product_projection,
)


def _write_product_file(folder, name, records):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.sanitized.json").write_text(
        json.dumps({
            "batch_id": name, "provider": "CAFE24",
            "resource": "products", "records": records,
        }),
        encoding="utf-8",
    )


def _record(number=1, name="Sample product"):
    return {
        "product_no": number, "product_code": f"P{number}",
        "product_name": name, "brand_code": "B1", "shop_no": 1,
        "updated_date": "2026-09-01T10:00:00+09:00",
        "internal_product_name": "excluded internal note",
        "shipping_fee_type": "excluded",
        "display": "T",
        "selling": "T",
        "sold_out": "F",
        "maximum_quantity": 0,
        "price": "10000.00",
        "retail_price": "12000.00",
        "custom_product_code": "TEST-CUSTOM-001",
        "list_image": "https://example.test/product.jpg",
        "origin_place_value": "KOREA",
    }


class R07ActualSafeProjectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.source = root / "sanitized" / "products"
        self.output = root / "private" / "product"

    def test_private_product_snapshot_is_allowlisted_and_hash_linked(self):
        _write_product_file(self.source, "product-full-000000-test", [_record()])
        result = build_product_projection(
            self.source,
            self.output,
            require_category_data=False,
        )
        snapshot = (self.output / "product_safe_snapshot.jsonl").read_bytes()
        manifest_bytes = (self.output / "product_safe_manifest.json").read_bytes()
        row = json.loads(snapshot.splitlines()[0])
        manifest = json.loads(manifest_bytes)

        self.assertEqual(set(row), SNAPSHOT_FIELDS)
        self.assertIsNone(row["as_of"])
        self.assertEqual(row["updated_date"], "2026-09-01T10:00:00+09:00")
        self.assertNotIn("internal_product_name", row)
        self.assertNotIn("shipping_fee_type", row)
        self.assertEqual(
            manifest["official_status"],
            "SUPPORTED_FOR_R07_PRE_PRODUCT_EVAL",
        )
        self.assertTrue(manifest["retrieval_compatible"])
        self.assertIsNone(manifest["counts"]["unique_variant_sku"])
        self.assertEqual(manifest["forbidden_projection_field_count"], 0)
        self.assertEqual(hashlib.sha256(snapshot).hexdigest(), result["snapshot_file_sha256"])
        self.assertEqual(hashlib.sha256(manifest_bytes).hexdigest(), result["manifest_file_sha256"])

    def test_duplicate_product_never_silently_selects_a_batch(self):
        _write_product_file(self.source, "product-full-000000-test", [_record()])
        _write_product_file(self.source, "product-full-000025-test", [_record()])
        with self.assertRaisesRegex(ValueError, "validation failed"):
            build_product_projection(
            self.source,
            self.output,
            require_category_data=False,
        )
        self.assertFalse(self.output.exists())

    def test_product_name_with_pii_is_rejected_before_write(self):
        _write_product_file(self.source, "product-full-000000-test", [
            _record(name="Contact " + "example@" + "example.com")
        ])
        with self.assertRaisesRegex(ValueError, "content safety scan failed"):
            build_product_projection(
            self.source,
            self.output,
            require_category_data=False,
        )
        self.assertFalse(self.output.exists())
