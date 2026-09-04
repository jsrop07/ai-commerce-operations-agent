import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from openai import OpenAI


MODEL_ID = "gpt-5.6-luna"
TEMPERATURE = 0.0
INPUT_PRICE_PER_1M = 0.20
CACHED_INPUT_PRICE_PER_1M = 0.02
OUTPUT_PRICE_PER_1M = 1.20

def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return yaml.safe_load(file)


def load_json(path: Path) -> dict[str, Any]:
    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def build_json_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "intent",
            "entities",
            "risk",
            "route",
            "confidence",
        ],
        "properties": {
            "intent": {
                "type": "string",
                "enum": [
                    "PRODUCT_INFO",
                    "COMPATIBILITY",
                    "STOCK_AVAILABILITY",
                    "RESTOCK",
                    "ORDER_STATUS",
                    "DELIVERY",
                    "RESERVATION_PREORDER",
                    "RETURN_EXCHANGE",
                    "REFUND_CANCEL",
                    "OTHER",
                ],
            },
            "entities": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "type",
                        "value",
                    ],
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": [
                                "PRODUCT",
                                "SKU",
                                "BRAND",
                                "CATEGORY",
                                "LANGUAGE",
                                "ORDER_REF",
                                "QUANTITY",
                                "DATE_TIME",
                                "CHANNEL",
                                "ISSUE_TYPE",
                            ],
                        },
                        "value": {
                            "type": "string",
                        },
                    },
                },
            },
            "risk": {
                "type": "string",
                "enum": [
                    "LOW",
                    "MEDIUM",
                    "HIGH",
                    "PROHIBITED",
                ],
            },
            "route": {
                "type": "string",
                "enum": [
                    "SLLM",
                    "HUMAN_REVIEW",
                ],
            },
            "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
            },
        },
    }


def render_prompt(
    prompt: dict[str, Any],
    inquiry_text: str,
) -> str:
    system = prompt["system"]
    instruction = prompt["instruction"]
    examples = prompt["examples"]

    payload = {
        "system": system,
        "instruction": instruction,
        "examples": examples,
        "input": {
            "sanitized_inquiry":
                inquiry_text,
        },
    }

    return json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
    )


def usage_value(
    usage: Any,
    name: str,
) -> int:
    if usage is None:
        return 0

    value = getattr(
        usage,
        name,
        0,
    )

    return int(value or 0)

def cached_input_tokens(usage: Any) -> int:
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


def calculate_cost(
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
        +
        cached_tokens
        / 1_000_000
        * CACHED_INPUT_PRICE_PER_1M
        +
        output_tokens
        / 1_000_000
        * OUTPUT_PRICE_PER_1M
    )

    return round(cost, 8)

def call_model(
    client: OpenAI,
    prompt_text: str,
) -> dict[str, Any]:
    started = time.perf_counter()

    response = client.responses.create(
        model=MODEL_ID,
        input=prompt_text,
        temperature=TEMPERATURE,
        reasoning={
            "effort": "none",
        },
        store=False,
        text={
            "format": {
                "type": "json_schema",
                "name":
                    "inquiry_classification",
                "strict": True,
                "schema":
                    build_json_schema(),
            }
        },
    )

    elapsed_ms = (
        time.perf_counter()
        - started
    ) * 1000

    raw_text = response.output_text

    try:
        prediction = json.loads(
            raw_text
        )

        json_valid = True

    except json.JSONDecodeError:
        prediction = {}
        json_valid = False

    usage = response.usage
    input_tokens = usage_value(
        usage,
        "input_tokens",
    )

    output_tokens = usage_value(
        usage,
        "output_tokens",
    )

    cached_tokens = cached_input_tokens(
        usage
    )

    estimated_cost = calculate_cost(
        input_tokens=input_tokens,
        cached_tokens=cached_tokens,
        output_tokens=output_tokens,
    )

    return {
        "prediction": prediction,
        "json_valid": json_valid,
        "latency_ms": round(
            elapsed_ms,
            2,
        ),
        "token": {
            "input": input_tokens,
            "output": output_tokens,
            "cache": cached_tokens,
        },
        "cost": estimated_cost,
        "raw_output": (
            raw_text
            if not json_valid
            else None
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--prompt",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--dataset",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--split",
        default="validation",
        choices=[
            "train",
            "validation",
            "test",
        ],
    )

    parser.add_argument(
        "--output",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit records for smoke testing.",
    )

    args = parser.parse_args()

    load_dotenv()

    if not os.getenv(
        "OPENAI_API_KEY"
    ):
        print(
            "OPENAI_RUN_BLOCKED "
            "reason=OPENAI_API_KEY_MISSING"
        )
        return 2

    prompt = load_yaml(
        args.prompt
    )

    dataset = load_json(
        args.dataset
    )

    records = [
        record
        for record
        in dataset["records"]
        if record["split"]
        == args.split
    ]

    if args.limit is not None:
        if args.limit <= 0:
            raise ValueError(
                "--limit must be positive"
            )

        records = records[
            :args.limit
        ]

    if not records:
        raise ValueError(
            f"no records for split: "
            f"{args.split}"
        )

    client = OpenAI()

    output_records = []

    for index, record in enumerate(
        records,
        start=1,
    ):
        prompt_text = render_prompt(
            prompt,
            record["text"],
        )

        result = call_model(
            client,
            prompt_text,
        )

        output_records.append(
            {
                "id":
                    record["id"],
                "expected":
                    record["expected"],
                "prediction":
                    result[
                        "prediction"
                    ],
                "json_valid":
                    result[
                        "json_valid"
                    ],
                "latency_ms":
                    result[
                        "latency_ms"
                    ],
                "token":
                    result["token"],
                "cost": 
                    result["cost"],
                "raw_output":
                    result[
                        "raw_output"
                    ],
            }
        )

        print(
            f"MODEL_SAMPLE_OK "
            f"{index}/{len(records)} "
            f"id={record['id']} "
            f"json_valid="
            f"{result['json_valid']}"
        )

    output = {
        "schema_version":
            "prompt-predictions.v0.1",
        "provider":
            "openai",
        "model":
            MODEL_ID,
        "temperature":
            TEMPERATURE,
        "seed":
            None,
        "seed_supported":
            False,
        "reasoning_effort":
            "none",
        "store":
            False,
        "split":
            args.split,
        "prompt_id":
            prompt["prompt_id"],
        "prompt_version":
            prompt["version"],
        "execution_status":
            "MODEL_API",
        "records":
            output_records,
    }

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with args.output.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            output,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print(
        "OPENAI_PROMPT_RUN_OK "
        f"prompt={prompt['prompt_id']} "
        f"samples={len(records)} "
        f"model={MODEL_ID}"
    )

    print(
        f"OUTPUT={args.output}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())