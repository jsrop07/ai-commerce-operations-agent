import argparse
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_RATIOS = {
    "train": 0.6,
    "validation": 0.2,
    "test": 0.2,
}


def parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def validate_records(records: list[dict[str, Any]]) -> None:
    required = {
        "record_id",
        "customer_group",
        "thread_group",
        "occurred_at",
    }

    for record in records:
        missing = required - record.keys()

        if missing:
            raise ValueError(
                f"{record.get('record_id', '<unknown>')} missing fields: "
                f"{sorted(missing)}"
            )

        parse_datetime(record["occurred_at"])


def build_customer_components(
    records: list[dict[str, Any]],
) -> list[list[dict[str, Any]]]:
    by_customer: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for record in records:
        by_customer[record["customer_group"]].append(record)

    groups = list(by_customer.values())

    groups.sort(
        key=lambda group: min(
            parse_datetime(record["occurred_at"])
            for record in group
        )
    )

    return groups


def assign_groups(
    groups: list[list[dict[str, Any]]],
    ratios: dict[str, float] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    ratios = ratios or DEFAULT_RATIOS

    total_records = sum(len(group) for group in groups)

    train_target = total_records * ratios["train"]
    validation_target = total_records * ratios["validation"]

    splits = {
        "train": [],
        "validation": [],
        "test": [],
    }

    for group in groups:
        if len(splits["train"]) < train_target:
            target_split = "train"
        elif len(splits["validation"]) < validation_target:
            target_split = "validation"
        else:
            target_split = "test"

        splits[target_split].extend(group)

    return splits


def group_values(
    records: list[dict[str, Any]],
    field: str,
) -> set[str]:
    return {str(record[field]) for record in records}


def calculate_group_overlap(
    splits: dict[str, list[dict[str, Any]]],
    field: str,
) -> dict[str, list[str]]:
    train = group_values(splits["train"], field)
    validation = group_values(splits["validation"], field)
    test = group_values(splits["test"], field)

    return {
        "train_validation": sorted(train & validation),
        "train_test": sorted(train & test),
        "validation_test": sorted(validation & test),
    }


def calculate_time_ranges(
    splits: dict[str, list[dict[str, Any]]],
) -> dict[str, dict[str, str | None]]:
    result: dict[str, dict[str, str | None]] = {}

    for split_name, records in splits.items():
        if not records:
            result[split_name] = {
                "min": None,
                "max": None,
            }
            continue

        timestamps = sorted(
            parse_datetime(record["occurred_at"])
            for record in records
        )

        result[split_name] = {
            "min": timestamps[0].isoformat(),
            "max": timestamps[-1].isoformat(),
        }

    return result


def build_report(
    splits: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    total = sum(len(records) for records in splits.values())

    counts = {
        split_name: len(records)
        for split_name, records in splits.items()
    }

    ratios = {
        split_name: (
            round(len(records) / total, 4)
            if total
            else 0.0
        )
        for split_name, records in splits.items()
    }

    customer_overlap = calculate_group_overlap(
        splits,
        "customer_group",
    )

    thread_overlap = calculate_group_overlap(
        splits,
        "thread_group",
    )

    overlap_count = sum(
        len(values)
        for values in customer_overlap.values()
    ) + sum(
        len(values)
        for values in thread_overlap.values()
    )

    return {
        "schema_version": "group-split-report.v0.1",
        "total_records": total,
        "counts": counts,
        "ratios": ratios,
        "customer_overlap": customer_overlap,
        "thread_overlap": thread_overlap,
        "group_overlap_count": overlap_count,
        "time_ranges": calculate_time_ranges(splits),
    }


def split_records(
    records: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    validate_records(records)

    groups = build_customer_components(records)
    splits = assign_groups(groups)
    report = build_report(splits)

    return splits, report


def load_fixture(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    return payload["records"]


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--fixture",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--report",
        type=Path,
        required=True,
    )

    args = parser.parse_args()

    records = load_fixture(args.fixture)

    _, report = split_records(records)

    args.report.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with args.report.open("w", encoding="utf-8") as file:
        json.dump(
            report,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print(
        f"GROUP_SPLIT_OK "
        f"total={report['total_records']} "
        f"train={report['counts']['train']} "
        f"validation={report['counts']['validation']} "
        f"test={report['counts']['test']} "
        f"overlap={report['group_overlap_count']}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())