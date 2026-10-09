from __future__ import annotations

import re
from dataclasses import dataclass

from ai.services.grounded_explanation import GroundedExplanationInput
from ai.services.grounded_explanation_output import GroundedExplanationOutput


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: tuple[str, ...]


def validate_grounded_explanation(
    *,
    model_input: GroundedExplanationInput,
    model_output: GroundedExplanationOutput,
    condition: str = "BASIC",
) -> ValidationResult:
    errors: list[str] = []

    normalized_condition = condition.upper()
    if normalized_condition not in {"BASIC", "CITATION"}:
        errors.append(f"UNKNOWN_CONDITION:{condition}")

    allowed_citations = {
        (item.source_id, item.version)
        for item in model_input.evidence
    }

    for citation in model_output.citations:
        if (citation.source_id, citation.version) not in allowed_citations:
            errors.append(
                f"CITATION_NOT_ALLOWED:{citation.source_id}:{citation.version}"
            )

    if (
        normalized_condition == "CITATION"
        and model_output.status.value == "ANSWER"
        and not model_output.citations
    ):
        errors.append("CITATION_REQUIRED")

    numeric_fields = {
        "required_qty": model_input.required_qty,
        "secured_qty": model_input.secured_qty,
        "expected_inventory": model_input.expected_inventory,
        "available_inventory": model_input.available_inventory,
        "reserved": model_input.reserved,
        "confirmed_incoming": model_input.confirmed_incoming,
        "shortage_qty": model_input.shortage_qty,
    }

    for fact in model_output.used_numeric_facts:
        if fact.field not in numeric_fields:
            errors.append(f"NUMERIC_FIELD_NOT_ALLOWED:{fact.field}")
            continue

        expected_value = numeric_fields[fact.field]

        if expected_value is None:
            errors.append(f"NUMERIC_FIELD_NULL:{fact.field}")
            continue

        if fact.value != expected_value:
            errors.append(
                f"NUMERIC_VALUE_MISMATCH:{fact.field}:{expected_value}:{fact.value}"
            )

        if fact.unit != "count":
            errors.append(
                f"NUMERIC_UNIT_NOT_ALLOWED:{fact.field}:{fact.unit}"
            )

    text = " ".join(
        (
            model_output.conclusion,
            *model_output.used_facts,
            model_output.next_check or "",
        )
    )

    mentioned_counts = {int(value) for value in re.findall(r"(\d+)\s*개", text)}
    declared_counts = {fact.value for fact in model_output.used_numeric_facts}
    if mentioned_counts - declared_counts:
        errors.append("NUMERIC_FACT_REQUIRED")

    shortage_mentions = {
        int(value)
        for value in re.findall(
            r"(\d+)\s*개(?:가|이)?\s*부족",
            text,
        )
    }

    if shortage_mentions:
        if model_input.shortage_qty is None:
            errors.append(
                "SHORTAGE_MENTIONED_WHEN_UNKNOWN"
            )
        elif shortage_mentions != {
            model_input.shortage_qty
        }:
            errors.append(
                "SHORTAGE_VALUE_MISMATCH"
            )

        declared_shortage = {
            fact.value
            for fact in model_output.used_numeric_facts
            if fact.field == "shortage_qty"
        }

        if (
            model_input.shortage_qty is not None
            and model_input.shortage_qty
            not in declared_shortage
        ):
            errors.append(
                "SHORTAGE_NUMERIC_FACT_REQUIRED"
            )
            
    tentative_confirmed_error = ("잠정입고는 확정입고로 봅니다" in text or "잠정입고를 확정입고로 봅니다" in text or "잠정입고를 확정입고로 간주" in text or "TENTATIVE는 CONFIRMED" in text)
    if tentative_confirmed_error:
        errors.append("TENTATIVE_CONFIRMED_SEMANTIC_ERROR")

    return ValidationResult(
        valid=not errors,
        errors=tuple(dict.fromkeys(errors)),
    )
