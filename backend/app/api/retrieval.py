"""Synthetic retrieval and guarded C06 policy explanation endpoints."""

import json
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError
from starlette.concurrency import run_in_threadpool

from ai.services.grounded_explanation_provider import DEFAULT_CONFIG_PATH
from backend.app.core.config import Environment
from backend.app.services.actual_retrieval_summary import (
    ActualSummary,
    ActualSummaryFailure,
    load_actual_summary,
)
from backend.app.services.c04_lookup import SourceType
from backend.app.services.demo_provider_quota import (
    DemoQuotaDenied,
    QuotaLimits,
    call_with_demo_quota,
)
from backend.app.services.grounded_explanation_bridge import (
    explain_policy,
    forbidden_structure,
    hold,
)
from backend.app.services.retrieval_runtime import RetrievalFailure, SearchInput
from backend.app.services.retrieval_summary import DevSummary, SummaryFailure, load_summary
from contracts.api import ApiEnvelope

router = APIRouter(prefix="/api/v1/retrieval", tags=["retrieval"])


class ExplanationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=2000)
    condition: Literal["BASIC", "CITATION"] = "CITATION"
    scope: Literal["POLICY_ONLY", "C02_AGGREGATE"] = "POLICY_ONLY"


class ExplanationResponse(BaseModel):
    status: Literal["ANSWER", "HOLD"]
    conclusion: str
    used_facts: list[str]
    used_numeric_facts: list[dict]
    citations: list[dict]
    next_check: str | None
    model_used: bool
    data_mode: str
    request_id: str
    warnings: list[str]
    c04_lookup: list[dict]


class C04Key(BaseModel):
    source_id: str
    version: str
    chunk_id: str


class SearchCitation(BaseModel):
    rank: int
    score: float
    source_type: SourceType
    source_id: str
    title: str
    version: str
    semantic_chunk_id: str
    semantic_excerpt: str
    semantic_excerpt_hash: str
    as_of: AwareDatetime | None
    c04_lookup: C04Key | None
    c04_excerpt_hash: str | None
    mapping_status: Literal["MAPPED", "MAPPING_MISSING"]


class SearchProjection(BaseModel):
    method: str
    selection_status: str
    data_mode: Literal["SYNTHETIC_DEMO"]
    index_version: str
    actual_retrieval_executed: Literal[True]
    citations: list[SearchCitation]
    result_status: Literal["RESULTS", "ZERO_CITATIONS"]
    answer_status: str
    warnings: list[str]
    required_lookup: list[str]
    human_review_required: bool
    human_review_reason: list[str]


class SearchError(BaseModel):
    detail: str


@router.get("/summary", response_model=ApiEnvelope[DevSummary], responses={
    403: {"model": SearchError, "description": "Synthetic DEV scope only"},
    422: {"model": SearchError, "description": "No query parameters or body accepted"},
    503: {"model": SearchError, "description": "Artifact unavailable or invalid"},
})
async def summary(request: Request):
    if request.query_params or await request.body():
        raise HTTPException(422, "RETRIEVAL_SUMMARY_INPUT_FORBIDDEN")
    settings = request.app.state.settings
    if settings.environment.value not in {"TEST", "LOCAL", "DEMO"}:
        raise HTTPException(403, "RETRIEVAL_SUMMARY_DEMO_ONLY")
    runtime = getattr(request.app.state, "retrieval_runtime", None)
    available = bool(runtime and runtime.corpus and runtime.corpus.status == "READY"
                     and runtime.corpus.search_rows and runtime.method == "BM25"
                     and runtime.tenant_id == settings.tenant_id)
    try:
        data = await run_in_threadpool(
            load_summary, tenant_id=settings.tenant_id, runtime_search_available=available,
        )
    except SummaryFailure as exc:
        raise HTTPException(503, str(exc)) from None
    return ApiEnvelope(tenant_id=settings.tenant_id, request_id=f"req_{uuid4().hex}",
                       trace_id=f"tr_{uuid4().hex}", data=data, as_of=datetime.now(UTC))


@router.get("/actual-summary", response_model=ActualSummary, responses={
    403: {"model": SearchError, "description": "Private evaluation scope only"},
    422: {"model": SearchError, "description": "No query parameters or body accepted"},
    503: {"model": SearchError, "description": "Aggregate artifact unavailable or invalid"},
})
async def actual_summary(request: Request):
    if request.query_params or await request.body():
        raise HTTPException(422, "ACTUAL_SUMMARY_INPUT_FORBIDDEN")
    if request.app.state.settings.environment.value not in {"TEST", "LOCAL"}:
        raise HTTPException(403, "ACTUAL_SUMMARY_PRIVATE_ONLY")
    try:
        return await run_in_threadpool(load_actual_summary)
    except ActualSummaryFailure as exc:
        raise HTTPException(503, str(exc)) from None


@router.post("/search", response_model=ApiEnvelope[SearchProjection], responses={
    403: {"model": SearchError, "description": "Query safety blocked before retrieval"},
    503: {"model": SearchError, "description": "Runtime or index unavailable/busy"},
    504: {"model": SearchError, "description": "Retrieval deadline exceeded"},
})
async def search(body: SearchInput, request: Request):
    runtime = getattr(request.app.state, "retrieval_runtime", None)
    if runtime is None:
        raise HTTPException(503, "RETRIEVAL_RUNTIME_UNAVAILABLE")
    try:
        result, projection = await runtime.search(body)
    except RetrievalFailure as exc:
        raise HTTPException(exc.status, exc.code) from None
    return ApiEnvelope(
        tenant_id=request.app.state.settings.tenant_id,
        request_id=result.request_id, trace_id=result.trace_id,
        data=projection, warnings=list(result.warnings), as_of=datetime.now(UTC),
    )


@router.post("/explanations", response_model=ApiEnvelope[ExplanationResponse])
async def explain(request: Request):
    request_id = f"req_{uuid4().hex}"
    settings = request.app.state.settings
    quota_call = None
    if settings.environment == Environment.DEMO:
        session_id = request.scope.get("c22_demo_session_id")
        factory = request.app.state.v2_db_session_factory
        if session_id is None or settings.v2_tenant_id is None or factory is None:
            data = hold("C24_SESSION_REQUIRED", "SYNTHETIC_DEMO", request_id)
            return ApiEnvelope(tenant_id=settings.tenant_id, request_id=request_id,
                               trace_id=f"tr_{uuid4().hex}", data=data,
                               as_of=datetime.now(UTC))
        try:
            limits = QuotaLimits.from_settings(settings)
            config = json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
            model = config["model"]
            calls = 1 + int(config["max_retries"])
            input_tokens = settings.demo_quota_reserve_input_tokens
            output_tokens = settings.demo_quota_reserve_output_tokens
            if (config.get("provider") != "openai" or not model or calls < 1
                    or input_tokens is None or output_tokens is None
                    or input_tokens < 1
                    or output_tokens < calls * int(config["max_output_tokens"])):
                raise DemoQuotaDenied("C24_QUOTA_UNCONFIGURED")
            def quota_call(provider_call):
                return call_with_demo_quota(
                    provider_call, factory=factory, tenant_id=settings.v2_tenant_id,
                    session_id=session_id, request_id=request_id, model=model,
                    calls=calls, input_tokens=input_tokens,
                    output_tokens=output_tokens, limits=limits,
                )
        except (DemoQuotaDenied, ValueError, KeyError, OSError, TypeError):
            data = hold("C24_QUOTA_UNCONFIGURED", "SYNTHETIC_DEMO", request_id)
            return ApiEnvelope(tenant_id=settings.tenant_id, request_id=request_id,
                               trace_id=f"tr_{uuid4().hex}", data=data,
                               as_of=datetime.now(UTC))
    try:
        raw = await request.json()
    except ValueError:
        raise HTTPException(422, "C06_REQUEST_INVALID") from None
    if not isinstance(raw, dict):
        raise HTTPException(422, "C06_REQUEST_INVALID")
    if forbidden_structure(raw):
        return ApiEnvelope(tenant_id=settings.tenant_id, request_id=request_id,
                           trace_id=f"tr_{uuid4().hex}",
                           data=hold("FORBIDDEN_INPUT", "SYNTHETIC_DEMO", request_id),
                           as_of=datetime.now(UTC))
    if set(raw) - {"question", "condition", "scope"}:
        raise HTTPException(422, "C06_REQUEST_INVALID")
    try:
        body = ExplanationRequest.model_validate(raw)
    except ValidationError:
        raise HTTPException(422, "C06_REQUEST_INVALID") from None
    if body.scope == "C02_AGGREGATE":
        data = hold("NOT_SUPPORTED_C02_RUNTIME_SOURCE_MISSING",
                    "SYNTHETIC_DEMO", request_id)
    else:
        runtime = getattr(request.app.state, "retrieval_runtime", None)
        if runtime is None:
            data = hold("RUNTIME_UNAVAILABLE", "SYNTHETIC_DEMO", request_id)
        else:
            try:
                _, projection = await runtime.search(SearchInput(query=body.question))
                data = await run_in_threadpool(
                    explain_policy, question=body.question, condition=body.condition,
                    projection=projection,
                    lookup_service=request.app.state.c04_lookup_service,
                    tenant_id=settings.tenant_id, request_id=request_id,
                    provider=getattr(request.app.state, "c06_provider", None),
                    settings=settings, quota_call=quota_call,
                )
            except RetrievalFailure as exc:
                reason = ("NO_SOURCE" if exc.code == "RETRIEVAL_INDEX_UNAVAILABLE"
                          else "FORBIDDEN_INPUT" if exc.status == 403
                          else "RUNTIME_UNAVAILABLE")
                data = hold(reason, "SYNTHETIC_DEMO", request_id)
    return ApiEnvelope(tenant_id=settings.tenant_id, request_id=request_id,
                       trace_id=f"tr_{uuid4().hex}", data=data,
                       as_of=datetime.now(UTC))
