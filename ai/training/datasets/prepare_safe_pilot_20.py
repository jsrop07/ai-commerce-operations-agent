from __future__ import annotations

import json
from pathlib import Path


INPUT_PATH = Path(
    "artifacts/experiments/day11/external_safe_candidates.jsonl"
)

OUTPUT_PATH = Path(
    "artifacts/experiments/day11/safe_pilot_20.jsonl"
)


def load_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> int:
    rows = load_jsonl(INPUT_PATH)

    # deterministic pilot
    rows = sorted(
        rows,
        key=lambda row: row["record_id"],
    )

    pilot = rows[:20]

    OUTPUT_PATH.write_text(
        "\n".join(
            json.dumps(row, ensure_ascii=False)
            for row in pilot
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"SAFE_SOURCE_ROWS={len(rows)}")
    print(f"PILOT_ROWS={len(pilot)}")
    print(
        "UNIQUE_IDS="
        f"{len({row['record_id'] for row in pilot})}"
    )
    print(f"OUTPUT={OUTPUT_PATH}")
    print("TEST_DATA_USED=False")
    print("STATUS=SAFE_PILOT_READY")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())