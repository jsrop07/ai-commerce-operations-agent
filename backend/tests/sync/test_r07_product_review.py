"""Synthetic safe-snapshot fixtures only; no protected source access."""

import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from backend.app.sync.r07_product_review import COLUMNS, build_review


class R07ProductReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.snapshot = root / "product_safe_snapshot.jsonl"
        self.manifest = root / "product_safe_manifest.json"
        self.review = root / "review"

    def _fixture(self, rows):
        snapshot_bytes = b"".join(
            (json.dumps(row, ensure_ascii=False) + "\n").encode("utf-8")
            for row in rows
        )
        self.snapshot.write_bytes(snapshot_bytes)
        self.manifest.write_text(json.dumps({
            "official_status": "BLOCKED",
            "retrieval_compatible": False,
            "snapshot_file_sha256": hashlib.sha256(snapshot_bytes).hexdigest(),
            "counts": {"projected_records": len(rows)},
            "source_support": {"PRODUCT": "BLOCKED"},
        }), encoding="utf-8")

    def test_csv_sample_pretty_copy_and_inputs(self):
        rows = [
            {"product_no": 1, "product_code": "P001", "product_name": "한글, 상품",
             "brand_code": "B", "shop_no": 1, "updated_date": None,
             "as_of": None, "source": "TEST", "version": "v1",
             "data_mode": "PRIVATE_ACTUAL_EVAL", "quality_status": "BLOCKED",
             "source_type": "PRODUCT"},
            {"product_no": 2, "product_code": "P002", "product_name": "둘째",
             "brand_code": None, "shop_no": 1, "updated_date": None,
             "as_of": None, "source": "TEST", "version": "v1",
             "data_mode": "PRIVATE_ACTUAL_EVAL", "quality_status": "BLOCKED",
             "source_type": "PRODUCT"},
        ]
        self._fixture(rows)
        before_snapshot = self.snapshot.read_bytes()
        before_manifest = self.manifest.read_bytes()

        result = build_review(self.snapshot, self.manifest, self.review)
        with (self.review / "product_safe_review.csv").open(
            encoding="utf-8-sig", newline=""
        ) as stream:
            csv_rows = list(csv.DictReader(stream))
        with (self.review / "product_safe_review_sample.csv").open(
            encoding="utf-8-sig", newline=""
        ) as stream:
            sample_rows = list(csv.DictReader(stream))

        self.assertEqual(len(csv_rows), len(rows))
        self.assertEqual(len(sample_rows), len(rows))
        self.assertEqual(list(csv_rows[0]), list(COLUMNS))
        self.assertEqual(csv_rows[0]["product_name"], "한글, 상품")
        self.assertEqual(csv_rows[0]["as_of"], "")
        self.assertEqual(csv_rows[1]["brand_code"], "")
        self.assertEqual(result["metrics"]["unexpected_fields"], {"source_type": 2})
        self.assertEqual(result["metrics"]["as_of_null_count"], 2)
        self.assertEqual(
            json.loads((self.review / "product_safe_manifest.review.json").read_text(encoding="utf-8")),
            json.loads(before_manifest),
        )
        self.assertEqual(self.snapshot.read_bytes(), before_snapshot)
        self.assertEqual(self.manifest.read_bytes(), before_manifest)

    def test_manifest_hash_mismatch_stops_before_output(self):
        self._fixture([{"product_no": 1}])
        manifest = json.loads(self.manifest.read_text(encoding="utf-8"))
        manifest["snapshot_file_sha256"] = "0" * 64
        self.manifest.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "hash does not match"):
            build_review(self.snapshot, self.manifest, self.review)
        self.assertFalse(self.review.exists())

    def test_formula_like_text_is_not_written_to_excel_csv(self):
        self._fixture([{
            "product_no": 1, "product_code": "P001", "product_name": "=1+1",
            "data_mode": "PRIVATE_ACTUAL_EVAL", "quality_status": "BLOCKED",
        }])
        with self.assertRaisesRegex(ValueError, "formula-like"):
            build_review(self.snapshot, self.manifest, self.review)
        self.assertFalse(self.review.exists())
