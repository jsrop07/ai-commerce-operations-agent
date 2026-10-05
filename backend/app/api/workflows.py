"""Agent workflow state and R10 review API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from backend.app.core.config import Environment
from backend.app.services.agent_run_repository import (
    AgentCheckpointVersionConflict,
    get_agent_run,
)
from backend.app.services.agent_workflow_runtime import (
    AgentWorkflowAIContractError,
    AgentWorkflowContractError,
    AgentWorkflowNotFound,
    AgentWorkflowOwnershipError,
    AgentWorkflowReviewConflict,
    AgentWorkflowSafetyViolation,
    AIHandoffRequired,
    review_and_resume_reservation_replan,
)

router = APIRouter(
    prefix="/api/v1/workflows",
    tags=["workflows"],
)


class AgentStateResponse(BaseModel):
    workflow_id: str
    thread_id: str
    current_node: str
    status: str

    state_schema_version: int = Field(
        ge=1
    )
    checkpoint_version: int = Field(
        ge=1
    )

    evidence_ids: list[str]

    reason: str | None = None

    checkpoint_at: datetime


class ReviewOverride(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proposed_delay_days: int = Field(ge=0, le=365)


class WorkflowReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["APPROVE", "EDIT", "REJECT"]
    expected_checkpoint_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
    review_override: ReviewOverride | None = None
    reason: Literal["STOCK_RECHECK", "INCOMING_RECHECK", "PLAN_ADJUSTMENT"] | None = None


def _trusted_actor(request: Request) -> str:
    if request.app.state.settings.environment not in {Environment.LOCAL, Environment.TEST}:
        raise HTTPException(status_code=403, detail="C09_ENVIRONMENT_FORBIDDEN")
    actor = request.scope.get("c09_trusted_actor_id")
    if not isinstance(actor, str) or not actor:
        raise HTTPException(status_code=403, detail="C09_TRUSTED_ACTOR_REQUIRED")
    return actor


def _response(row) -> AgentStateResponse:
    return AgentStateResponse(
        workflow_id=row.workflow_id, thread_id=row.thread_id,
        current_node=row.current_node, status=row.status,
        state_schema_version=row.state_schema_version,
        checkpoint_version=row.checkpoint_version,
        evidence_ids=list(row.evidence_ids or []), reason=row.reason,
        checkpoint_at=row.checkpoint_at,
    )


@router.get(
    "/{workflow_id}/threads/{thread_id}/state",
    response_model=AgentStateResponse,
)
def get_workflow_state(
    request: Request,
    workflow_id: str,
    thread_id: str,
) -> AgentStateResponse:
    """현재 tenant의 Agent workflow checkpoint를 조회한다."""

    tenant_id = (
        request.app.state.settings.tenant_id
    )

    with Session(
        request.app.state.db_engine
    ) as session:
        row = get_agent_run(
            session,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            thread_id=thread_id,
        )

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="AGENT_STATE_NOT_FOUND",
        )

    if row.state.get("owner_actor_id") is not None:
        if row.state["owner_actor_id"] != _trusted_actor(request):
            raise HTTPException(status_code=404, detail="AGENT_STATE_NOT_FOUND")

    return _response(row)


@router.post(
    "/{workflow_id}/threads/{thread_id}/review",
    response_model=AgentStateResponse,
)
def review_workflow(
    request: Request, workflow_id: str, thread_id: str,
    payload: WorkflowReviewRequest,
) -> AgentStateResponse:
    """R10 NEW contract: guarded review with an AI-owned resume seam."""
    actor_id = _trusted_actor(request)
    tenant_id = request.app.state.settings.tenant_id
    try:
        with Session(request.app.state.db_engine) as session:
            review_and_resume_reservation_replan(
                session, tenant_id=tenant_id, workflow_id=workflow_id,
                thread_id=thread_id, actor_id=actor_id,
                decision=payload.decision,
                expected_checkpoint_version=payload.expected_checkpoint_version,
                idempotency_key=payload.idempotency_key,
                review_override=(payload.review_override.model_dump()
                                 if payload.review_override else None),
                reason=payload.reason,
                resume_callable=getattr(request.app.state, "agent_resume_callable", None),
            )
            row = get_agent_run(
                session, tenant_id=tenant_id, workflow_id=workflow_id,
                thread_id=thread_id,
            )
            if row is None:
                raise RuntimeError("checkpoint disappeared after review")
            return _response(row)
    except (AgentWorkflowNotFound, AgentWorkflowOwnershipError) as exc:
        raise HTTPException(status_code=404, detail="AGENT_STATE_NOT_FOUND") from exc
    except AgentCheckpointVersionConflict as exc:
        raise HTTPException(status_code=409, detail="CHECKPOINT_VERSION_CONFLICT") from exc
    except AgentWorkflowReviewConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (AgentWorkflowContractError, AgentWorkflowSafetyViolation) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (AIHandoffRequired, AgentWorkflowAIContractError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
