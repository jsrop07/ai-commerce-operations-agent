import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def normalize_entities(
    entities: list[dict[str, Any]],
) -> set[tuple[str, str]]:
    normalized = set()

    for entity in entities:
        entity_type = str(
            entity.get("type", "")
        ).strip()

        value = str(
            entity.get("value", "")
        ).strip()

        normalized.add(
            (
                entity_type,
                value,
            )
        )

    return normalized


def classify_record(
    record: dict[str, Any],
) -> list[str]:
    categories = []

    expected = record["expected"]
    prediction = record["prediction"]

    if not record.get(
        "json_valid",
        False,
    ):
        categories.append(
            "SCHEMA_ERROR"
        )

        return categories

    if (
        prediction.get("intent")
        != expected.get("intent")
    ):
        categories.append(
            "WRONG_INTENT"
        )

    expected_entities = normalize_entities(
        expected.get(
            "entities",
            [],
        )
    )

    predicted_entities = normalize_entities(
        prediction.get(
            "entities",
            [],
        )
    )

    missing_entities = (
        expected_entities
        - predicted_entities
    )

    extra_entities = (
        predicted_entities
        - expected_entities
    )

    if missing_entities:
        categories.append(
            "ENTITY_MISS"
        )

    if extra_entities:
        categories.append(
            "OVER_ANSWER"
        )

    expected_risk = expected.get(
        "risk"
    )

    predicted_route = prediction.get(
        "route"
    )

    if (
        expected_risk
        in {
            "HIGH",
            "PROHIBITED",
        }
        and predicted_route
        != "HUMAN_REVIEW"
    ):
        categories.append(
            "UNSAFE_ROUTE"
        )

    return categories


def analyze_file(
    path: Path,
) -> dict[str, Any]:
    data = load_json(path)

    errors = []

    category_counts = {
        "WRONG_INTENT": 0,
        "ENTITY_MISS": 0,
        "SCHEMA_ERROR": 0,
        "UNSAFE_ROUTE": 0,
        "OVER_ANSWER": 0,
    }

    for record in data["records"]:
        categories = classify_record(
            record
        )

        if not categories:
            continue

        for category in categories:
            category_counts[
                category
            ] += 1

        errors.append(
            {
                "id":
                    record["id"],
                "categories":
                    categories,
                "expected":
                    record["expected"],
                "prediction":
                    record["prediction"],
                "json_valid":
                    record.get(
                        "json_valid",
                        False,
                    ),
            }
        )

    return {
        "schema_version":
            "prompt-error-analysis.v0.1",
        "variant":
            data["prompt_id"],
        "model":
            data["model"],
        "temperature":
            data["temperature"],
        "seed":
            data.get("seed"),
        "seed_supported":
            data.get(
                "seed_supported",
                False,
            ),
        "sample_count":
            len(data["records"]),
        "error_sample_count":
            len(errors),
        "category_counts":
            category_counts,
        "errors":
            errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--predictions",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--output",
        type=Path,
        required=True,
    )

    args = parser.parse_args()

    result = analyze_file(
        args.predictions
    )

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
        "PROMPT_ERROR_ANALYSIS_OK"
    )

    print(
        f"VARIANT={result['variant']}"
    )

    print(
        f"SAMPLES={result['sample_count']}"
    )

    print(
        "ERROR_SAMPLES="
        f"{result['error_sample_count']}"
    )

    for (
        category,
        count,
    ) in result[
        "category_counts"
    ].items():
        print(
            f"{category}={count}"
        )

    print(
        f"OUTPUT={args.output}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())