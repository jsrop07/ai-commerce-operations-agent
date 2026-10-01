from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import (
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    OpenAI,
    RateLimitError,
)

from ai.evaluation.run_r06_grounded_provider import (
    build_model_output,
    build_output_schema,
    cached_input_tokens,
    estimate_cost_usd,
    load_json,
    load_yaml,
    usage_value,
)
from ai.services.grounded_explanation import (
    ExplanationEvidence,
    build_policy_grounded_explanation_input,
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

OUTPUT_PATH = (
    ROOT
    / "artifacts"
    / "experiments"
    / "OPS-RAG-01"
    / "r06_grounded_comparison_results.json"
)

BASIC_PROMPT_PATH = (
    ROOT
    / "ai"
    / "prompts"
    / "grounded_explanation"
    / "basic.yaml"
)

CITATION_PROMPT_PATH = (
    ROOT
    / "ai"
    / "prompts"
    / "grounded_explanation"
    / "citation.yaml"
)

CASE_IDS = (
    "GE-D-005",
    "GE-D-007",
    "GE-D-016",
)

CONDITIONS = (
    "BASIC",
    "CITATION",
)

SOURCE_TYPE_BY_SOURCE_ID = {
    "policy_shipping_demo": "POLICY",
    "policy_reservation_shortage_demo": "POLICY",
    "incoming_stock_demo_tentative_001": "INCOMING_STOCK",
}

RETRYABLE_ERRORS = (
    APIConnectionError,
    APITimeoutError,
    RateLimitError,
    InternalServerError,
)


def save_json(
    path: Path,
    payload: dict[str, Any],
) -> None:
    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def save_config(
    config: dict[str, Any],
) -> None:
    save_json(
        CONFIG_PATH,
        config,
    )


def build_evidence(
    case: dict[str, Any],
) -> tuple[ExplanationEvidence, ...]:
    items: list[ExplanationEvidence] = []

    for raw in case["evidence"]:
        source_id = raw["source_id"]

        source_type = (
            SOURCE_TYPE_BY_SOURCE_ID.get(
                source_id
            )
        )

        if source_type is None:
            raise ValueError(
                "unknown source type for "
                f"{source_id}"
            )

        items.append(
            ExplanationEvidence(
                source_type=source_type,
                source_id=source_id,
                version=raw["version"],
                excerpt=raw[
                    "expected_excerpt"
                ],
                as_of=None,
            )
        )

    return tuple(items)


def build_instructions(
    *,
    prompt: dict[str, Any],
    condition: str,
) -> str:
    common = (
        "\n\n"
        "반드시 제공된 evidence 범위 안에서만 답한다.\n"
        "이 비교실험에는 Backend가 검증한 수량 필드가 제공되지 않는다.\n"
        "따라서 used_numeric_facts는 빈 배열이어야 한다.\n"
        "질문에 숫자가 포함되어 있더라도 Backend 검증 수치가 아니면 "
        "새로운 운영 수치 사실로 사용하지 않는다.\n"
        "status는 ANSWER 또는 HOLD만 사용한다.\n"
        "근거가 충분하면 ANSWER, 부족하면 HOLD를 사용한다.\n"
    )

    if condition == "BASIC":
        condition_rule = (
            "BASIC 조건에서는 citation이 필수가 아니다."
        )
    elif condition == "CITATION":
        condition_rule = (
            "CITATION 조건에서는 답변에 사용한 모든 근거의 "
            "source_id와 version을 citations에 포함한다."
        )
    else:
        raise ValueError(
            f"unknown condition: {condition}"
        )

    return (
        prompt["system"].strip()
        + common
        + condition_rule
    )


def prompt_path_for_condition(
    condition: str,
) -> Path:
    if condition == "BASIC":
        return BASIC_PROMPT_PATH

    if condition == "CITATION":
        return CITATION_PROMPT_PATH

    raise ValueError(
        f"unknown condition: {condition}"
    )


def write_partial_result(
    *,
    records: list[dict[str, Any]],
    config: dict[str, Any],
) -> None:
    payload = {
        "schema_version":
            "r06-grounded-comparison.v0.1",
        "execution_status":
            "RUNNING",
        "provider":
            config["provider"],
        "model":
            config["model"],
        "case_ids":
            list(CASE_IDS),
        "conditions":
            list(CONDITIONS),
        "records":
            records,
    }

    save_json(
        OUTPUT_PATH,
        payload,
    )


def update_config_after_request(
    *,
    config: dict[str, Any],
    request_attempts: int,
    retries: int,
    estimated_cost_usd: float,
    case_completed: bool,
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

    config[
        "actual_comparison_provider_calls"
    ] = (
        int(
            config.get(
                "actual_comparison_provider_calls",
                0,
            )
        )
        + request_attempts
    )

    if case_completed:
        config[
            "actual_comparison_cases_completed"
        ] = (
            int(
                config.get(
                    "actual_comparison_cases_completed",
                    0,
                )
            )
            + 1
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

    save_config(
        config
    )


def call_one(
    *,
    client: OpenAI,
    config: dict[str, Any],
    case: dict[str, Any],
    condition: str,
) -> dict[str, Any]:
    prompt = load_yaml(
        prompt_path_for_condition(
            condition
        )
    )

    if prompt["condition"] != condition:
        raise ValueError(
            "prompt condition mismatch"
        )

    evidence = build_evidence(
        case
    )

    model_input = (
        build_policy_grounded_explanation_input(
            question=case["query"],
            data_mode=case["data_mode"],
            evidence=evidence,
        )
    )

    instructions = build_instructions(
        prompt=prompt,
        condition=condition,
    )

    max_retries = int(
        config["max_retries"]
    )

    request_attempts = 0
    retries = 0
    response = None

    started = time.perf_counter()

    while True:
        request_attempts += 1

        try:
            response = (
                client.responses.create(
                    model=config["model"],
                    instructions=instructions,
                    input=json.dumps(
                        model_input.to_dict(),
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

        except RETRYABLE_ERRORS:
            if retries >= max_retries:
                raise

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
            "provider response is None"
        )

    parsed = json.loads(
        response.output_text
    )

    model_output = build_model_output(
        parsed
    )

    validation = (
        validate_grounded_explanation(
            model_input=model_input,
            model_output=model_output,
            condition=condition,
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

    update_config_after_request(
        config=config,
        request_attempts=request_attempts,
        retries=retries,
        estimated_cost_usd=estimated_cost,
        case_completed=True,
    )

    return {
        "evaluation_id":
            f"{case['case_id']}-{condition}",
        "case_id":
            case["case_id"],
        "condition":
            condition,
        "category":
            case["category"],
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
        "estimated_cost_usd":
            estimated_cost,
        "question":
            case["query"],
        "expected_answer":
            case["expected_answer"],
        "source_ids": [
            item.source_id
            for item in evidence
        ],
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
    }


def main() -> int:
    load_dotenv()

    config = load_json(
        CONFIG_PATH
    )

    if not os.getenv(
        "OPENAI_API_KEY"
    ):
        print(
            "R06_COMPARISON_BLOCKED "
            "reason=OPENAI_API_KEY_MISSING"
        )
        return 2

    if (
        config.get("smoke_status")
        != "PASSED"
    ):
        print(
            "R06_COMPARISON_BLOCKED "
            "reason=SMOKE_NOT_PASSED"
        )
        return 2

    planned = int(
        config[
            "planned_counts"
        ][
            "comparison_provider_calls"
        ]
    )

    if planned != 6:
        print(
            "R06_COMPARISON_BLOCKED "
            "reason=COMPARISON_PLAN_NOT_6"
        )
        return 2

    existing_comparison_calls = int(
        config.get(
            "actual_comparison_provider_calls",
            0,
        )
    )

    if existing_comparison_calls != 0:
        print(
            "R06_COMPARISON_BLOCKED "
            "reason=COMPARISON_ALREADY_STARTED"
        )
        return 2

    budget_limit = float(
        config["budget_limit_usd"]
    )

    current_cost = float(
        config.get(
            "estimated_cost_usd_total",
            0.0,
        )
    )

    if current_cost >= budget_limit:
        print(
            "R06_COMPARISON_BLOCKED "
            "reason=BUDGET_LIMIT_REACHED"
        )
        return 2

    fixture = load_json(
        FIXTURE_PATH
    )

    case_map = {
        item["case_id"]: item
        for item in fixture["records"]
        if item["case_id"] in CASE_IDS
    }

    missing = [
        case_id
        for case_id in CASE_IDS
        if case_id not in case_map
    ]

    if missing:
        print(
            "R06_COMPARISON_BLOCKED "
            "reason=CASES_MISSING"
        )
        print(
            "MISSING=",
            missing,
        )
        return 2

    client = OpenAI(
        max_retries=0,
    )

    records: list[
        dict[str, Any]
    ] = []

    for case_id in CASE_IDS:
        case = case_map[
            case_id
        ]

        for condition in CONDITIONS:
            current_cost = float(
                config.get(
                    "estimated_cost_usd_total",
                    0.0,
                )
            )

            if current_cost >= budget_limit:
                print(
                    "R06_COMPARISON_STOPPED "
                    "reason=BUDGET_LIMIT_REACHED"
                )

                write_partial_result(
                    records=records,
                    config=config,
                )

                return 3

            print(
                "R06_COMPARISON_CALL "
                f"case={case_id} "
                f"condition={condition}"
            )

            try:
                result = call_one(
                    client=client,
                    config=config,
                    case=case,
                    condition=condition,
                )
            except Exception as exc:
                write_partial_result(
                    records=records,
                    config=config,
                )

                print(
                    "R06_COMPARISON_ERROR"
                )
                print(
                    "CASE=",
                    case_id,
                )
                print(
                    "CONDITION=",
                    condition,
                )
                print(
                    "ERROR_TYPE=",
                    type(exc).__name__,
                )
                print(
                    "ERROR=",
                    str(exc),
                )

                return 4

            records.append(
                result
            )

            write_partial_result(
                records=records,
                config=config,
            )

            print(
                "R06_COMPARISON_RESULT "
                f"case={case_id} "
                f"condition={condition} "
                f"valid="
                f"{result['validation']['valid']} "
                f"latency_ms="
                f"{result['latency_ms']} "
                f"cost_usd="
                f"{result['estimated_cost_usd']}"
            )

    valid_count = sum(
        item["validation"]["valid"]
        for item in records
    )

    final = {
        "schema_version":
            "r06-grounded-comparison.v0.1",
        "execution_status":
            "COMPLETE",
        "provider":
            config["provider"],
        "model":
            config["model"],
        "case_ids":
            list(CASE_IDS),
        "conditions":
            list(CONDITIONS),
        "counts": {
            "evaluation_cases":
                len(records),
            "validator_passed":
                valid_count,
            "validator_failed":
                len(records)
                - valid_count,
            "provider_attempts":
                sum(
                    item[
                        "request_attempts"
                    ]
                    for item
                    in records
                ),
            "retries":
                sum(
                    item["retries"]
                    for item
                    in records
                ),
        },
        "total_estimated_cost_usd":
            round(
                sum(
                    item[
                        "estimated_cost_usd"
                    ]
                    for item
                    in records
                ),
                8,
            ),
        "records":
            records,
    }

    save_json(
        OUTPUT_PATH,
        final,
    )

    config[
        "comparison_status"
    ] = (
        "PASSED"
        if valid_count == 6
        else "COMPLETE_WITH_VALIDATION_FAILURE"
    )

    save_config(
        config
    )

    print(
        "R06_COMPARISON_COMPLETE"
    )
    print(
        "CASES=",
        len(records),
    )
    print(
        "VALIDATOR_PASSED=",
        valid_count,
    )
    print(
        "VALIDATOR_FAILED=",
        len(records) - valid_count,
    )
    print(
        "PROVIDER_ATTEMPTS=",
        final["counts"][
            "provider_attempts"
        ],
    )
    print(
        "RETRIES=",
        final["counts"][
            "retries"
        ],
    )
    print(
        "COMPARISON_COST_USD=",
        final[
            "total_estimated_cost_usd"
        ],
    )
    print(
        "TOTAL_ACTUAL_CALLS=",
        config[
            "actual_provider_calls"
        ],
    )
    print(
        "OUTPUT=",
        OUTPUT_PATH,
    )

    return (
        0
        if valid_count == 6
        else 5
    )


if __name__ == "__main__":
    raise SystemExit(
        main()
    )