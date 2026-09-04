"""Demo-only event simulator and read API."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, status

from backend.app.core.config import Environment
from contracts.api import ApiEnvelope
from contracts.events import CanonicalCommerceEvent

router = APIRouter(prefix="/api/v1", tags=["demo"])


@router.post("/demo/events", status_code=status.HTTP_202_ACCEPTED)
def publish_demo_event(event: CanonicalCommerceEvent, request: Request) -> dict[str, object]:
    if request.app.state.settings.environment != Environment.DEMO:
        raise HTTPException(status_code=403, detail={"code": "POLICY_DENIED"})
    request_id = request.headers.get("x-request-id", f"req_{uuid4().hex}")
    trace_id = request.headers.get("x-trace-id", f"tr_{uuid4().hex}")
    receipt = request.app.state.pipeline.process(
        event.model_dump(mode="json"),
        environment="DEMO",
        request_id=request_id,
        trace_id=trace_id,
    )
    return {
        "event_id": event.event_id,
        "status": receipt.status,
        "request_id": request_id,
        "trace_id": trace_id,
        "correlation_id": event.correlation_id,
    }


@router.get("/insights", response_model=ApiEnvelope[list[dict[str, Any]]])
def insights(request: Request) -> ApiEnvelope[list[dict[str, Any]]]:
    request_id = request.headers.get("x-request-id", f"req_{uuid4().hex}")
    trace_id = request.headers.get("x-trace-id", f"tr_{uuid4().hex}")
    return ApiEnvelope(
        tenant_id=request.app.state.settings.tenant_id,
        request_id=request_id,
        trace_id=trace_id,
        data=request.app.state.pipeline.insights,
        evidence_ids=[
            evidence
            for item in request.app.state.pipeline.insights
            for evidence in item["evidence_ids"]
        ],
        as_of=datetime.now(UTC),
    )
