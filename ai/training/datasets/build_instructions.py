from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_HANDOFF = Path("artifacts/integration/day08/ai_handoff.json")
DEFAULT_OUTPUT = Path("artifacts/experiments/day11")

EXPECTED_COLLECTED = 700
EXPECTED_CANONICAL = 624
EXPECTED_DEDUPE_EXCLUDED = 76
EXPECTED_CONFLICTS = 0
EXPECTED_QUERY_EVAL_SEED = 608
EXPECTED_CUSTOMER_INQUIRIES = 302
EXPECTED_REPLY_CANDIDATES = 306

MIN_CLASS_SUPPORT = 10
MIN_TRAIN_SUPPORT = 8
MIN_VALIDATION_SUPPORT = 2

LABEL_VERSION = "nlu-label-v1"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_handoff(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def stable_group_id(record: dict[str, Any]) -> str:
    # 개인정보가 아닌 board/article 관계만 이용한다.
    board_no = record.get("board_no")
    article_no = record.get("article_no")
    parent_article_no = record.get("parent_article_no")

    root_no = parent_article_no or article_no
    raw = f"board:{board_no}:thread:{root_no}"

    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def validate_source_counts(inquiries: dict[str, Any]) -> None:
    checks = {
        "collected_article_count": EXPECTED_COLLECTED,
        "canonical_candidate_count": EXPECTED_CANONICAL,
        "dedupe_excluded_count": EXPECTED_DEDUPE_EXCLUDED,
        "conflict_quarantine_count": EXPECTED_CONFLICTS,
    }

    for field, expected in checks.items():
        actual = inquiries.get(field)
        if actual != expected:
            raise ValueError(
                f"{field}: expected={expected}, actual={actual}"
            )

    seed = inquiries.get("query_eval_seed", [])

    if len(seed) != EXPECTED_QUERY_EVAL_SEED:
        raise ValueError(
            "query_eval_seed count mismatch: "
            f"expected={EXPECTED_QUERY_EVAL_SEED}, actual={len(seed)}"
        )

    source_counts = Counter(row.get("source_type") for row in seed)

    if source_counts["CUSTOMER_INQUIRY"] != EXPECTED_CUSTOMER_INQUIRIES:
        raise ValueError(
            "CUSTOMER_INQUIRY count mismatch: "
            f"expected={EXPECTED_CUSTOMER_INQUIRIES}, "
            f"actual={source_counts['CUSTOMER_INQUIRY']}"
        )

    if (
        source_counts["HISTORICAL_REPLY_CANDIDATE"]
        != EXPECTED_REPLY_CANDIDATES
    ):
        raise ValueError(
            "HISTORICAL_REPLY_CANDIDATE count mismatch: "
            f"expected={EXPECTED_REPLY_CANDIDATES}, "
            f"actual={source_counts['HISTORICAL_REPLY_CANDIDATE']}"
        )


def build_review_candidates(
    inquiries: dict[str, Any],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    for row in inquiries["query_eval_seed"]:
        if row.get("source_type") != "CUSTOMER_INQUIRY":
            continue

        text = row.get("sanitized_query_text")

        if not text:
            continue

        result.append(
            {
                "record_id": (
                    f"cafe24-b{row.get('board_no')}-a{row.get('article_no')}"
                ),
                "group_id": stable_group_id(row),
                "board_no": row.get("board_no"),
                "article_no": row.get("article_no"),
                "source_role": row.get("source_role"),
                "input_text": text,
                "review": {
                    "status": "REVIEW_REQUIRED",
                    "reviewer": None,
                    "reviewed_at": None,
                    "label_version": LABEL_VERSION,
                    "intent": None,
                    "entities": [],
                    "risk": None,
                    "required_lookup": [],
                    "human_review_required": None,
                },
            }
        )

    return result


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(
                json.dumps(
                    row,
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n"
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--handoff",
        type=Path,
        default=DEFAULT_HANDOFF,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT,
    )
    parser.add_argument(
        "--fixture",
        action="store_true",
        help="구조 검증용. 실제 미검수 label을 READY로 승격하지 않는다.",
    )
    args = parser.parse_args()

    handoff = load_handoff(args.handoff)
    inquiries = handoff["inquiries"]

    validate_source_counts(inquiries)

    candidates = build_review_candidates(inquiries)

    if len(candidates) != EXPECTED_CUSTOMER_INQUIRIES:
        raise ValueError(
            "review candidate count mismatch: "
            f"expected={EXPECTED_CUSTOMER_INQUIRIES}, "
            f"actual={len(candidates)}"
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)

    candidates_path = args.output_dir / "nlu_review_candidates.jsonl"
    manifest_path = args.output_dir / "instruction_manifest.json"
    audit_path = args.output_dir / "label_audit.json"

    write_jsonl(candidates_path, candidates)

    reviewed = [
        row
        for row in candidates
        if row["review"]["status"] == "REVIEWED"
    ]

    audit = {
        "schema_version": "day11-label-audit.v1",
        "label_version": LABEL_VERSION,
        "minimum_class_support": {
            "total": MIN_CLASS_SUPPORT,
            "train": MIN_TRAIN_SUPPORT,
            "validation": MIN_VALIDATION_SUPPORT,
        },
        "real_inquiry_candidates": len(candidates),
        "reviewed_count": len(reviewed),
        "unreviewed_count": len(candidates) - len(reviewed),
        "train_ready_count": 0,
        "validation_ready_count": 0,
        "test_accessed": False,
        "status": "BLOCKED_REVIEW_REQUIRED",
        "note": (
            "미검수 label은 Train/Validation truth로 승격하지 않는다. "
            "Historical reply candidate는 NLU truth에서 제외한다."
        ),
    }

    audit_path.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    manifest = {
        "schema_version": "instruction-dataset-manifest.v1",
        "source": str(args.handoff),
        "source_sha256": sha256_file(args.handoff),
        "source_class": "SANITIZED_REAL",
        "collected_article_count": inquiries["collected_article_count"],
        "canonical_candidate_count": inquiries["canonical_candidate_count"],
        "dedupe_excluded_count": inquiries["dedupe_excluded_count"],
        "conflict_quarantine_count": inquiries["conflict_quarantine_count"],
        "query_eval_seed_count": len(inquiries["query_eval_seed"]),
        "customer_inquiry_count": len(candidates),
        "historical_reply_candidate_count": EXPECTED_REPLY_CANDIDATES,
        "review_candidates": str(candidates_path),
        "review_candidates_sha256": sha256_file(candidates_path),
        "label_audit": str(audit_path),
        "label_audit_sha256": sha256_file(audit_path),
        "retrieval_golden_separate": True,
        "test_sealed": True,
        "status": audit["status"],
    }

    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"REAL_INQUIRY_CANDIDATES={len(candidates)}")
    print(f"REVIEWED={len(reviewed)}")
    print(f"UNREVIEWED={len(candidates) - len(reviewed)}")
    print("TRAIN_READY=0")
    print("VALIDATION_READY=0")
    print("TEST_ACCESSED=False")
    print(f"STATUS={audit['status']}")
    print(f"CANDIDATES={candidates_path}")
    print(f"MANIFEST={manifest_path}")
    print(f"LABEL_AUDIT={audit_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())