from __future__ import annotations

import csv
import json
from pathlib import Path


INPUT_PATH = Path(
    "artifacts/experiments/day11/base_label_pilot_20.jsonl"
)

RESULT_PATH = Path(
    "artifacts/experiments/day11/base_label_pilot_20_results.jsonl"
)

OUTPUT_PATH = Path(
    "artifacts/experiments/day11/base_label_pilot_20_review.csv"
)


ALLOWED_INTENTS = {
    "PRODUCT_INFO",
    "COMPATIBILITY",
    "STOCK_AVAILABILITY",
    "RESTOCK",
    "ORDER_STATUS",
    "DELIVERY",
    "RESERVATION_PREORDER",
    "RETURN_EXCHANGE",
    "REFUND_CANCEL",
    "OTHER",
}

ALLOWED_EXCLUSIONS = {
    "NON_INQUIRY",
    "INSUFFICIENT_CONTEXT",
    "OUT_OF_SCOPE",
}


def load_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def conditional_schema_valid(proposal: dict | None) -> bool:
    if not isinstance(proposal, dict):
        return False

    eligible = proposal.get("eligible_for_nlu")
    intent = proposal.get("intent")
    exclusion = proposal.get("exclusion_reason")

    if eligible is True:
        if exclusion is not None:
            return False
        if intent not in ALLOWED_INTENTS:
            return False

    elif eligible is False:
        if exclusion not in ALLOWED_EXCLUSIONS:
            return False
        if intent not in {None, "", "OTHER"}:
            return False

    else:
        return False

    if not isinstance(proposal.get("entities"), list):
        return False

    if proposal.get("risk") not in {
        "LOW",
        "MEDIUM",
        "HIGH",
        "PROHIBITED",
    }:
        return False

    if not isinstance(
        proposal.get("human_review_required"),
        bool,
    ):
        return False

    return True


def main() -> int:
    inputs = load_jsonl(INPUT_PATH)
    results = load_jsonl(RESULT_PATH)

    input_map = {
        row["record_id"]: row
        for row in inputs
    }

    fieldnames = [
        "record_id",
        "input_text",
        "qwen_schema_valid",
        "qwen_eligible_for_nlu",
        "qwen_exclusion_reason",
        "qwen_intent",
        "qwen_entities_json",
        "qwen_risk",
        "qwen_human_review_required",
        "review_eligible_for_nlu",
        "review_exclusion_reason",
        "review_intent",
        "review_entities_json",
        "review_risk",
        "review_human_review_required",
        "review_status",
        "review_note",
    ]

    output_rows = []

    for result in results:
        source = input_map[result["record_id"]]
        proposal = result.get("proposal") or {}

        output_rows.append(
            {
                "record_id": result["record_id"],
                "input_text": source["messages"][1]["content"],
                "qwen_schema_valid": conditional_schema_valid(
                    result.get("proposal")
                ),
                "qwen_eligible_for_nlu": proposal.get(
                    "eligible_for_nlu"
                ),
                "qwen_exclusion_reason": proposal.get(
                    "exclusion_reason"
                ),
                "qwen_intent": proposal.get("intent"),
                "qwen_entities_json": json.dumps(
                    proposal.get("entities", []),
                    ensure_ascii=False,
                ),
                "qwen_risk": proposal.get("risk"),
                "qwen_human_review_required": proposal.get(
                    "human_review_required"
                ),
                "review_eligible_for_nlu": "",
                "review_exclusion_reason": "",
                "review_intent": "",
                "review_entities_json": "",
                "review_risk": "",
                "review_human_review_required": "",
                "review_status": "REVIEW_REQUIRED",
                "review_note": "",
            }
        )

    with OUTPUT_PATH.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
        )
        writer.writeheader()
        writer.writerows(output_rows)

    valid = sum(
        row["qwen_schema_valid"] is True
        for row in output_rows
    )

    print(f"ROWS={len(output_rows)}")
    print(f"QWEN_CONDITIONAL_SCHEMA_VALID={valid}")
    print(f"QWEN_CONDITIONAL_SCHEMA_INVALID={len(output_rows) - valid}")
    print(f"OUTPUT={OUTPUT_PATH}")
    print("TRUTH_PROMOTED=0")
    print("STATUS=HUMAN_REVIEW_REQUIRED")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())