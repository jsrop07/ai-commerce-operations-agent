import json
from pathlib import Path

from ai.data.synthetic.generator import (
    find_private_overlap,
    generate_dataset,
    load_forbidden_strings,
    find_private_fingerprint_overlap,

)

ROOT = Path(__file__).resolve().parents[3]

PRIVATE_FIXTURE_PATH = (
    ROOT
    / "ai"
    / "tests"
    / "fixtures"
    / "private_unique_strings_fixture.json"
)


def test_private_fixture_exists():
    assert PRIVATE_FIXTURE_PATH.exists()


def test_same_seed_produces_identical_dataset():
    first = generate_dataset(
        seed=42,
        count=20,
    )

    second = generate_dataset(
        seed=42,
        count=20,
    )

    assert first == second
    assert first["dataset_hash"] == second["dataset_hash"]


def test_different_seed_changes_dataset():
    first = generate_dataset(
        seed=42,
        count=20,
    )

    second = generate_dataset(
        seed=43,
        count=20,
    )

    assert first["dataset_hash"] != second["dataset_hash"]


def test_generated_records_have_ground_truth():
    dataset = generate_dataset(
        seed=42,
        count=20,
    )

    for record in dataset["records"]:
        assert record["intent"]
        assert isinstance(
            record["entities"],
            list,
        )

        assert record["entities"]
        assert record["source"] == "SYNTHETIC"


def test_compatibility_records_have_relation_truth():
    dataset = generate_dataset(
        seed=42,
        count=100,
    )

    compatibility_records = [
        record
        for record in dataset["records"]
        if record["intent"] == "COMPATIBILITY"
    ]

    assert compatibility_records

    for record in compatibility_records:
        assert record["relations"]

        assert (
            record["relations"][0]["relation_type"]
            == "EXPANSION_OF"
        )


def test_no_private_unique_string_overlap():
    dataset = generate_dataset(
        seed=42,
        count=100,
    )

    forbidden = load_forbidden_strings(
        PRIVATE_FIXTURE_PATH
    )

    overlaps = find_private_overlap(
        dataset,
        forbidden,
    )

    assert overlaps == []


def test_dataset_contains_no_customer_identifier_fields():
    dataset = generate_dataset(
        seed=42,
        count=20,
    )

    serialized = json.dumps(
        dataset,
        ensure_ascii=False,
    )

    forbidden_field_names = (
        "customer_name",
        "phone",
        "email",
        "address",
        "resident_id",
    )

    for field_name in forbidden_field_names:
        assert field_name not in serialized

def test_private_fingerprint_overlap_is_zero():
    dataset = generate_dataset(
        seed=42,
        count=20,
    )

    private_unique_strings = [
        "PRIVATE SANITIZED PRODUCT XYZ",
        "PRIVATE SANITIZED QUERY ABC",
    ]

    overlaps = find_private_fingerprint_overlap(
        dataset,
        private_unique_strings,
        "test-secret-key",
    )

    assert overlaps == []


def test_private_fingerprint_overlap_detects_duplicate():
    dataset = generate_dataset(
        seed=42,
        count=20,
    )

    private_unique_strings = [
        dataset["records"][0]["text"],
    ]

    overlaps = find_private_fingerprint_overlap(
        dataset,
        private_unique_strings,
        "test-secret-key",
    )

    assert len(overlaps) == 1