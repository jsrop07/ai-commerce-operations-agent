"""Read-only Backend inventory projection API."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from backend.app.core.config import Environment
from backend.app.models_v2.catalog import ProductV2, ProductVariantV2
from backend.app.models_v2.operations import InventorySnapshotV2
from backend.app.services.inventory_projection import build_inventory_projection
from contracts.api import ApiEnvelope
from backend.app.api.catalog_v2 import (
    _require_v2_runtime,
    _require_catalog_tenant,
)

router = APIRouter(
    prefix="/api/v1",
    tags=["inventory"],
)


def _demo_inventory_projections(request: Request):
    """Read only tenant-scoped synthetic V2 snapshots; never use the legacy pipeline."""
    settings = request.app.state.settings

    # Catalog V2와 동일한 DB 및 Tenant 접근 정책을 적용한다.
    factory, tenant_id, environment = _require_v2_runtime(request)

    with factory() as db:
        _require_catalog_tenant(db, tenant_id, environment)

        rows = db.execute(
            select(InventorySnapshotV2, ProductV2, ProductVariantV2)
            .join(ProductV2, (ProductV2.tenant_id == InventorySnapshotV2.tenant_id)
                  & (ProductV2.id == InventorySnapshotV2.product_id))
            .join(ProductVariantV2, (ProductVariantV2.tenant_id == InventorySnapshotV2.tenant_id)
                  & (ProductVariantV2.id == InventorySnapshotV2.product_variant_id)
                  & (ProductVariantV2.product_id == ProductV2.id))
            .where(InventorySnapshotV2.tenant_id == tenant_id,
                   InventorySnapshotV2.source_system == "SYNTHETIC_DEMO",
                   ProductV2.product_code.like("DEMO-P-%"),
                   ProductVariantV2.variant_code.like("DEMO-SKU-%"))
            .order_by(InventorySnapshotV2.data_as_of.desc(),
                      InventorySnapshotV2.created_at.desc(), InventorySnapshotV2.id.desc())
        ).all()
        latest = {}
        for snapshot, _product, variant in rows:
            latest.setdefault(variant.variant_code, snapshot)

    now = datetime.now(UTC)
    projections = []
    for sku_id, snapshot in latest.items():
        as_of = snapshot.data_as_of
        if as_of is not None and as_of.tzinfo is None:
            as_of = as_of.replace(tzinfo=UTC)
        # V2 stores no freshness TTL. Treat historical snapshots as stale rather
        # than claiming that their quantity is confirmed current inventory.
        age_seconds = max(0, int((now - as_of).total_seconds())) if as_of else 1
        projections.append(build_inventory_projection(
            tenant_id=settings.tenant_id, sku_id=sku_id,
            source_on_hand=snapshot.on_hand_quantity, ledger_delta=0,
            reserved=snapshot.reserved_quantity, confirmed_incoming=None,
            quality_status=snapshot.data_quality_status,
            ttl_seconds=0, age_seconds=age_seconds,
            provider="SYNTHETIC_DEMO", as_of=as_of,
            risk_level="UNKNOWN", evidence=(f"operations.inventory_snapshots:{snapshot.id}",),
        ))
    return projections


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

    if (request.app.state.settings.environment == Environment.DEMO
            and request.app.state.db_session_factory is None):
        projections = _demo_inventory_projections(request)
    else:
        pipeline = request.app.state.pipeline
        if pipeline.db_session_factory is not None and not pipeline.inventory_projections:
            pipeline.rebuild_inventory_projections(
                tenant_id=request.app.state.settings.tenant_id,
            )
        projections = [
            projection for projection in request.app.state.inventory_projections
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
