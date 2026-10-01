"""Demo-only event simulator and read API."""

import json
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, status

from backend.app.core.config import Environment
from backend.app.services.c04_lookup import C04LookupService
from backend.app.services.demo import prepare_synthetic_reservations
from contracts.api import ApiEnvelope
from contracts.events import CanonicalCommerceEvent, EventType

router = APIRouter(prefix="/api/v1", tags=["demo"])


@router.post("/demo/reservations/prepare")
async def prepare_demo_reservations(request: Request) -> dict[str, object]:
    """Explicit in-memory Day9 reservation preparation for Synthetic Demo."""
    settings = request.app.state.settings
    if settings.environment != Environment.DEMO:
        raise HTTPException(status_code=403, detail={"code": "POLICY_DENIED"})
    if request.query_params or await request.body():
        raise HTTPException(status_code=422, detail="DEMO_RESERVATION_INPUT_FORBIDDEN")
    try:
        created, total = prepare_synthetic_reservations(
            request.app.state, tenant_id=settings.tenant_id,
        )
    except ValueError:
        raise HTTPException(status_code=409, detail="DEMO_RESERVATION_CONFLICT") from None
    return {
        "status": "READY" if created else "ALREADY_READY",
        "data_mode": "SYNTHETIC_DEMO",
        "tenant_id": settings.tenant_id,
        "created_count": created,
        "row_count": total,
        "request_id": request.headers.get("x-request-id", f"req_{uuid4().hex}"),
    }


def _demo_inventory_source_id(tenant_id: str, insight_id: str) -> str:
    identity = json.dumps([tenant_id, insight_id], ensure_ascii=False).encode("utf-8")
    return f"demo_inventory_{sha256(identity).hexdigest()}"


def _register_demo_inventory(request: Request, insight: dict[str, Any]) -> None:
    """Optional handoff: only the calculation allowlist crosses into C04."""
    try:
        settings = request.app.state.settings
        if settings.environment != Environment.DEMO or insight["type"] != "INVENTORY_RISK":
            return
        service = request.app.state.c04_lookup_service
        if not isinstance(service, C04LookupService):
            return
        calculation = insight["calculation"]
        content = {name: calculation[name] for name in (
            "starting_inventory", "sold", "expected_inventory",
        )}
        if any(type(value) is not int for value in content.values()):
            return
        if insight["rule_version"] != "shadow-inventory-v1":
            return
        content["rule_version"] = insight["rule_version"]
        result = service.register_demo_record(
            {
                "tenant_id": settings.tenant_id,
                "source_id": _demo_inventory_source_id(settings.tenant_id, insight["insight_id"]),
                "source_type": "INVENTORY_SNAPSHOT",
                "title": "Synthetic Demo offline-sale inventory calculation",
                "version": "v1", "as_of": datetime.now(UTC),
                "pii_status": "CLEAN", "data_mode": "SYNTHETIC_DEMO",
                "visibility": "DEMO_PUBLIC",
                "content": json.dumps(content, sort_keys=True, ensure_ascii=False),
            },
            environment=settings.environment, tenant_id=settings.tenant_id,
        )
        insight["c04_lookup"] = {
            "source_id": result.source_id, "version": result.version, "chunk_id": result.chunk_id,
        }
    except Exception:
        # This optional projection must never turn completed ingestion into a failure.
        # Do not log the record, event payload or exception text.
        return


def _insight_with_verified_lookup(request: Request, insight: dict[str, Any]) -> dict[str, Any]:
    result = {key: value for key, value in insight.items() if key != "c04_lookup"}
    try:
        settings = request.app.state.settings
        if settings.environment != Environment.DEMO:
            return result
        key = insight.get("c04_lookup")
        if not isinstance(key, dict) or set(key) != {"source_id", "version", "chunk_id"}:
            return result
        source_id = _demo_inventory_source_id(settings.tenant_id, insight["insight_id"])
        if key != {"source_id": source_id, "version": "v1", "chunk_id": f"{source_id}:v1:c04:0"}:
            return result
        service = request.app.state.c04_lookup_service
        if not isinstance(service, C04LookupService):
            return result
        service.lookup(tenant_id=settings.tenant_id, **key)
        result["c04_lookup"] = dict(key)
    except Exception:
        # Fail closed for the optional key without hiding the existing insight.
        pass
    return result


@router.post("/demo/events", status_code=status.HTTP_202_ACCEPTED)
def publish_demo_event(event: CanonicalCommerceEvent, request: Request) -> dict[str, object]:
    if request.app.state.settings.environment != Environment.DEMO:
        raise HTTPException(status_code=403, detail={"code": "POLICY_DENIED"})
    request_id = request.headers.get("x-request-id", f"req_{uuid4().hex}")
    trace_id = request.headers.get("x-trace-id", f"tr_{uuid4().hex}")
    pipeline = request.app.state.pipeline
    first_new_insight = len(pipeline.insights)
    receipt = request.app.state.pipeline.process(
        event.model_dump(mode="json"),
        environment="DEMO",
        request_id=request_id,
        trace_id=trace_id,
    )
    if (
        event.event_type == EventType.OFFLINE_SALE_RECORDED
        and event.tenant_id == request.app.state.settings.tenant_id
    ):
        for insight in pipeline.insights[first_new_insight:]:
            if insight.get("insight_id") == f"ins_{event.event_id}":
                _register_demo_inventory(request, insight)
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
        data=[
            _insight_with_verified_lookup(request, item)
            for item in request.app.state.pipeline.insights
        ],
        evidence_ids=[
            evidence
            for item in request.app.state.pipeline.insights
            for evidence in item["evidence_ids"]
        ],
        as_of=datetime.now(UTC),
    )
