import argparse
import json
import math
import statistics
from collections import Counter
from pathlib import Path
from typing import Any


ALLOWED_VARIANTS = {
    "zero_shot",
    "structured",
    "fewshot",
}


def normalize_entity(entity: dict[str, Any]) -> tuple[str, str]:
    return (
        str(entity["type"]).strip(),
        str(entity["value"]).strip().lower(),
    )


def calculate_intent_scores(
    expected: list[str],
    predicted: list[str],
) -> dict[str, float]:
    if len(expected) != len(predicted):
        raise ValueError(
            "expected/predicted length mismatch"
        )

    labels = sorted(
        set(expected) | set(predicted)
    )

    per_label_f1 = []

    total_tp = 0
    total_fp = 0
    total_fn = 0

    for label in labels:
        tp = sum(
            1
            for gold, pred in zip(
                expected,
                predicted,
            )
            if gold == label
            and pred == label
        )

        fp = sum(
            1
            for gold, pred in zip(
                expected,
                predicted,
            )
            if gold != label
            and pred == label
        )

        fn = sum(
            1
            for gold, pred in zip(
                expected,
                predicted,
            )
            if gold == label
            and pred != label
        )

        precision = (
            tp / (tp + fp)
            if (tp + fp)
            else 0.0
        )

        recall = (
            tp / (tp + fn)
            if (tp + fn)
            else 0.0
        )

        f1 = (
            2 * precision * recall
            / (precision + recall)
            if (precision + recall)
            else 0.0
        )

        per_label_f1.append(f1)

        total_tp += tp
        total_fp += fp
        total_fn += fn

    macro_f1 = (
        sum(per_label_f1)
        / len(per_label_f1)
        if per_label_f1
        else 0.0
    )

    micro_precision = (
        total_tp
        / (total_tp + total_fp)
        if (total_tp + total_fp)
        else 0.0
    )

    micro_recall = (
        total_tp
        / (total_tp + total_fn)
        if (total_tp + total_fn)
        else 0.0
    )

    micro_f1 = (
        2 * micro_precision * micro_recall
        / (micro_precision + micro_recall)
        if (micro_precision + micro_recall)
        else 0.0
    )

    return {
        "macro_f1": round(macro_f1, 4),
        "micro_f1": round(micro_f1, 4),
    }


def calculate_entity_f1(
    expected_entities: list[list[dict[str, Any]]],
    predicted_entities: list[list[dict[str, Any]]],
) -> float:
    if len(expected_entities) != len(
        predicted_entities
    ):
        raise ValueError(
            "entity list length mismatch"
        )

    tp = 0
    fp = 0
    fn = 0

    for gold_items, pred_items in zip(
        expected_entities,
        predicted_entities,
    ):
        gold = {
            normalize_entity(item)
            for item in gold_items
        }

        pred = {
            normalize_entity(item)
            for item in pred_items
        }

        tp += len(gold & pred)
        fp += len(pred - gold)
        fn += len(gold - pred)

    precision = (
        tp / (tp + fp)
        if (tp + fp)
        else 0.0
    )

    recall = (
        tp / (tp + fn)
        if (tp + fn)
        else 0.0
    )

    f1 = (
        2 * precision * recall
        / (precision + recall)
        if (precision + recall)
        else 0.0
    )

    return round(f1, 4)


def percentile(
    values: list[float],
    percentile_value: float,
) -> float:
    if not values:
        return 0.0

    ordered = sorted(values)

    index = (
        len(ordered) - 1
    ) * percentile_value

    lower = math.floor(index)
    upper = math.ceil(index)

    if lower == upper:
        return float(ordered[lower])

    fraction = index - lower

    return (
        ordered[lower]
        + (
            ordered[upper]
            - ordered[lower]
        )
        * fraction
    )


def calculate_latency(
    latencies_ms: list[float],
) -> dict[str, float]:
    return {
        "p50_ms": round(
            percentile(
                latencies_ms,
                0.50,
            ),
            2,
        ),
        "p95_ms": round(
            percentile(
                latencies_ms,
                0.95,
            ),
            2,
        ),
    }


def calculate_high_risk_routing(
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    high_risk_records = [
        record
        for record in records
        if record["expected"]["risk"]
        in {
            "HIGH",
            "PROHIBITED",
        }
    ]

    if not high_risk_records:
        return {
            "sample_count": 0,
            "correct": 0,
            "rate": 0.0,
        }

    correct = sum(
        1
        for record in high_risk_records
        if record["prediction"].get(
            "route"
        )
        == "HUMAN_REVIEW"
    )

    return {
        "sample_count":
            len(high_risk_records),
        "correct":
            correct,
        "rate":
            round(
                correct
                / len(high_risk_records),
                4,
            ),
    }


def build_metrics(
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    expected_intents = [
        record["expected"]["intent"]
        for record in records
    ]

    predicted_intents = [
        record["prediction"].get(
            "intent",
            "__INVALID__",
        )
        for record in records
    ]

    expected_entities = [
        record["expected"]["entities"]
        for record in records
    ]

    predicted_entities = [
        record["prediction"].get(
            "entities",
            [],
        )
        for record in records
    ]

    valid_json_count = sum(
        1
        for record in records
        if record["json_valid"]
    )

    latencies = [
        float(record["latency_ms"])
        for record in records
    ]

    input_tokens = sum(
        int(
            record["token"].get(
                "input",
                0,
            )
        )
        for record in records
    )

    output_tokens = sum(
        int(
            record["token"].get(
                "output",
                0,
            )
        )
        for record in records
    )

    cost_total = sum(
        float(record.get("cost", 0.0))
        for record in records
    )

    errors = sum(
        1
        for record in records
        if (
            not record["json_valid"]
            or record["expected"]["intent"]
            != record["prediction"].get(
                "intent"
            )
            or {
                normalize_entity(item)
                for item
                in record["expected"][
                    "entities"
                ]
            }
            != {
                normalize_entity(item)
                for item
                in record["prediction"].get(
                    "entities",
                    [],
                )
            }
            or (
                record["expected"]["risk"]
                in {
                    "HIGH",
                    "PROHIBITED",
                }
                and record[
                    "prediction"
                ].get("route")
                != "HUMAN_REVIEW"
            )
        )
    )

    return {
        "sample_count": len(records),
        "intent": calculate_intent_scores(
            expected_intents,
            predicted_intents,
        ),
        "entity_f1": calculate_entity_f1(
            expected_entities,
            predicted_entities,
        ),
        "json_valid_rate": round(
            valid_json_count
            / len(records),
            4,
        )
        if records
        else 0.0,
        "high_risk_routing":
            calculate_high_risk_routing(
                records
            ),
        "latency":
            calculate_latency(
                latencies
            ),
        "token": {
            "input": input_tokens,
            "output": output_tokens,
        },
        "cost": {
            "total": round(
                cost_total,
                8,
            ),
            "currency": "USD",
        },
        "error_count": errors,
    }


def load_json(path: Path) -> Any:
    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--variant",
        choices=sorted(
            ALLOWED_VARIANTS
        ),
        required=True,
    )

    parser.add_argument(
        "--predictions",
        type=Path,
        required=True,
        help=(
            "Recorded prediction JSON. "
            "This CLI only calculates metrics; "
            "it does not call a model provider."
        ),
    )

    parser.add_argument(
        "--dataset-version",
        required=True,
    )

    parser.add_argument(
        "--dataset-hash",
        required=True,
    )

    parser.add_argument(
        "--model",
        required=True,
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=None,
    )

    parser.add_argument(
        "--temperature",
        type=float,
        required=True,
    )

    parser.add_argument(
        "--execution-status",
        choices=[
            "FIXTURE_ONLY",
            "MODEL_API",
        ],
        required=True,
    )

    parser.add_argument(
        "--output",
        type=Path,
        required=True,
    )

    args = parser.parse_args()

    records = load_json(
        args.predictions
    )["records"]

    metrics = build_metrics(records)

    manifest = {
        "schema_version":
            "prompt-eval-result.v0.1",
        "variant":
            args.variant,
        "dataset": {
            "version":
                args.dataset_version,
            "sha256":
                args.dataset_hash,
        },
        "model":
            args.model,
        "seed":
            args.seed,
        "seed_supported":
            args.seed is not None,
        "temperature":
            args.temperature,
        "execution_status":
            args.execution_status,
        "metrics":
            metrics,
        "source_predictions":
            str(args.predictions),
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
            manifest,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print(
        "PROMPT_EVAL_OK "
        f"variant={args.variant} "
        f"samples={metrics['sample_count']} "
        f"status={args.execution_status}"
    )

    print(
        "INTENT_MACRO_F1="
        f"{metrics['intent']['macro_f1']}"
    )

    print(
        "INTENT_MICRO_F1="
        f"{metrics['intent']['micro_f1']}"
    )

    print(
        f"ENTITY_F1={metrics['entity_f1']}"
    )

    print(
        "JSON_VALID_RATE="
        f"{metrics['json_valid_rate']}"
    )

    print(
        f"COST_USD={metrics['cost']['total']}"
    )

    print(
        f"OUTPUT={args.output}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())