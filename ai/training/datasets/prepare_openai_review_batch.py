from __future__ import annotations

import csv
import json
from pathlib import Path


SAFE_PATH = Path(
    "artifacts/experiments/day11/external_safe_candidates.jsonl"
)

REVIEWED_PATH = Path(
    "artifacts/experiments/day11/pilot_20_reviewed_truth.csv"
)

OUTPUT_PATH = Path(
    "artifacts/experiments/day11/openai_review_batch.jsonl"
)


def load_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> int:
    safe_rows = load_jsonl(SAFE_PATH)

    with REVIEWED_PATH.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as f:
        reviewed_rows = list(csv.DictReader(f))

    reviewed_ids = {
        row["record_id"]
        for row in reviewed_rows
    }

    remaining = [
        row
        for row in safe_rows
        if row["record_id"] not in reviewed_ids
    ]

    OUTPUT_PATH.write_text(
        "\n".join(
            json.dumps(row, ensure_ascii=False)
            for row in remaining
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"SAFE_ROWS={len(safe_rows)}")
    print(f"ALREADY_REVIEWED={len(reviewed_ids)}")
    print(f"OPENAI_REVIEW_BATCH={len(remaining)}")
    print(f"UNIQUE_IDS={len({r['record_id'] for r in remaining})}")
    print(f"OUTPUT={OUTPUT_PATH}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())