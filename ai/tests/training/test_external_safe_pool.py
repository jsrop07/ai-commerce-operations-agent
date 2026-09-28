import json
from pathlib import Path

from ai.data.redaction import contains_pii
from ai.training.datasets.audit_pii_candidates import (
    ADDRESS_CONTEXT,
    ADDRESS_PATTERNS,
    KOREAN_NAME_CUES,
)


SAFE_PATH = Path(
    "artifacts/experiments/day11/external_safe_candidates.jsonl"
)

AUDIT_PATH = Path(
    "artifacts/experiments/day11/external_blocked_audit.json"
)


def load_jsonl(path: Path) -> list[dict]:
    rows = []

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))

    return rows


def test_safe_pool_count() -> None:
    rows = load_jsonl(SAFE_PATH)

    assert len(rows) == 267


def test_safe_pool_has_no_known_pii_patterns() -> None:
    rows = load_jsonl(SAFE_PATH)

    for row in rows:
        text = row["input_text"]

        assert not contains_pii(text)


def test_safe_pool_has_no_korean_name_candidates() -> None:
    rows = load_jsonl(SAFE_PATH)

    for row in rows:
        text = row["input_text"]

        assert not any(
            pattern.search(text)
            for pattern in KOREAN_NAME_CUES
        )


def test_safe_pool_has_no_detailed_address_candidates() -> None:
    rows = load_jsonl(SAFE_PATH)

    for row in rows:
        text = row["input_text"]

        assert not any(
            pattern.search(text)
            for pattern in ADDRESS_PATTERNS
        )


def test_safe_pool_has_no_address_context() -> None:
    rows = load_jsonl(SAFE_PATH)

    for row in rows:
        assert not ADDRESS_CONTEXT.search(row["input_text"])


def test_blocked_audit_contains_no_raw_text() -> None:
    audit = json.loads(
        AUDIT_PATH.read_text(encoding="utf-8")
    )

    assert audit["source_count"] == 302
    assert audit["safe_count"] == 267
    assert audit["blocked_count"] == 35
    assert audit["raw_text_in_audit"] is False

    for row in audit["blocked_records"]:
        assert "input_text" not in row

def test_safe_pool_has_no_order_id_candidates():
    import json
    import re
    from pathlib import Path

    pattern = re.compile(
        r"(?<!\d)\d{8}-\d{6,}(?!\d)"
    )

    path = Path(
        "artifacts/experiments/day11/"
        "external_safe_candidates.jsonl"
    )

    rows = [
        json.loads(line)
        for line in path.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]

    for row in rows:
        text = row["input_text"]
        assert pattern.search(text) is None


def test_known_order_id_record_is_blocked():
    import json
    from pathlib import Path

    path = Path(
        "artifacts/experiments/day11/"
        "external_blocked_audit.json"
    )

    data = json.loads(
        path.read_text(encoding="utf-8")
    )

    matches = [
        row
        for row in data["blocked_records"]
        if row["record_id"] == "cafe24-b5-a642"
    ]

    assert len(matches) == 1

    assert (
        "ORDER_ID_CANDIDATE"
        in matches[0]["reasons"]
    )