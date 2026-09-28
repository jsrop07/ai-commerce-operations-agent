from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from ai.data.redaction import contains_pii


INPUT_PATH = Path(
    "artifacts/experiments/day11/nlu_review_candidates.jsonl"
)

KOREAN_NAME_CUES = [
    re.compile(r"[가-힣]{2,4}\s*(?:라고\s*합니다|이라고\s*합니다)"),
    re.compile(r"(?:이름|성함)[은는이가:]?\s*[가-힣]{2,4}"),
]

ADDRESS_PATTERNS = [
    re.compile(r"[가-힣0-9]+(?:시|도)\s+[가-힣0-9]+(?:구|군)"),
    re.compile(r"[가-힣0-9]+(?:구|군)\s+[가-힣0-9]+(?:동|읍|면)"),
    re.compile(r"[가-힣0-9]+(?:로|길)\s*\d+"),
    re.compile(r"\d+(?:-\d+)?\s*(?:번지|번길)"),
]

ADDRESS_CONTEXT = re.compile(
    r"(?:주소|배송지|수령지|받을\s*곳|보낼\s*곳)"
)


def load_rows() -> list[dict]:
    rows = []

    with INPUT_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))

    return rows


def main() -> int:
    rows = load_rows()

    counts = Counter()

    for row in rows:
        text = row["input_text"]

        if contains_pii(text):
            counts["EXISTING_PATTERN"] += 1

        if any(pattern.search(text) for pattern in KOREAN_NAME_CUES):
            counts["KOREAN_NAME_CANDIDATE"] += 1

        if any(pattern.search(text) for pattern in ADDRESS_PATTERNS):
            counts["DETAILED_ADDRESS_CANDIDATE"] += 1

        if ADDRESS_CONTEXT.search(text):
            counts["ADDRESS_CONTEXT"] += 1

    print(f"TOTAL_ROWS={len(rows)}")
    print(f"EXISTING_PATTERN={counts['EXISTING_PATTERN']}")
    print(f"KOREAN_NAME_CANDIDATE={counts['KOREAN_NAME_CANDIDATE']}")
    print(
        "DETAILED_ADDRESS_CANDIDATE="
        f"{counts['DETAILED_ADDRESS_CANDIDATE']}"
    )
    print(f"ADDRESS_CONTEXT={counts['ADDRESS_CONTEXT']}")
    print("RAW_TEXT_PRINTED=0")
    print("STATUS=PII_AUDIT_ONLY")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())