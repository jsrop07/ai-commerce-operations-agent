from __future__ import annotations

import csv
from pathlib import Path


INPUT_PATH = Path(
    "artifacts/experiments/day11/base_label_pilot_20_review_draft.csv"
)

OUTPUT_PATH = Path(
    "artifacts/experiments/day11/base_label_pilot_20_review_after_service.csv"
)


AFTER_SERVICE_IDS = {
    "cafe24-b5-a432",
    "cafe24-b5-a436",
    "cafe24-b5-a485",
    "cafe24-b5-a539",
    "cafe24-b5-a575",
    "cafe24-b5-a646",
    "cafe24-b5-a657",
    "cafe24-b5-a665",
}


def main() -> int:
    with INPUT_PATH.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as f:
        rows = list(csv.DictReader(f))

    changed = 0

    for row in rows:
        if row["record_id"] in AFTER_SERVICE_IDS:
            row["review_intent"] = "AFTER_SERVICE"
            row["review_note"] = (
                "상품 수령 후 부품 누락/파손/오배송/"
                "구성품 이상 등 A/S 문의로 AFTER_SERVICE 적용."
            )
            changed += 1

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
    print(f"AFTER_SERVICE_CHANGED={changed}")
    print(f"OUTPUT={OUTPUT_PATH}")
    print("REVIEW_STATUS=DRAFT_REVIEW")
    print("TRUTH_PROMOTED=0")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())