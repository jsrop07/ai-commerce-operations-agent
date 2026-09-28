from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path


INPUT_PATH = Path(
    "artifacts/experiments/day11/priority_review_queue.csv"
)

OUTPUT_PATH = Path(
    "artifacts/experiments/day11/minimum_review_subset.csv"
)

NEEDED = {
    "AFTER_SERVICE": 2,
    "DELIVERY": 5,
    "REFUND_CANCEL": 8,
    "OTHER": 9,
    "RETURN_EXCHANGE": 9,
    "RESTOCK": 9,
    "PRODUCT_INFO": 9,
    "COMPATIBILITY": 10,
    "STOCK_AVAILABILITY": 10,
    "ORDER_STATUS": 10,
    "RESERVATION_PREORDER": 10,
}


def main() -> int:
    with INPUT_PATH.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as f:
        rows = list(csv.DictReader(f))

    selected = []
    counts = defaultdict(int)

    for row in rows:
        intent = row["proposed_intent"]
        limit = NEEDED.get(intent, 0)

        if counts[intent] >= limit:
            continue

        selected.append(row)
        counts[intent] += 1

    if not selected:
        raise RuntimeError("No rows selected")

    with OUTPUT_PATH.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=selected[0].keys(),
        )
        writer.writeheader()
        writer.writerows(selected)

    print(f"SELECTED_ROWS={len(selected)}")

    for intent, needed in NEEDED.items():
        print(
            f"{intent}: "
            f"selected={counts[intent]} "
            f"needed={needed}"
        )

    print(f"OUTPUT={OUTPUT_PATH}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())