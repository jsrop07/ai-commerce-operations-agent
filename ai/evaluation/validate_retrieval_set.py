import hashlib
import json
import sys
from pathlib import Path


ALLOWED_SLICES = {
    "product_exact",
    "product_alias_typo",
    "compatibility",
    "component",
    "inventory_freshness",
    "order_delivery",
    "policy",
    "no_answer",
}

ALLOWED_ANSWERABILITY = {
    "ANSWERABLE",
    "ABSTAIN",
}

ALLOWED_SPLITS = {
    "validation",
    "test",
}


def validate_record(record: dict, line_number: int) -> list[str]:
    errors: list[str] = []

    required = {
        "query_id",
        "query",
        "slice",
        "language",
        "tenant_id",
        "relevant",
        "expected_answerability",
        "split",
    }

    missing = sorted(required - record.keys())

    if missing:
        errors.append(
            f"line {line_number}: missing fields: {', '.join(missing)}"
        )
        return errors

    if not isinstance(record["query_id"], str) or not record["query_id"]:
        errors.append(f"line {line_number}: query_id must be non-empty string")

    if not isinstance(record["query"], str) or not record["query"].strip():
        errors.append(f"line {line_number}: query must be non-empty string")

    if record["slice"] not in ALLOWED_SLICES:
        errors.append(f"line {line_number}: invalid slice")

    if record["expected_answerability"] not in ALLOWED_ANSWERABILITY:
        errors.append(f"line {line_number}: invalid expected_answerability")

    if record["split"] not in ALLOWED_SPLITS:
        errors.append(f"line {line_number}: invalid split")

    if not isinstance(record["relevant"], list):
        errors.append(f"line {line_number}: relevant must be list")
        return errors

    for index, item in enumerate(record["relevant"]):
        if not isinstance(item, dict):
            errors.append(
                f"line {line_number}: relevant[{index}] must be object"
            )
            continue

        if "source_id" not in item or "grade" not in item:
            errors.append(
                f"line {line_number}: relevant[{index}] missing source_id/grade"
            )
            continue

        if not isinstance(item["source_id"], str) or not item["source_id"]:
            errors.append(
                f"line {line_number}: relevant[{index}].source_id invalid"
            )

        if item["grade"] not in {0, 1, 2, 3}:
            errors.append(
                f"line {line_number}: relevant[{index}].grade must be 0..3"
            )

    if record["expected_answerability"] == "ANSWERABLE":
        if not any(item.get("grade") == 3 for item in record["relevant"]):
            errors.append(
                f"line {line_number}: ANSWERABLE requires grade 3 evidence"
            )

    if record["expected_answerability"] == "ABSTAIN":
        if any(item.get("grade", 0) >= 2 for item in record["relevant"]):
            errors.append(
                f"line {line_number}: ABSTAIN must not have grade >= 2 evidence"
            )

    return errors


def load_records(path: Path) -> tuple[list[dict], list[str]]:
    records: list[dict] = []
    errors: list[str] = []

    with path.open("r", encoding="utf-8") as file:
        for line_number, raw_line in enumerate(file, start=1):
            line = raw_line.strip()

            if not line:
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(
                    f"line {line_number}: invalid JSON: {exc.msg}"
                )
                continue

            records.append(record)
            errors.extend(validate_record(record, line_number))

    return records, errors


def dataset_hash(records: list[dict]) -> str:
    canonical = "\n".join(
        json.dumps(
            record,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        for record in records
    )

    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def main() -> int:
    if len(sys.argv) != 2:
        print(
            "usage: python -m ai.evaluation.validate_retrieval_set "
            "<golden_retrieval.jsonl>"
        )
        return 2

    path = Path(sys.argv[1])

    if not path.exists():
        print(f"FILE_NOT_FOUND: {path}")
        return 2

    records, errors = load_records(path)

    query_ids = [record.get("query_id") for record in records]

    if len(query_ids) != len(set(query_ids)):
        errors.append("duplicate query_id detected")

    if errors:
        print("RETRIEVAL_SET_VALIDATION_FAILED")

        for error in errors:
            print(error)

        return 1

    print("RETRIEVAL_SET_VALIDATION_OK")
    print(f"QUERY_COUNT={len(records)}")
    print(f"SPLIT_HASH={dataset_hash(records)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())