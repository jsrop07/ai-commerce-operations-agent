from __future__ import annotations

from ai.services.grounded_explanation_output import (
    ClaimCitation,
    ExplanationStatus,
    GroundedExplanationOutput,
    NumericFact,
)
from ai.services.grounded_explanation_provider import (
    GroundedProviderResult,
    ProviderReceipt,
    ProviderUsage,
)
from ai.services.reservation_replan_assist import (
    ReservationReplanAssistContractError,
    build_reservation_replan_model_input,
    run_reservation_replan_ai_assist,
)


def make_state() -> dict:
    return {
        "source_as_of": "2026-10-05T10:00:00+09:00",
        "entities": {
            "sku_id": "DEMO-SKU-001",
        },
        "rule_results": {
            "required_qty": 5,
            "secured_qty": 1,
            "confirmed_incoming_qty": 2,
            "tentative_incoming_qty": 0,
            "shortage": 2,
            "incoming_delay_days": 3,
            "calculation_status": "CONFIRMED",
            "replan_required": True,
            "requires_ai_assist": True,
        },
        "retrieval_result": {
            "data_mode": "SYNTHETIC_DEMO",
            "quality_status": "APPROVED",
            "citations": [
                {
                    "source_type": "POLICY",
                    "source_id": "policy-demo-001",
                    "version": "v1",
                    "excerpt": (
                        "예약 재계획은 확정된 수량과 "
                        "승인된 근거만 사용한다."
                    ),
                    "as_of": None,
                }
            ],
        },
    }


def make_provider_result(
    *,
    required_qty: int = 5,
) -> GroundedProviderResult:
    output = GroundedExplanationOutput(
        status=ExplanationStatus.ANSWER,
        conclusion=(
            f"필요수량 {required_qty}개 기준으로 "
            "사람 검토가 필요합니다."
        ),
        used_facts=(
            "Backend 확정 수치와 승인 근거만 사용함",
        ),
        used_numeric_facts=(
            NumericFact(
                field="required_qty",
                value=required_qty,
                unit="count",
            ),
        ),
        citations=(
            ClaimCitation(
                source_id="policy-demo-001",
                version="v1",
            ),
        ),
        next_check="사람 검토 후 승인 여부 확인",
    )

    return GroundedProviderResult(
        output=output,
        model_used=True,
        receipt=ProviderReceipt(
            provider="openai",
            model="gpt-5.6-luna",
            response_id="resp_r10_fake_001",
            latency_ms=12.5,
            attempts=1,
            retries=0,
            usage=ProviderUsage(
                input_tokens=100,
                cached_input_tokens=0,
                output_tokens=30,
            ),
        ),
    )


def test_build_input_preserves_only_matching_numeric_meanings():
    model_input = build_reservation_replan_model_input(
        make_state()
    )

    assert model_input.required_qty == 5
    assert model_input.confirmed_incoming == 2

    assert model_input.expected_inventory is None
    assert model_input.available_inventory is None
    assert model_input.reserved is None

    assert model_input.data_mode == "SYNTHETIC_DEMO"
    assert len(model_input.evidence) == 1


def test_missing_safe_citations_is_blocked():
    state = make_state()
    state["retrieval_result"]["citations"] = []

    try:
        build_reservation_replan_model_input(state)
    except ReservationReplanAssistContractError as exc:
        assert "citations" in str(exc)
    else:
        raise AssertionError(
            "expected contract error"
        )


def test_assist_success_is_answer_with_receipt():
    calls = {"count": 0}

    def fake_provider(
        model_input,
        *,
        condition,
        client,
    ):
        calls["count"] += 1
        assert condition == "CITATION"
        assert model_input.required_qty == 5
        return make_provider_result()

    result = run_reservation_replan_ai_assist(
        make_state(),
        provider_runner=fake_provider,
    )

    assert calls["count"] == 1
    assert result["status"] == "ANSWER"
    assert result["used"] is True
    assert result["runtime_kind"] == "REAL_MODEL"
    assert (
        result["reason"]
        == "R10_AI_ASSIST_VALIDATED"
    )
    assert (
        result["receipt"]["response_id"]
        == "resp_r10_fake_001"
    )


def test_numeric_mismatch_is_held_after_validation():
    def fake_provider(
        model_input,
        *,
        condition,
        client,
    ):
        return make_provider_result(
            required_qty=999
        )

    result = run_reservation_replan_ai_assist(
        make_state(),
        provider_runner=fake_provider,
    )

    assert result["status"] == "HOLD"
    assert (
        result["reason"]
        == "MODEL_OUTPUT_VALIDATION_FAILED"
    )
    assert any(
        error.startswith(
            "NUMERIC_VALUE_MISMATCH:required_qty"
        )
        for error in result["validation_errors"]
    )


def test_requires_ai_assist_false_is_rejected():
    state = make_state()
    state["rule_results"]["requires_ai_assist"] = False

    try:
        build_reservation_replan_model_input(state)
    except ReservationReplanAssistContractError as exc:
        assert "requires_ai_assist" in str(exc)
    else:
        raise AssertionError(
            "expected contract error"
        )
