"""Agent workflow state read API."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.services.agent_run_repository import (
    get_agent_run,
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

    return AgentStateResponse(
        workflow_id=row.workflow_id,
        thread_id=row.thread_id,
        current_node=row.current_node,
        status=row.status,
        state_schema_version=(
            row.state_schema_version
        ),
        checkpoint_version=(
            row.checkpoint_version
        ),
        evidence_ids=list(
            row.evidence_ids or []
        ),
        reason=row.reason,
        checkpoint_at=row.checkpoint_at,
    )