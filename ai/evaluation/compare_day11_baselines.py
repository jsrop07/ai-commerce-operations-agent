from __future__ import annotations

import csv
import json
from pathlib import Path


TRUTH_PATH = Path(
    "artifacts/experiments/day11/"
    "pilot_20_reviewed_truth.csv"
)

QWEN_PATH = Path(
    "artifacts/experiments/day11/"
    "qwen_safe_pilot_20_results.jsonl"
)

OPENAI_PATH = Path(
    "artifacts/experiments/day11/"
    "openai_label_pilot_20_results.jsonl"
)

OUTPUT_PATH = Path(
    "artifacts/experiments/day11/"
    "day11_baseline_comparison.json"
)


ALLOWED_ENTITY_TYPES = {
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
}


def load_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]


def load_truth(path: Path) -> dict[str, dict]:
    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as f:
        rows = list(csv.DictReader(f))

    return {
        row["record_id"]: row
        for row in rows
    }


def to_bool(value: str) -> bool:
    return value.strip().lower() == "true"


def normalize_truth(row: dict) -> dict:
    return {
        "eligible_for_nlu": to_bool(
            row["eligible_for_nlu"]
        ),
        "intent": (
            row["intent"]
            if row["intent"]
            else None
        ),
        "risk": row["risk"],
        "human_review_required": to_bool(
            row["human_review_required"]
        ),
    }


def evaluate(
    name: str,
    rows: list[dict],
    truth: dict[str, dict],
) -> dict:
    total = 0
    intent_correct = 0
    risk_correct = 0
    eligible_correct = 0
    human_correct = 0
    schema_valid = 0

    entity_total = 0
    entity_valid = 0

    for row in rows:
        record_id = row["record_id"]

        if record_id not in truth:
            continue

        total += 1

        proposal = row.get("proposal")

        if proposal is None:
            continue

        truth_row = normalize_truth(
            truth[record_id]
        )

        if (
            proposal.get("intent")
            == truth_row["intent"]
        ):
            intent_correct += 1

        if (
            proposal.get("risk")
            == truth_row["risk"]
        ):
            risk_correct += 1

        if (
            proposal.get("eligible_for_nlu")
            == truth_row["eligible_for_nlu"]
        ):
            eligible_correct += 1

        if (
            proposal.get("human_review_required")
            == truth_row[
                "human_review_required"
            ]
        ):
            human_correct += 1

        if name == "qwen":
            if row.get("valid_json_schema"):
                schema_valid += 1
        else:
            if row.get("schema_valid"):
                schema_valid += 1

        for entity in proposal.get(
            "entities",
            [],
        ):
            entity_total += 1

            if (
                entity.get("type")
                in ALLOWED_ENTITY_TYPES
            ):
                entity_valid += 1

    def rate(value: int) -> float:
        if total == 0:
            return 0.0
        return round(value / total, 4)

    entity_valid_rate = (
        round(
            entity_valid / entity_total,
            4,
        )
        if entity_total
        else 1.0
    )

    return {
        "rows": total,
        "intent_accuracy": rate(
            intent_correct
        ),
        "risk_accuracy": rate(
            risk_correct
        ),
        "eligibility_accuracy": rate(
            eligible_correct
        ),
        "human_review_accuracy": rate(
            human_correct
        ),
        "full_schema_valid_rate": rate(
            schema_valid
        ),
        "entity_taxonomy_valid_rate": (
            entity_valid_rate
        ),
        "entity_count": entity_total,
        "entity_valid_count": entity_valid,
    }


def main() -> int:
    truth = load_truth(TRUTH_PATH)
    qwen = load_jsonl(QWEN_PATH)
    openai = load_jsonl(OPENAI_PATH)

    result = {
        "truth_rows": len(truth),
        "qwen": evaluate(
            "qwen",
            qwen,
            truth,
        ),
        "openai": evaluate(
            "openai",
            openai,
            truth,
        ),
        "test_data_used": False,
        "truth_source": (
            "operator-reviewed pilot truth"
        ),
    }

    OUTPUT_PATH.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())