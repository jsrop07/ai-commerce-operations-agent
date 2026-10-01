from datetime import datetime, timezone

from ai.services.grounded_explanation import ExplanationEvidence, GroundedExplanationInput
from ai.services.grounded_explanation_output import ClaimCitation, ExplanationStatus, GroundedExplanationOutput
from ai.services.grounded_explanation_validator import validate_grounded_explanation


def _input() -> GroundedExplanationInput:
    return GroundedExplanationInput(question="확정입고 수량은?", sku_id="DEMO-SKU-001", product_no=1, required_qty=5, expected_inventory=None, available_inventory=1, reserved=1, confirmed_incoming=2, calculation_status="READY", quality_status="VERIFIED", data_mode="SYNTHETIC_DEMO", as_of=datetime(2026,9,26,4,0,tzinfo=timezone.utc).isoformat(), evidence=(ExplanationEvidence(source_type="POLICY", source_id="policy_reservation_shortage_demo", version="v1", excerpt="확정입고 관련 정책", as_of=None),))


def test_numeric_text_without_structured_fact_is_rejected() -> None:
    result = validate_grounded_explanation(model_input=_input(), model_output=GroundedExplanationOutput(status=ExplanationStatus.ANSWER, conclusion="확정입고는 3개입니다.", used_facts=(), citations=(ClaimCitation(source_id="policy_reservation_shortage_demo", version="v1"),), next_check=None), condition="CITATION")
    assert result.valid is False
    assert "NUMERIC_FACT_REQUIRED" in result.errors
