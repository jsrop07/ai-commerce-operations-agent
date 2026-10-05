"""AI LangGraph와 Backend checkpoint 저장소 연결."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai.agents.reservation_replan_graph import (
    AgentState,
    run_reservation_replan_workflow,
)
from backend.app.models.agent import AgentRun
from backend.app.services.agent_run_repository import (
    AgentCheckpointVersionConflict,
    get_agent_run,
    save_agent_checkpoint,
)

AI_AGENT_SCHEMA_VERSION = "agent-state.v0.1"
BACKEND_STATE_SCHEMA_VERSION = 1


class AgentWorkflowSafetyViolation(Exception):
    """Agent 결과가 Backend 안전 경계를 위반함."""


class AgentWorkflowContractError(Exception):
    """AI AgentState와 Backend 저장 계약이 맞지 않음."""


class AgentWorkflowNotFound(Exception):
    """No run belongs to this tenant and identity."""


class AgentWorkflowOwnershipError(Exception):
    """Run does not belong to the trusted actor."""


class AgentWorkflowReviewConflict(Exception):
    """Review request conflicts with checkpoint state or an earlier request."""


class AIHandoffRequired(Exception):
    """AI-owned resume entrypoint is not connected."""


class AgentWorkflowAIContractError(Exception):
    """AI resume result did not satisfy the persisted state contract."""


class AgentResumeCallable(Protocol):
    def __call__(
        self, *, persisted_state: AgentState, decision: str,
        review_override: dict[str, int] | None,
        reviewed_proposal: dict[str, Any] | None,
        reason: str | None, workflow_id: str, thread_id: str,
        tenant_id: str, checkpoint_version: int,
    ) -> AgentState: ...


def _state_output_hash(
    state: dict[str, Any],
) -> str:
    payload = json.dumps(
        state,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(payload).hexdigest()


def review_and_resume_reservation_replan(
    session: Session,
    *,
    tenant_id: str,
    workflow_id: str,
    thread_id: str,
    actor_id: str,
    decision: str,
    expected_checkpoint_version: int,
    idempotency_key: str,
    review_override: dict[str, int] | None = None,
    reason: str | None = None,
    resume_callable: AgentResumeCallable | None = None,
) -> AgentState:
    """Guard and persist review; AI owns APPROVE/EDIT resume semantics."""
    # PostgreSQL serializes concurrent review clicks before the AI seam is called.
    row = session.scalar(
        select(AgentRun).where(
            AgentRun.tenant_id == tenant_id,
            AgentRun.workflow_id == workflow_id,
            AgentRun.thread_id == thread_id,
        ).with_for_update()
    )
    if row is None:
        raise AgentWorkflowNotFound
    state = deepcopy(row.state)
    if state.get("owner_actor_id") != actor_id:
        raise AgentWorkflowOwnershipError
    request_hash = _state_output_hash({
        "actor_id": actor_id, "decision": decision,
        "expected_checkpoint_version": expected_checkpoint_version,
        "review_override": review_override, "reason": reason,
    })
    previous = state.get("review_requests", {}).get(idempotency_key)
    if previous is not None:
        if previous == request_hash:
            return AgentState(**state)
        raise AgentWorkflowReviewConflict("IDEMPOTENCY_CONFLICT")
    if row.checkpoint_version != expected_checkpoint_version:
        raise AgentCheckpointVersionConflict("CHECKPOINT_VERSION_CONFLICT")
    if (row.status != "WAITING" or row.current_node != "wait_for_human"
            or state.get("approval_state") != "PENDING"
            or state.get("next_allowed_nodes") != ["resume_after_human"]):
        raise AgentWorkflowReviewConflict("WORKFLOW_NOT_RESUMABLE")
    if len(state.get("proposed_actions", [])) != 1:
        raise AgentWorkflowReviewConflict("PROPOSAL_NOT_REVIEWABLE")
    if state.get("provider_write_count") != 0 or any(
        action.get("external_write") is True
        for action in state.get("proposed_actions", [])
    ):
        raise AgentWorkflowSafetyViolation("unsafe checkpoint proposal")
    reviewed_proposal = None
    if decision == "EDIT":
        if review_override is None or set(review_override) != {"proposed_delay_days"}:
            raise AgentWorkflowContractError("EDIT_REQUIRES_PROPOSED_DELAY_DAYS")
        reviewed_proposal = {
            **deepcopy(state["proposed_actions"][0]),
            "review_override": deepcopy(review_override),
        }
    elif review_override is not None:
        raise AgentWorkflowContractError("REVIEW_OVERRIDE_ONLY_FOR_EDIT")
    if decision == "REJECT":
        next_state = deepcopy(state)
        next_state.update({
            "status": "BLOCKED", "approval_state": "REJECTED",
            "reason": "HUMAN_REJECTED", "next_allowed_nodes": [],
        })
    else:
        if resume_callable is None:
            raise AIHandoffRequired("AI_HANDOFF_REQUIRED")
        result = resume_callable(
            persisted_state=AgentState(**deepcopy(state)), decision=decision,
            review_override=deepcopy(review_override),
            reviewed_proposal=deepcopy(reviewed_proposal), reason=reason,
            workflow_id=workflow_id, thread_id=thread_id,
            tenant_id=tenant_id, checkpoint_version=expected_checkpoint_version,
        )
        if not isinstance(result, dict):
            raise AgentWorkflowAIContractError("AI_RESUME_RESULT_INVALID")
        next_state = deepcopy(result)
        for field in (
            "workflow_id", "thread_id", "tenant_id", "schema_version",
            "entities", "rule_results", "proposed_actions", "trigger_event_ids",
            "source_as_of", "owner_actor_id", "task_type", "risk_level",
            "current_schedule", "initial_input", "data_mode", "source",
        ):
            if next_state.get(field) != state.get(field):
                raise AgentWorkflowAIContractError("AI_RESUME_CHANGED_ORIGINAL_INPUT")
        if ("evidence_ids" not in next_state
                or "provider_write_count" not in next_state):
            raise AgentWorkflowAIContractError("AI_RESUME_RESULT_INVALID")
        if next_state.get("status") not in {
            "RUNNING", "WAITING", "BLOCKED", "FAILED", "COMPLETED",
        } or not next_state.get("current_node") or not next_state.get("reason"):
            raise AgentWorkflowAIContractError("AI_RESUME_RESULT_INVALID")
    next_state["review_decision"] = decision
    next_state["review_reason"] = reason or ""
    if reviewed_proposal is not None:
        next_state["review_override"] = deepcopy(review_override)
        next_state["reviewed_proposal"] = reviewed_proposal
    next_state["review_requests"] = {
        **state.get("review_requests", {}), idempotency_key: request_hash,
    }
    try:
        return _save_final_state(
            session, final_state=AgentState(**next_state),
            expected_checkpoint_version=expected_checkpoint_version,
        )
    except AgentCheckpointVersionConflict:
        # A concurrent identical click may have won the CAS.
        current = get_agent_run(
            session, tenant_id=tenant_id, workflow_id=workflow_id, thread_id=thread_id
        )
        if (
            current is not None
            and current.state.get("review_requests", {}).get(idempotency_key) == request_hash
        ):
            return AgentState(**current.state)
        raise


def run_and_checkpoint_reservation_replan(
    session: Session,
    *,
    initial_state: AgentState,
    expected_checkpoint_version: int = 0,
) -> AgentState:
    """
    실제 AI LangGraph를 실행하고
    최종 안전 checkpoint를 PostgreSQL에 저장한다.
    """

    if initial_state.get("provider_write_count", 0) != 0:
        raise AgentWorkflowSafetyViolation("provider_write_count must be 0")

    final_state = (
        run_reservation_replan_workflow(
            initial_state
        )
    )

    return _save_final_state(
        session, final_state=final_state,
        expected_checkpoint_version=expected_checkpoint_version,
    )


def _save_final_state(
    session: Session, *, final_state: AgentState,
    expected_checkpoint_version: int,
) -> AgentState:
    """Validate AI output and store it through the existing checkpoint CAS."""

    workflow_id = final_state.get(
        "workflow_id"
    )
    thread_id = final_state.get(
        "thread_id"
    )
    tenant_id = final_state.get(
        "tenant_id"
    )
    schema_version = final_state.get(
        "schema_version"
    )
    current_node = final_state.get(
        "current_node"
    )
    status = final_state.get(
        "status"
    )
    reason = final_state.get(
        "reason"
    )

    required = {
        "workflow_id": workflow_id,
        "thread_id": thread_id,
        "tenant_id": tenant_id,
        "schema_version": schema_version,
        "current_node": current_node,
        "status": status,
        "reason": reason,
    }

    missing = [
        name
        for name, value in required.items()
        if value in (None, "")
    ]

    if missing:
        raise AgentWorkflowContractError(
            "missing AgentState fields: "
            + ",".join(missing)
        )

    if schema_version != AI_AGENT_SCHEMA_VERSION:
        raise AgentWorkflowContractError(
            "unsupported AI AgentState schema: "
            f"{schema_version}"
        )

    provider_write_count = int(
        final_state.get(
            "provider_write_count",
            0,
        )
    )

    if provider_write_count != 0:
        raise AgentWorkflowSafetyViolation(
            "provider_write_count must be 0"
        )

    proposed_actions = final_state.get(
        "proposed_actions",
        [],
    )

    for action in [*proposed_actions, final_state.get("reviewed_proposal") or {}]:
        if action.get("external_write") is True:
            raise AgentWorkflowSafetyViolation(
                "external_write proposal is prohibited"
            )

    evidence_ids = tuple(
        dict.fromkeys(
            final_state.get(
                "evidence_ids",
                [],
            )
        )
    )

    model_result = final_state.get(
        "model_result",
        {},
    )

    model_version = (
        model_result.get("model_id")
        if isinstance(
            model_result,
            dict,
        )
        else None
    )

    serializable_state = dict(
        final_state
    )

    save_agent_checkpoint(
        session,
        tenant_id=str(tenant_id),
        workflow_id=str(workflow_id),
        thread_id=str(thread_id),
        current_node=str(current_node),
        status=str(status),
        state=serializable_state,
        state_schema_version=(
            BACKEND_STATE_SCHEMA_VERSION
        ),
        expected_checkpoint_version=(
            expected_checkpoint_version
        ),
        checkpoint_at=datetime.now(UTC),
        evidence_ids=evidence_ids,
        reason=str(reason),
        model_version=model_version,
        output_hash=_state_output_hash(
            serializable_state
        ),
    )

    return final_state
