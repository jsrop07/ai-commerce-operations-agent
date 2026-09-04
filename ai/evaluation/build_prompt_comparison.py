import argparse
import json
import math
import random
from pathlib import Path
from typing import Any


VARIANT_ORDER = [
    "zero_shot",
    "structured",
    "fewshot",
]

BOOTSTRAP_SEED = 42
BOOTSTRAP_RUNS = 5000


def load_json(
    path: Path,
) -> dict[str, Any]:
    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def normalize_entities(
    entities: list[dict[str, Any]],
) -> set[tuple[str, str]]:
    return {
        (
            str(entity.get("type", "")).strip(),
            str(entity.get("value", "")).strip(),
        )
        for entity in entities
    }


def intent_micro_f1(
    records: list[dict[str, Any]],
) -> float:
    if not records:
        return 0.0

    correct = sum(
        1
        for record in records
        if record["expected"].get("intent")
        == record["prediction"].get("intent")
    )

    return correct / len(records)


def intent_macro_f1(
    records: list[dict[str, Any]],
) -> float:
    labels = sorted(
        {
            record["expected"].get("intent")
            for record in records
        }
        |
        {
            record["prediction"].get("intent")
            for record in records
        }
    )

    scores = []

    for label in labels:
        tp = fp = fn = 0

        for record in records:
            expected = record[
                "expected"
            ].get("intent")

            predicted = record[
                "prediction"
            ].get("intent")

            if (
                expected == label
                and predicted == label
            ):
                tp += 1

            elif (
                expected != label
                and predicted == label
            ):
                fp += 1

            elif (
                expected == label
                and predicted != label
            ):
                fn += 1

        precision = (
            tp / (tp + fp)
            if tp + fp
            else 0.0
        )

        recall = (
            tp / (tp + fn)
            if tp + fn
            else 0.0
        )

        f1 = (
            2 * precision * recall
            / (precision + recall)
            if precision + recall
            else 0.0
        )

        scores.append(f1)

    return (
        sum(scores) / len(scores)
        if scores
        else 0.0
    )


def entity_f1(
    records: list[dict[str, Any]],
) -> float:
    tp = fp = fn = 0

    for record in records:
        expected = normalize_entities(
            record["expected"].get(
                "entities",
                [],
            )
        )

        predicted = normalize_entities(
            record["prediction"].get(
                "entities",
                [],
            )
        )

        tp += len(
            expected & predicted
        )

        fp += len(
            predicted - expected
        )

        fn += len(
            expected - predicted
        )

    precision = (
        tp / (tp + fp)
        if tp + fp
        else 0.0
    )

    recall = (
        tp / (tp + fn)
        if tp + fn
        else 0.0
    )

    return (
        2 * precision * recall
        / (precision + recall)
        if precision + recall
        else 0.0
    )


def percentile(
    values: list[float],
    q: float,
) -> float:
    values = sorted(values)

    if not values:
        return 0.0

    position = (
        len(values) - 1
    ) * q

    lower = math.floor(position)
    upper = math.ceil(position)

    if lower == upper:
        return values[lower]

    fraction = position - lower

    return (
        values[lower]
        * (1 - fraction)
        +
        values[upper]
        * fraction
    )


def bootstrap_ci(
    records: list[dict[str, Any]],
    metric_fn,
    *,
    seed: int,
    runs: int,
) -> dict[str, float]:
    rng = random.Random(seed)

    estimates = []

    size = len(records)

    for _ in range(runs):
        sample = [
            records[
                rng.randrange(size)
            ]
            for _ in range(size)
        ]

        estimates.append(
            metric_fn(sample)
        )

    return {
        "lower": round(
            percentile(
                estimates,
                0.025,
            ),
            4,
        ),
        "upper": round(
            percentile(
                estimates,
                0.975,
            ),
            4,
        ),
        "method":
            "percentile_bootstrap",
    }


def wilson_ci(
    successes: int,
    total: int,
) -> dict[str, Any]:
    if total == 0:
        return {
            "lower": None,
            "upper": None,
            "method": "wilson",
            "sample_count": 0,
        }

    z = 1.959963984540054

    p = successes / total

    denominator = (
        1
        + z * z / total
    )

    centre = (
        p
        + z * z
        / (2 * total)
    ) / denominator

    margin = (
        z
        * math.sqrt(
            (
                p * (1 - p)
                + z * z
                / (4 * total)
            )
            / total
        )
        / denominator
    )

    return {
        "lower":
            round(
                max(
                    0.0,
                    centre - margin,
                ),
                4,
            ),
        "upper":
            round(
                min(
                    1.0,
                    centre + margin,
                ),
                4,
            ),
        "method": "wilson",
        "sample_count": total,
    }


def json_valid_ci(
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    correct = sum(
        1
        for record in records
        if record.get(
            "json_valid",
            False,
        )
    )

    return wilson_ci(
        correct,
        len(records),
    )


def high_risk_routing_ci(
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    relevant = [
        record
        for record in records
        if record["expected"].get(
            "risk"
        )
        in {
            "HIGH",
            "PROHIBITED",
        }
    ]

    correct = sum(
        1
        for record in relevant
        if record["prediction"].get(
            "route"
        )
        == "HUMAN_REVIEW"
    )

    result = wilson_ci(
        correct,
        len(relevant),
    )

    result["correct"] = correct

    return result


def exact_error_count(
    records: list[dict[str, Any]],
) -> int:
    count = 0

    for record in records:
        if (
            record["expected"].get(
                "intent"
            )
            != record[
                "prediction"
            ].get("intent")
        ):
            count += 1
            continue

        if normalize_entities(
            record[
                "expected"
            ].get(
                "entities",
                [],
            )
        ) != normalize_entities(
            record[
                "prediction"
            ].get(
                "entities",
                [],
            )
        ):
            count += 1
            continue

        if not record.get(
            "json_valid",
            False,
        ):
            count += 1
            continue

        expected_risk = record[
            "expected"
        ].get("risk")

        if (
            expected_risk
            in {
                "HIGH",
                "PROHIBITED",
            }
            and record[
                "prediction"
            ].get("route")
            != "HUMAN_REVIEW"
        ):
            count += 1

    return count


def make_variant_result(
    variant: str,
    prediction_data:
        dict[str, Any],
    eval_data:
        dict[str, Any],
    *,
    bootstrap_seed: int,
    bootstrap_runs: int,
) -> dict[str, Any]:
    records = prediction_data[
        "records"
    ]

    metrics = eval_data[
        "metrics"
    ]

    micro_correct = sum(
        1
        for record in records
        if record["expected"].get(
            "intent"
        )
        == record["prediction"].get(
            "intent"
        )
    )

    return {
        "variant": variant,
        "prompt_id":
            prediction_data[
                "prompt_id"
            ],
        "prompt_version":
            prediction_data[
                "prompt_version"
            ],
        "sample_count":
            len(records),

        "metrics": {
            "intent_macro_f1":
                metrics[
                    "intent"
                ][
                    "macro_f1"
                ],

            "intent_macro_f1_ci95":
                bootstrap_ci(
                    records,
                    intent_macro_f1,
                    seed=
                        bootstrap_seed,
                    runs=
                        bootstrap_runs,
                ),

            "intent_micro_f1":
                metrics[
                    "intent"
                ][
                    "micro_f1"
                ],

            "intent_micro_f1_ci95":
                wilson_ci(
                    micro_correct,
                    len(records),
                ),

            "entity_f1":
                metrics[
                    "entity_f1"
                ],

            "entity_f1_ci95":
                bootstrap_ci(
                    records,
                    entity_f1,
                    seed=
                        bootstrap_seed
                        + 1,
                    runs=
                        bootstrap_runs,
                ),

            "json_valid_rate":
                metrics[
                    "json_valid_rate"
                ],

            "json_valid_rate_ci95":
                json_valid_ci(
                    records
                ),

            "high_risk_routing":
                metrics[
                    "high_risk_routing"
                ][
                    "rate"
                ],

            "high_risk_routing_ci95":
                high_risk_routing_ci(
                    records
                ),

            "latency": metrics[
                "latency"
            ],

            "token": metrics[
                "token"
            ],

            "cost": metrics[
                "cost"
            ],

            "error_count":
                exact_error_count(
                    records
                ),
        },

        "execution": {
            "provider":
                prediction_data.get(
                    "provider"
                ),
            "model":
                prediction_data.get(
                    "model"
                ),
            "temperature":
                prediction_data.get(
                    "temperature"
                ),
            "model_seed":
                prediction_data.get(
                    "seed"
                ),
            "model_seed_supported":
                prediction_data.get(
                    "seed_supported",
                    False,
                ),
            "reasoning_effort":
                prediction_data.get(
                    "reasoning_effort"
                ),
            "store":
                prediction_data.get(
                    "store"
                ),
            "execution_status":
                prediction_data.get(
                    "execution_status"
                ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--day03-dir",
        type=Path,
        default=Path(
            "artifacts/"
            "experiments/day03"
        ),
    )

    parser.add_argument(
        "--output",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--bootstrap-runs",
        type=int,
        default=BOOTSTRAP_RUNS,
    )

    parser.add_argument(
        "--bootstrap-seed",
        type=int,
        default=BOOTSTRAP_SEED,
    )

    args = parser.parse_args()

    variants = {}

    for variant in VARIANT_ORDER:
        if variant == "fewshot":
            prediction_name = (
                "fewshot_predictions.json"
            )
            eval_name = (
                "fewshot_eval.json"
            )

        elif variant == "structured":
            prediction_name = (
                "structured_predictions.json"
            )
            eval_name = (
                "structured_eval.json"
            )

        else:
            prediction_name = (
                "zero_shot_predictions.json"
            )
            eval_name = (
                "zero_shot_eval.json"
            )

        prediction_path = (
            args.day03_dir
            / prediction_name
        )

        eval_path = (
            args.day03_dir
            / eval_name
        )

        prediction_data = load_json(
            prediction_path
        )

        eval_data = load_json(
            eval_path
        )

        variants[variant] = (
            make_variant_result(
                variant,
                prediction_data,
                eval_data,
                bootstrap_seed=
                    args.bootstrap_seed,
                bootstrap_runs=
                    args.bootstrap_runs,
            )
        )

    result = {
        "schema_version":
            "prompt-comparison.v0.1",
        "experiment_id":
            "PROMPT-01",
        "status":
            "MEASURED_SMALL_VALIDATION",
        "dataset": {
            "version": "v0.1",
            "split": "validation",
            "sample_count": 8,
            "sha256":
                "17f86dcefa6401bb"
                "93fb9e8c8274da4e"
                "37724d79a1971f6a"
                "a034aed7b96a93f5",
        },

        "statistics": {
            "confidence_level":
                0.95,
            "bootstrap_runs":
                args.bootstrap_runs,
            "bootstrap_seed":
                args.bootstrap_seed,
            "bootstrap_seed_scope":
                "STATISTICAL_RESAMPLING_ONLY",
        },

        "variants":
            variants,

        "tradeoff_summary": {
            "zero_shot": {
                "strengths": [
                    "highest intent score",
                    "lowest total cost",
                ],
                "weaknesses": [
                    "entity over-generation",
                    "7 of 8 error samples",
                ],
            },

            "structured": {
                "strengths": [
                    "lowest observed p50/p95 latency",
                    "high-risk route preserved",
                ],
                "weaknesses": [
                    "intent score below zero-shot",
                    "lowest entity F1",
                    "higher token/cost than zero-shot",
                    "7 of 8 error samples",
                ],
            },

            "fewshot": {
                "strengths": [
                    "highest entity F1",
                    "fewest error samples",
                    "high-risk route preserved",
                ],
                "weaknesses": [
                    "higher token/cost",
                    "observed p95 latency outlier",
                    "reservation vs delivery confusion remains",
                ],
            },
        },

        "safety_notes": [
            (
                "High-risk routing had only "
                "1 eligible validation sample."
            ),
            (
                "Routing success does not imply "
                "risk-label correctness."
            ),
            (
                "PROHIBITED->HIGH was observed "
                "while HUMAN_REVIEW remained correct."
            ),
        ],

        "data_quality_notes": [
            (
                "DATE_TIME annotation ambiguity "
                "was observed."
            ),
            (
                "Golden entity annotation "
                "guideline requires review."
            ),
        ],

        "limitations": [
            (
                "Validation contains only "
                "8 samples."
            ),
            (
                "Confidence intervals are wide "
                "and unstable at this sample size."
            ),
            (
                "Results must not be generalized "
                "as final production performance."
            ),
            (
                "Validation results are for "
                "Day 4 integration candidate "
                "selection only."
            ),
            (
                "The final decision requires "
                "larger evaluation and later "
                "Base sLLM/QLoRA/API comparison."
            ),
        ],

        "decision":
            "PENDING_DAY04_CANDIDATE_LOCK",

        "external_api_calls_day04":
            0,

        "additional_api_cost_usd_day04":
            0.0,

        "gpu_cost_usd_day04":
            0.0,
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
            result,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print(
        "PROMPT_COMPARISON_OK "
        f"variants={len(variants)} "
        f"bootstrap_runs="
        f"{args.bootstrap_runs}"
    )

    for variant in VARIANT_ORDER:
        metrics = variants[
            variant
        ][
            "metrics"
        ]

        print(
            variant,
            "MACRO=",
            metrics[
                "intent_macro_f1"
            ],
            "ENTITY=",
            metrics[
                "entity_f1"
            ],
            "ERRORS=",
            metrics[
                "error_count"
            ],
            "COST=",
            metrics[
                "cost"
            ][
                "total"
            ],
        )

    print(
        f"OUTPUT={args.output}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())