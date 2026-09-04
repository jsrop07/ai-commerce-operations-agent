"""Validate that Day 4 defect/evidence rows are complete."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

REQUIRED = {
    "work_id",
    "requirement_id",
    "test",
    "command",
    "expected",
    "actual",
    "status",
    "evidence_path",
    "safety_result",
    "severity",
    "owner",
    "reproduction",
    "cause",
    "next_action",
}


def main(path: str) -> int:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or set(rows[0]) != REQUIRED:
        raise SystemExit("invalid defect log columns or empty report")
    incomplete = [row["work_id"] for row in rows if any(not row[key] for key in REQUIRED)]
    if incomplete:
        raise SystemExit(f"incomplete rows: {incomplete}")
    blocking = sum(row["severity"] in {"S0", "S1", "S2"} for row in rows)
    print(f"blocking_defects={blocking}")
    return 0 if blocking == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
