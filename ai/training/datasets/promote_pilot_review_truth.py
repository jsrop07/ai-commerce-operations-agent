from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml


INPUT_PATH = Path(
    "artifacts/experiments/day11/"
    "openai_label_pilot_20_review_draft.csv"
)

OUTPUT_PATH = Path(
    "artifacts/experiments/day11/"
    "pilot_20_reviewed_truth.csv"
)

TAXONOMY_PATH = Path("ai/data/taxonomy.yaml")


def main() -> int:
    with INPUT_PATH.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as f:
        rows = list(csv.DictReader(f))

    taxonomy = yaml.safe_load(
        TAXONOMY_PATH.read_text(encoding="utf-8")
    )

    taxonomy_version = str(
        taxonomy.get("schema_version", "unknown")
    )

    reviewed_at = datetime.now(
        ZoneInfo("Asia/Seoul")
    ).isoformat(timespec="seconds")

    output_rows = []

    for row in rows:
        if row["review_status"] != "DRAFT_REVIEW":
            raise ValueError(
                f"{row['record_id']}: "
                f"unexpected review_status="
                f"{row['review_status']}"
            )

        output_rows.append(
            {
                "record_id": row["record_id"],
                "input_text": row["input_text"],
                "eligible_for_nlu": row[
                    "review_eligible_for_nlu"
                ],
                "exclusion_reason": row[
                    "review_exclusion_reason"
                ],
                "intent": row["review_intent"],
                "entities_json": row[
                    "review_entities_json"
                ],
                "risk": row["review_risk"],
                "human_review_required": row[
                    "review_human_review_required"
                ],
                "review_status": "REVIEWED",
                "reviewer": "operator",
                "reviewed_at": reviewed_at,
                "label_version": taxonomy_version,
                "review_note": row["review_note"],
            }
        )

    with OUTPUT_PATH.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=output_rows[0].keys(),
        )
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"ROWS={len(output_rows)}")
    print(
        "REVIEWED="
        f"{sum(r['review_status'] == 'REVIEWED' for r in output_rows)}"
    )
    print(f"REVIEWER=operator")
    print(f"REVIEWED_AT={reviewed_at}")
    print(f"LABEL_VERSION={taxonomy_version}")
    print(f"OUTPUT={OUTPUT_PATH}")
    print("STATUS=PILOT_TRUTH_REVIEWED")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())