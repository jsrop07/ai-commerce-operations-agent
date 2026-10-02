"""Create a minimal V2-safe category projection from the Day09 catalog handoff."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any


SOURCE_PATH = Path(
    "artifacts/integration/day09/ai_catalog_handoff.json"
)

OUTPUT_DIR = Path(
    "artifacts/experiments/V2-DB/private/category"
)

SNAPSHOT_PATH = OUTPUT_DIR / "category_v2_safe_snapshot.jsonl"
MANIFEST_PATH = OUTPUT_DIR / "category_v2_safe_manifest.json"
REVIEW_PATH = OUTPUT_DIR / "category_v2_safe_review.csv"

EXPECTED_SOURCE_SCHEMA = "day09-ai-catalog-handoff.v1"
EXPECTED_CATEGORY_COUNT = 123

# Observed in this fixed snapshot:
# category 1 is absent, while exactly ten depth=1 categories reference it.
SOURCE_ROOT_SENTINEL = 1


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def canonical_sha256(rows: list[dict[str, Any]]) -> str:
    payload = json.dumps(
        rows,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(payload).hexdigest()


def main() -> None:
    if not SOURCE_PATH.is_file():
        raise RuntimeError("Day09 category handoff not found")

    source = json.loads(
        SOURCE_PATH.read_text(encoding="utf-8")
    )

    if source.get("schema_version") != EXPECTED_SOURCE_SCHEMA:
        raise RuntimeError("unexpected Day09 handoff schema")

    categories = source.get("categories")

    if not isinstance(categories, list):
        raise RuntimeError("categories must be a list")

    if len(categories) != EXPECTED_CATEGORY_COUNT:
        raise RuntimeError(
            f"unexpected category count: {len(categories)}"
        )

    category_nos = {
        int(row["category_no"])
        for row in categories
    }

    if len(category_nos) != EXPECTED_CATEGORY_COUNT:
        raise RuntimeError("duplicate category_no detected")

    root_children = [
        row
        for row in categories
        if row.get("parent_category_no")
        not in (None, "", 0, "0")
        and int(row["parent_category_no"])
        == SOURCE_ROOT_SENTINEL
    ]

    if len(root_children) != 10:
        raise RuntimeError(
            "unexpected root sentinel child count"
        )

    if any(
        int(row["category_depth"]) != 1
        for row in root_children
    ):
        raise RuntimeError(
            "root sentinel references non-depth-1 category"
        )

    projected: list[dict[str, Any]] = []

    for row in categories:
        category_no = int(row["category_no"])
        category_name = str(
            row.get("category_name") or ""
        ).strip()
        category_depth = int(row["category_depth"])

        if not category_name:
            raise RuntimeError(
                f"missing category_name for {category_no}"
            )

        if category_depth < 0:
            raise RuntimeError(
                f"negative category_depth for {category_no}"
            )

        raw_parent = row.get("parent_category_no")

        if raw_parent in (None, "", 0, "0"):
            parent_category_no = None
        else:
            parent_category_no = int(raw_parent)

        if parent_category_no == SOURCE_ROOT_SENTINEL:
            if category_depth != 1:
                raise RuntimeError(
                    "root sentinel used outside depth 1"
                )

            parent_category_no = None

        elif (
            parent_category_no is not None
            and parent_category_no not in category_nos
        ):
            raise RuntimeError(
                "unresolved parent_category_no "
                f"{parent_category_no}"
            )

        as_of = row.get("as_of")

        projected.append(
            {
                "category_no": category_no,
                "category_name": category_name,
                "parent_category_no": parent_category_no,
                "category_depth": category_depth,
                "as_of": as_of,
            }
        )

    projected.sort(
        key=lambda row: int(row["category_no"])
    )

    projected_nos = {
        int(row["category_no"])
        for row in projected
    }

    unresolved_parents = sorted(
        {
            int(row["parent_category_no"])
            for row in projected
            if row["parent_category_no"] is not None
            and int(row["parent_category_no"])
            not in projected_nos
        }
    )

    if unresolved_parents:
        raise RuntimeError(
            f"unresolved projected parents: "
            f"{unresolved_parents}"
        )

    normalized_root_count = sum(
        1
        for row in projected
        if row["parent_category_no"] is None
        and row["category_depth"] == 1
    )

    if normalized_root_count != 10:
        raise RuntimeError(
            "unexpected normalized root count"
        )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with SNAPSHOT_PATH.open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as file:
        for row in projected:
            file.write(
                json.dumps(
                    row,
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n"
            )

    with REVIEW_PATH.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "category_no",
                "category_name",
                "parent_category_no",
                "category_depth",
                "as_of",
            ],
        )

        writer.writeheader()
        writer.writerows(projected)

    manifest = {
        "schema_version": "v2-category-safe-candidate.v1",
        "source_schema_version": EXPECTED_SOURCE_SCHEMA,
        "source_file": str(SOURCE_PATH).replace("\\", "/"),
        "snapshot_file": str(SNAPSHOT_PATH).replace("\\", "/"),
        "review_file": str(REVIEW_PATH).replace("\\", "/"),
        "category_count": len(projected),
        "normalized_root_sentinel": SOURCE_ROOT_SENTINEL,
        "normalized_root_count": normalized_root_count,
        "unresolved_parent_count": 0,
        "fields": [
            "category_no",
            "category_name",
            "parent_category_no",
            "category_depth",
            "as_of",
        ],
        "excluded_fields": [
            "evidence_ids",
            "provenance",
            "source_classification",
        ],
        "canonical_sha256": canonical_sha256(projected),
        "approval_status": "PENDING_USER_REVIEW",
    }

    MANIFEST_PATH.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print("CATEGORY_SAFE_PROJECTION_OK")
    print(f"CATEGORY_COUNT={len(projected)}")
    print(
        f"NORMALIZED_ROOT_COUNT="
        f"{normalized_root_count}"
    )
    print("UNRESOLVED_PARENT_COUNT=0")
    print(
        f"SNAPSHOT_SHA256="
        f"{sha256_file(SNAPSHOT_PATH)}"
    )
    print(
        f"MANIFEST_SHA256="
        f"{sha256_file(MANIFEST_PATH)}"
    )
    print(f"REVIEW_FILE={REVIEW_PATH}")


if __name__ == "__main__":
    main()