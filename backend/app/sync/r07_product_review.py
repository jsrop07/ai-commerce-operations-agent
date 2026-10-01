"""Turn an existing safe PRODUCT snapshot into human review files only."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

PRODUCT_DIR = Path("artifacts/experiments/OPS-R07-PRE/private/product")
SNAPSHOT_PATH = PRODUCT_DIR / "product_safe_snapshot.jsonl"
MANIFEST_PATH = PRODUCT_DIR / "product_safe_manifest.json"
REVIEW_DIR = PRODUCT_DIR / "review"

COLUMNS = (
    "product_no",
    "product_code",
    "custom_product_code",
    "product_name",
    "brand_code",
    "shop_no",
    "display",
    "selling",
    "sold_out",
    "category_nos",
    "is_preorder",
    "retail_price",
    "price",
    "maximum_quantity",
    "list_image",
    "origin_place_value",
    "updated_date",
    "as_of",
    "source",
    "version",
    "data_mode",
    "quality_status",
)
NOTICE = "이 파일은 사용자 직접 검수용이며 AI/RAG 실험 승인 자료가 아님"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _blank(value: object) -> bool:
    return value is None or isinstance(value, str) and not value.strip()


def _csv_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return ",".join(str(item) for item in value)
    raise ValueError("review field has unsupported value type")


def _sample_indices(count: int) -> list[int]:
    starts = (0, count // 4, count // 2, count * 3 // 4, max(0, count - 10))
    return sorted({index for start in starts for index in range(start, min(start + 10, count))})


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=COLUMNS, lineterminator="\r\n")
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != list(COLUMNS):
            raise ValueError("review CSV columns differ from allowlist")
        return list(reader)


def _counts(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(
        "NULL" if row.get(field) is None else str(row[field]) for row in rows
    ).items()))


def _duplicate_count(rows: list[dict[str, Any]], field: str) -> int:
    seen: set[object] = set()
    duplicates = 0
    for row in rows:
        value = row.get(field)
        if _blank(value):
            continue
        if value in seen:
            duplicates += 1
        else:
            seen.add(value)
    return duplicates


def build_review(
    snapshot_path: Path = SNAPSHOT_PATH,
    manifest_path: Path = MANIFEST_PATH,
    review_dir: Path = REVIEW_DIR,
) -> dict[str, object]:
    snapshot_bytes = snapshot_path.read_bytes()
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("invalid manifest")
    if manifest.get("official_status") != "BLOCKED" or manifest.get("retrieval_compatible") is not False:
        raise ValueError("review input is not a blocked candidate")
    if manifest.get("snapshot_file_sha256") != _sha256(snapshot_bytes):
        raise ValueError("snapshot hash does not match manifest")
    rows: list[dict[str, Any]] = []
    unexpected: Counter[str] = Counter()
    for line in snapshot_bytes.splitlines():
        if not line.strip():
            raise ValueError("snapshot has an empty record line")
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError("snapshot row is not an object")
        unexpected.update(set(row) - set(COLUMNS))
        rows.append(row)
    if manifest.get("counts", {}).get("projected_records") != len(rows):
        raise ValueError("snapshot count does not match manifest")

    review_rows = [{key: _csv_value(row.get(key)) for key in COLUMNS} for row in rows]
    formula_like_values = sum(
        value.lstrip().startswith(("=", "+", "-", "@"))
        for row in review_rows for value in row.values() if value
    )
    if formula_like_values:
        raise ValueError("CSV formula-like value requires manual handling")
    sample_indices = _sample_indices(len(rows))
    sample_rows = [review_rows[index] for index in sample_indices]

    review_dir.mkdir(parents=True, exist_ok=True)
    csv_path = review_dir / "product_safe_review.csv"
    sample_path = review_dir / "product_safe_review_sample.csv"
    pretty_path = review_dir / "product_safe_manifest.review.json"
    summary_path = review_dir / "product_safe_review_summary.txt"
    _write_csv(csv_path, review_rows)
    _write_csv(sample_path, sample_rows)
    if _read_csv(csv_path) != review_rows or _read_csv(sample_path) != sample_rows:
        raise ValueError("review CSV values differ from snapshot projection")
    pretty_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if json.loads(pretty_path.read_text(encoding="utf-8")) != manifest:
        raise ValueError("pretty manifest changed meaning")
    if snapshot_path.read_bytes() != snapshot_bytes or manifest_path.read_bytes() != manifest_bytes:
        raise ValueError("review source changed during generation")

    hashes = {
        "input_snapshot_sha256": _sha256(snapshot_bytes),
        "input_manifest_sha256": _sha256(manifest_bytes),
        "review_csv_sha256": _sha256(csv_path.read_bytes()),
        "review_sample_csv_sha256": _sha256(sample_path.read_bytes()),
        "review_pretty_manifest_sha256": _sha256(pretty_path.read_bytes()),
    }
    metrics = {
        "snapshot_records": len(rows),
        "csv_rows": len(review_rows),
        "sample_csv_rows": len(sample_rows),
        "xlsx_rows": None,
        "columns": list(COLUMNS),
        "unexpected_field_count": len(unexpected),
        "unexpected_fields": dict(sorted(unexpected.items())),
        "empty_product_name": sum(_blank(row.get("product_name")) for row in rows),
        "empty_product_code": sum(_blank(row.get("product_code")) for row in rows),
        "duplicate_product_no": _duplicate_count(rows, "product_no"),
        "duplicate_product_code": _duplicate_count(rows, "product_code"),
        "data_mode_counts": _counts(rows, "data_mode"),
        "quality_status_counts": _counts(rows, "quality_status"),
        "as_of_null_count": sum(row.get("as_of") is None for row in rows),
        "csv_formula_like_value_count": formula_like_values,
    }
    lines = [
        NOTICE,
        "null_rule: JSON null -> empty CSV cell; non-null values unchanged",
        "encoding: UTF-8 BOM; CRLF row endings",
        "sample_rule: original zero-based positions 0, floor(N/4), floor(N/2), floor(3N/4), max(0,N-10); 10 rows from each; overlapping positions deduplicated and sorted",
        "xlsx: not generated; no project XLSX authoring dependency",
    ]
    lines.extend(f"{key}: {json.dumps(value, ensure_ascii=False, sort_keys=True)}" for key, value in metrics.items())
    lines.extend(f"{key}: {value}" for key, value in hashes.items())
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"metrics": metrics, "hashes": hashes, "review_dir": str(review_dir)}


if __name__ == "__main__":
    result = build_review()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
