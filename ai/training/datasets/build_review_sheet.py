from __future__ import annotations

import csv
import json
from pathlib import Path


INPUT_PATH = Path(
    "artifacts/experiments/day11/nlu_review_candidates.jsonl"
)

OUTPUT_PATH = Path(
    "artifacts/experiments/day11/nlu_review_sheet.csv"
)


def load_jsonl(path: Path) -> list[dict]:
    rows = []

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if line:
                rows.append(json.loads(line))

    return rows


def main() -> int:
    rows = load_jsonl(INPUT_PATH)

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fieldnames = [
        "record_id",
        "group_id",
        "board_no",
        "article_no",
        "source_role",
        "input_text",
        "proposed_intent",
        "intent",
        "entities_json",
        "risk",
        "required_lookup_json",
        "human_review_required",
        "review_status",
        "reviewer",
        "reviewed_at",
        "label_version",
        "review_note",
    ]

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

        for row in rows:
            review = row["review"]

            writer.writerow(
                {
                    "record_id": row["record_id"],
                    "group_id": row["group_id"],
                    "board_no": row["board_no"],
                    "article_no": row["article_no"],
                    "source_role": row["source_role"],
                    "input_text": row["input_text"],
                    "proposed_intent": "",
                    "intent": "",
                    "entities_json": "[]",
                    "risk": "",
                    "required_lookup_json": "[]",
                    "human_review_required": "",
                    "review_status": "REVIEW_REQUIRED",
                    "reviewer": "",
                    "reviewed_at": "",
                    "label_version": review["label_version"],
                    "review_note": "",
                }
            )

    print(f"REVIEW_ROWS={len(rows)}")
    print(f"OUTPUT={OUTPUT_PATH}")
    print("STATUS=REVIEW_SHEET_CREATED")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())