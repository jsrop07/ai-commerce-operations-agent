from __future__ import annotations

import json
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

AgentStatus = Literal[
    "RUNNING",
    "WAITING",
    "BLOCKED",
    "FAILED",
    "COMPLETED",
]


class AgentState(TypedDict, total=False):
    # Backend 최소 handoff 필드
    workflow_id: str
    thread_id: str
    tenant_id: str
    schema_version: str
    current_node: str
    status: AgentStatus
    evidence_ids: list[str]
    reason: str

    # 공식 AgentState 설계 필드
    trigger_event_ids: list[str]
    task_type: str
    risk_level: str
    confidence: float | None
    entities: dict[str, Any]
    source_as_of: str | None
    rule_results: dict[str, Any]
    retrieval_result: dict[str, Any]
    model_result: dict[str, Any]
    proposed_actions: list[dict[str, Any]]
    approval_state: str | None
    tool_receipts: list[dict[str, Any]]
    retry_count: dict[str, int]
    deadlines: dict[str, str]
    errors: list[dict[str, Any]]
    audit_ids: list[str]
    next_allowed_nodes: list[str]

    # Day11 실행 증거용 내부 필드
    transition_history: list[dict[str, str]]
    provider_write_count: int


TASK_TYPE = "reservation_replan_review"


def _append_transition(
    state: AgentState,
    *,
    node: str,
    reason: str,
) -> list[dict[str, str]]:
    history = list(state.get("transition_history", []))
    history.append(
        {
            "node": node,
            "reason": reason,
        }
    )
    return history

FORBIDDEN_AI_INPUT_KEYS = frozenset(
    {
        "order_id",
        "order_item_id",
        "order_line_id",
        "customer_id",
        "customer_group",
        "shipping_address",
        "shipping_info",
        "payment_info",
        "payment_details",
        "customer_memo",
        "free_memo",
        "inquiry_body",
        "inquiry_text",
        "order_lookup_id",
        "order_lookup_url",
        "reverse_lookup_ref",
        "reverse_lookup_url",
    }
)

FORBIDDEN_AI_INPUT_COLLECTION_KEYS = frozenset(
    {
        "order_items",
        "order_lines",
        "orders",
        "order_quantities",
        "customer_orders",
        "review_items",
        "excluded_order_item_ids",
        "transaction_timestamps",
        "affected_order_ids",
    }
)

def _find_forbidden_ai_input(
    value: Any,
    *,
    path: str = "state",
) -> str | None:
    if isinstance(value, dict):
        for raw_key, nested in value.items():
            key = str(raw_key).lower()

            if key in FORBIDDEN_AI_INPUT_KEYS:
                return f"{path}.{raw_key}"

            if key in FORBIDDEN_AI_INPUT_COLLECTION_KEYS:
                return f"{path}.{raw_key}"

            found = _find_forbidden_ai_input(
                nested,
                path=f"{path}.{raw_key}",
            )
            if found is not None:
                return found

    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            found = _find_forbidden_ai_input(
                nested,
                path=f"{path}[{index}]",
            )
            if found is not None:
                return found

    return None

def validate_input(state: AgentState) -> dict[str, Any]:
    required = (
        "workflow_id",
        "thread_id",
        "tenant_id",
        "schema_version",
        "task_type",
    )

    missing = [
        field
        for field in required
        if not state.get(field)
    ]

    if missing:
        reason = (
            "INVALID_INPUT_MISSING_FIELDS:"
            + ",".join(missing)
        )
        return {
            "current_node": "validate_input",
            "status": "BLOCKED",
            "reason": reason,
            "errors": [
                {
                    "code": "INVALID_INPUT",
                    "missing_fields": missing,
                }
            ],
            "next_allowed_nodes": [],
            "transition_history": _append_transition(
                state,
                node="validate_input",
                reason=reason,
            ),
            "provider_write_count": 0,
        }

    if state["task_type"] != TASK_TYPE:
        reason = "UNSUPPORTED_TASK_TYPE"
        return {
            "current_node": "validate_input",
            "status": "BLOCKED",
            "reason": reason,
            "errors": [
                {
                    "code": "UNSUPPORTED_TASK_TYPE",
                    "expected": TASK_TYPE,
                    "actual": state["task_type"],
                }
            ],
            "next_allowed_nodes": [],
            "transition_history": _append_transition(
                state,
                node="validate_input",
                reason=reason,
            ),
            "provider_write_count": 0,
        }

    forbidden_path = _find_forbidden_ai_input(
        {
            "entities": state.get("entities", {}),
            "rule_results": state.get(
                "rule_results",
                {},
            ),
            "retrieval_result": state.get(
                "retrieval_result",
                {},
            ),
            "model_result": state.get(
                "model_result",
                {},
            ),
            "tool_receipts": state.get(
                "tool_receipts",
                [],
            ),
        }
    )

    if forbidden_path is not None:
        reason = "FORBIDDEN_AI_INPUT"
        return {
            "current_node": "validate_input",
            "status": "BLOCKED",
            "reason": reason,
            "errors": [
                {
                    "code": "FORBIDDEN_AI_INPUT",
                    "path": forbidden_path,
                }
            ],
            "next_allowed_nodes": [],
            "transition_history": _append_transition(
                state,
                node="validate_input",
                reason=reason,
            ),
            "provider_write_count": 0,
        }
    reason = "INPUT_VALIDATED"
    return {
        "current_node": "validate_input",
        "status": "RUNNING",
        "reason": reason,
        "errors": list(state.get("errors", [])),
        "next_allowed_nodes": ["check_rules"],
        "transition_history": _append_transition(
            state,
            node="validate_input",
            reason=reason,
        ),
        "provider_write_count": 0,
    }


def check_rules(state: AgentState) -> dict[str, Any]:
    rule_results = state.get("rule_results") or {}

    if not rule_results:
        reason = "RULE_RESULTS_REQUIRED"
        return {
            "current_node": "check_rules",
            "status": "BLOCKED",
            "reason": reason,
            "next_allowed_nodes": [],
            "transition_history": _append_transition(
                state,
                node="check_rules",
                reason=reason,
            ),
            "provider_write_count": 0,
        }

    # Rule 자체를 AI가 다시 계산하지 않는다.
    # Backend/결정론적 규칙 계층이 산출한 값을 소비한다.
    replan_required = rule_results.get(
        "replan_required"
    )

    if replan_required is False:
        reason = "RULE_CONFIRMED_NO_REPLAN_REQUIRED"
        return {
            "current_node": "check_rules",
            "status": "COMPLETED",
            "reason": reason,
            "next_allowed_nodes": [],
            "transition_history": _append_transition(
                state,
                node="check_rules",
                reason=reason,
            ),
            "provider_write_count": 0,
        }

    if replan_required is not True:
        reason = "RULE_REPLAN_DECISION_MISSING"
        return {
            "current_node": "check_rules",
            "status": "BLOCKED",
            "reason": reason,
            "next_allowed_nodes": [],
            "transition_history": _append_transition(
                state,
                node="check_rules",
                reason=reason,
            ),
            "provider_write_count": 0,
        }

    reason = "RULE_CONFIRMED_REPLAN_REVIEW_REQUIRED"
    return {
        "current_node": "check_rules",
        "status": "RUNNING",
        "reason": reason,
        "next_allowed_nodes": ["assist_context"],
        "transition_history": _append_transition(
            state,
            node="check_rules",
            reason=reason,
        ),
        "provider_write_count": 0,
    }


def assist_context(state: AgentState) -> dict[str, Any]:
    evidence_ids = list(
        state.get("evidence_ids", [])
    )
    rule_results = state.get("rule_results") or {}

    if not evidence_ids:
        reason = "EVIDENCE_REQUIRED"
        return {
            "current_node": "assist_context",
            "status": "BLOCKED",
            "reason": reason,
            "retrieval_result": {
                "status": "BLOCKED",
                "reason": "NO_EVIDENCE_AVAILABLE",
                "used": False,
            },
            "model_result": {
                "status": "NOT_RUN",
                "used": False,
            },
            "next_allowed_nodes": [],
            "transition_history": _append_transition(
                state,
                node="assist_context",
                reason=reason,
            ),
            "provider_write_count": 0,
        }

    requires_ai_assist = bool(
        rule_results.get(
            "requires_ai_assist",
            False,
        )
    )

    # Day11 현재 실제 Base model runtime은 아직 없음.
    model_result = {
        "status": "OPEN",
        "used": False,
        "model_id": None,
        "adapter_id": None,
        "reason": "BASE_MODEL_RUNTIME_NOT_AVAILABLE",
    }

    retrieval_result = {
        "status": "PRE_RESOLVED_EVIDENCE",
        "used": True,
        "evidence_ids": evidence_ids,
        "reason": (
            "DAY11_GRAPH_CONSUMES_EXISTING_"
            "VERIFIED_EVIDENCE"
        ),
    }

    if requires_ai_assist:
        reason = "AI_ASSIST_REQUIRED_BUT_RUNTIME_OPEN"
        return {
            "current_node": "assist_context",
            "status": "BLOCKED",
            "reason": reason,
            "retrieval_result": retrieval_result,
            "model_result": model_result,
            "next_allowed_nodes": [],
            "transition_history": _append_transition(
                state,
                node="assist_context",
                reason=reason,
            ),
            "provider_write_count": 0,
        }

    reason = (
        "RULE_AND_EVIDENCE_SUFFICIENT_"
        "AI_ASSIST_OPTIONAL_OPEN"
    )

    return {
        "current_node": "assist_context",
        "status": "RUNNING",
        "reason": reason,
        "retrieval_result": retrieval_result,
        "model_result": model_result,
        "next_allowed_nodes": ["build_proposal"],
        "transition_history": _append_transition(
            state,
            node="assist_context",
            reason=reason,
        ),
        "provider_write_count": 0,
    }


def build_proposal(state: AgentState) -> dict[str, Any]:
    rule_results = state.get("rule_results") or {}
    evidence_ids = list(
        state.get("evidence_ids", [])
    )

    proposal = {
        "action_type": "REPLAN_REVIEW_PROPOSAL",
        "external_write": False,
        "requires_human_review": True,
        "rule_results": rule_results,
        "evidence_ids": evidence_ids,
        "note": (
            "Internal proposal only. "
            "No provider write is permitted."
        ),
    }

    reason = "INTERNAL_REPLAN_PROPOSAL_CREATED"

    return {
        "current_node": "build_proposal",
        "status": "RUNNING",
        "reason": reason,
        "proposed_actions": [proposal],
        "approval_state": "PENDING",
        "next_allowed_nodes": ["wait_for_human"],
        "transition_history": _append_transition(
            state,
            node="build_proposal",
            reason=reason,
        ),
        "provider_write_count": 0,
    }


def wait_for_human(state: AgentState) -> dict[str, Any]:
    reason = "HUMAN_REVIEW_REQUIRED"

    return {
        "current_node": "wait_for_human",
        "status": "WAITING",
        "reason": reason,
        "approval_state": "PENDING",
        # Day12 resume 구현 전까지 실제 전이는 하지 않는다.
        "next_allowed_nodes": [
            "resume_after_human"
        ],
        "transition_history": _append_transition(
            state,
            node="wait_for_human",
            reason=reason,
        ),
        "provider_write_count": 0,
    }


def _route_after_validate(
    state: AgentState,
) -> str:
    if state.get("status") == "BLOCKED":
        return "end"
    return "check_rules"


def _route_after_rules(
    state: AgentState,
) -> str:
    if state.get("status") in {
        "BLOCKED",
        "COMPLETED",
    }:
        return "end"
    return "assist_context"


def _route_after_assist(
    state: AgentState,
) -> str:
    if state.get("status") == "BLOCKED":
        return "end"
    return "build_proposal"


def build_reservation_replan_graph():
    builder = StateGraph(AgentState)

    builder.add_node(
        "validate_input",
        validate_input,
    )
    builder.add_node(
        "check_rules",
        check_rules,
    )
    builder.add_node(
        "assist_context",
        assist_context,
    )
    builder.add_node(
        "build_proposal",
        build_proposal,
    )
    builder.add_node(
        "wait_for_human",
        wait_for_human,
    )

    builder.add_edge(
        START,
        "validate_input",
    )

    builder.add_conditional_edges(
        "validate_input",
        _route_after_validate,
        {
            "check_rules": "check_rules",
            "end": END,
        },
    )

    builder.add_conditional_edges(
        "check_rules",
        _route_after_rules,
        {
            "assist_context": "assist_context",
            "end": END,
        },
    )

    builder.add_conditional_edges(
        "assist_context",
        _route_after_assist,
        {
            "build_proposal": "build_proposal",
            "end": END,
        },
    )

    builder.add_edge(
        "build_proposal",
        "wait_for_human",
    )
    builder.add_edge(
        "wait_for_human",
        END,
    )

    return builder.compile()


GRAPH = build_reservation_replan_graph()


def run_reservation_replan_workflow(
    initial_state: AgentState,
) -> AgentState:
    result = GRAPH.invoke(initial_state)
    return AgentState(**result)


def _day11_demo_state() -> AgentState:
    return AgentState(
        workflow_id="wf_day11_replan_001",
        thread_id="thread_day11_replan_001",
        tenant_id="demo_store",
        schema_version="agent-state.v0.1",
        trigger_event_ids=[
            "evt_demo_incoming_delay_001"
        ],
        current_node="",
        status="RUNNING",
        task_type=TASK_TYPE,
        risk_level="MEDIUM",
        confidence=None,
        entities={
            "reservation_id":
                "reservation_demo_001",
            "sku_id":
                "sku_demo_001",
        },
        evidence_ids=[
            "ev_rule_reservation_shortage_001",
            "ev_incoming_delay_001",
        ],
        source_as_of="2026-09-13T15:00:00+09:00",
        rule_results={
            "reservation_shortage_qty": 2,
            "incoming_delay_days": 3,
            "replan_required": True,
            "requires_ai_assist": False,
        },
        retrieval_result={},
        model_result={},
        proposed_actions=[],
        approval_state=None,
        tool_receipts=[],
        retry_count={},
        deadlines={},
        errors=[],
        audit_ids=[],
        next_allowed_nodes=[],
        transition_history=[],
        provider_write_count=0,
    )


if __name__ == "__main__":
    final_state = run_reservation_replan_workflow(
        _day11_demo_state()
    )
    print(
        json.dumps(
            final_state,
            ensure_ascii=False,
            indent=2,
        )
    )