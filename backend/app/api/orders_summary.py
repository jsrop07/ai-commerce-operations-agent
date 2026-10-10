"""Synthetic Demo 최근 주문일 집계 API (읽기 전용)."""

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Literal
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, select

from backend.app.api.catalog_v2 import (
    _require_catalog_tenant,
    _require_v2_runtime,
)
from backend.app.core.config import Environment
from backend.app.models_v2.catalog import ProductVariantV2
from backend.app.models_v2.operations import OrderItemV2, OrderV2
from backend.app.services.demo_session import COOKIE_NAME, resolve_demo_session
from contracts.api import ApiEnvelope

router = APIRouter(
    prefix="/api/v1/orders",
    tags=["orders"],
)

KST = ZoneInfo("Asia/Seoul")
SOURCE_SYSTEM = "SYNTHETIC_DEMO"


class OrderItemListData(BaseModel):
    product_name: str
    option_name: str | None
    quantity: int


class OrderListData(BaseModel):
    order_number: str
    order_date: datetime | None
    total_order_amount: str | None
    total_paid_amount: str | None
    paid: Literal["T", "F"]
    canceled: Literal["T", "F", "M"]
    shipping_status: Literal["T", "F", "M"]
    source_system: Literal["SYNTHETIC_DEMO"]
    items: list[OrderItemListData]


class OrdersPageData(BaseModel):
    items: list[OrderListData]
    total: int
    limit: int
    offset: int


class SalesAmountData(BaseModel):
    amount: str | None
    order_count: int
    null_order_count: int


class SalesStatusCounts(BaseModel):
    paid: dict[Literal["T", "F"], int]
    canceled: dict[Literal["T", "F", "M"], int]
    shipping_status: dict[Literal["T", "F", "M"], int]


class SalesDailyData(BaseModel):
    order_date: date
    order_count: int
    order_amount: SalesAmountData
    paid_amount: SalesAmountData


class SalesSummaryData(BaseModel):
    status: Literal["AVAILABLE", "NO_DATA"]
    source_system: Literal["SYNTHETIC_DEMO"]
    timezone: Literal["Asia/Seoul"]
    from_date: date | None
    to_date: date | None
    currency: None
    currency_status: Literal["UNSPECIFIED_IN_SOURCE"]
    paid_amount_semantics: Literal["SOURCE_TOTAL_PAID_AMOUNT_NOT_SETTLED_REVENUE"]
    daily_gap_policy: Literal["OMIT_DAYS_WITHOUT_ORDERS"]
    order_count: int
    undated_order_count: int
    order_amount: SalesAmountData
    paid_amount: SalesAmountData
    statuses: SalesStatusCounts
    daily: list[SalesDailyData]


def _amount_data(values: list[Decimal | None]) -> SalesAmountData:
    known = [value for value in values if value is not None]
    return SalesAmountData(
        amount=str(sum(known, Decimal("0.00"))) if known else None,
        order_count=len(known),
        null_order_count=len(values) - len(known),
    )


def _escaped_contains(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


@router.get("", response_model=ApiEnvelope[OrdersPageData])
def list_orders(
    request: Request,
    order_number: str | None = Query(default=None, min_length=1, max_length=255),
    product_name: str | None = Query(default=None, min_length=1, max_length=100),
    from_date: date | None = None,
    to_date: date | None = None,
    paid: Literal["T", "F"] | None = None,
    canceled: Literal["T", "F", "M"] | None = None,
    shipping_status: Literal["T", "F", "M"] | None = None,
    sort_by: Literal["order_date", "order_number"] = "order_date",
    sort_order: Literal["asc", "desc"] = "desc",
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ApiEnvelope[OrdersPageData]:
    """Return shared, synthetic C15 orders without customer or payment identifiers."""
    if request.app.state.settings.environment != Environment.DEMO:
        raise HTTPException(status_code=403, detail="ORDERS_DEMO_ONLY")
    allowed = {
        "order_number",
        "product_name",
        "from_date",
        "to_date",
        "paid",
        "canceled",
        "shipping_status",
        "sort_by",
        "sort_order",
        "limit",
        "offset",
    }
    if set(request.query_params) - allowed or any(
        len(request.query_params.getlist(key)) != 1 for key in request.query_params
    ):
        raise HTTPException(status_code=422, detail="ORDERS_FILTER_UNSUPPORTED")
    if from_date is not None and to_date is not None and from_date > to_date:
        raise HTTPException(status_code=422, detail="ORDERS_DATE_RANGE_INVALID")
    if to_date == date.max:
        raise HTTPException(status_code=422, detail="ORDERS_DATE_RANGE_INVALID")
    factory, tenant_id, environment = _require_v2_runtime(request)
    with factory() as db:
        _require_catalog_tenant(db, tenant_id, environment)
        if (
            resolve_demo_session(
                db,
                tenant_id=tenant_id,
                token=request.cookies.get(COOKIE_NAME),
                touch=False,
            )
            is None
        ):
            raise HTTPException(status_code=401, detail="DEMO_SESSION_REQUIRED")

        filters = [OrderV2.tenant_id == tenant_id, OrderV2.source_system == SOURCE_SYSTEM]
        if order_number is not None:
            filters.append(
                OrderV2.external_order_id.ilike(_escaped_contains(order_number), escape="\\")
            )
        if product_name is not None:
            filters.append(
                select(OrderItemV2.id)
                .where(
                    OrderItemV2.tenant_id == tenant_id,
                    OrderItemV2.order_id == OrderV2.id,
                    OrderItemV2.source_product_name.ilike(
                        _escaped_contains(product_name), escape="\\"
                    ),
                )
                .exists()
            )
        if from_date is not None:
            start = datetime.combine(from_date, time.min, tzinfo=KST).astimezone(UTC)
            filters.append(OrderV2.source_order_at >= start)
        if to_date is not None:
            end = datetime.combine(to_date + timedelta(days=1), time.min, tzinfo=KST).astimezone(
                UTC
            )
            filters.append(OrderV2.source_order_at < end)
        for column, value in (
            (OrderV2.paid, paid),
            (OrderV2.canceled, canceled),
            (OrderV2.shipping_status, shipping_status),
        ):
            if value is not None:
                filters.append(column == value)

        total = db.scalar(select(func.count(OrderV2.id)).where(*filters)) or 0
        primary = OrderV2.source_order_at if sort_by == "order_date" else OrderV2.external_order_id
        direction = primary.asc if sort_order == "asc" else primary.desc
        # A unique secondary key keeps pages stable when timestamps are equal or NULL.
        order_by = (
            direction().nulls_last() if sort_by == "order_date" else direction(),
            OrderV2.id.asc(),
        )
        orders = db.scalars(
            select(OrderV2).where(*filters).order_by(*order_by).limit(limit).offset(offset)
        ).all()
        order_ids = [order.id for order in orders]
        items_by_order = {order_id: [] for order_id in order_ids}
        if order_ids:
            items = db.scalars(
                select(OrderItemV2)
                .where(
                    OrderItemV2.tenant_id == tenant_id,
                    OrderItemV2.order_id.in_(order_ids),
                )
                .order_by(OrderItemV2.order_id, OrderItemV2.external_order_item_id, OrderItemV2.id)
            ).all()
            variant_ids = {
                item.product_variant_id for item in items if item.product_variant_id is not None
            }
            variants = (
                db.scalars(
                    select(ProductVariantV2).where(
                        ProductVariantV2.tenant_id == tenant_id,
                        ProductVariantV2.id.in_(variant_ids),
                    )
                ).all()
                if variant_ids
                else []
            )
            option_by_variant = {variant.id: variant.option_name for variant in variants}
            for item in items:
                items_by_order[item.order_id].append(
                    OrderItemListData(
                        product_name=item.source_product_name,
                        option_name=option_by_variant.get(item.product_variant_id),
                        quantity=item.quantity,
                    )
                )
        result = [
            OrderListData(
                order_number=order.external_order_id,
                order_date=order.source_order_at,
                total_order_amount=str(order.total_order_amount)
                if order.total_order_amount is not None
                else None,
                total_paid_amount=str(order.total_paid_amount)
                if order.total_paid_amount is not None
                else None,
                paid=order.paid,
                canceled=order.canceled,
                shipping_status=order.shipping_status,
                source_system=SOURCE_SYSTEM,
                items=items_by_order[order.id],
            )
            for order in orders
        ]
    return ApiEnvelope(
        tenant_id=request.app.state.settings.tenant_id,
        request_id=f"req_{uuid4().hex}",
        trace_id=f"tr_{uuid4().hex}",
        data=OrdersPageData(items=result, total=total, limit=limit, offset=offset),
        as_of=datetime.now(UTC),
    )


@router.get("/sales-summary", response_model=ApiEnvelope[SalesSummaryData])
def get_sales_summary(
    request: Request,
    from_date: date | None = None,
    to_date: date | None = None,
) -> ApiEnvelope[SalesSummaryData]:
    """Aggregate C15 order amounts; paid amount is not settled or net revenue."""
    if request.app.state.settings.environment != Environment.DEMO:
        raise HTTPException(status_code=403, detail="SALES_SUMMARY_DEMO_ONLY")
    allowed = {"from_date", "to_date"}
    if set(request.query_params) - allowed or any(
        len(request.query_params.getlist(key)) != 1 for key in request.query_params
    ):
        raise HTTPException(status_code=422, detail="SALES_SUMMARY_FILTER_UNSUPPORTED")
    if from_date is not None and to_date is not None and from_date > to_date:
        raise HTTPException(status_code=422, detail="SALES_SUMMARY_DATE_RANGE_INVALID")
    if to_date == date.max:
        raise HTTPException(status_code=422, detail="SALES_SUMMARY_DATE_RANGE_INVALID")

    factory, tenant_id, environment = _require_v2_runtime(request)
    with factory() as db:
        _require_catalog_tenant(db, tenant_id, environment)
        if (
            resolve_demo_session(
                db,
                tenant_id=tenant_id,
                token=request.cookies.get(COOKIE_NAME),
                touch=False,
            )
            is None
        ):
            raise HTTPException(status_code=401, detail="DEMO_SESSION_REQUIRED")
        filters = [OrderV2.tenant_id == tenant_id, OrderV2.source_system == SOURCE_SYSTEM]
        if from_date is not None:
            start = datetime.combine(from_date, time.min, tzinfo=KST).astimezone(UTC)
            filters.append(OrderV2.source_order_at >= start)
        if to_date is not None:
            end = datetime.combine(to_date + timedelta(days=1), time.min, tzinfo=KST).astimezone(
                UTC
            )
            filters.append(OrderV2.source_order_at < end)
        orders = db.execute(
            select(
                OrderV2.source_order_at,
                OrderV2.total_order_amount,
                OrderV2.total_paid_amount,
                OrderV2.paid,
                OrderV2.canceled,
                OrderV2.shipping_status,
            ).where(*filters)
        ).all()

    order_amounts = [row.total_order_amount for row in orders]
    paid_amounts = [row.total_paid_amount for row in orders]
    statuses = SalesStatusCounts(
        paid={state: sum(row.paid == state for row in orders) for state in ("T", "F")},
        canceled={state: sum(row.canceled == state for row in orders) for state in ("T", "F", "M")},
        shipping_status={
            state: sum(row.shipping_status == state for row in orders) for state in ("T", "F", "M")
        },
    )
    by_date: dict[date, list] = {}
    undated_count = 0
    for row in orders:
        if row.source_order_at is None:
            undated_count += 1
            continue
        at = row.source_order_at
        if at.tzinfo is None:
            at = at.replace(tzinfo=UTC)
        by_date.setdefault(at.astimezone(KST).date(), []).append(row)
    daily = [
        SalesDailyData(
            order_date=day,
            order_count=len(day_orders),
            order_amount=_amount_data([row.total_order_amount for row in day_orders]),
            paid_amount=_amount_data([row.total_paid_amount for row in day_orders]),
        )
        for day, day_orders in sorted(by_date.items())
    ]
    return ApiEnvelope(
        tenant_id=request.app.state.settings.tenant_id,
        request_id=f"req_{uuid4().hex}",
        trace_id=f"tr_{uuid4().hex}",
        data=SalesSummaryData(
            status="AVAILABLE" if orders else "NO_DATA",
            source_system=SOURCE_SYSTEM,
            timezone="Asia/Seoul",
            from_date=from_date,
            to_date=to_date,
            currency=None,
            currency_status="UNSPECIFIED_IN_SOURCE",
            paid_amount_semantics="SOURCE_TOTAL_PAID_AMOUNT_NOT_SETTLED_REVENUE",
            daily_gap_policy="OMIT_DAYS_WITHOUT_ORDERS",
            order_count=len(orders),
            undated_order_count=undated_count,
            order_amount=_amount_data(order_amounts),
            paid_amount=_amount_data(paid_amounts),
            statuses=statuses,
            daily=daily,
        ),
        as_of=datetime.now(UTC),
    )


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
            select(func.max(OrderV2.source_order_at)).where(*base_filters)
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
                select(func.count(OrderV2.id)).where(
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
            "reference_date": (recent_date.isoformat() if recent_date is not None else None),
            "timezone": "Asia/Seoul",
            "source_system": SOURCE_SYSTEM,
            "aggregation": "LATEST_ORDER_DATE",
            "includes_all_order_statuses": True,
        },
        "evidence_ids": [],
        "warnings": ([] if status == "AVAILABLE" else ["RECENT_ORDERS_EMPTY"]),
        "as_of": now.isoformat(),
    }
