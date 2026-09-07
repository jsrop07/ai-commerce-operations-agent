"""Read-only mapping review API."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Request

from backend.app.services.ingestion.mapping_projection import (
    build_mapping_read_projection,
)
from contracts.api import ApiEnvelope

router = APIRouter(
    prefix="/api/v1",
    tags=["mappings"],
)


@router.get(
    "/mappings",
    response_model=ApiEnvelope[list[dict[str, Any]]],
)
def mappings(
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

    projection = build_mapping_read_projection(
        queue=request.app.state.mapping_queue,
    )

    projection = [
        item for item in projection if item.tenant_id == request.app.state.settings.tenant_id
    ]

    return ApiEnvelope(
        tenant_id=request.app.state.settings.tenant_id,
        request_id=request_id,
        trace_id=trace_id,
        data=[asdict(item) for item in projection],
        evidence_ids=[item.source_identity_key for item in projection],
        as_of=datetime.now(UTC),
    )
