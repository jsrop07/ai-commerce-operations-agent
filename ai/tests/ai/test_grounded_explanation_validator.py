from datetime import datetime, timezone

from ai.services.grounded_explanation import ExplanationEvidence, GroundedExplanationInput
from ai.services.grounded_explanation_output import ClaimCitation, ExplanationStatus, GroundedExplanationOutput, NumericFact
from ai.services.grounded_explanation_validator import validate_grounded_explanation

def _input() -> GroundedExplanationInput:
    return GroundedExplanationInput(
    question="확정입고 2개는 어떻게 취급해?",
    sku_id="DEMO-SKU-001",
    product_no=1,
    required_qty=5,
    secured_qty=1,
    expected_inventory=None,
    available_inventory=1,
    reserved=1,
    confirmed_incoming=2,
    shortage_qty=2,
    calculation_status="READY",
    quality_status="VERIFIED",
    data_mode="SYNTHETIC_DEMO",
    as_of=datetime(2026, 9, 26, 4, 0, tzinfo=timezone.utc).isoformat(),
    evidence=(
        ExplanationEvidence(
            source_type="POLICY",
            source_id="policy_reservation_shortage_demo",
            version="v1",
            excerpt="확정입고 수량은 확보수량에 포함할 수 있습니다.",
            as_of=None,
        ),
    ),
)

def test_valid_output_passes() -> None:
    result = validate_grounded_explanation(model_input=_input(), model_output=GroundedExplanationOutput(status=ExplanationStatus.ANSWER, conclusion="확정입고 2개는 확보수량에 포함할 수 있습니다.", used_facts=("확정입고 2개",), citations=(ClaimCitation(source_id="policy_reservation_shortage_demo", version="v1"),), next_check=None, used_numeric_facts=(NumericFact(field="confirmed_incoming", value=2),)))
    assert result.valid is True
    assert result.errors == ()

def test_unapproved_citation_is_rejected() -> None:
    result = validate_grounded_explanation(model_input=_input(), model_output=GroundedExplanationOutput(status=ExplanationStatus.ANSWER, conclusion="확정입고 2개를 설명합니다.", used_facts=("확정입고 2개",), citations=(ClaimCitation(source_id="unknown_source", version="v9"),), next_check=None))
    assert result.valid is False
    assert any(x.startswith("CITATION_NOT_ALLOWED") for x in result.errors)

def test_new_number_is_rejected() -> None:
    result = validate_grounded_explanation(model_input=_input(), model_output=GroundedExplanationOutput(status=ExplanationStatus.ANSWER, conclusion="확정입고 수량을 설명합니다.", used_facts=(), citations=(ClaimCitation(source_id="policy_reservation_shortage_demo", version="v1"),), next_check=None, used_numeric_facts=(NumericFact(field="confirmed_incoming", value=3),)))
    assert result.valid is False
    assert "NUMERIC_VALUE_MISMATCH:confirmed_incoming:2:3" in result.errors

def test_null_as_zero_is_rejected() -> None:
    result = validate_grounded_explanation(model_input=_input(), model_output=GroundedExplanationOutput(status=ExplanationStatus.ANSWER, conclusion="예상재고를 설명합니다.", used_facts=(), citations=(ClaimCitation(source_id="policy_reservation_shortage_demo", version="v1"),), next_check=None, used_numeric_facts=(NumericFact(field="expected_inventory", value=0),)))
    assert result.valid is False
    assert "NUMERIC_FIELD_NULL:expected_inventory" in result.errors

def test_tentative_confirmed_confusion_is_rejected() -> None:
    result = validate_grounded_explanation(model_input=_input(), model_output=GroundedExplanationOutput(status=ExplanationStatus.ANSWER, conclusion="잠정입고는 확정입고로 봅니다.", used_facts=(), citations=(ClaimCitation(source_id="policy_reservation_shortage_demo", version="v1"),), next_check=None))
    assert result.valid is False
    assert "TENTATIVE_CONFIRMED_SEMANTIC_ERROR" in result.errors
