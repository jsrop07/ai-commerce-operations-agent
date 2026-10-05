from __future__ import annotations

from dataclasses import asdict
from typing import Any, Callable, Mapping

from ai.services.grounded_explanation import (
    ExplanationEvidence,
    GroundedExplanationInput,
)
from ai.services.grounded_explanation_provider import (
    GroundedProviderResult,
    run_grounded_explanation,
)
from ai.services.grounded_explanation_validator import (
    validate_grounded_explanation,
)


R10_ASSIST_QUESTION = (
    "예약 재계획 검토를 위해 제공된 근거와 Backend 확정 수치만 설명하세요. "
    "수량, 날짜, 관계를 재계산하거나 새로 만들지 마세요. "
    "확실하지 않은 내용은 추정하지 말고 보류하세요."
)


class ReservationReplanAssistContractError(ValueError):
    "R10 Agent assist 입력 계약 위반."


def _require_non_empty_text(
    payload: Mapping[str, Any],
    key: str,
) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ReservationReplanAssistContractError(
            f"missing or invalid {key}"
        )
    return value.strip()


def _optional_int(value: Any, *, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ReservationReplanAssistContractError(
            f"{field} must be int or None"
        )
    return value


def _build_evidence(
    retrieval_result: Mapping[str, Any],
) -> tuple[ExplanationEvidence, ...]:
    raw_citations = retrieval_result.get("citations")
    if not isinstance(raw_citations, list) or not raw_citations:
        raise ReservationReplanAssistContractError(
            "retrieval_result.citations is required"
        )

    evidence: list[ExplanationEvidence] = []

    for index, raw in enumerate(raw_citations):
        if not isinstance(raw, Mapping):
            raise ReservationReplanAssistContractError(
                f"citation[{index}] must be an object"
            )

        source_type = _require_non_empty_text(
            raw,
            "source_type",
        )
        source_id = _require_non_empty_text(
            raw,
            "source_id",
        )
        version = _require_non_empty_text(
            raw,
            "version",
        )
        excerpt = _require_non_empty_text(
            raw,
            "excerpt",
        )

        as_of = raw.get("as_of")
        if as_of is not None:
            if not isinstance(as_of, str) or not as_of.strip():
                raise ReservationReplanAssistContractError(
                    f"citation[{index}].as_of must be text or None"
                )
            as_of = as_of.strip()

        evidence.append(
            ExplanationEvidence(
                source_type=source_type,
                source_id=source_id,
                version=version,
                excerpt=excerpt,
                as_of=as_of,
            )
        )

    return tuple(evidence)


def build_reservation_replan_model_input(
    state: Mapping[str, Any],
) -> GroundedExplanationInput:
    rule_results = state.get("rule_results")
    retrieval_result = state.get("retrieval_result")
    entities = state.get("entities")

    if not isinstance(rule_results, Mapping):
        raise ReservationReplanAssistContractError(
            "rule_results is required"
        )
    if not isinstance(retrieval_result, Mapping):
        raise ReservationReplanAssistContractError(
            "retrieval_result is required"
        )
    if not isinstance(entities, Mapping):
        raise ReservationReplanAssistContractError(
            "entities is required"
        )

    if not bool(rule_results.get("requires_ai_assist", False)):
        raise ReservationReplanAssistContractError(
            "requires_ai_assist must be true"
        )

    data_mode = _require_non_empty_text(
        retrieval_result,
        "data_mode",
    )

    source_as_of = state.get("source_as_of")
    if source_as_of is not None:
        if (
            not isinstance(source_as_of, str)
            or not source_as_of.strip()
        ):
            raise ReservationReplanAssistContractError(
                "source_as_of must be text or None"
            )
        source_as_of = source_as_of.strip()

    sku_id = entities.get("sku_id")
    if sku_id is not None:
        if not isinstance(sku_id, str) or not sku_id.strip():
            raise ReservationReplanAssistContractError(
                "entities.sku_id must be text or None"
            )
        sku_id = sku_id.strip()

    product_no = _optional_int(
        entities.get("product_no"),
        field="entities.product_no",
    )

    # R10에서는 C03 수치의 의미를 바꾸지 않는다.
    # GroundedExplanationInput에 의미가 정확히 대응되는 값만 전달한다.
    required_qty = _optional_int(
        rule_results.get("required_qty"),
        field="rule_results.required_qty",
    )
    confirmed_incoming = _optional_int(
        rule_results.get("confirmed_incoming_qty"),
        field="rule_results.confirmed_incoming_qty",
    )

    calculation_status = rule_results.get(
        "calculation_status"
    )
    if calculation_status is not None:
        if (
            not isinstance(calculation_status, str)
            or not calculation_status.strip()
        ):
            raise ReservationReplanAssistContractError(
                "rule_results.calculation_status "
                "must be text or None"
            )
        calculation_status = calculation_status.strip()

    quality_status = retrieval_result.get("quality_status")
    if quality_status is not None:
        if (
            not isinstance(quality_status, str)
            or not quality_status.strip()
        ):
            raise ReservationReplanAssistContractError(
                "retrieval_result.quality_status "
                "must be text or None"
            )
        quality_status = quality_status.strip()

    return GroundedExplanationInput(
        question=R10_ASSIST_QUESTION,
        sku_id=sku_id,
        product_no=product_no,
        required_qty=required_qty,
        expected_inventory=None,
        available_inventory=None,
        reserved=None,
        confirmed_incoming=confirmed_incoming,
        calculation_status=calculation_status,
        quality_status=quality_status,
        data_mode=data_mode,
        as_of=source_as_of,
        evidence=_build_evidence(retrieval_result),
    )


def _serialize_output(
    result: GroundedProviderResult,
) -> dict[str, Any]:
    output = result.output

    return {
        "status": output.status.value,
        "conclusion": output.conclusion,
        "used_facts": list(output.used_facts),
        "used_numeric_facts": [
            asdict(item)
            for item in output.used_numeric_facts
        ],
        "citations": [
            asdict(item)
            for item in output.citations
        ],
        "next_check": output.next_check,
    }


def _serialize_receipt(
    result: GroundedProviderResult,
) -> dict[str, Any]:
    receipt = result.receipt

    return {
        "provider": receipt.provider,
        "model": receipt.model,
        "response_id": receipt.response_id,
        "latency_ms": receipt.latency_ms,
        "attempts": receipt.attempts,
        "retries": receipt.retries,
        "usage": asdict(receipt.usage),
    }


def run_reservation_replan_ai_assist(
    state: Mapping[str, Any],
    *,
    client: Any = None,
    provider_runner: Callable[..., GroundedProviderResult] = (
        run_grounded_explanation
    ),
) -> dict[str, Any]:
    model_input = build_reservation_replan_model_input(
        state
    )

    provider_result = provider_runner(
        model_input,
        condition="CITATION",
        client=client,
    )

    validation = validate_grounded_explanation(
        model_input=model_input,
        model_output=provider_result.output,
        condition="CITATION",
    )

    if not validation.valid:
        return {
            "status": "HOLD",
            "used": bool(provider_result.model_used),
            "runtime_kind": "REAL_MODEL",
            "reason": "MODEL_OUTPUT_VALIDATION_FAILED",
            "validation_errors": list(
                validation.errors
            ),
            "output": _serialize_output(
                provider_result
            ),
            "receipt": _serialize_receipt(
                provider_result
            ),
        }

    if provider_result.output.status.value != "ANSWER":
        return {
            "status": "HOLD",
            "used": bool(provider_result.model_used),
            "runtime_kind": "REAL_MODEL",
            "reason": "MODEL_RETURNED_HOLD",
            "validation_errors": [],
            "output": _serialize_output(
                provider_result
            ),
            "receipt": _serialize_receipt(
                provider_result
            ),
        }

    return {
        "status": "ANSWER",
        "used": bool(provider_result.model_used),
        "runtime_kind": "REAL_MODEL",
        "reason": "R10_AI_ASSIST_VALIDATED",
        "validation_errors": [],
        "output": _serialize_output(
            provider_result
        ),
        "receipt": _serialize_receipt(
            provider_result
        ),
    }
