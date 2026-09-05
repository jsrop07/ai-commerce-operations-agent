from pathlib import Path

from ai.evaluation.validate_retrieval_set import load_records, dataset_hash


DATASET_PATH = Path("ai/evaluation/datasets/golden_retrieval.jsonl")


def test_golden_retrieval_has_at_least_60_queries() -> None:
    records, errors = load_records(DATASET_PATH)

    assert errors == []
    assert len(records) >= 60


def test_golden_retrieval_has_all_required_slices() -> None:
    records, errors = load_records(DATASET_PATH)

    assert errors == []

    slices = {record["slice"] for record in records}

    assert slices == {
        "product_exact",
        "product_alias_typo",
        "compatibility",
        "component",
        "inventory_freshness",
        "order_delivery",
        "policy",
        "no_answer",
    }


def test_golden_retrieval_has_validation_and_test_splits() -> None:
    records, errors = load_records(DATASET_PATH)

    assert errors == []

    splits = {record["split"] for record in records}

    assert splits == {"validation", "test"}


def test_golden_retrieval_hash_is_stable() -> None:
    records, errors = load_records(DATASET_PATH)

    assert errors == []

    first = dataset_hash(records)
    second = dataset_hash(records)

    assert first == second
    assert len(first) == 64