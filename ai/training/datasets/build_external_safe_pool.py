from __future__ import annotations

import re
import json
from collections import Counter
from pathlib import Path

from ai.data.redaction import contains_pii
from ai.training.datasets.audit_pii_candidates import (
    ADDRESS_CONTEXT,
    ADDRESS_PATTERNS,
    KOREAN_NAME_CUES,
)

ORDER_ID_CANDIDATE_PATTERN = re.compile(
    r"(?<!\d)\d{8}-\d{6,}(?!\d)"
)

INPUT_PATH = Path(
    "artifacts/experiments/day11/nlu_review_candidates.jsonl"
)

SAFE_OUTPUT = Path(
    "artifacts/experiments/day11/external_safe_candidates.jsonl"
)

BLOCKED_OUTPUT = Path(
    "artifacts/experiments/day11/external_blocked_audit.json"
)


def load_rows() -> list[dict]:
    rows = []

    with INPUT_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))

    return rows


def audit_reasons(text: str) -> list[str]:
    reasons: list[str] = []

    if contains_pii(text):
        reasons.append("EXISTING_PII_PATTERN")

    if any(pattern.search(text) for pattern in KOREAN_NAME_CUES):
        reasons.append("KOREAN_NAME_CANDIDATE")

    if ORDER_ID_CANDIDATE_PATTERN.search(text):
        reasons.append("ORDER_ID_CANDIDATE")

    if any(pattern.search(text) for pattern in ADDRESS_PATTERNS):
        reasons.append("DETAILED_ADDRESS_CANDIDATE")

    if ADDRESS_CONTEXT.search(text):
        reasons.append("ADDRESS_CONTEXT")

    return reasons


def main() -> int:
    rows = load_rows()

    safe_rows = []
    blocked_rows = []
    reason_counts = Counter()

    for row in rows:
        reasons = audit_reasons(row["input_text"])

        if reasons:
            blocked_rows.append(
                {
                    "record_id": row["record_id"],
                    "group_id": row["group_id"],
                    "reasons": reasons,
                }
            )

            reason_counts.update(reasons)
            continue

        safe_rows.append(row)

    with SAFE_OUTPUT.open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as f:
        for row in safe_rows:
            f.write(
                json.dumps(
                    row,
                    ensure_ascii=False,
                )
                + "\n"
            )

    audit = {
        "schema_version": "day11-external-pii-gate.v1",
        "source_count": len(rows),
        "safe_count": len(safe_rows),
        "blocked_count": len(blocked_rows),
        "reason_counts": dict(reason_counts),
        "blocked_records": blocked_rows,
        "raw_text_in_audit": False,
        "status": "SAFE_POOL_CREATED",
    }

    BLOCKED_OUTPUT.write_text(
        json.dumps(
            audit,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"SOURCE_ROWS={len(rows)}")
    print(f"SAFE_ROWS={len(safe_rows)}")
    print(f"BLOCKED_ROWS={len(blocked_rows)}")

    for reason, count in sorted(reason_counts.items()):
        print(f"{reason}={count}")

    print("BLOCKED_RAW_TEXT_STORED=False")
    print(f"SAFE_OUTPUT={SAFE_OUTPUT}")
    print(f"AUDIT_OUTPUT={BLOCKED_OUTPUT}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())