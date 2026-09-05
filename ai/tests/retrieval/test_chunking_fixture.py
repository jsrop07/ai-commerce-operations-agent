import json
from pathlib import Path


FIXTURE_PATH = Path(
    "ai/tests/fixtures/retrieval_chunking_corpus.jsonl"
)


def load_records() -> list[dict]:
    return [
        json.loads(line)
        for line in FIXTURE_PATH.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]


def test_chunking_fixture_has_required_fields() -> None:
    records = load_records()

    required = {
        "source_id",
        "source_type",
        "version",
        "pii_status",
        "title",
        "content",
    }

    for record in records:
        assert required.issubset(record)


def test_chunking_fixture_is_pii_clean() -> None:
    records = load_records()

    assert all(
        record["pii_status"] == "CLEAN"
        for record in records
    )


def test_chunking_fixture_uses_allowed_source_types() -> None:
    records = load_records()

    assert {
        record["source_type"]
        for record in records
    } <= {"PRODUCT", "POLICY"}


def test_chunking_fixture_preserves_policy_versions() -> None:
    records = load_records()

    versions = {
        record["version"]
        for record in records
        if record["source_id"] == "policy_shipping_demo"
    }

    assert versions == {"v1", "v2"}