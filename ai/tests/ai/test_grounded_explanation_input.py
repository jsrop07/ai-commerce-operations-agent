from datetime import datetime, timezone

import pytest

from ai.services.grounded_explanation import (
    ExplanationEvidence,
    build_grounded_explanation_input,
)
from contracts.ai_sku_aggregate import AiSkuAggregate


def _aggregate() -> AiSkuAggregate:
    return AiSkuAggregate(
        sku_id="DEMO-SKU-001",
        product_no=1,
        required_qty=5,
        expected_inventory=None,
        available_inventory=1,
        reserved=1,
        confirmed_incoming=2,
        calculation_status="READY",
        quality_status="VERIFIED",
        data_mode="SYNTHETIC_DEMO",
        as_of=datetime(
            2026, 9, 26, 4, 0,
            tzinfo=timezone.utc,
        ),
        evidence_ids=("policy_reservation_shortage_demo",),
    )


def _evidence() -> tuple[ExplanationEvidence, ...]:
    return (
        ExplanationEvidence(
            source_type="POLICY",
            source_id="policy_reservation_shortage_demo",
            version="v1",
            excerpt="부족수량은 Backend 계산 결과를 기준으로 사용합니다.",
            as_of=None,
        ),
    )


def test_builds_allowlisted_payload() -> None:
    payload = build_grounded_explanation_input(
        question="예약 부족 판단을 설명해줘",
        aggregate=_aggregate(),
        evidence=_evidence(),
        provider_call_allowed=True,
    ).to_dict()

    assert payload["sku_id"] == "DEMO-SKU-001"
    assert payload["required_qty"] == 5
    assert payload["expected_inventory"] is None
    assert payload["confirmed_incoming"] == 2

    forbidden = {
        "order_id",
        "order_item_id",
        "customer_id",
        "shipping",
        "payment",
        "inquiry",
        "free_memo",
        "affected_order_ids",
        "score",
        "confidence",
    }

    assert forbidden.isdisjoint(payload.keys())
    assert forbidden.isdisjoint(
        payload["evidence"][0].keys()
    )


def test_hold_cannot_build_provider_payload() -> None:
    with pytest.raises(
        ValueError,
        match="provider call blocked",
    ):
        build_grounded_explanation_input(
            question="지금 판매 가능한 재고가 있어?",
            aggregate=_aggregate(),
            evidence=_evidence(),
            provider_call_allowed=False,
        )


def test_evidence_is_required() -> None:
    with pytest.raises(
        ValueError,
        match="requires evidence",
    ):
        build_grounded_explanation_input(
            question="예약 부족 판단을 설명해줘",
            aggregate=_aggregate(),
            evidence=(),
            provider_call_allowed=True,
        )
