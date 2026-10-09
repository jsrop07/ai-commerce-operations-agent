"""Synthetic Demo 최근 주문일 집계 API (읽기 전용)."""

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import func, select

from backend.app.api.catalog_v2 import (
    _require_catalog_tenant,
    _require_v2_runtime,
)
from backend.app.core.config import Environment
from backend.app.models_v2.operations import OrderV2


router = APIRouter(
    prefix="/api/v1/orders",
    tags=["orders"],
)

KST = ZoneInfo("Asia/Seoul")
SOURCE_SYSTEM = "SYNTHETIC_DEMO"


@router.get("/recent-summary")
def get_recent_order_summary(request: Request):
    """가장 최근 주문이 발생한 KST 날짜의 주문 건수를 집계한다."""

    settings = request.app.state.settings

    # 포트폴리오용 Synthetic Demo에서만 제공한다.
    if settings.environment != Environment.DEMO:
        raise HTTPException(
            status_code=403,
            detail="RECENT_ORDERS_DEMO_ONLY",
        )

    factory, tenant_id, environment = _require_v2_runtime(request)

    with factory() as db:
        # 기존 Catalog V2와 동일한 Tenant 접근 검증
        _require_catalog_tenant(db, tenant_id, environment)

        base_filters = (
            OrderV2.tenant_id == tenant_id,
            OrderV2.source_system == SOURCE_SYSTEM,
        )

        # 가장 최근 주문 발생 시각
        latest_at = db.execute(
            select(func.max(OrderV2.source_order_at))
            .where(*base_filters)
        ).scalar_one()

        recent_date = None
        order_count = None
        status = "NO_DATA"

        if latest_at is not None:
            # PostgreSQL timestamptz는 정상적으로 timezone-aware여야 한다.
            # UTC로 저장된 과거 naive 값은 UTC로 해석한다.
            if latest_at.tzinfo is None:
                latest_at = latest_at.replace(tzinfo=UTC)

            recent_date = latest_at.astimezone(KST).date()

            # 한국 시간 최근 주문일의 시작/종료 경계
            start_kst = datetime.combine(
                recent_date,
                time.min,
                tzinfo=KST,
            )
            end_kst = start_kst + timedelta(days=1)

            start_utc = start_kst.astimezone(UTC)
            end_utc = end_kst.astimezone(UTC)

            # 주문 상품 수량이 아닌 주문 레코드 건수
            order_count = db.execute(
                select(func.count(OrderV2.id))
                .where(
                    *base_filters,
                    OrderV2.source_order_at >= start_utc,
                    OrderV2.source_order_at < end_utc,
                )
            ).scalar_one()

            status = "AVAILABLE"

    now = datetime.now(UTC)

    return {
        "schema_version": "1.0",
        "tenant_id": settings.tenant_id,
        "request_id": f"req_{uuid4().hex}",
        "trace_id": f"tr_{uuid4().hex}",
        "data": {
            "status": status,
            "order_count": order_count,
            "reference_date": (
                recent_date.isoformat()
                if recent_date is not None
                else None
            ),
            "timezone": "Asia/Seoul",
            "source_system": SOURCE_SYSTEM,
            "aggregation": "LATEST_ORDER_DATE",
            "includes_all_order_statuses": True,
        },
        "evidence_ids": [],
        "warnings": (
            []
            if status == "AVAILABLE"
            else ["RECENT_ORDERS_EMPTY"]
        ),
        "as_of": now.isoformat(),
    }