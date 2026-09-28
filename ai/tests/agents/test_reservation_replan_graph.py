from __future__ import annotations

from ai.agents.reservation_replan_graph import (
    TASK_TYPE,
    AgentState,
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


def test_required_ai_runtime_open_is_blocked() -> None:
    state = make_state()
    state["rule_results"]["requires_ai_assist"] = True

    result = run_reservation_replan_workflow(
        state
    )

    assert result["status"] == "BLOCKED"
    assert result["current_node"] == "assist_context"
    assert (
        result["reason"]
        == "AI_ASSIST_REQUIRED_BUT_RUNTIME_OPEN"
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