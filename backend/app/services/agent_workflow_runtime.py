"""AI LangGraph와 Backend checkpoint 저장소 연결."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from ai.agents.reservation_replan_graph import (
    AgentState,
    run_reservation_replan_workflow,
)
from backend.app.services.agent_run_repository import (
    save_agent_checkpoint,
)


AI_AGENT_SCHEMA_VERSION = "agent-state.v0.1"
BACKEND_STATE_SCHEMA_VERSION = 1


class AgentWorkflowSafetyViolation(Exception):
    """Agent 결과가 Backend 안전 경계를 위반함."""


class AgentWorkflowContractError(Exception):
    """AI AgentState와 Backend 저장 계약이 맞지 않음."""


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

    final_state = (
        run_reservation_replan_workflow(
            initial_state
        )
    )

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

    for action in proposed_actions:
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