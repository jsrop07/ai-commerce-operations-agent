"""Read-only Backend inventory projection API."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Request

from contracts.api import ApiEnvelope

router = APIRouter(
    prefix="/api/v1",
    tags=["inventory"],
)


@router.get(
    "/inventory",
    response_model=ApiEnvelope[list[dict[str, Any]]],
)
def inventory(
    request: Request,
) -> ApiEnvelope[list[dict[str, Any]]]:
    request_id = request.headers.get(
        "x-request-id",
        f"req_{uuid4().hex}",
    )
    trace_id = request.headers.get(
        "x-trace-id",
        f"tr_{uuid4().hex}",
    )

    pipeline = request.app.state.pipeline
    if (
        pipeline.db_session_factory is not None
        and not pipeline.inventory_projections
    ):
        pipeline.rebuild_inventory_projections(
            tenant_id=request.app.state.settings.tenant_id,
        )

    projections = [
        projection
        for projection in request.app.state.inventory_projections
        if projection.tenant_id == request.app.state.settings.tenant_id
    ]

    data = [asdict(projection) for projection in projections]

    evidence_ids = [
        evidence_id for projection in projections for evidence_id in projection.evidence
    ]

    warnings: list[str] = []

    if not data:
        warnings.append(
            "INVENTORY_PROJECTION_EMPTY:"
            " usable actual inventory "
            "projection is not available"
        )

    return ApiEnvelope(
        tenant_id=request.app.state.settings.tenant_id,
        request_id=request_id,
        trace_id=trace_id,
        data=data,
        evidence_ids=evidence_ids,
        warnings=warnings,
        as_of=datetime.now(UTC),
    )
