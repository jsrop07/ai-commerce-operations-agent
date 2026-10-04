import pytest

from ai.evaluation.r09_conversation_contract import (
    AiAnswerContract,
    ContextTransition,
    ConversationContext,
    ConversationStatus,
    next_context_revision,
    should_accept_response,
    should_requery_current_source,
    validate_ai_safe_context,
    validate_answer_contract,
)


def test_related_target_increments_context_revision():
    assert (
        next_context_revision(
            3,
            ContextTransition.SAME_PROBLEM_RELATED_TARGET,
        )
        == 4
    )


def test_unrelated_target_starts_new_revision():
    assert (
        next_context_revision(
            3,
            ContextTransition.UNRELATED_TARGET,
        )
        == 1
    )


def test_new_problem_starts_new_revision():
    assert (
        next_context_revision(
            3,
            ContextTransition.NEW_PROBLEM,
        )
        == 1
    )


def test_late_response_is_rejected():
    assert should_accept_response(3, 4) is False


def test_current_response_is_accepted():
    assert should_accept_response(4, 4) is True


def test_safe_context_passes():
    context = ConversationContext(
        conversation_id="conv-demo-001",
        turn_id="turn-demo-001",
        context_revision=1,
        canonical_intent="DELAY_IMPACT",
        analysis_kind="RELATION_DOCUMENT",
        target_type="INCOMING_STOCK",
        target_id="incoming-demo-001",
        question="이 입고 지연이 어떤 Task에 영향을 주나?",
        evidence_ids=("ev-demo-001",),
        status=ConversationStatus.ANSWER,
    )

    validate_ai_safe_context(context)


def test_order_linked_context_is_rejected():
    context = ConversationContext(
        conversation_id="conv-demo-001",
        turn_id="turn-demo-002",
        context_revision=2,
        canonical_intent="DELAY_IMPACT",
        analysis_kind=None,
        target_type="ORDER",
        target_id="order_id:123",
        question="이 주문을 확인해줘",
    )

    with pytest.raises(ValueError):
        validate_ai_safe_context(context)

def test_context_revision_zero_is_invalid():
    with pytest.raises(ValueError):
        next_context_revision(
            0,
            ContextTransition.SAME_PROBLEM_RELATED_TARGET,
        )


def test_stale_evidence_requires_requery():
    assert (
        should_requery_current_source(
            stale=True,
        )
        is True
    )


def test_unknown_source_as_of_requires_requery():
    assert (
        should_requery_current_source(
            source_as_of_unknown=True,
        )
        is True
    )


def test_history_alone_does_not_force_requery():
    assert (
        should_requery_current_source()
        is False
    )


def test_answer_requires_evidence():
    answer = AiAnswerContract(
        conclusion="입고 지연 영향이 있습니다.",
        key_facts=("+72h",),
        evidence_ids=(),
        next_checks=("현재 입고 상태 재조회",),
        status=ConversationStatus.ANSWER,
    )

    with pytest.raises(ValueError):
        validate_answer_contract(answer)


def test_grounded_answer_contract_passes():
    answer = AiAnswerContract(
        conclusion="입고 지연 영향이 있습니다.",
        key_facts=("+72h",),
        evidence_ids=("ev-demo-001",),
        next_checks=("현재 입고 상태 재조회",),
        status=ConversationStatus.ANSWER,
    )

    validate_answer_contract(answer)

def test_intent_and_analysis_kind_are_separate_fields():
    context = ConversationContext(
        conversation_id="conv-demo-001",
        turn_id="turn-demo-003",
        context_revision=2,
        canonical_intent="IMPACT_ANALYSIS",
        analysis_kind="RELATION_DOCUMENT",
        target_type="INCOMING_STOCK",
        target_id="incoming-demo-001",
        question="이 입고 지연 영향 범위를 확인해줘.",
        status=ConversationStatus.HOLD,
    )

    assert context.canonical_intent == "IMPACT_ANALYSIS"
    assert context.analysis_kind == "RELATION_DOCUMENT"