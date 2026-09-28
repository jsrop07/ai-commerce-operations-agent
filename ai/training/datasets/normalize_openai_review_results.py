from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


PATH = Path(
    "artifacts/experiments/day11/"
    "openai_review_batch_results.jsonl"
)

BACKUP_PATH = Path(
    "artifacts/experiments/day11/"
    "openai_review_batch_results.before_normalize.jsonl"
)


def main() -> int:
    rows = [
        json.loads(line)
        for line in PATH.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]

    print(
        "BEFORE_TYPES=",
        Counter(
            type(row.get("proposal")).__name__
            for row in rows
        ),
    )

    # 원본 보관
    BACKUP_PATH.write_text(
        PATH.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    converted = 0
    failed = []

    for row in rows:
        proposal = row.get("proposal")

        if isinstance(proposal, dict):
            continue

        if isinstance(proposal, str):
            try:
                parsed = json.loads(proposal)
            except json.JSONDecodeError:
                failed.append(row["record_id"])
                continue

            if not isinstance(parsed, dict):
                failed.append(row["record_id"])
                continue

            row["proposal"] = parsed
            converted += 1
            continue

        failed.append(row["record_id"])

    if failed:
        print("FAILED_COUNT=", len(failed))
        print("FAILED_IDS=", failed[:10])
        raise RuntimeError(
            "Some proposals could not be normalized"
        )

    PATH.write_text(
        "\n".join(
            json.dumps(
                row,
                ensure_ascii=False,
            )
            for row in rows
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"ROWS={len(rows)}")
    print(f"CONVERTED={converted}")
    print("FAILED=0")
    print(
        "AFTER_TYPES=",
        Counter(
            type(row.get("proposal")).__name__
            for row in rows
        ),
    )
    print(f"BACKUP={BACKUP_PATH}")
    print("STATUS=NORMALIZED")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())