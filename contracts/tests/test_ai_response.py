import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "contracts" / "ai_response.schema.json"


def load_schema():
    with SCHEMA_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def valid_rule_response():
    return {
        "schema_version": "ai-response.v0.1",
        "request_id": "req_demo_001",
        "trace_id": "trace_demo_001",
        "task_type": "inventory_calculation",
        "route": "RULE_SQL",
        "route_reason": "Deterministic inventory calculation",
        "confidence": 1.0,
        "evidence_ids": ["evt_demo_001"],
        "warnings": [],
        "model": {
            "model_run_id": None,
            "model_id": None,
            "prompt_version": None,
        },
        "token": {
            "input": 0,
            "output": 0,
            "cache": 0,
        },
        "latency": {
            "total_ms": 2.5,
        },
        "cost": {
            "estimated": 0.0,
            "currency": "USD",
        },
    }


def test_ai_response_schema_exists():
    assert SCHEMA_PATH.exists()


def test_valid_rule_response_passes():
    validator = Draft202012Validator(load_schema())

    errors = list(validator.iter_errors(valid_rule_response()))

    assert errors == []


def test_missing_route_reason_fails():
    payload = valid_rule_response()
    del payload["route_reason"]

    validator = Draft202012Validator(load_schema())

    errors = list(validator.iter_errors(payload))

    assert errors


def test_confidence_out_of_range_fails():
    payload = valid_rule_response()
    payload["confidence"] = 1.5

    validator = Draft202012Validator(load_schema())

    errors = list(validator.iter_errors(payload))

    assert errors
