from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from contracts.ai_sku_aggregate import AiSkuAggregate


@dataclass(frozen=True)
class ExplanationEvidence:
    source_type: str
    source_id: str
    version: str
    excerpt: str
    as_of: str | None


@dataclass(frozen=True)
class GroundedExplanationInput:
    question: str
    sku_id: str | None
    product_no: int | None
    required_qty: int | None
    secured_qty: int | None
    expected_inventory: int | None
    available_inventory: int | None
    reserved: int | None
    confirmed_incoming: int | None
    shortage_qty: int | None
    calculation_status: str | None
    quality_status: str | None
    data_mode: str
    as_of: str | None
    evidence: tuple[ExplanationEvidence, ...]
    
    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["evidence"] = [
            asdict(item)
            for item in self.evidence
        ]
        return payload


def build_grounded_explanation_input(
    *,
    question: str,
    aggregate: AiSkuAggregate,
    evidence: tuple[ExplanationEvidence, ...],
    provider_call_allowed: bool,
    shortage_qty: int | None,
    secured_qty: int | None = None,
) -> GroundedExplanationInput:
    if not question.strip():
        raise ValueError("question must not be empty")

    if not provider_call_allowed:
        raise ValueError(
            "provider call blocked by source suitability"
        )

    if not evidence:
        raise ValueError(
            "grounded explanation requires evidence"
        )

    return GroundedExplanationInput(
        question=question.strip(),
        sku_id=aggregate.sku_id,
        product_no=aggregate.product_no,
        required_qty=aggregate.required_qty,
        secured_qty=secured_qty,
        expected_inventory=aggregate.expected_inventory,
        available_inventory=aggregate.available_inventory,
        reserved=aggregate.reserved,
        confirmed_incoming=aggregate.confirmed_incoming,
        shortage_qty=shortage_qty,
        calculation_status=aggregate.calculation_status,
        quality_status=aggregate.quality_status,
        data_mode=aggregate.data_mode,
        as_of=aggregate.as_of.isoformat(),
        evidence=evidence,
    )

def build_reservation_grounded_explanation_input(
    *,
    question: str,
    sku_id: str,
    required_qty: int,
    secured_qty: int | None,
    confirmed_incoming_qty: int | None,
    shortage_qty: int | None,
    calculation_status: str,
    quality_status: str,
    data_mode: str,
    as_of: str,
    evidence: tuple[ExplanationEvidence, ...],
    provider_call_allowed: bool,
) -> GroundedExplanationInput:
    if not question.strip():
        raise ValueError("question must not be empty")

    if not provider_call_allowed:
        raise ValueError(
            "provider call blocked by source suitability"
        )

    if not evidence:
        raise ValueError(
            "grounded explanation requires evidence"
        )

    return GroundedExplanationInput(
        question=question.strip(),
        sku_id=sku_id,
        product_no=None,
        required_qty=required_qty,
        secured_qty=secured_qty,
        expected_inventory=None,
        available_inventory=None,
        reserved=None,
        confirmed_incoming=confirmed_incoming_qty,
        shortage_qty=shortage_qty,
        calculation_status=calculation_status,
        quality_status=quality_status,
        data_mode=data_mode,
        as_of=as_of,
        evidence=evidence,
    )

def build_product_grounded_explanation_input(
    *,
    question: str,
    data_mode: str,
    evidence: tuple[ExplanationEvidence, ...],
) -> GroundedExplanationInput:
    if not question.strip():
        raise ValueError("question must not be empty")

    if not data_mode.strip():
        raise ValueError("data_mode must not be empty")

    if not evidence:
        raise ValueError(
            "grounded explanation requires evidence"
        )

    return GroundedExplanationInput(
        question=question.strip(),
        sku_id=None,
        product_no=None,
        required_qty=None,
        secured_qty=None,
        expected_inventory=None,
        available_inventory=None,
        reserved=None,
        confirmed_incoming=None,
        shortage_qty=None,
        calculation_status=None,
        quality_status=None,
        data_mode=data_mode.strip(),
        as_of=None,
        evidence=evidence,
    )

def build_policy_grounded_explanation_input(
    *,
    question: str,
    data_mode: str,
    evidence: tuple[ExplanationEvidence, ...],
) -> GroundedExplanationInput:
    if not question.strip():
        raise ValueError("question must not be empty")
    if not data_mode.strip():
        raise ValueError("data_mode must not be empty")
    if not evidence:
        raise ValueError("grounded explanation requires evidence")

    return GroundedExplanationInput(
        question=question.strip(),
        sku_id=None,
        product_no=None,
        required_qty=None,
        secured_qty=None,
        expected_inventory=None,
        available_inventory=None,
        reserved=None,
        confirmed_incoming=None,
        shortage_qty=None,
        calculation_status=None,
        quality_status=None,
        data_mode=data_mode.strip(),
        as_of=None,
        evidence=evidence,
    )

