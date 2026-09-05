import json
from pathlib import Path

from jsonschema import Draft202012Validator


SCHEMA_PATH = Path("ai/retrieval/metadata.schema.json")


def load_validator() -> Draft202012Validator:
    with SCHEMA_PATH.open("r", encoding="utf-8") as file:
        schema = json.load(file)

    return Draft202012Validator(schema)


def make_base_metadata() -> dict:
    return {
        "tenant_id": "demo_store",
        "product_id": "prod_demo_001",
        "brand_id": "brand_demo_001",
        "category": "board_game",
        "language": "ko",
        "base_game_id": None,
        "expansion_type": None,
        "source_type": "PRODUCT",
        "as_of": None,
        "version": "v0.1",
    }


def test_product_metadata_is_valid() -> None:
    validator = load_validator()
    payload = make_base_metadata()

    errors = list(validator.iter_errors(payload))

    assert errors == []


def test_optional_domain_values_may_be_null() -> None:
    validator = load_validator()
    payload = make_base_metadata()

    payload["product_id"] = None
    payload["brand_id"] = None
    payload["category"] = None
    payload["language"] = None
    payload["base_game_id"] = None
    payload["expansion_type"] = None

    errors = list(validator.iter_errors(payload))

    assert errors == []


def test_missing_required_metadata_field_is_invalid() -> None:
    validator = load_validator()
    payload = make_base_metadata()

    del payload["tenant_id"]

    errors = list(validator.iter_errors(payload))

    assert errors


def test_live_inventory_requires_as_of() -> None:
    validator = load_validator()
    payload = make_base_metadata()

    payload["source_type"] = "INVENTORY_SNAPSHOT"
    payload["as_of"] = None

    errors = list(validator.iter_errors(payload))

    assert errors


def test_live_inventory_accepts_valid_as_of() -> None:
    validator = load_validator()
    payload = make_base_metadata()

    payload["source_type"] = "INVENTORY_SNAPSHOT"
    payload["as_of"] = "2026-09-04T06:00:00Z"

    errors = list(validator.iter_errors(payload))

    assert errors == []


def test_unknown_source_type_is_invalid() -> None:
    validator = load_validator()
    payload = make_base_metadata()

    payload["source_type"] = "UNKNOWN_SOURCE"

    errors = list(validator.iter_errors(payload))

    assert errors