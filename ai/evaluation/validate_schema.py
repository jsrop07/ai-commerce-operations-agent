import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


SCHEMA_PATH = Path(__file__).with_name("experiment.schema.json")


def validate_file(target_path: Path) -> int:
    with SCHEMA_PATH.open("r", encoding="utf-8") as file:
        schema = json.load(file)

    with target_path.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda error: list(error.path))

    if errors:
        print("SCHEMA_VALIDATION_FAILED")

        for error in errors:
            location = ".".join(str(part) for part in error.path) or "<root>"
            print(f"{location}: {error.message}")

        return 1

    print("SCHEMA_VALIDATION_OK")
    return 0


def main() -> int:
    if len(sys.argv) != 2:
        print(
            "usage: python -m ai.evaluation.validate_schema "
            "<experiment-result.json>"
        )
        return 2

    target_path = Path(sys.argv[1])

    if not target_path.exists():
        print(f"FILE_NOT_FOUND: {target_path}")
        return 2

    return validate_file(target_path)


if __name__ == "__main__":
    raise SystemExit(main())