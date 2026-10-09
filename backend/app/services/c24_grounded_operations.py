from __future__ import annotations

from uuid import UUID
from openai import OpenAI

from sqlalchemy.orm import sessionmaker

from ai.services.grounded_explanation import (
    ExplanationEvidence,
    GroundedExplanationInput,
    build_product_grounded_explanation_input,
    build_reservation_grounded_explanation_input,
)
from ai.services.grounded_explanation_output import (
    ExplanationStatus,
)
from ai.services.grounded_explanation_provider import (
    GroundedProviderError,
    GroundedProviderTimeout,
    run_grounded_explanation,
)
from ai.services.grounded_explanation_validator import (
    validate_grounded_explanation,
)
from backend.app.core.config import Settings
from backend.app.services.demo_provider_quota import (
    DemoQuotaDenied,
    QuotaLimits,
    call_with_demo_quota,
)

from ai.services.grounded_explanation import (
    ExplanationEvidence,
    GroundedExplanationInput,
    build_reservation_grounded_explanation_input,
)
from backend.app.services.reservation_projection import (
    ReservationRiskProjection,
)


def build_reservation_explanation_input(
    *,
    question: str,
    projection: ReservationRiskProjection,
    evidence: tuple[ExplanationEvidence, ...],
    provider_call_allowed: bool,
) -> GroundedExplanationInput:
    """Translate authoritative Backend reservation facts without recalculation."""

    if projection.data_mode != "SYNTHETIC_DEMO":
        raise ValueError(
            "C24_SYNTHETIC_DEMO_REQUIRED"
        )

    if projection.source_classification != "SYNTHETIC_DEMO":
        raise ValueError(
            "C24_SOURCE_CLASSIFICATION_BLOCKED"
        )

    return build_reservation_grounded_explanation_input(
        question=question,
        sku_id=projection.sku_id,
        required_qty=projection.required_qty,
        secured_qty=projection.secured_qty,
        confirmed_incoming_qty=(
            projection.confirmed_incoming_qty
        ),
        shortage_qty=projection.shortage,
        calculation_status=projection.calculation_status,
        quality_status=projection.quality_status,
        data_mode=projection.data_mode,
        as_of=projection.as_of.isoformat(),
        evidence=evidence,
        provider_call_allowed=provider_call_allowed,
    )

def run_product_grounded_explanation(
    *,
    factory: sessionmaker,
    settings: Settings,
    tenant_id: UUID,
    demo_session_id: UUID,
    request_id: str,
    question: str,
    data_mode: str,
    evidence_id: str,
    evidence_version: str,
    evidence_excerpt: str,
):
    model_input = build_product_grounded_explanation_input(
        question=question,
        data_mode=data_mode,
        evidence=(
            ExplanationEvidence(
                source_type="PRODUCT",
                source_id=evidence_id,
                version=evidence_version,
                excerpt=evidence_excerpt,
                as_of=None,
            ),
        ),
    )

    limits = QuotaLimits.from_settings(settings)

    if settings.openai_api_key is None:
        raise DemoQuotaDenied(
            "C24_OPENAI_CREDENTIAL_REQUIRED"
        )

    client = OpenAI(
        api_key=settings.openai_api_key.get_secret_value(),
        max_retries=0,
    )

    result = call_with_demo_quota(
        lambda: run_grounded_explanation(
            model_input,
            condition="CITATION",
            client=client,
        ),
        factory=factory,
        tenant_id=tenant_id,
        session_id=demo_session_id,
        request_id=request_id,
        model=limits.priced_model,
        calls=1,
        input_tokens=settings.demo_quota_reserve_input_tokens,
        output_tokens=settings.demo_quota_reserve_output_tokens,
        limits=limits,
    )

    validation = validate_grounded_explanation(
        model_input=model_input,
        model_output=result.output,
        condition="CITATION",
    )

    if not validation.valid:
        raise ValueError(
            "C24_GROUNDED_OUTPUT_INVALID:"
            + ",".join(validation.errors)
        )

    return result

def run_reservation_grounded_explanation(
    *,
    factory: sessionmaker,
    settings: Settings,
    tenant_id: UUID,
    demo_session_id: UUID,
    request_id: str,
    question: str,
    projection: ReservationRiskProjection,
):
    evidence = (
        ExplanationEvidence(
            source_type="RESERVATION_RISK",
            source_id=(
                f"reservation-risk:"
                f"{projection.reservation_id}"
            ),
            version=projection.as_of.isoformat(),
            excerpt=(
                f"SKU: {projection.sku_id}\n"
                f"필요 수량: {projection.required_qty}\n"
                f"확보 수량: {projection.secured_qty}\n"
                f"확정 입고: "
                f"{projection.confirmed_incoming_qty}\n"
                f"부족 수량: {projection.shortage}\n"
                f"계산 상태: "
                f"{projection.calculation_status}\n"
                f"배송 위험: {projection.delivery_risk}"
            ),
            as_of=projection.as_of.isoformat(),
        ),
    )

    model_input = build_reservation_explanation_input(
        question=question,
        projection=projection,
        evidence=evidence,
        provider_call_allowed=True,
    )

    limits = QuotaLimits.from_settings(settings)

    if settings.openai_api_key is None:
        raise DemoQuotaDenied(
            "C24_OPENAI_CREDENTIAL_REQUIRED"
        )

    client = OpenAI(
        api_key=(
            settings.openai_api_key.get_secret_value()
        ),
        max_retries=0,
    )

    result = call_with_demo_quota(
        lambda: run_grounded_explanation(
            model_input,
            condition="CITATION",
            client=client,
        ),
        factory=factory,
        tenant_id=tenant_id,
        session_id=demo_session_id,
        request_id=request_id,
        model=limits.priced_model,
        calls=1,
        input_tokens=(
            settings.demo_quota_reserve_input_tokens
        ),
        output_tokens=(
            settings.demo_quota_reserve_output_tokens
        ),
        limits=limits,
    )

    validation = validate_grounded_explanation(
        model_input=model_input,
        model_output=result.output,
        condition="CITATION",
    )

    if not validation.valid:
        raise ValueError(
            "C24_RESERVATION_OUTPUT_INVALID:"
            + ",".join(validation.errors)
        )

    return result