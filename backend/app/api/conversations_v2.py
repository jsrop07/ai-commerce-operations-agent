"""C09 PRE typed conversation API. No AI execution occurs here."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from backend.app.api.catalog_v2 import _require_catalog_tenant, _require_v2_runtime
from backend.app.core.config import Environment
from backend.app.services.conversation_v2 import (
    C09ContractError,
    TargetInput,
    append_turn,
    create_conversation,
    read_conversation,
    recent_conversations,
    reopen_conversation,
)
from contracts.api import ApiEnvelope

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations-v2"])


class ContextInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    targetType: Literal["PRODUCT", "INCOMING", "TASK"]
    targetId: str = Field(min_length=1, max_length=255)
    targetLabel: str = Field(min_length=1, max_length=255)
    source: str = Field(min_length=1, max_length=64)
    asOf: datetime | None

    def canonical(self) -> TargetInput:
        return TargetInput(self.targetType, self.targetId, self.targetLabel, self.source, self.asOf)


class CreateConversationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    context: ContextInput


class AppendTurnInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    context: ContextInput
    intent: Literal["INSPECT_TARGET", "FOLLOW_RELATED_TARGET"]


class ContextView(BaseModel):
    context_revision: int
    target_type: str
    target_id: str
    target_label: str | None
    source: str | None
    source_as_of: datetime | None
    data_mode: str | None


class MessageView(BaseModel):
    message_id: str
    message_order: int
    role: str
    content: str
    response_status: str
    intent: str | None
    analysis_kind: str | None
    context: ContextView


class AgentRunReference(BaseModel):
    workflow_id: str
    thread_id: str
    run_status: str


class ConversationView(BaseModel):
    conversation_id: str
    conversation_status: str
    current_context_revision: int
    context: ContextView | None
    messages: list[MessageView]
    agent_runs: list[AgentRunReference]


def _runtime(request: Request):
    # Auth middleware has not yet been installed. Client headers/body never establish ownership.
    actor_id = request.scope.get("c09_trusted_actor_id")
    if not isinstance(actor_id, str) or not actor_id:
        raise HTTPException(status_code=403, detail="C09_TRUSTED_ACTOR_REQUIRED")
    if request.app.state.settings.environment not in {Environment.LOCAL, Environment.TEST}:
        raise HTTPException(status_code=403, detail="C09_ENVIRONMENT_FORBIDDEN")
    session_factory, tenant_id = _require_v2_runtime(request)
    return session_factory, tenant_id, actor_id


def _fail(error: C09ContractError) -> None:
    status_code = {"HOLD": 422, "MISSING": 404, "STALE": 409, "CONFLICT": 409, "ERROR": 503}[
        error.status
    ]
    raise HTTPException(
        status_code=status_code, detail={"status": error.status, "code": error.code}
    )


def _envelope(tenant_id: UUID, data):
    return ApiEnvelope(
        tenant_id=str(tenant_id),
        request_id=f"req_{uuid4().hex}",
        trace_id=f"tr_{uuid4().hex}",
        evidence_ids=[],
        warnings=[],
        as_of=datetime.now(UTC),
        data=data,
    )


@router.post("", response_model=ApiEnvelope[ConversationView], status_code=201)
def new_conversation(request: Request, payload: CreateConversationInput):
    session_factory, tenant_id, actor_id = _runtime(request)
    with session_factory() as session:
        _require_catalog_tenant(session, tenant_id)
        try:
            row = create_conversation(
                session, tenant_id=tenant_id, actor_id=actor_id, target=payload.context.canonical()
            )
            data = read_conversation(
                session, tenant_id=tenant_id, actor_id=actor_id, conversation_id=row.id
            )
        except C09ContractError as error:
            _fail(error)
    return _envelope(tenant_id, data)


@router.post("/{conversation_id}/messages", response_model=ApiEnvelope[ConversationView])
def append_message(request: Request, conversation_id: UUID, payload: AppendTurnInput):
    session_factory, tenant_id, actor_id = _runtime(request)
    with session_factory() as session:
        _require_catalog_tenant(session, tenant_id)
        try:
            append_turn(
                session,
                tenant_id=tenant_id,
                actor_id=actor_id,
                conversation_id=conversation_id,
                target=payload.context.canonical(),
                intent=payload.intent,
            )
            data = read_conversation(
                session, tenant_id=tenant_id, actor_id=actor_id, conversation_id=conversation_id
            )
        except C09ContractError as error:
            _fail(error)
    return _envelope(tenant_id, data)


@router.get("/{conversation_id}", response_model=ApiEnvelope[ConversationView])
def conversation_detail(request: Request, conversation_id: UUID):
    session_factory, tenant_id, actor_id = _runtime(request)
    with session_factory() as session:
        _require_catalog_tenant(session, tenant_id)
        try:
            data = read_conversation(
                session, tenant_id=tenant_id, actor_id=actor_id, conversation_id=conversation_id
            )
        except C09ContractError as error:
            _fail(error)
    return _envelope(tenant_id, data)


@router.get("", response_model=ApiEnvelope[list[ConversationView]])
def recent(request: Request, limit: int = Query(default=20, ge=1, le=50)):
    session_factory, tenant_id, actor_id = _runtime(request)
    with session_factory() as session:
        _require_catalog_tenant(session, tenant_id)
        try:
            data = recent_conversations(
                session, tenant_id=tenant_id, actor_id=actor_id, limit=limit
            )
        except C09ContractError as error:
            _fail(error)
    return _envelope(tenant_id, data)


@router.post("/{conversation_id}/reopen", response_model=ApiEnvelope[ConversationView])
def reopen(request: Request, conversation_id: UUID):
    session_factory, tenant_id, actor_id = _runtime(request)
    with session_factory() as session:
        _require_catalog_tenant(session, tenant_id)
        try:
            reopen_conversation(
                session, tenant_id=tenant_id, actor_id=actor_id, conversation_id=conversation_id
            )
            data = read_conversation(
                session, tenant_id=tenant_id, actor_id=actor_id, conversation_id=conversation_id
            )
        except C09ContractError as error:
            _fail(error)
    return _envelope(tenant_id, data)
