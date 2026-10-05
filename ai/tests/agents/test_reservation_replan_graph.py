from __future__ import annotations

from ai.agents.reservation_replan_graph import (
    TASK_TYPE,
    AgentState,
    resume_reservation_replan_after_review,
    run_reservation_replan_workflow,
)


def make_state() -> AgentState:
    return AgentState(
        workflow_id="wf_test_001",
        thread_id="thread_test_001",
        tenant_id="demo_store",
        schema_version="agent-state.v0.1",
        trigger_event_ids=["evt_test_001"],
        current_node="",
        status="RUNNING",
        task_type=TASK_TYPE,
        risk_level="MEDIUM",
        confidence=None,
        entities={"sku_id": "sku_test_001"},
        evidence_ids=[
            "ev_rule_001",
            "ev_delay_001",
        ],
        source_as_of="2026-09-13T15:00:00+09:00",
        rule_results={
            "required_qty": 5,
            "secured_qty": 1,
            "confirmed_incoming_qty": 2,
            "tentative_incoming_qty": 0,
            "shortage": 2,
            "calculation_status": "CONFIRMED",
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


def test_actual_langgraph_reaches_waiting() -> None:
    result = run_reservation_replan_workflow(
        make_state()
    )

    assert result["status"] == "WAITING"
    assert result["current_node"] == "wait_for_human"
    assert result["reason"] == "HUMAN_REVIEW_REQUIRED"

    node_names = [
        item["node"]
        for item in result["transition_history"]
    ]

    assert node_names == [
        "validate_input",
        "check_rules",
        "assist_context",
        "build_proposal",
        "wait_for_human",
    ]

    assert len(result["proposed_actions"]) == 1
    assert (
        result["proposed_actions"][0]["external_write"]
        is False
    )

    assert result["provider_write_count"] == 0


def test_model_runtime_is_not_faked() -> None:
    result = run_reservation_replan_workflow(
        make_state()
    )

    assert result["model_result"]["status"] == "OPEN"
    assert result["model_result"]["used"] is False
    assert (
        result["model_result"]["reason"]
        == "BASE_MODEL_RUNTIME_NOT_AVAILABLE"
    )


def test_missing_evidence_is_blocked() -> None:
    state = make_state()
    state["evidence_ids"] = []

    result = run_reservation_replan_workflow(
        state
    )

    assert result["status"] == "BLOCKED"
    assert result["current_node"] == "assist_context"
    assert result["reason"] == "EVIDENCE_REQUIRED"
    assert result.get("proposed_actions", []) == []
    assert result["provider_write_count"] == 0


def test_required_ai_without_payload_is_blocked() -> None:
    state = make_state()
    state["rule_results"]["requires_ai_assist"] = True

    result = run_reservation_replan_workflow(
        state
    )

    assert result["status"] == "BLOCKED"
    assert result["current_node"] == "assist_context"
    assert (
        result["reason"]
        == "AI_ASSIST_EVIDENCE_PAYLOAD_REQUIRED"
    )
    assert result["model_result"]["used"] is False
    assert result["provider_write_count"] == 0

def test_no_replan_required_finishes_without_proposal() -> None:
    state = make_state()
    state["rule_results"]["replan_required"] = False

    result = run_reservation_replan_workflow(
        state
    )

    assert result["status"] == "COMPLETED"
    assert result["current_node"] == "check_rules"
    assert (
        result["reason"]
        == "RULE_CONFIRMED_NO_REPLAN_REQUIRED"
    )
    assert result.get("proposed_actions", []) == []
    assert result["provider_write_count"] == 0


def test_missing_required_input_is_blocked() -> None:
    state = make_state()
    state.pop("thread_id")

    result = run_reservation_replan_workflow(
        state
    )

    assert result["status"] == "BLOCKED"
    assert result["current_node"] == "validate_input"
    assert result["reason"].startswith(
        "INVALID_INPUT_MISSING_FIELDS"
    )
    assert result["provider_write_count"] == 0


def test_order_id_in_entities_is_blocked() -> None:
    state = make_state()
    state["entities"]["order_id"] = "ORDER-CANARY-001"

    result = run_reservation_replan_workflow(
        state
    )

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "FORBIDDEN_AI_INPUT"
    assert result["errors"][0]["code"] == (
        "FORBIDDEN_AI_INPUT"
    )


def test_customer_id_in_rule_results_is_blocked() -> None:
    state = make_state()
    state["rule_results"]["customer_id"] = (
        "CUSTOMER-CANARY-001"
    )

    result = run_reservation_replan_workflow(
        state
    )

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "FORBIDDEN_AI_INPUT"


def test_nested_order_line_id_is_blocked() -> None:
    state = make_state()
    state["rule_results"]["nested"] = {
        "order_line_id": "LINE-CANARY-001"
    }

    result = run_reservation_replan_workflow(
        state
    )

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "FORBIDDEN_AI_INPUT"


def test_order_line_collection_is_blocked() -> None:
    state = make_state()
    state["entities"]["order_lines"] = [
        {
            "sku_id": "sku_demo_001",
            "quantity": 1,
        }
    ]

    result = run_reservation_replan_workflow(
        state
    )

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "FORBIDDEN_AI_INPUT"


def test_masked_order_row_is_still_blocked() -> None:
    state = make_state()
    state["entities"]["order_lines"] = [
        {
            "order_id": "<ORDER_REF>",
            "sku_id": "sku_demo_001",
        }
    ]

    result = run_reservation_replan_workflow(
        state
    )

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "FORBIDDEN_AI_INPUT"


def test_allowed_sku_aggregate_still_reaches_waiting() -> None:
    state = make_state()

    result = run_reservation_replan_workflow(
        state
    )

    assert result["status"] == "WAITING"
    assert result["provider_write_count"] == 0

def test_c03_rule_results_are_preserved_in_proposal() -> None:
    state = make_state()

    result = run_reservation_replan_workflow(
        state
    )

    proposal = result["proposed_actions"][0]
    rule_results = proposal["rule_results"]

    assert rule_results["required_qty"] == 5
    assert rule_results["secured_qty"] == 1
    assert (
        rule_results["confirmed_incoming_qty"]
        == 2
    )
    assert (
        rule_results["tentative_incoming_qty"]
        == 0
    )
    assert rule_results["shortage"] == 2
    assert (
        rule_results["calculation_status"]
        == "CONFIRMED"
    )

def test_affected_order_ids_are_blocked() -> None:
    state = make_state()
    state["rule_results"]["affected_order_ids"] = [
        "ORDER-CANARY-001"
    ]

    result = run_reservation_replan_workflow(
        state
    )

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "FORBIDDEN_AI_INPUT"

def test_unknown_c03_values_are_not_coerced_to_zero() -> None:
    state = make_state()
    state["rule_results"].update(
        {
            "secured_qty": None,
            "confirmed_incoming_qty": 2,
            "shortage": None,
            "calculation_status": (
                "SECURED_QTY_UNKNOWN"
            ),
        }
    )

    result = run_reservation_replan_workflow(
        state
    )

    rule_results = result["proposed_actions"][0][
        "rule_results"
    ]

    assert rule_results["secured_qty"] is None
    assert rule_results["shortage"] is None
    assert (
        rule_results["calculation_status"]
        == "SECURED_QTY_UNKNOWN"
    )

def _with_r10_safe_evidence(
    state: AgentState,
) -> AgentState:
    state["rule_results"]["requires_ai_assist"] = True
    state["retrieval_result"] = {
        "status": "PRE_RESOLVED_EVIDENCE",
        "used": True,
        "data_mode": "SYNTHETIC_DEMO",
        "quality_status": "APPROVED",
        "evidence_ids": list(
            state["evidence_ids"]
        ),
        "citations": [
            {
                "source_type": "POLICY",
                "source_id": "policy-demo-001",
                "version": "v1",
                "excerpt": (
                    "예약 재계획은 승인 근거와 "
                    "확정된 수치만 사용한다."
                ),
                "as_of": None,
            }
        ],
    }
    return state


def test_required_ai_assist_reaches_waiting(
    monkeypatch,
) -> None:
    import ai.agents.reservation_replan_graph as graph_module

    calls = {"count": 0}

    def fake_assist(state):
        calls["count"] += 1
        assert (
            state["rule_results"]["required_qty"]
            == 5
        )
        return {
            "status": "ANSWER",
            "used": True,
            "runtime_kind": "REAL_MODEL",
            "reason": "R10_AI_ASSIST_VALIDATED",
            "validation_errors": [],
            "output": {
                "status": "ANSWER",
                "conclusion": "사람 검토가 필요합니다.",
                "used_facts": [],
                "used_numeric_facts": [],
                "citations": [
                    {
                        "source_id": "policy-demo-001",
                        "version": "v1",
                    }
                ],
                "next_check": "사람 검토",
            },
            "receipt": {
                "provider": "openai",
                "model": "gpt-5.6-luna",
                "response_id": "resp_r10_fake_graph",
                "latency_ms": 1.0,
                "attempts": 1,
                "retries": 0,
                "usage": {
                    "input_tokens": 10,
                    "cached_input_tokens": 0,
                    "output_tokens": 5,
                },
            },
        }

    monkeypatch.setattr(
        graph_module,
        "_R10_AI_ASSIST_RUNNER",
        fake_assist,
    )

    result = run_reservation_replan_workflow(
        _with_r10_safe_evidence(
            make_state()
        )
    )

    assert calls["count"] == 1
    assert result["status"] == "WAITING"
    assert result["current_node"] == "wait_for_human"
    assert result["model_result"]["status"] == "ANSWER"
    assert result["model_result"]["used"] is True
    assert result["provider_write_count"] == 0


def test_review_approve_completes_without_model_recall(
    monkeypatch,
) -> None:
    import ai.agents.reservation_replan_graph as graph_module

    waiting = run_reservation_replan_workflow(
        make_state()
    )

    def fail_if_called(state):
        raise AssertionError(
            "resume must not recall model"
        )

    monkeypatch.setattr(
        graph_module,
        "_R10_AI_ASSIST_RUNNER",
        fail_if_called,
    )

    result = resume_reservation_replan_after_review(
        waiting,
        decision="APPROVE",
        reason="operator approved",
    )

    assert result["status"] == "COMPLETED"
    assert (
        result["current_node"]
        == "resume_after_human"
    )
    assert result["approval_state"] == "APPROVED"
    assert result["provider_write_count"] == 0


def test_review_edit_preserves_original_and_waits_again() -> None:
    from copy import deepcopy

    waiting = run_reservation_replan_workflow(
        make_state()
    )
    original_rules = deepcopy(
        waiting["rule_results"]
    )
    original_actions = deepcopy(
        waiting["proposed_actions"]
    )

    result = resume_reservation_replan_after_review(
        waiting,
        decision="EDIT",
        review_override={
            "proposed_delay_days": 2,
        },
        reviewed_proposal={
            "proposed_delay_days": 2,
            "external_write": False,
        },
        reason="operator edit",
    )

    assert result["status"] == "WAITING"
    assert result["current_node"] == "wait_for_human"
    assert (
        result["reason"]
        == "HUMAN_REVIEW_EDIT_REQUIRES_REVIEW"
    )
    assert result["rule_results"] == original_rules
    assert result["proposed_actions"] == original_actions
    assert (
        result["reviewed_proposal"][
            "proposed_delay_days"
        ]
        == 2
    )
    assert result["provider_write_count"] == 0


def test_review_reject_blocks_without_external_write() -> None:
    waiting = run_reservation_replan_workflow(
        make_state()
    )

    result = resume_reservation_replan_after_review(
        waiting,
        decision="REJECT",
        reason="operator rejected",
    )

    assert result["status"] == "BLOCKED"
    assert result["approval_state"] == "REJECTED"
    assert result["provider_write_count"] == 0


def test_resume_rejects_non_waiting_state() -> None:
    state = make_state()

    try:
        resume_reservation_replan_after_review(
            state,
            decision="APPROVE",
        )
    except ValueError as exc:
        assert "not resumable" in str(exc)
    else:
        raise AssertionError(
            "expected ValueError"
        )
