from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ALLOWED_SOURCE_TYPES = {
    "PRODUCT",
    "POLICY",
    "INVENTORY_SNAPSHOT",
    "INCOMING_STOCK",
}

ALLOWED_CATEGORIES = {
    "PRODUCT_EXACT_ALIAS",
    "POLICY",
    "INVENTORY_RESERVATION_INTERPRETATION",
    "SCHEDULE_RELATION",
    "AMBIGUOUS_TARGET",
    "NO_EVIDENCE_OR_STALE",
}

ALLOWED_ANSWERABILITY = {
    "ANSWERABLE",
    "HOLD",
}

ALLOWED_HOLD_REASONS = {
    "AMBIGUOUS_TARGET",
    "NO_SOURCE",
    "STALE_EVIDENCE",
}

FORBIDDEN_KEYS = {
    "order_id",
    "order_line_id",
    "customer_id",
    "shipping_id",
    "payment_id",
    "inquiry_id",
    "affected_order_ids",
    "reservation_id",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue

        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"{path}:{line_number}: invalid JSON: {exc}"
            ) from exc

        if not isinstance(row, dict):
            raise ValueError(
                f"{path}:{line_number}: row must be object"
            )

        rows.append(row)

    return rows


def excerpt_hash(text: str) -> str:
    return "sha256:" + hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def validate_corpus(
    corpus: list[dict[str, Any]],
) -> dict[tuple[str, str], dict[str, Any]]:
    index: dict[
        tuple[str, str],
        dict[str, Any],
    ] = {}

    for row in corpus:
        source_id = row.get("source_id")
        version = row.get("version")
        source_type = row.get("source_type")

        if not source_id or not version:
            raise ValueError(
                "corpus source_id/version required"
            )

        key = (source_id, version)

        if key in index:
            raise ValueError(
                f"duplicate corpus source/version: {key}"
            )

        if source_type not in ALLOWED_SOURCE_TYPES:
            raise ValueError(
                f"unsupported source_type: "
                f"{source_id}:{source_type}"
            )

        if row.get("pii_status") != "CLEAN":
            raise ValueError(
                f"pii_status must be CLEAN: {source_id}"
            )

        if row.get("data_mode") != "SYNTHETIC_DEMO":
            raise ValueError(
                f"data_mode must be SYNTHETIC_DEMO: "
                f"{source_id}"
            )

        if row.get("visibility") != "DEMO_PUBLIC":
            raise ValueError(
                f"visibility must be DEMO_PUBLIC: "
                f"{source_id}"
            )

        for forbidden_key in FORBIDDEN_KEYS:
            if forbidden_key in row:
                raise ValueError(
                    f"forbidden corpus key: "
                    f"{source_id}:{forbidden_key}"
                )

        if source_type in {
            "INVENTORY_SNAPSHOT",
            "INCOMING_STOCK",
        }:
            if not row.get("as_of"):
                raise ValueError(
                    f"live source missing as_of: "
                    f"{source_id}"
                )

        content = row.get("content")

        if not isinstance(content, str) or not content.strip():
            raise ValueError(
                f"corpus content required: {source_id}"
            )

        index[key] = row

    return index


def validate_eval(
    rows: list[dict[str, Any]],
    corpus_index: dict[
        tuple[str, str],
        dict[str, Any],
    ],
    expected_split: str,
) -> None:
    case_ids: set[str] = set()
    case_groups: set[str] = set()

    for row in rows:
        case_id = row.get("case_id")
        case_group = row.get("case_group")

        if not case_id or not case_group:
            raise ValueError(
                "case_id/case_group required"
            )

        if case_id in case_ids:
            raise ValueError(
                f"duplicate case_id: {case_id}"
            )

        if case_group in case_groups:
            raise ValueError(
                f"duplicate case_group: {case_group}"
            )

        case_ids.add(case_id)
        case_groups.add(case_group)

        category = row.get("category")

        if category not in ALLOWED_CATEGORIES:
            raise ValueError(
                f"{case_id}: invalid category: {category}"
            )

        if row.get("split") != expected_split:
            raise ValueError(
                f"{case_id}: split must be "
                f"{expected_split}"
            )

        if row.get("data_mode") != "SYNTHETIC_DEMO":
            raise ValueError(
                f"{case_id}: invalid data_mode"
            )

        answerability = row.get("answerability")

        if answerability not in ALLOWED_ANSWERABILITY:
            raise ValueError(
                f"{case_id}: invalid answerability"
            )

        expected_answer = row.get("expected_answer")
        hold_reason = row.get("hold_reason")
        evidence = row.get("evidence")

        if not isinstance(evidence, list):
            raise ValueError(
                f"{case_id}: evidence must be list"
            )

        if answerability == "ANSWERABLE":
            if not expected_answer:
                raise ValueError(
                    f"{case_id}: ANSWERABLE needs "
                    "expected_answer"
                )

            if hold_reason is not None:
                raise ValueError(
                    f"{case_id}: ANSWERABLE cannot "
                    "have hold_reason"
                )

            if not evidence:
                raise ValueError(
                    f"{case_id}: ANSWERABLE needs evidence"
                )

        if answerability == "HOLD":
            if expected_answer is not None:
                raise ValueError(
                    f"{case_id}: HOLD expected_answer "
                    "must be null"
                )

            if hold_reason not in ALLOWED_HOLD_REASONS:
                raise ValueError(
                    f"{case_id}: invalid hold_reason"
                )

        for item in evidence:
            source_id = item.get("source_id")
            version = item.get("version")
            excerpt = item.get("expected_excerpt")
            expected_hash = item.get(
                "expected_excerpt_hash"
            )

            key = (source_id, version)

            if key not in corpus_index:
                raise ValueError(
                    f"{case_id}: dangling evidence "
                    f"{source_id}:{version}"
                )

            if not excerpt:
                raise ValueError(
                    f"{case_id}: evidence excerpt missing"
                )

            corpus_content = corpus_index[key]["content"]

            if excerpt not in corpus_content:
                raise ValueError(
                    f"{case_id}: evidence excerpt "
                    f"not found in corpus: {source_id}"
                )

            actual_hash = excerpt_hash(excerpt)

            if expected_hash != actual_hash:
                raise ValueError(
                    f"{case_id}: excerpt hash mismatch: "
                    f"{source_id}"
                )

    category_counts: dict[str, int] = {}

    for row in rows:
        category = row["category"]
        category_counts[category] = (
            category_counts.get(category, 0) + 1
        )

    expected_per_category = (
        4 if expected_split == "DEV" else 2
    )

    for category in ALLOWED_CATEGORIES:
        actual = category_counts.get(category, 0)

        if actual != expected_per_category:
            raise ValueError(
                f"{expected_split}: "
                f"{category} count must be "
                f"{expected_per_category}, got {actual}"
            )

    expected_total = (
        24 if expected_split == "DEV" else 12
    )

    if len(rows) != expected_total:
        raise ValueError(
            f"{expected_split}: total count must be "
            f"{expected_total}, got {len(rows)}"
        )

    if expected_split == "DEV":
        relation_case_count = sum(
            bool(row.get("relation_tags"))
            for row in rows
        )

        if relation_case_count < 6:
            raise ValueError(
                "DEV: relation-tagged cases "
                f"must be >= 6, got {relation_case_count}"
            )

def main() -> int:
    if len(sys.argv) != 3:
        print(
            "usage: python -m "
            "ai.evaluation.validate_grounded_eval "
            "<corpus.jsonl> <eval.jsonl>"
        )
        return 2

    corpus_path = Path(sys.argv[1])
    eval_path = Path(sys.argv[2])

    try:
        corpus = load_jsonl(corpus_path)
        eval_rows = load_jsonl(eval_path)

        corpus_index = validate_corpus(corpus)

        split = "FINAL" if "final" in eval_path.name else "DEV"

        validate_eval(
            eval_rows,
            corpus_index,
            split,
        )

    except (
        ValueError,
        KeyError,
        TypeError,
        OSError,
    ) as exc:
        print(f"VALIDATION_FAILED: {exc}")
        return 1

    print(
        "VALIDATION_OK "
        f"corpus={len(corpus)} "
        f"eval={len(eval_rows)} "
        f"split={split}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())