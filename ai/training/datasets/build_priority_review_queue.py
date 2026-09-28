from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path


INPUT_PATH = Path(
    "artifacts/experiments/day11/openai_review_batch.jsonl"
)

RESULT_PATH = Path(
    "artifacts/experiments/day11/openai_review_batch_results.jsonl"
)

OUTPUT_PATH = Path(
    "artifacts/experiments/day11/priority_review_queue.csv"
)

CURRENT_SUPPORT = {
    "AFTER_SERVICE": 8,
    "DELIVERY": 5,
    "REFUND_CANCEL": 2,
    "OTHER": 1,
    "RETURN_EXCHANGE": 1,
    "RESTOCK": 1,
    "PRODUCT_INFO": 1,
    "COMPATIBILITY": 0,
    "STOCK_AVAILABILITY": 0,
    "ORDER_STATUS": 0,
    "RESERVATION_PREORDER": 0,
}

TARGET_SUPPORT = 10


def load_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> int:
    inputs = {
        row["record_id"]: row
        for row in load_jsonl(INPUT_PATH)
    }

    results = load_jsonl(RESULT_PATH)

    rows = []

    for result in results:
        if not result.get("schema_valid"):
            continue

        proposal = result.get("proposal") or {}
        intent = proposal.get("intent")

        if intent is None:
            continue

        current = CURRENT_SUPPORT.get(intent, 0)
        deficit = max(TARGET_SUPPORT - current, 0)

        rows.append(
            {
                "record_id": result["record_id"],
                "input_text": inputs[result["record_id"]]["input_text"],
                "proposed_intent": intent,
                "proposed_risk": proposal["risk"],
                "proposed_eligible_for_nlu": proposal["eligible_for_nlu"],
                "proposed_human_review_required": proposal[
                    "human_review_required"
                ],
                "current_reviewed_support": current,
                "support_deficit": deficit,
                "review_intent": "",
                "review_risk": "",
                "review_eligible_for_nlu": "",
                "review_human_review_required": "",
                "review_status": "REVIEW_REQUIRED",
                "review_note": "",
            }
        )

    rows.sort(
        key=lambda r: (
            -int(r["support_deficit"]),
            r["proposed_intent"],
            r["record_id"],
        )
    )

    with OUTPUT_PATH.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=rows[0].keys(),
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"ROWS={len(rows)}")
    print(
        "PROPOSED_COUNTS=",
        dict(Counter(r["proposed_intent"] for r in rows)),
    )
    print(f"OUTPUT={OUTPUT_PATH}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())