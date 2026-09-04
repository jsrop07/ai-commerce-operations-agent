import json
from pathlib import Path

from ai.data.split_dataset import split_records


ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PATH = (
    ROOT
    / "ai"
    / "tests"
    / "fixtures"
    / "group_split_fixture.json"
)


def load_records():
    with FIXTURE_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)["records"]


def test_group_split_fixture_exists():
    assert FIXTURE_PATH.exists()


def test_all_records_are_preserved():
    records = load_records()
    splits, report = split_records(records)

    split_record_ids = {
        record["record_id"]
        for split_records_ in splits.values()
        for record in split_records_
    }

    original_ids = {
        record["record_id"]
        for record in records
    }

    assert split_record_ids == original_ids
    assert report["total_records"] == len(records)


def test_customer_group_overlap_is_zero():
    _, report = split_records(load_records())

    assert report["customer_overlap"] == {
        "train_validation": [],
        "train_test": [],
        "validation_test": [],
    }


def test_thread_group_overlap_is_zero():
    _, report = split_records(load_records())

    assert report["thread_overlap"] == {
        "train_validation": [],
        "train_test": [],
        "validation_test": [],
    }


def test_total_group_overlap_is_zero():
    _, report = split_records(load_records())

    assert report["group_overlap_count"] == 0


def test_all_three_splits_are_created():
    splits, _ = split_records(load_records())

    assert splits["train"]
    assert splits["validation"]
    assert splits["test"]


def test_split_ratios_are_reported():
    _, report = split_records(load_records())

    assert set(report["ratios"]) == {
        "train",
        "validation",
        "test",
    }

    assert round(
        sum(report["ratios"].values()),
        4,
    ) == 1.0


def test_time_order_is_preserved_between_splits():
    _, report = split_records(load_records())

    train_max = report["time_ranges"]["train"]["max"]
    validation_min = report["time_ranges"]["validation"]["min"]
    validation_max = report["time_ranges"]["validation"]["max"]
    test_min = report["time_ranges"]["test"]["min"]

    assert train_max <= validation_min
    assert validation_max <= test_min