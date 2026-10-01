from ai.services.grounded_explanation import ExplanationEvidence, GroundedExplanationInput
from ai.services.grounded_explanation_output import ClaimCitation, ExplanationStatus, GroundedExplanationOutput
from ai.services.grounded_explanation_validator import validate_grounded_explanation


def _input() -> GroundedExplanationInput:
    return GroundedExplanationInput(question="정책상 어떻게 처리해?", sku_id="DEMO-SKU-001", product_no=1, required_qty=None, expected_inventory=None, available_inventory=None, reserved=None, confirmed_incoming=None, calculation_status="UNKNOWN", quality_status="VERIFIED", data_mode="SYNTHETIC_DEMO", as_of=None, evidence=(ExplanationEvidence(source_type="POLICY", source_id="policy_reservation_shortage_demo", version="v1", excerpt="정책 근거", as_of=None),))


def test_basic_answer_without_citation_passes() -> None:
    result = validate_grounded_explanation(model_input=_input(), model_output=GroundedExplanationOutput(status=ExplanationStatus.ANSWER, conclusion="정책 근거에 따라 처리합니다.", used_facts=(), citations=(), next_check=None), condition="BASIC")
    assert result.valid is True
    assert result.errors == ()


def test_citation_answer_without_citation_fails() -> None:
    result = validate_grounded_explanation(model_input=_input(), model_output=GroundedExplanationOutput(status=ExplanationStatus.ANSWER, conclusion="정책 근거에 따라 처리합니다.", used_facts=(), citations=(), next_check=None), condition="CITATION")
    assert result.valid is False
    assert "CITATION_REQUIRED" in result.errors


def test_citation_answer_with_allowed_citation_passes() -> None:
    result = validate_grounded_explanation(model_input=_input(), model_output=GroundedExplanationOutput(status=ExplanationStatus.ANSWER, conclusion="정책 근거에 따라 처리합니다.", used_facts=(), citations=(ClaimCitation(source_id="policy_reservation_shortage_demo", version="v1"),), next_check=None), condition="CITATION")
    assert result.valid is True
    assert result.errors == ()
