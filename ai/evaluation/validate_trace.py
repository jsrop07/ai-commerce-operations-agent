import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_TOP_LEVEL = [
    "schema_version",
    "request_id",
    "trace_id",
    "execution_type",
    "task_type",
    "intent",
    "route",
    "route_reason",
    "evidence_ids",
    "prompt",
    "model",
    "token",
    "cost",
    "safety",
]


def load_json(
    path: Path,
) -> dict[str, Any]:
    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def validate_trace(
    data: dict[str, Any],
) -> list[str]:
    errors = []

    for field in REQUIRED_TOP_LEVEL:
        if field not in data:
            errors.append(
                f"missing field: {field}"
            )

    if errors:
        return errors

    if (
        data["schema_version"]
        != "ai-trace.v0.1"
    ):
        errors.append(
            "invalid schema_version"
        )

    if (
        data["execution_type"]
        != "MOCK"
    ):
        errors.append(
            "execution_type must be MOCK"
        )

    if not data["request_id"]:
        errors.append(
            "request_id is empty"
        )

    if not data["trace_id"]:
        errors.append(
            "trace_id is empty"
        )

    prompt = data["prompt"]

    for field in [
        "prompt_id",
        "version",
        "sha256",
        "path",
    ]:
        if field not in prompt:
            errors.append(
                f"missing prompt field: {field}"
            )

    model = data["model"]

    if model.get(
        "model_run_id"
    ) is not None:
        errors.append(
            "mock trace model_run_id "
            "must be null"
        )

    if model.get(
        "model_id"
    ) is not None:
        errors.append(
            "mock trace model_id "
            "must be null"
        )

    token = data["token"]

    if token != {
        "input": 0,
        "output": 0,
        "cache": 0,
    }:
        errors.append(
            "mock trace token "
            "must be all zero"
        )

    cost = data["cost"]

    if (
        cost.get("estimated")
        != 0.0
    ):
        errors.append(
            "mock trace cost "
            "must be zero"
        )

    safety = data["safety"]

    for field in [
        "external_model_calls",
        "tool_calls",
        "provider_calls",
        "auto_send_count",
    ]:
        if safety.get(field) != 0:
            errors.append(
                f"{field} must be zero"
            )

    if (
        safety.get(
            "production_write"
        )
        is not False
    ):
        errors.append(
            "production_write "
            "must be false"
        )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "trace",
        type=Path,
    )

    args = parser.parse_args()

    if not args.trace.exists():
        print(
            "TRACE_VALIDATION_FAIL "
            "reason=FILE_NOT_FOUND"
        )
        return 1

    data = load_json(
        args.trace
    )

    errors = validate_trace(
        data
    )

    if errors:
        print(
            "TRACE_VALIDATION_FAIL"
        )

        for error in errors:
            print(error)

        return 1

    print(
        "TRACE_VALIDATION_OK "
        f"request_id={data['request_id']} "
        f"trace_id={data['trace_id']} "
        f"execution_type="
        f"{data['execution_type']}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())