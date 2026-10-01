import pytest

from ai.services.grounded_explanation_output import ClaimCitation, ExplanationStatus, GroundedExplanationOutput


def test_answer_can_omit_citation() -> None:
    output = GroundedExplanationOutput(status=ExplanationStatus.ANSWER, conclusion="Backend-verified facts support this answer.", used_facts=("confirmed incoming 2",), citations=(), next_check=None)
    assert output.status == ExplanationStatus.ANSWER
    assert output.citations == ()


def test_answer_can_include_citation() -> None:
    output = GroundedExplanationOutput(status=ExplanationStatus.ANSWER, conclusion="Backend-verified facts support this answer.", used_facts=("confirmed incoming 2",), citations=(ClaimCitation(source_id="policy_reservation_shortage_demo", version="v1"),), next_check=None)
    assert len(output.citations) == 1


def test_hold_cannot_present_answer_facts() -> None:
    with pytest.raises(ValueError, match="HOLD must not present"):
        GroundedExplanationOutput(status=ExplanationStatus.HOLD, conclusion="Evidence is insufficient.", used_facts=("available inventory 1",), citations=(), next_check="Verify fresh evidence.")
