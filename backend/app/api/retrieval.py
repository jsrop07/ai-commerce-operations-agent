"""Synthetic retrieval citations only; no generated answer or external action."""

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import AwareDatetime, BaseModel
from starlette.concurrency import run_in_threadpool

from backend.app.services.c04_lookup import SourceType
from backend.app.services.retrieval_runtime import RetrievalFailure, SearchInput
from backend.app.services.retrieval_summary import DevSummary, SummaryFailure, load_summary
from contracts.api import ApiEnvelope

router = APIRouter(prefix="/api/v1/retrieval", tags=["retrieval"])


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
