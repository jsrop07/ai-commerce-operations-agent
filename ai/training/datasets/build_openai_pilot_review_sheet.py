from __future__ import annotations

import csv
import json
from pathlib import Path


INPUT_PATH = Path(
    "artifacts/experiments/day11/safe_pilot_20.jsonl"
)

RESULT_PATH = Path(
    "artifacts/experiments/day11/openai_label_pilot_20_results.jsonl"
)

OUTPUT_PATH = Path(
    "artifacts/experiments/day11/openai_label_pilot_20_review.csv"
)


def load_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]


def main() -> int:
    inputs = load_jsonl(INPUT_PATH)
    results = load_jsonl(RESULT_PATH)

    input_map = {
        row["record_id"]: row
        for row in inputs
    }

    fields = [
        "record_id",
        "input_text",
        "openai_eligible_for_nlu",
        "openai_exclusion_reason",
        "openai_intent",
        "openai_entities_json",
        "openai_risk",
        "openai_human_review_required",
        "review_eligible_for_nlu",
        "review_exclusion_reason",
        "review_intent",
        "review_entities_json",
        "review_risk",
        "review_human_review_required",
        "review_status",
        "review_note",
    ]

    rows = []

    for result in results:
        source = input_map[result["record_id"]]
        proposal = result["proposal"]

        rows.append(
            {
                "record_id": result["record_id"],
                "input_text": source["input_text"],
                "openai_eligible_for_nlu": proposal[
                    "eligible_for_nlu"
                ],
                "openai_exclusion_reason": proposal[
                    "exclusion_reason"
                ],
                "openai_intent": proposal["intent"],
                "openai_entities_json": json.dumps(
                    proposal["entities"],
                    ensure_ascii=False,
                ),
                "openai_risk": proposal["risk"],
                "openai_human_review_required": proposal[
                    "human_review_required"
                ],
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
            fieldnames=fields,
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"ROWS={len(rows)}")
    print(f"OUTPUT={OUTPUT_PATH}")
    print("STATUS=HUMAN_REVIEW_REQUIRED")
    print("TRUTH_PROMOTED=0")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())