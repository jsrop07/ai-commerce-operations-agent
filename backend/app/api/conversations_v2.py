"""C09 PRE typed conversation API. No AI execution occurs here."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from backend.app.api.catalog_v2 import _require_catalog_tenant, _require_v2_runtime
from backend.app.core.config import Environment
from backend.app.services.c09_view_context import ViewContextInput
from backend.app.services.conversation_v2 import (
    AnalysisKind,
    C09ContractError,
    Intent,
    MessageResponseStatus,
    TargetInput,
    analyze_product_search_turn,
    analyze_turn,
    append_turn,
    create_conversation,
    create_product_search_conversation,
    read_conversation,
    recent_conversations,
    reopen_conversation,
    resolve_target,
    validate_pre_storage,
    classify_operational_question,
)
from contracts.api import ApiEnvelope
from backend.app.services.c24_reservation_context import (
    ReservationContextError,
    resolve_product_reservation_projection,
)
router = APIRouter(prefix="/api/v1/conversations", tags=["conversations-v2"])


class ContextInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: Literal["ENTITY"] = "ENTITY"
    targetType: Literal["PRODUCT", "INCOMING", "TASK"]
    targetId: str = Field(min_length=1, max_length=255)
    targetLabel: str = Field(min_length=1, max_length=255)
    source: str = Field(min_length=1, max_length=64)
    asOf: datetime | None

    def canonical(self) -> TargetInput:
        return TargetInput(self.targetType, self.targetId, self.targetLabel, self.source, self.asOf)


class CreateConversationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    context: ContextInput | ViewContextInput


class AppendTurnInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    context: ContextInput | ViewContextInput
    intent: Intent
    analysis_kind: AnalysisKind | None = None
    request_revision: int | None = Field(default=None, ge=1)

class NaturalQuestionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context: ContextInput
    question: str = Field(min_length=1, max_length=500, strict=True)
    request_revision: int = Field(ge=1)


class ProductSearchTurnInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=200, strict=True)
    intent: Intent
    request_revision: int = Field(ge=1)


class ProductSearchConversationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=200, strict=True)


class ContextView(BaseModel):
    context_revision: int
    scope: Literal["ENTITY", "VIEW"] = "ENTITY"
    page: str | None = None
    filters: dict | None = None
    search: str | None = None
    date_range: dict | None = None
    sort: dict | None = None
    target_type: str | None
    target_id: str | None
    target_label: str | None
    source: str | None
    source_as_of: datetime | None
    data_mode: str | None


class MessageView(BaseModel):
    message_id: str
    message_order: int
    role: Literal["USER", "ASSISTANT"]
    content: str
    response_status: MessageResponseStatus
    intent: Intent | None
    analysis_kind: AnalysisKind | None
    request_message_id: str | None = None
    evidence_ids: list[str]
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
    # Only server middleware may establish ownership through request scope.
    actor_id = request.scope.get("c09_trusted_actor_id")
    if not isinstance(actor_id, str) or not actor_id:
        raise HTTPException(status_code=403, detail="C09_TRUSTED_ACTOR_REQUIRED")
    environment = request.app.state.settings.environment
    if environment not in {Environment.LOCAL, Environment.TEST, Environment.DEMO}:
        raise HTTPException(status_code=403, detail="C09_ENVIRONMENT_FORBIDDEN")
    if environment == Environment.DEMO and request.scope.get("c22_demo_session_id") is None:
        raise HTTPException(status_code=403, detail="C09_TRUSTED_ACTOR_REQUIRED")
    session_factory, tenant_id, _ = _require_v2_runtime(request)
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


def _canonical_context(context: ContextInput | ViewContextInput):
    return context.canonical() if isinstance(context, ContextInput) else context


@router.post("", response_model=ApiEnvelope[ConversationView], status_code=201)
def new_conversation(request: Request, payload: CreateConversationInput):
    session_factory, tenant_id, actor_id = _runtime(request)
    with session_factory() as session:
        _require_catalog_tenant(session, tenant_id, request.app.state.settings.environment)
        try:
            row = create_conversation(
                session, tenant_id=tenant_id, actor_id=actor_id,
                target=_canonical_context(payload.context)
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
        _require_catalog_tenant(session, tenant_id, request.app.state.settings.environment)
        try:
            if payload.analysis_kind is None and payload.request_revision is None:
                append_turn(
                    session,
                    tenant_id=tenant_id,
                    actor_id=actor_id,
                    conversation_id=conversation_id,
                    target=_canonical_context(payload.context),
                    intent=payload.intent,
                )
            elif (
                payload.analysis_kind not in (None, "NONE")
                and payload.request_revision is not None
            ):
                reservation_projection = None
                canonical_context = _canonical_context(
                    payload.context
                )
                validate_pre_storage(
                    actor_id,
                    canonical_context,
                    payload.intent,
                )
                if (
                    getattr(
                        canonical_context,
                        "target_type",
                        None,
                    )
                    == "PRODUCT"
                ):
                    resolved = resolve_target(
                        session,
                        tenant_id=tenant_id,
                        target=canonical_context,
                    )

                    if resolved.product_id is not None:
                        try:
                            reservation_projection = (
                                resolve_product_reservation_projection(
                                    session,
                                    tenant_id=tenant_id,
                                    projection_tenant_id=(
                                        request.app.state.settings.tenant_id
                                    ),
                                    product_id=resolved.product_id,
                                    projections=(
                                        request.app.state
                                        .reservation_risk_projections
                                    ),
                                )
                            )
                        except ReservationContextError:
                            reservation_projection = None
                analyze_turn(
                    session,
                    tenant_id=tenant_id,
                    actor_id=actor_id,
                    conversation_id=conversation_id,
                    target=canonical_context,
                    intent=payload.intent,
                    analysis_kind=payload.analysis_kind,
                    request_revision=payload.request_revision,
                    session_factory=session_factory,
                    demo_session_id=(
                        request.scope.get(
                            "c22_demo_session_id"
                        )
                    ),
                    settings=request.app.state.settings,
                    reservation_projection=reservation_projection,
                    neo4j_driver=getattr(request.app.state, "neo4j_driver", None),
                )
            else:
                raise C09ContractError("HOLD", "INCOMPLETE_ANALYSIS_REQUEST")
            data = read_conversation(
                session, tenant_id=tenant_id, actor_id=actor_id, conversation_id=conversation_id
            )
        except C09ContractError as error:
            _fail(error)
    return _envelope(tenant_id, data)

@router.post(
    "/{conversation_id}/questions",
    response_model=ApiEnvelope[ConversationView],
)
def append_natural_question(
    request: Request,
    conversation_id: UUID,
    payload: NaturalQuestionInput,
):
    session_factory, tenant_id, actor_id = _runtime(request)

    # 어떠한 질문 메시지도 저장하기 전에 검증한다.
    try:
        analysis_kind, _ = classify_operational_question(payload.question)
    except C09ContractError as error:
        _fail(error)

    target = payload.context.canonical()
    # Non-Product questions can be saved in the owned conversation, but the
    # existing grounded analysis routes are Product-only. Return a local HOLD.
    if target.target_type != "PRODUCT":
        analysis_kind = "DETERMINISTIC"
    
    with session_factory() as session:
        _require_catalog_tenant(
            session,
            tenant_id,
            request.app.state.settings.environment,
        )

        try:
            analyze_turn(
                session,
                tenant_id=tenant_id,
                actor_id=actor_id,
                conversation_id=conversation_id,
                target=target,
                intent="INSPECT_TARGET",
                analysis_kind=analysis_kind,
                request_revision=payload.request_revision,
                session_factory=session_factory,
                demo_session_id=request.scope.get("c22_demo_session_id"),
                settings=request.app.state.settings,
                neo4j_driver=getattr(
                    request.app.state, "neo4j_driver", None
                ),
                question=payload.question,
            )

            data = read_conversation(
                session,
                tenant_id=tenant_id,
                actor_id=actor_id,
                conversation_id=conversation_id,
            )

        except C09ContractError as error:
            _fail(error)

    return _envelope(tenant_id, data)

@router.post(
    "/product-search", response_model=ApiEnvelope[ConversationView], status_code=201,
)
def new_product_search_conversation(request: Request, payload: ProductSearchConversationInput):
    session_factory, tenant_id, actor_id = _runtime(request)
    with session_factory() as session:
        _require_catalog_tenant(session, tenant_id, request.app.state.settings.environment)
        try:
            row = create_product_search_conversation(
                session, tenant_id=tenant_id, actor_id=actor_id,
                query=payload.query,
                search_service=getattr(request.app.state, "product_search_service", None),
            )
            data = read_conversation(
                session, tenant_id=tenant_id, actor_id=actor_id, conversation_id=row.id,
            )
        except C09ContractError as error:
            _fail(error)
    return _envelope(tenant_id, data)


@router.post(
    "/{conversation_id}/product-search/messages",
    response_model=ApiEnvelope[ConversationView],
)
def append_product_search_message(
    request: Request, conversation_id: UUID, payload: ProductSearchTurnInput,
):
    session_factory, tenant_id, actor_id = _runtime(request)
    with session_factory() as session:
        _require_catalog_tenant(session, tenant_id, request.app.state.settings.environment)
        try:
            analyze_product_search_turn(
                session, tenant_id=tenant_id, actor_id=actor_id,
                conversation_id=conversation_id, query=payload.query,
                intent=payload.intent, request_revision=payload.request_revision,
                search_service=getattr(request.app.state, "product_search_service", None),
            )
            data = read_conversation(
                session, tenant_id=tenant_id, actor_id=actor_id, conversation_id=conversation_id,
            )
        except C09ContractError as error:
            _fail(error)
    return _envelope(tenant_id, data)


@router.get("/{conversation_id}", response_model=ApiEnvelope[ConversationView])
def conversation_detail(request: Request, conversation_id: UUID):
    session_factory, tenant_id, actor_id = _runtime(request)
    with session_factory() as session:
        _require_catalog_tenant(session, tenant_id, request.app.state.settings.environment)
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
        _require_catalog_tenant(session, tenant_id, request.app.state.settings.environment)
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
        _require_catalog_tenant(session, tenant_id, request.app.state.settings.environment)
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
