import argparse
from pathlib import Path


REQUIRED_CATEGORIES = [
    "WRONG_INTENT",
    "ENTITY_MISS",
    "SCHEMA_ERROR",
    "UNSAFE_ROUTE",
    "OVER_ANSWER",
]


def validate_prompt_template(
    path: Path,
) -> list[str]:
    if not path.exists():
        return [
            f"template not found: {path}"
        ]

    text = path.read_text(
        encoding="utf-8",
    )

    errors = []

    for category in REQUIRED_CATEGORIES:
        if category not in text:
            errors.append(
                f"missing category: {category}"
            )

    required_fields = [
        "Sample ID:",
        "Variant:",
        "Category:",
        "Expected Intent:",
        "Predicted Intent:",
        "Expected Entities:",
        "Predicted Entities:",
        "Expected Risk:",
        "Predicted Risk:",
        "Expected Route:",
        "Predicted Route:",
        "JSON Valid:",
        "Root Cause:",
        "Prompt Improvement Hypothesis:",
        "Severity:",
    ]

    for field in required_fields:
        if field not in text:
            errors.append(
                f"missing field: {field}"
            )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--template",
        required=True,
        choices=["prompt"],
    )

    args = parser.parse_args()

    if args.template == "prompt":
        path = Path(
            "ai/evaluation/templates/"
            "prompt_error_analysis.md"
        )
    else:
        raise ValueError(
            f"unsupported template: "
            f"{args.template}"
        )

    errors = validate_prompt_template(
        path
    )

    if errors:
        print(
            "ERROR_REPORT_TEMPLATE_FAIL"
        )

        for error in errors:
            print(error)

        return 1

    print(
        "ERROR_REPORT_TEMPLATE_OK "
        f"template={args.template} "
        f"categories="
        f"{len(REQUIRED_CATEGORIES)}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())