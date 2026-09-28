from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path


INPUT_PATH = Path(
    "artifacts/experiments/day11/nlu_review_sheet_proposed.csv"
)

SAMPLES_PER_INTENT = 2


def main() -> int:
    with INPUT_PATH.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as f:
        rows = list(csv.DictReader(f))

    grouped: dict[str, list[dict]] = defaultdict(list)

    for row in rows:
        grouped[row["proposed_intent"]].append(row)

    print(f"TOTAL={len(rows)}")

    for intent in sorted(grouped):
        items = grouped[intent]

        print()
        print(f"=== {intent} ({len(items)}) ===")

        for row in items[:SAMPLES_PER_INTENT]:
            text = " ".join(row["input_text"].split())

            if len(text) > 160:
                text = text[:157] + "..."

            print(
                f"{row['record_id']} | {text}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())