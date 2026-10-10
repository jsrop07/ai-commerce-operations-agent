"""Read-only, request-time Demo operations queue from stored facts and rules."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select

from contracts.api import ApiEnvelope
from backend.app.api.catalog_v2 import _require_catalog_tenant, _require_v2_runtime
from backend.app.api.inventory import _demo_inventory_projections
from backend.app.api.reservations import shortage_analysis
from backend.app.core.config import Environment
from backend.app.models_v2.catalog import ProductV2
from backend.app.models_v2.operations import IncomingShipmentV2, ReservationV2, TaskIncomingDependencyV2, TaskV2
from backend.app.services.c15_synthetic_seed import identity
from backend.app.services.demo_session import COOKIE_NAME, resolve_demo_session

router = APIRouter(prefix="/api/v1", tags=["dashboard"])


class QueueItem(BaseModel):
    id: str
    kind: Literal["CONDITIONAL_RESERVATION", "INVENTORY_STALE", "TASK_REVIEW"]
    state: Literal["CONDITIONAL", "DATA_STALE", "REVIEW_PENDING"]
    priority: Literal["HIGH", "MEDIUM", "LOW"] | None
    title: str
    reason: str
    evidence_ids: list[str]
    source_as_of: datetime | None
    target_path: Literal["/inventory", "/schedule"]
    target_id: str | None
    task_status: str | None = None
    task_due_at: datetime | None = None


class QueueData(BaseModel):
    status: Literal["READY", "NO_DATA", "CLEAR", "ANALYSIS_UNAVAILABLE"]
    calculation_mode: Literal["ON_REQUEST"] = "ON_REQUEST"
    items: list[QueueItem]
    source_counts: dict[str, int]


@router.get("/dashboard/urgent-queue", response_model=ApiEnvelope[QueueData])
def demo_urgent_queue(request: Request) -> ApiEnvelope[QueueData]:
    """Classify existing Demo facts on each GET; do not persist findings or call AI."""
    if request.app.state.settings.environment != Environment.DEMO:
        raise HTTPException(status_code=403, detail="QUEUE_DEMO_ONLY")
    if request.query_params:
        raise HTTPException(status_code=422, detail="QUEUE_FILTER_UNSUPPORTED")
    factory, tenant_id, environment = _require_v2_runtime(request)
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
        product_name = db.scalar(select(ProductV2.product_name).where(
            ProductV2.tenant_id == tenant_id, ProductV2.id == hero_product,
        ))
        task_rows = db.execute(
            select(TaskV2, IncomingShipmentV2)
            .join(TaskIncomingDependencyV2,
                  (TaskIncomingDependencyV2.tenant_id == TaskV2.tenant_id)
                  & (TaskIncomingDependencyV2.task_id == TaskV2.id))
            .join(IncomingShipmentV2,
                  (IncomingShipmentV2.tenant_id == TaskIncomingDependencyV2.tenant_id)
                  & (IncomingShipmentV2.id == TaskIncomingDependencyV2.incoming_shipment_id))
            .where(TaskV2.tenant_id == tenant_id,
                   TaskV2.product_id == hero_product,
                   TaskV2.task_type == "RESERVATION_SHORTAGE",
                   IncomingShipmentV2.source_system == "SYNTHETIC_DEMO",
                   IncomingShipmentV2.product_variant_id == hero_variant)
            .order_by(TaskV2.id, IncomingShipmentV2.id)
        ).all()

    inventory = _demo_inventory_projections(request)
    items: list[QueueItem] = []
    warnings: list[str] = []
    if len(reservations) == 1:
        analysis = shortage_analysis(request).data
        if analysis.baseline_unsecured_quantity is not None and analysis.baseline_unsecured_quantity > 0:
            projection_text = (
                f"예정 입고 {analysis.conditional_incoming_quantity}개가 사용·배분되면 "
                f"잔여 {analysis.conditional_shortage_quantity}개입니다. 수령·배분은 미확인입니다."
                if analysis.conditional_shortage_quantity is not None else
                "예정 입고를 반영한 잔여 수량은 판정할 수 없습니다."
            )
            items.append(QueueItem(
                id=f"reservation:{reservations[0].id}", kind="CONDITIONAL_RESERVATION",
                state="CONDITIONAL", priority="MEDIUM",
                title=f"{product_name or '상품명 확인 필요'} · 예약 수량 확보 검토",
                reason=(f"필요 {analysis.required_quantity}개, 확보 {analysis.secured_quantity}개. "
                        f"현재 미확보 {analysis.baseline_unsecured_quantity}개이며, {projection_text}"),
                evidence_ids=[f"operations.reservations:{reservations[0].id}"],
                source_as_of=None, target_path="/schedule", target_id=str(reservations[0].id),
            ))
        elif analysis.baseline_unsecured_quantity is None:
            warnings.append("RESERVATION_ANALYSIS_HOLD")
    elif len(reservations) > 1:
        warnings.append("RESERVATION_SOURCE_AMBIGUOUS")

    for projection in inventory:
        if projection.freshness != "FRESH" or not projection.confirmed_for_total:
            items.append(QueueItem(
                id=f"inventory:{projection.sku_id}", kind="INVENTORY_STALE",
                state="DATA_STALE", priority="MEDIUM",
                title=f"{projection.sku_id} · 재고 기준 확인 필요",
                reason="재고 Snapshot의 최신성 또는 품질이 확인되지 않아 현재 재고 위험을 판정할 수 없습니다.",
                evidence_ids=list(projection.evidence), source_as_of=projection.as_of,
                target_path="/inventory", target_id=projection.sku_id,
            ))

    seen_tasks: set[str] = set()
    for task, incoming in task_rows:
        if str(task.id) in seen_tasks or task.task_status not in {"PROPOSED", "BLOCKED"}:
            continue
        seen_tasks.add(str(task.id))
        items.append(QueueItem(
            id=f"task:{task.id}", kind="TASK_REVIEW", state="REVIEW_PENDING",
            priority=None, title="등록된 예약 검토 Task",
            reason=(f"{task.task_status} 상태의 기존 Task입니다. 입고 {incoming.external_reference or incoming.id}와 "
                    "시나리오 참조 관계가 있으며 부족 계산으로 자동 생성된 결과는 아닙니다."),
            evidence_ids=[f"operations.tasks:{task.id}", f"operations.incoming_shipments:{incoming.id}"],
            source_as_of=None, target_path="/schedule", target_id=str(task.id),
            task_status=task.task_status, task_due_at=task.due_at,
        ))

    counts = {"reservations": len(reservations), "inventory_snapshots": len(inventory),
              "linked_tasks": len(seen_tasks)}
    status: Literal["READY", "NO_DATA", "CLEAR", "ANALYSIS_UNAVAILABLE"] = (
        "ANALYSIS_UNAVAILABLE" if warnings else
        "READY" if items else "NO_DATA" if not any(counts.values()) else "CLEAR"
    )
    items.sort(key=lambda item: ({"HIGH": 0, "MEDIUM": 1, "LOW": 2, None: 3}[item.priority], item.id))
    return ApiEnvelope(
        tenant_id=str(tenant_id), request_id=f"req_{uuid4().hex}",
        trace_id=f"tr_{uuid4().hex}", as_of=datetime.now(UTC),
        evidence_ids=[], warnings=warnings,
        data=QueueData(status=status, items=items, source_counts=counts),
    )
