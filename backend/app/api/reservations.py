"""D09-BE-05 예약 위험 Read API."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Request

from contracts.api import ApiEnvelope


router = APIRouter(
    prefix="/api/v1",
    tags=["reservations"],
)


@router.get(
    "/reservations",
    response_model=ApiEnvelope[
        list[dict[str, Any]]
    ],
)
def reservations(
    request: Request,
) -> ApiEnvelope[
    list[dict[str, Any]]
]:
    request_id = request.headers.get(
        "x-request-id",
        f"req_{uuid4().hex}",
    )

    trace_id = request.headers.get(
        "x-trace-id",
        f"tr_{uuid4().hex}",
    )

    projections = [
        item
        for item in (
            request
            .app
            .state
            .reservation_risk_projections
        )
        if (
            item.tenant_id
            == (
                request
                .app
                .state
                .settings
                .tenant_id
            )
        )
    ]

    data = [
        asdict(item)
        for item in projections
    ]

    evidence_ids = list(
        dict.fromkeys(
            evidence_id
            for item in projections
            for evidence_id
            in item.evidence
        )
    )

    warnings: list[str] = []

    if not projections:
        warnings.append(
            "RESERVATION_RISK_EMPTY:"
            " no usable reservation "
            "risk projection available"
        )

    return ApiEnvelope(
        tenant_id=(
            request
            .app
            .state
            .settings
            .tenant_id
        ),
        request_id=request_id,
        trace_id=trace_id,
        data=data,
        evidence_ids=evidence_ids,
        warnings=warnings,
        as_of=datetime.now(UTC),
    )