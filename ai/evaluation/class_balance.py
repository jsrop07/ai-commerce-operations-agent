import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_FIELDS = (
    "intent",
    "category",
    "issue",
)

MINORITY_RATIO_THRESHOLD = 0.5


def validate_records(
    records: list[dict[str, Any]],
    fields: tuple[str, ...] = DEFAULT_FIELDS,
) -> None:
    if not records:
        raise ValueError("records must not be empty")

    for record in records:
        if "record_id" not in record:
            raise ValueError("record_id is required")

        for field in fields:
            value = record.get(field)

            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"{record['record_id']} has invalid {field}"
                )


def recommendation_for(
    support: int,
    max_support: int,
) -> tuple[str, list[str]]:
    if max_support <= 0:
        raise ValueError("max_support must be positive")

    ratio_to_max = support / max_support

    if ratio_to_max < MINORITY_RATIO_THRESHOLD:
        return (
            "MINORITY",
            [
                "REVIEW_LABEL_COVERAGE",
                "LOSS_WEIGHTING_CANDIDATE",
                "TARGETED_SYNTHETIC_CANDIDATE",
            ],
        )

    return (
        "NORMAL",
        ["NONE"],
    )


def analyze_field(
    records: list[dict[str, Any]],
    field: str,
) -> dict[str, Any]:
    counts = Counter(
        record[field]
        for record in records
    )

    max_support = max(counts.values())

    classes = []

    for label, support in sorted(
        counts.items(),
        key=lambda item: (-item[1], item[0]),
    ):
        status, recommendations = recommendation_for(
            support,
            max_support,
        )

        classes.append(
            {
                "label": label,
                "support": support,
                "share": round(
                    support / len(records),
                    4,
                ),
                "ratio_to_max": round(
                    support / max_support,
                    4,
                ),
                "balance_status": status,
                "recommendations": recommendations,
            }
        )

    minority_classes = [
        item["label"]
        for item in classes
        if item["balance_status"] == "MINORITY"
    ]

    return {
        "field": field,
        "total_records": len(records),
        "class_count": len(classes),
        "max_support": max_support,
        "minority_threshold_ratio": MINORITY_RATIO_THRESHOLD,
        "minority_classes": minority_classes,
        "classes": classes,
    }


def build_report(
    records: list[dict[str, Any]],
    fields: tuple[str, ...] = DEFAULT_FIELDS,
) -> dict[str, Any]:
    validate_records(records, fields)

    return {
        "schema_version": "class-balance-report.v0.1",
        "total_records": len(records),
        "fields": {
            field: analyze_field(records, field)
            for field in fields
        },
        "policy": {
            "minority_rule": (
                "support / max_support < 0.5"
            ),
            "automatic_oversampling": False,
            "recommended_order": [
                "REVIEW_LABEL_COVERAGE",
                "LOSS_WEIGHTING_CANDIDATE",
                "TARGETED_SYNTHETIC_CANDIDATE",
            ],
        },
    }


def write_json_report(
    report: dict[str, Any],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            report,
            file,
            ensure_ascii=False,
            indent=2,
        )


def write_csv_report(
    report: dict[str, Any],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "field",
                "label",
                "support",
                "share",
                "ratio_to_max",
                "balance_status",
                "recommendations",
            ],
        )

        writer.writeheader()

        for field_name, field_report in report["fields"].items():
            for item in field_report["classes"]:
                writer.writerow(
                    {
                        "field": field_name,
                        "label": item["label"],
                        "support": item["support"],
                        "share": item["share"],
                        "ratio_to_max": item["ratio_to_max"],
                        "balance_status": item["balance_status"],
                        "recommendations": "|".join(
                            item["recommendations"]
                        ),
                    }
                )


def load_records(path: Path) -> list[dict[str, Any]]:
    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        payload = json.load(file)

    return payload["records"]


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--fixture",
        action="store_true",
    )

    parser.add_argument(
        "--input",
        type=Path,
    )

    parser.add_argument(
        "--json-output",
        type=Path,
        default=Path(
            "artifacts/experiments/day02/"
            "class_balance_report.json"
        ),
    )

    parser.add_argument(
        "--csv-output",
        type=Path,
        default=Path(
            "artifacts/experiments/day02/"
            "class_balance_report.csv"
        ),
    )

    args = parser.parse_args()

    if args.fixture:
        input_path = Path(
            "ai/tests/fixtures/"
            "class_balance_fixture.json"
        )
    elif args.input:
        input_path = args.input
    else:
        parser.error(
            "--fixture or --input is required"
        )

    records = load_records(input_path)

    report = build_report(records)

    write_json_report(
        report,
        args.json_output,
    )

    write_csv_report(
        report,
        args.csv_output,
    )

    minority_total = sum(
        len(field["minority_classes"])
        for field in report["fields"].values()
    )

    print(
        "CLASS_BALANCE_OK "
        f"records={report['total_records']} "
        f"minority_classes={minority_total}"
    )

    print(
        f"JSON_REPORT={args.json_output}"
    )

    print(
        f"CSV_REPORT={args.csv_output}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())