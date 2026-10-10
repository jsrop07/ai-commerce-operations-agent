"""D09-BE-05 예약 위험 Read API."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime, time
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select

from contracts.api import ApiEnvelope
from backend.app.api.catalog_v2 import _require_catalog_tenant, _require_v2_runtime
from backend.app.core.config import Environment
from backend.app.models_v2.operations import IncomingShipmentV2, InventorySnapshotV2, ReservationV2
from backend.app.services.c15_synthetic_seed import identity
from backend.app.services.demo_session import COOKIE_NAME, resolve_demo_session
from backend.app.services.reservation_shortage import IncomingEvidence, calculate_reservation_shortage


router = APIRouter(
    prefix="/api/v1",
    tags=["reservations"],
)

KST = ZoneInfo("Asia/Seoul")


class ShortageIncoming(BaseModel):
    external_reference: str | None
    expected_quantity: int
    expected_arrival_at: datetime | None
    incoming_status: str
    confidence_status: str
    treatment: str


class ShortageAnalysis(BaseModel):
    status: str
    source_system: str
    required_quantity: int
    secured_quantity: int | None
    promised_date: str | None
    reservation_quality: str
    baseline_unsecured_quantity: int | None
    conditional_shortage_quantity: int | None
    conditional_incoming_quantity: int
    inventory_data_as_of: datetime | None
    incoming_source_as_of: None
    allocation_verified: bool
    receipt_verified: bool
    incoming: list[ShortageIncoming]
    warnings: list[str]


@router.get("/reservations/shortage-analysis", response_model=ApiEnvelope[ShortageAnalysis])
def shortage_analysis(request: Request) -> ApiEnvelope[ShortageAnalysis]:
    """Read the fixed Synthetic reservation; never create or update a Task."""
    if request.app.state.settings.environment != Environment.DEMO:
        raise HTTPException(status_code=403, detail="RESERVATION_ANALYSIS_DEMO_ONLY")
    if request.query_params:
        raise HTTPException(status_code=422, detail="RESERVATION_ANALYSIS_FILTER_UNSUPPORTED")
    factory, tenant_id, environment = _require_v2_runtime(request)
    # C15's stable identifiers locate the existing scenario without generating seed rows.
    hero_product = identity("product", "9")
    hero_variant = identity("variant", "DEMO-SKU-0009-01")
    with factory() as db:
        _require_catalog_tenant(db, tenant_id, environment)
        if resolve_demo_session(
            db, tenant_id=tenant_id, token=request.cookies.get(COOKIE_NAME), touch=False,
        ) is None:
            raise HTTPException(status_code=401, detail="DEMO_SESSION_REQUIRED")
        reservations = db.scalars(select(ReservationV2).where(
            ReservationV2.tenant_id == tenant_id,
            ReservationV2.product_id == hero_product,
            ReservationV2.product_variant_id == hero_variant,
        )).all()
        if not reservations:
            raise HTTPException(status_code=404, detail="SYNTHETIC_RESERVATION_NOT_FOUND")
        if len(reservations) != 1:
            raise HTTPException(status_code=409, detail="SYNTHETIC_RESERVATION_NOT_UNIQUE")
        reservation = reservations[0]
        incoming = db.scalars(select(IncomingShipmentV2).where(
            IncomingShipmentV2.tenant_id == tenant_id,
            IncomingShipmentV2.product_id == hero_product,
            IncomingShipmentV2.product_variant_id == hero_variant,
            IncomingShipmentV2.source_system == "SYNTHETIC_DEMO",
        ).order_by(IncomingShipmentV2.expected_arrival_at, IncomingShipmentV2.id)).all()
        snapshot = db.scalars(select(InventorySnapshotV2).where(
            InventorySnapshotV2.tenant_id == tenant_id,
            InventorySnapshotV2.product_id == hero_product,
            InventorySnapshotV2.product_variant_id == hero_variant,
            InventorySnapshotV2.source_system == "SYNTHETIC_DEMO",
        ).order_by(InventorySnapshotV2.data_as_of.desc().nulls_last(), InventorySnapshotV2.id)).first()

    warnings = ["NO_RESERVATION_ALLOCATION", "INCOMING_SOURCE_AS_OF_UNAVAILABLE"]
    baseline = None
    conditional = None
    candidates: list[IncomingEvidence] = []
    lines: list[ShortageIncoming] = []
    quality_ok = reservation.source_quality_status == "CONFIRMED"
    if quality_ok:
        baseline = calculate_reservation_shortage(
            required_qty=reservation.required_quantity,
            secured_qty=reservation.secured_quantity,
        ).shortage
    else:
        warnings.append("RESERVATION_QUALITY_UNCONFIRMED")
    promised_end = (datetime.combine(reservation.promised_date, time.max, tzinfo=KST)
                    if reservation.promised_date is not None else None)
    if promised_end is None:
        warnings.append("PROMISED_DATE_UNAVAILABLE")
    for item in incoming:
        arrival = item.expected_arrival_at
        if arrival is not None and arrival.tzinfo is None:
            arrival = arrival.replace(tzinfo=UTC)
        treatment = "EXCLUDED_UNVERIFIED"
        if item.incoming_status == "RECEIVED":
            treatment = "EXCLUDED_RECEIVED_MAY_ALREADY_BE_SECURED"
        elif (quality_ok and promised_end is not None
              and arrival is not None
              and arrival.astimezone(KST) <= promised_end
              and item.incoming_status in {"EXPECTED", "CONFIRMED"}
              and item.confidence_status == "CONFIRMED"):
            treatment = "CONDITIONAL_UNRECEIVED"
            candidates.append(IncomingEvidence(
                evidence_id=str(item.id), quantity=item.expected_quantity,
                confirmation_status="CONFIRMED", quality_status="CONFIRMED",
                freshness="FRESH", source_classification="SYNTHETIC_DEMO",
            ))
        elif arrival is None:
            treatment = "EXCLUDED_DATE_UNKNOWN"
        elif promised_end is not None and arrival.astimezone(KST) > promised_end:
            treatment = "EXCLUDED_AFTER_PROMISE"
        lines.append(ShortageIncoming(
            external_reference=item.external_reference,
            expected_quantity=item.expected_quantity,
            expected_arrival_at=item.expected_arrival_at,
            incoming_status=item.incoming_status,
            confidence_status=item.confidence_status,
            treatment=treatment,
        ))
    if candidates and baseline is not None:
        # FRESH is a counterfactual input here, not an assertion about source freshness.
        conditional = calculate_reservation_shortage(
            required_qty=reservation.required_quantity,
            secured_qty=reservation.secured_quantity,
            incoming=tuple(candidates),
        ).shortage
        warnings.append("CONDITIONAL_ARRIVAL_NOT_RECEIPT")
        if any(item.expected_arrival_at and
               (item.expected_arrival_at if item.expected_arrival_at.tzinfo else
                item.expected_arrival_at.replace(tzinfo=UTC)) < datetime.now(UTC)
               for item in incoming):
            warnings.append("PAST_EXPECTED_ARRIVAL_UNRECEIVED")
    data = ShortageAnalysis(
        status="CONDITIONAL" if conditional is not None else "HOLD",
        source_system="SYNTHETIC_DEMO",
        required_quantity=reservation.required_quantity,
        secured_quantity=reservation.secured_quantity,
        promised_date=reservation.promised_date.isoformat() if reservation.promised_date else None,
        reservation_quality=reservation.source_quality_status,
        baseline_unsecured_quantity=baseline,
        conditional_shortage_quantity=conditional,
        conditional_incoming_quantity=sum(item.quantity or 0 for item in candidates),
        inventory_data_as_of=snapshot.data_as_of if snapshot else None,
        incoming_source_as_of=None,
        allocation_verified=False,
        receipt_verified=False,
        incoming=lines,
        warnings=warnings,
    )
    return ApiEnvelope(
        tenant_id=str(tenant_id), request_id=f"req_{uuid4().hex}",
        trace_id=f"tr_{uuid4().hex}", data=data, as_of=datetime.now(UTC),
        warnings=warnings, evidence_ids=[],
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
