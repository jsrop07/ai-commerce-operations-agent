import json
from pathlib import Path

import jsonschema

from ai.services.mock_runtime import (
    MockAIRuntime,
)


ROOT = Path(__file__).resolve().parents[3]

SCHEMA_PATH = (
    ROOT
    / "contracts"
    / "ai_response.schema.json"
)


def load_schema():
    return json.loads(
        SCHEMA_PATH.read_text(
            encoding="utf-8"
        )
    )


def test_mock_runtime_is_deterministic():
    runtime = MockAIRuntime()

    kwargs = {
        "request_id":
            "req_day04_mock_001",
        "trace_id":
            "trace_day04_mock_001",
        "intent":
            "PRODUCT_INFO",
        "risk":
            "LOW",
        "evidence_ids": [
            "ev_demo_product_001",
        ],
    }

    first = runtime.run(**kwargs)
    second = runtime.run(**kwargs)

    assert first == second


def test_mock_response_matches_contract():
    runtime = MockAIRuntime()

    response = runtime.run(
        request_id=
            "req_day04_mock_002",

        trace_id=
            "trace_day04_mock_002",

        intent=
            "STOCK_AVAILABILITY",

        risk=
            "LOW",

        evidence_ids=[
            "ev_demo_inventory_001",
        ],
    )

    jsonschema.validate(
        instance=response,
        schema=load_schema(),
    )


def test_mock_does_not_claim_model_run():
    runtime = MockAIRuntime()

    response = runtime.run(
        request_id=
            "req_day04_mock_003",

        trace_id=
            "trace_day04_mock_003",

        intent=
            "DELIVERY",

        risk=
            "LOW",
    )

    assert (
        response["model"]["model_run_id"]
        is None
    )

    assert (
        response["model"]["model_id"]
        is None
    )

    assert response["token"] == {
        "input": 0,
        "output": 0,
        "cache": 0,
    }

    assert (
        response["cost"]["estimated"]
        == 0.0
    )


def test_mock_has_zero_external_actions():
    runtime = MockAIRuntime()

    runtime.run(
        request_id=
            "req_day04_mock_004",

        trace_id=
            "trace_day04_mock_004",

        intent=
            "PRODUCT_INFO",

        risk=
            "LOW",
    )

    assert (
        runtime.counters
        .external_model_calls
        == 0
    )

    assert (
        runtime.counters.tool_calls
        == 0
    )

    assert (
        runtime.counters.provider_calls
        == 0
    )

    assert (
        runtime.counters.auto_send_count
        == 0
    )


def test_mock_uses_active_prompt_version():
    runtime = MockAIRuntime()

    response = runtime.run(
        request_id=
            "req_day04_mock_005",

        trace_id=
            "trace_day04_mock_005",

        intent=
            "PRODUCT_INFO",

        risk=
            "LOW",
    )

    assert (
        response["model"][
            "prompt_version"
        ]
        == "0.1.0"
    )