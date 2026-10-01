import json
from pathlib import Path

from ai.services.grounded_explanation import (
    ExplanationEvidence,
    build_policy_grounded_explanation_input,
)
from ai.services.grounded_explanation_output import (
    ClaimCitation,
    ExplanationStatus,
    GroundedExplanationOutput,
    NumericFact,
)
from ai.services.grounded_explanation_validator import (
    validate_grounded_explanation,
)

PATH = Path(
    "artifacts/experiments/OPS-RAG-01/"
    "r06_grounded_comparison_results.json"
)

SOURCE_TYPE_BY_SOURCE_ID = {
    "policy_shipping_demo": "POLICY",
    "policy_reservation_shortage_demo": "POLICY",
    "incoming_stock_demo_tentative_001": "INCOMING_STOCK",
}

data = json.loads(
    PATH.read_text(encoding="utf-8")
)

passed = 0
failed = 0

for record in data["records"]:
    evidence = tuple(
        ExplanationEvidence(
            source_type=SOURCE_TYPE_BY_SOURCE_ID[item["source_id"]],
            source_id=item["source_id"],
            version=item["version"],
            excerpt="",
            as_of=None,
        )
        for item in record["model_output"]["citations"]
    )

    model_input = build_policy_grounded_explanation_input(
        question=record["question"],
        data_mode=record["data_mode"],
        evidence=evidence,
    )

    model_output = GroundedExplanationOutput(
        status=ExplanationStatus(
            record["model_output"]["status"]
        ),
        conclusion=record["model_output"]["conclusion"],
        used_facts=tuple(
            record["model_output"]["used_facts"]
        ),
        citations=tuple(
            ClaimCitation(
                source_id=item["source_id"],
                version=item["version"],
            )
            for item in record["model_output"]["citations"]
        ),
        next_check=record["model_output"]["next_check"],
        used_numeric_facts=tuple(
            NumericFact(
                field=item["field"],
                value=item["value"],
                unit=item["unit"],
            )
            for item in record["model_output"][
                "used_numeric_facts"
            ]
        ),
    )

    result = validate_grounded_explanation(
        model_input=model_input,
        model_output=model_output,
        condition=record["condition"],
    )

    print(
        record["evaluation_id"],
        "PASS" if result.valid else "FAIL",
        list(result.errors),
    )

    if result.valid:
        passed += 1
    else:
        failed += 1

print("REVALIDATED_PASS=", passed)
print("REVALIDATED_FAIL=", failed)

for record in data["records"]:
    evidence = tuple(
        ExplanationEvidence(
            source_type=SOURCE_TYPE_BY_SOURCE_ID[item["source_id"]],
            source_id=item["source_id"],
            version=item["version"],
            excerpt="",
            as_of=None,
        )
        for item in record["model_output"]["citations"]
    )

    model_input = build_policy_grounded_explanation_input(
        question=record["question"],
        data_mode=record["data_mode"],
        evidence=evidence,
    )

    model_output = GroundedExplanationOutput(
        status=ExplanationStatus(
            record["model_output"]["status"]
        ),
        conclusion=record["model_output"]["conclusion"],
        used_facts=tuple(
            record["model_output"]["used_facts"]
        ),
        citations=tuple(
            ClaimCitation(
                source_id=item["source_id"],
                version=item["version"],
            )
            for item in record["model_output"]["citations"]
        ),
        next_check=record["model_output"]["next_check"],
        used_numeric_facts=tuple(
            NumericFact(
                field=item["field"],
                value=item["value"],
                unit=item["unit"],
            )
            for item in record["model_output"]["used_numeric_facts"]
        ),
    )

    result = validate_grounded_explanation(
        model_input=model_input,
        model_output=model_output,
        condition=record["condition"],
    )

    record["validation"] = {
        "valid": result.valid,
        "errors": list(result.errors),
        "revalidated": True,
    }

data["counts"]["validator_passed"] = passed
data["counts"]["validator_failed"] = failed
data["validation_rechecked"] = True

PATH.write_text(
    json.dumps(
        data,
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)

print("COMPARISON_JSON_UPDATED=True")