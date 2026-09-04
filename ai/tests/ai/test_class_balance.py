import json
from pathlib import Path

from ai.evaluation.class_balance import (
    build_report,
)


ROOT = Path(__file__).resolve().parents[3]

FIXTURE_PATH = (
    ROOT
    / "ai"
    / "tests"
    / "fixtures"
    / "class_balance_fixture.json"
)


def load_records():
    with FIXTURE_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)["records"]


def test_class_balance_fixture_exists():
    assert FIXTURE_PATH.exists()


def test_report_contains_required_fields():
    report = build_report(
        load_records()
    )

    assert set(report["fields"]) == {
        "intent",
        "category",
        "issue",
    }


def test_support_sums_to_record_count():
    report = build_report(
        load_records()
    )

    for field_report in report["fields"].values():
        total_support = sum(
            item["support"]
            for item in field_report["classes"]
        )

        assert total_support == report["total_records"]


def test_minority_classes_are_reported():
    report = build_report(
        load_records()
    )

    assert report["fields"]["intent"]["minority_classes"]


def test_product_info_has_expected_support():
    report = build_report(
        load_records()
    )

    intent_classes = {
        item["label"]: item
        for item in report["fields"]["intent"]["classes"]
    }

    assert intent_classes["PRODUCT_INFO"]["support"] == 3


def test_automatic_oversampling_is_disabled():
    report = build_report(
        load_records()
    )

    assert report["policy"]["automatic_oversampling"] is False


def test_minority_has_recommendations():
    report = build_report(
        load_records()
    )

    minority_items = [
        item
        for field in report["fields"].values()
        for item in field["classes"]
        if item["balance_status"] == "MINORITY"
    ]

    assert minority_items

    for item in minority_items:
        assert "REVIEW_LABEL_COVERAGE" in item["recommendations"]
        assert "TARGETED_SYNTHETIC_CANDIDATE" in item["recommendations"]