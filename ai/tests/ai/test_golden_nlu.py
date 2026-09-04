import json
from pathlib import Path

import yaml

from ai.data.redaction import contains_pii


ROOT = Path(__file__).resolve().parents[3]

GOLDEN_PATH = (
    ROOT
    / "ai"
    / "evaluation"
    / "datasets"
    / "golden_nlu_v0.1.json"
)

TAXONOMY_PATH = (
    ROOT
    / "ai"
    / "data"
    / "taxonomy.yaml"
)


def load_golden():
    with GOLDEN_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def load_taxonomy():
    with TAXONOMY_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        return yaml.safe_load(file)


def labels_for(section: str) -> set[str]:
    taxonomy = load_taxonomy()

    return {
        item["label"]
        for item in taxonomy[section]
    }


def test_golden_nlu_exists():
    assert GOLDEN_PATH.exists()


def test_dataset_metadata():
    payload = load_golden()

    assert payload["dataset_id"] == "golden_nlu"
    assert payload["version"] == "v0.1"
    assert payload["pii_status"] == "CLEAN"
    assert payload["contains_real_data"] is False


def test_record_ids_are_unique():
    payload = load_golden()

    ids = [
        record["id"]
        for record in payload["records"]
    ]

    assert len(ids) == len(set(ids))


def test_required_splits_exist():
    payload = load_golden()

    splits = {
        record["split"]
        for record in payload["records"]
    }

    assert splits == {
        "train",
        "validation",
        "test",
    }


def test_intents_match_taxonomy():
    allowed = labels_for("intent")
    payload = load_golden()

    for record in payload["records"]:
        intent = record["expected"]["intent"]

        assert intent in allowed, (
            f"{record['id']} invalid intent: {intent}"
        )


def test_entity_types_match_taxonomy():
    allowed = labels_for("entity")
    payload = load_golden()

    for record in payload["records"]:
        for entity in record["expected"]["entities"]:
            assert entity["type"] in allowed, (
                f"{record['id']} invalid entity: "
                f"{entity['type']}"
            )


def test_risks_match_taxonomy():
    allowed = labels_for("risk")
    payload = load_golden()

    for record in payload["records"]:
        risk = record["expected"]["risk"]

        assert risk in allowed, (
            f"{record['id']} invalid risk: {risk}"
        )


def test_routes_are_allowed():
    allowed_routes = {
        "SLLM",
        "HUMAN_REVIEW",
    }

    payload = load_golden()

    for record in payload["records"]:
        route = record["expected"]["route"]

        assert route in allowed_routes, (
            f"{record['id']} invalid route: {route}"
        )


def test_prohibited_cases_go_to_human_review():
    payload = load_golden()

    for record in payload["records"]:
        expected = record["expected"]

        if expected["risk"] == "PROHIBITED":
            assert expected["route"] == "HUMAN_REVIEW"


def test_no_detectable_pii_in_text():
    payload = load_golden()

    for record in payload["records"]:
        assert contains_pii(record["text"]) is False, (
            f"{record['id']} contains detectable PII"
        )


def test_no_duplicate_text_across_splits():
    payload = load_golden()

    texts = {}

    for record in payload["records"]:
        normalized = " ".join(
            record["text"].lower().split()
        )

        if normalized in texts:
            raise AssertionError(
                f"duplicate text: "
                f"{texts[normalized]} / {record['id']}"
            )

        texts[normalized] = record["id"]