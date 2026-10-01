from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from openai import (
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    OpenAI,
    RateLimitError,
)

from ai.services.grounded_explanation import (
    ExplanationEvidence,
    build_policy_grounded_explanation_input,
)
from ai.services.grounded_explanation_output import (
    ClaimCitation,
    ExplanationStatus,
    GroundedExplanationOutput,
    NumericFact,
)
from ai.services.grounded_explanation_validator import (
    validate_grounded_explanation,
)


ROOT = Path(__file__).resolve().parents[2]

CONFIG_PATH = (
    ROOT
    / "artifacts"
    / "experiments"
    / "OPS-RAG-01"
    / "r06_run_config.json"
)

FIXTURE_PATH = (
    ROOT
    / "artifacts"
    / "experiments"
    / "OPS-RAG-01"
    / "r06_dev5_fixture.json"
)

PROMPT_PATH = (
    ROOT
    / "ai"
    / "prompts"
    / "grounded_explanation"
    / "basic.yaml"
)

OUTPUT_PATH = (
    ROOT
    / "artifacts"
    / "experiments"
    / "OPS-RAG-01"
    / "r06_smoke_ge_d_005_basic.json"
)

CASE_ID = "GE-D-005"
CONDITION = "BASIC"

# GPT-5.6 Luna published text-token pricing.
INPUT_PRICE_PER_1M = 0.20
CACHED_INPUT_PRICE_PER_1M = 0.02
OUTPUT_PRICE_PER_1M = 1.20


def load_json(path: Path) -> dict[str, Any]:
    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return yaml.safe_load(file)


def build_output_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "status",
            "conclusion",
            "used_facts",
            "used_numeric_facts",
            "citations",
            "next_check",
        ],
        "properties": {
            "status": {
                "type": "string",
                "enum": [
                    "ANSWER",
                    "HOLD",
                ],
            },
            "conclusion": {
                "type": "string",
            },
            "used_facts": {
                "type": "array",
                "items": {
                    "type": "string",
                },
            },
            "used_numeric_facts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "field",
                        "value",
                        "unit",
                    ],
                    "properties": {
                        "field": {
                            "type": "string",
                            "enum": [
                                "required_qty",
                                "expected_inventory",
                                "available_inventory",
                                "reserved",
                                "confirmed_incoming",
                            ],
                        },
                        "value": {
                            "type": "integer",
                        },
                        "unit": {
                            "type": "string",
                            "enum": [
                                "count",
                            ],
                        },
                    },
                },
            },
            "citations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "source_id",
                        "version",
                    ],
                    "properties": {
                        "source_id": {
                            "type": "string",
                        },
                        "version": {
                            "type": "string",
                        },
                    },
                },
            },
            "next_check": {
                "anyOf": [
                    {
                        "type": "string",
                    },
                    {
                        "type": "null",
                    },
                ],
            },
        },
    }


def build_model_output(
    payload: dict[str, Any],
) -> GroundedExplanationOutput:
    return GroundedExplanationOutput(
        status=ExplanationStatus(
            payload["status"]
        ),
        conclusion=payload["conclusion"],
        used_facts=tuple(
            payload["used_facts"]
        ),
        citations=tuple(
            ClaimCitation(
                source_id=item["source_id"],
                version=item["version"],
            )
            for item in payload["citations"]
        ),
        next_check=payload["next_check"],
        used_numeric_facts=tuple(
            NumericFact(
                field=item["field"],
                value=item["value"],
                unit=item["unit"],
            )
            for item
            in payload["used_numeric_facts"]
        ),
    )


def usage_value(
    usage: Any,
    name: str,
) -> int:
    if usage is None:
        return 0

    return int(
        getattr(
            usage,
            name,
            0,
        )
        or 0
    )


def cached_input_tokens(
    usage: Any,
) -> int:
    if usage is None:
        return 0

    details = getattr(
        usage,
        "input_tokens_details",
        None,
    )

    if details is None:
        return 0

    return int(
        getattr(
            details,
            "cached_tokens",
            0,
        )
        or 0
    )


def estimate_cost_usd(
    *,
    input_tokens: int,
    cached_tokens: int,
    output_tokens: int,
) -> float:
    uncached_tokens = max(
        input_tokens - cached_tokens,
        0,
    )

    cost = (
        uncached_tokens
        / 1_000_000
        * INPUT_PRICE_PER_1M
        + cached_tokens
        / 1_000_000
        * CACHED_INPUT_PRICE_PER_1M
        + output_tokens
        / 1_000_000
        * OUTPUT_PRICE_PER_1M
    )

    return round(
        cost,
        8,
    )


def update_run_config(
    *,
    config: dict[str, Any],
    request_attempts: int,
    retries: int,
    estimated_cost_usd: float,
    smoke_status: str,
) -> None:
    config["actual_provider_calls"] = (
        int(
            config.get(
                "actual_provider_calls",
                0,
            )
        )
        + request_attempts
    )

    config["actual_retries"] = (
        int(
            config.get(
                "actual_retries",
                0,
            )
        )
        + retries
    )

    config["estimated_cost_usd_total"] = round(
        float(
            config.get(
                "estimated_cost_usd_total",
                0.0,
            )
        )
        + estimated_cost_usd,
        8,
    )

    config["smoke_status"] = smoke_status

    CONFIG_PATH.write_text(
        json.dumps(
            config,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def main() -> int:
    load_dotenv()

    config = load_json(
        CONFIG_PATH
    )

    if (
        config.get("provider")
        != "openai"
    ):
        print(
            "R06_SMOKE_BLOCKED "
            "reason=PROVIDER_NOT_OPENAI"
        )
        return 2

    if not config.get("model"):
        print(
            "R06_SMOKE_BLOCKED "
            "reason=MODEL_MISSING"
        )
        return 2

    if not os.getenv(
        "OPENAI_API_KEY"
    ):
        print(
            "R06_SMOKE_BLOCKED "
            "reason=OPENAI_API_KEY_MISSING"
        )
        return 2

    budget_limit = float(
        config["budget_limit_usd"]
    )

    existing_estimated_cost = float(
        config.get(
            "estimated_cost_usd_total",
            0.0,
        )
    )

    if (
        existing_estimated_cost
        >= budget_limit
    ):
        print(
            "R06_SMOKE_BLOCKED "
            "reason=BUDGET_LIMIT_REACHED"
        )
        return 2

    max_base_requests = int(
        config[
            "planned_counts"
        ][
            "currently_runnable_provider_calls_without_retries"
        ]
    )

    existing_calls = int(
        config.get(
            "actual_provider_calls",
            0,
        )
    )

    if existing_calls >= max_base_requests:
        print(
            "R06_SMOKE_BLOCKED "
            "reason=CALL_LIMIT_REACHED"
        )
        return 2

    fixture = load_json(
        FIXTURE_PATH
    )

    case = next(
        (
            item
            for item
            in fixture["records"]
            if item["case_id"]
            == CASE_ID
        ),
        None,
    )

    if case is None:
        print(
            "R06_SMOKE_BLOCKED "
            "reason=CASE_NOT_FOUND"
        )
        return 2

    if (
        case["answerability"]
        != "ANSWERABLE"
    ):
        print(
            "R06_SMOKE_BLOCKED "
            "reason=CASE_NOT_ANSWERABLE"
        )
        return 2

    prompt = load_yaml(
        PROMPT_PATH
    )

    if (
        prompt["condition"]
        != CONDITION
    ):
        print(
            "R06_SMOKE_BLOCKED "
            "reason=PROMPT_CONDITION_MISMATCH"
        )
        return 2

    evidence = tuple(
        ExplanationEvidence(
            source_type="POLICY",
            source_id=item["source_id"],
            version=item["version"],
            excerpt=item[
                "expected_excerpt"
            ],
            as_of=None,
        )
        for item
        in case["evidence"]
    )

    model_input = (
        build_policy_grounded_explanation_input(
            question=case["query"],
            data_mode=case["data_mode"],
            evidence=evidence,
        )
    )

    input_payload = (
        model_input.to_dict()
    )

    instructions = (
        prompt["system"].strip()
        + "\n\n"
        + "반드시 제공된 evidence 범위 안에서만 답한다.\n"
        + "이 문항에는 Backend가 제공한 수량 숫자가 없다.\n"
        + "따라서 used_numeric_facts는 빈 배열이어야 한다.\n"
        + "BASIC 조건에서는 citation이 필수가 아니다.\n"
        + "status는 ANSWER 또는 HOLD만 사용한다.\n"
        + "근거가 충분하면 ANSWER, 충분하지 않으면 HOLD를 사용한다."
    )

    client = OpenAI(
        max_retries=0,
    )

    max_retries = int(
        config["max_retries"]
    )

    request_attempts = 0
    retries = 0
    response = None

    started = time.perf_counter()

    retryable_errors = (
        APIConnectionError,
        APITimeoutError,
        RateLimitError,
        InternalServerError,
    )

    while True:
        request_attempts += 1

        try:
            response = (
                client.responses.create(
                    model=config["model"],
                    instructions=instructions,
                    input=json.dumps(
                        input_payload,
                        ensure_ascii=False,
                    ),
                    max_output_tokens=int(
                        config[
                            "max_output_tokens"
                        ]
                    ),
                    reasoning={
                        "effort":
                            config[
                                "reasoning_effort"
                            ]
                    },
                    store=False,
                    temperature=float(
                        config[
                            "temperature"
                        ]
                    ),
                    text={
                        "format": {
                            "type":
                                "json_schema",
                            "name":
                                "r06_grounded_explanation",
                            "strict":
                                True,
                            "schema":
                                build_output_schema(),
                        }
                    },
                    timeout=float(
                        config[
                            "timeout_seconds"
                        ]
                    ),
                )
            )

            break

        except retryable_errors as exc:
            if retries >= max_retries:
                elapsed_ms = round(
                    (
                        time.perf_counter()
                        - started
                    )
                    * 1000,
                    2,
                )

                update_run_config(
                    config=config,
                    request_attempts=(
                        request_attempts
                    ),
                    retries=retries,
                    estimated_cost_usd=0.0,
                    smoke_status=(
                        "PROVIDER_ERROR"
                    ),
                )

                print(
                    "R06_SMOKE_PROVIDER_ERROR"
                )
                print(
                    "ERROR_TYPE=",
                    type(exc).__name__,
                )
                print(
                    "ATTEMPTS=",
                    request_attempts,
                )
                print(
                    "RETRIES=",
                    retries,
                )
                print(
                    "LATENCY_MS=",
                    elapsed_ms,
                )

                return 3

            retries += 1

    elapsed_ms = round(
        (
            time.perf_counter()
            - started
        )
        * 1000,
        2,
    )

    if response is None:
        raise RuntimeError(
            "response must not be None"
        )

    raw_output = response.output_text

    try:
        parsed = json.loads(
            raw_output
        )
    except json.JSONDecodeError as exc:
        update_run_config(
            config=config,
            request_attempts=(
                request_attempts
            ),
            retries=retries,
            estimated_cost_usd=0.0,
            smoke_status=(
                "OUTPUT_PARSE_ERROR"
            ),
        )

        print(
            "R06_SMOKE_PARSE_ERROR"
        )
        print(
            "ERROR=",
            str(exc),
        )

        return 4

    model_output = (
        build_model_output(
            parsed
        )
    )

    validation = (
        validate_grounded_explanation(
            model_input=model_input,
            model_output=model_output,
            condition=CONDITION,
        )
    )

    usage = getattr(
        response,
        "usage",
        None,
    )

    input_tokens = usage_value(
        usage,
        "input_tokens",
    )

    output_tokens = usage_value(
        usage,
        "output_tokens",
    )

    cached_tokens = (
        cached_input_tokens(
            usage
        )
    )

    estimated_cost = (
        estimate_cost_usd(
            input_tokens=input_tokens,
            cached_tokens=cached_tokens,
            output_tokens=output_tokens,
        )
    )

    result = {
        "schema_version":
            "r06-grounded-smoke.v0.1",
        "case_id":
            CASE_ID,
        "condition":
            CONDITION,
        "provider":
            config["provider"],
        "model":
            config["model"],
        "data_mode":
            case["data_mode"],
        "provider_called":
            True,
        "request_attempts":
            request_attempts,
        "retries":
            retries,
        "response_id":
            getattr(
                response,
                "id",
                None,
            ),
        "latency_ms":
            elapsed_ms,
        "usage": {
            "input_tokens":
                input_tokens,
            "cached_input_tokens":
                cached_tokens,
            "output_tokens":
                output_tokens,
        },
        "cost": {
            "estimated_usd":
                estimated_cost,
            "basis":
                "measured_token_usage_x_published_model_rates",
            "provider_invoice_cost_measured":
                False,
        },
        "model_output":
            parsed,
        "validation": {
            "valid":
                validation.valid,
            "errors":
                list(
                    validation.errors
                ),
        },
        "expected_answer":
            case["expected_answer"],
        "source_ids": [
            item.source_id
            for item
            in evidence
        ],
    }

    OUTPUT_PATH.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    smoke_status = (
        "PASSED"
        if validation.valid
        else "FAILED_VALIDATION"
    )

    update_run_config(
        config=config,
        request_attempts=(
            request_attempts
        ),
        retries=retries,
        estimated_cost_usd=(
            estimated_cost
        ),
        smoke_status=(
            smoke_status
        ),
    )

    print(
        "R06_SMOKE_COMPLETE"
    )
    print(
        "CASE_ID=",
        CASE_ID,
    )
    print(
        "CONDITION=",
        CONDITION,
    )
    print(
        "MODEL=",
        config["model"],
    )
    print(
        "VALID=",
        validation.valid,
    )
    print(
        "ERRORS=",
        list(
            validation.errors
        ),
    )
    print(
        "ATTEMPTS=",
        request_attempts,
    )
    print(
        "RETRIES=",
        retries,
    )
    print(
        "INPUT_TOKENS=",
        input_tokens,
    )
    print(
        "OUTPUT_TOKENS=",
        output_tokens,
    )
    print(
        "ESTIMATED_COST_USD=",
        estimated_cost,
    )
    print(
        "LATENCY_MS=",
        elapsed_ms,
    )
    print(
        "OUTPUT=",
        OUTPUT_PATH,
    )

    return (
        0
        if validation.valid
        else 5
    )


if __name__ == "__main__":
    raise SystemExit(
        main()
    )