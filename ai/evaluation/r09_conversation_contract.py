from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


# AI-side answer/evaluation state only.
# Backend MessageV2.response_status의 최종 enum/string contract가 아니다.
# 실제 message response_status는 Backend 통합 계약을 따른다.
class ConversationStatus(str, Enum):
    ANSWER = "ANSWER"
    NO_EDGE = "NO_EDGE"
    HOLD = "HOLD"
    ERROR = "ERROR"


class ContextTransition(str, Enum):
    SAME_PROBLEM_RELATED_TARGET = "SAME_PROBLEM_RELATED_TARGET"
    UNRELATED_TARGET = "UNRELATED_TARGET"
    NEW_PROBLEM = "NEW_PROBLEM"


@dataclass(frozen=True)
class ConversationContext:
    conversation_id: str
    turn_id: str
    context_revision: int

    canonical_intent: str
    analysis_kind: str | None

    target_type: str
    target_id: str

    question: str

    evidence_ids: tuple[str, ...] = ()
    source_versions: tuple[str, ...] = ()

    as_of: str | None = None

    status: ConversationStatus = ConversationStatus.HOLD
    hold_reason: str | None = None
    stale: bool = False

def next_context_revision(
    current_revision: int,
    transition: ContextTransition,
) -> int:
    """
    같은 conversation 안에서 관련 context로 이동하면 revision을 증가시킨다.

    UNRELATED_TARGET / NEW_PROBLEM은 새 conversation을 의미하므로
    그 새 conversation의 최초 revision은 Backend DB 제약과 맞춰 1이다.
    """

    if current_revision < 1:
        raise ValueError(
            "context revision must be a positive integer"
        )

    if transition == ContextTransition.SAME_PROBLEM_RELATED_TARGET:
        return current_revision + 1

    if transition in {
        ContextTransition.UNRELATED_TARGET,
        ContextTransition.NEW_PROBLEM,
    }:
        return 1

    raise ValueError(f"unsupported transition: {transition}")

class EvidenceRefreshDecision(str, Enum):
    REUSE_HISTORY_CONTEXT_ONLY = "REUSE_HISTORY_CONTEXT_ONLY"
    REQUERY_CURRENT_SOURCE = "REQUERY_CURRENT_SOURCE"


def should_requery_current_source(
    *,
    source_freshness_changed: bool = False,
    source_as_of_unknown: bool = False,
    context_changed: bool = False,
    stale: bool = False,
    mutable_operational_data: bool = False,
) -> bool:
    """
    Conversation history는 과거 상호작용 문맥으로만 사용한다.
    현재 사실/evidence가 필요하면 조건에 따라 source를 다시 조회한다.
    """
    return any(
        (
            source_freshness_changed,
            source_as_of_unknown,
            context_changed,
            stale,
            mutable_operational_data,
        )
    )

def should_accept_response(
    request_revision: int,
    current_revision: int,
) -> bool:
    """
    늦게 도착한 이전 context 결과가 현재 대상 화면을 덮지 않게 한다.
    """
    return request_revision == current_revision


def validate_ai_safe_context(
    context: ConversationContext,
) -> None:
    """
    AI context에 최소 금지 식별자가 직접 들어오는 것을 방어한다.

    이 검사는 전체 안전 보장을 대신하지 않고,
    Backend allowlist/projection 경계와 함께 사용한다.
    """
    forbidden_tokens = (
        "order_id",
        "order_line_id",
        "customer_id",
        "recipient",
        "shipping_address",
        "payment_id",
        "inquiry_body",
    )

    searchable = " ".join(
        (
            context.question,
            context.target_type,
            context.target_id,
            *context.evidence_ids,
        )
    ).lower()

    for token in forbidden_tokens:
        if token in searchable:
            raise ValueError(
                f"forbidden AI context token detected: {token}"
            )

@dataclass(frozen=True)
class AiAnswerContract:
    conclusion: str
    key_facts: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    next_checks: tuple[str, ...]
    status: ConversationStatus


def validate_answer_contract(
    answer: AiAnswerContract,
) -> None:
    if not answer.conclusion.strip():
        raise ValueError("conclusion is required")

    if answer.status == ConversationStatus.ANSWER:
        if not answer.evidence_ids:
            raise ValueError(
                "ANSWER requires at least one evidence_id"
            )

    if answer.status in {
        ConversationStatus.NO_EDGE,
        ConversationStatus.HOLD,
    }:
        # NO_EDGE/HOLD는 fabricated evidence를 요구하지 않는다.
        return