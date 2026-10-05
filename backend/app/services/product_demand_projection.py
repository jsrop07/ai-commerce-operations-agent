"""R09 product-level demand projection from synthetic operational orders."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from backend.app.models_v2.catalog import ProductV2
from backend.app.models_v2.operations import OrderItemV2, OrderV2

SYNTHETIC_ORDER_SOURCE = "SYNTHETIC_DEMO"
LOW_SAMPLE_EFFECTIVE_ORDER_COUNT = 3


@dataclass(frozen=True)
class ProductDemandProjection:
    product_no: int
    product_name: str

    order_count: int
    order_item_count: int
    ordered_quantity: int

    effective_order_count: int
    effective_quantity: int

    canceled_order_count: int
    canceled_quantity: int

    uncertain_order_count: int
    uncertain_quantity: int

    unpaid_order_count: int
    unpaid_quantity: int

    recent_10d_effective_quantity: int
    previous_10d_effective_quantity: int

    trend_direction: str
    trend_delta: int
    trend_ratio: float | None

    shipping_pending_count: int
    shipping_partial_count: int
    shipping_complete_count: int

    data_mode: str
    quality_status: str
    as_of: datetime


def _trend(
    recent: int,
    previous: int,
) -> tuple[str, int, float | None]:
    delta = recent - previous

    if previous == 0 and recent > 0:
        return "SURGE", delta, None

    if previous == 0:
        return "FLAT", delta, None

    ratio = round(recent / previous, 4)

    if recent > previous:
        direction = "UP"
    elif recent < previous:
        direction = "DOWN"
    else:
        direction = "FLAT"

    return direction, delta, ratio


def _quality(
    *,
    order_count: int,
    effective_order_count: int,
) -> str:
    if order_count == 0:
        return "NO_DATA"

    if (
        effective_order_count
        < LOW_SAMPLE_EFFECTIVE_ORDER_COUNT
    ):
        return "LOW_SAMPLE"

    return "OK"


def project_product_demand(
    session: Session,
    *,
    tenant_id: UUID,
    product_id: UUID,
) -> ProductDemandProjection:
    """Build a product aggregate without exposing order-level evidence."""

    product = session.execute(
        select(
            ProductV2.id,
            ProductV2.cafe24_product_no,
            ProductV2.product_name,
        ).where(
            ProductV2.tenant_id == tenant_id,
            ProductV2.id == product_id,
        )
    ).one_or_none()

    if product is None:
        raise ValueError("PRODUCT_NOT_FOUND")

    max_order_at = session.scalar(
        select(
            func.max(OrderV2.source_order_at)
        ).where(
            OrderV2.tenant_id == tenant_id,
            OrderV2.source_system
            == SYNTHETIC_ORDER_SOURCE,
        )
    )

    if max_order_at is None:
        raise ValueError(
            "SYNTHETIC_DEMO_ORDER_SOURCE_MISSING"
        )

    if max_order_at.tzinfo is None:
        max_order_at = max_order_at.replace(
            tzinfo=UTC
        )

    # 가장 최근 synthetic 주문 날짜를 기준으로
    # 최근 10일 / 직전 10일의 달력 구간을 고정한다.
    as_of = datetime.combine(
        max_order_at.date(),
        time.max,
        tzinfo=UTC,
    )

    recent_start = datetime.combine(
        max_order_at.date() - timedelta(days=9),
        time.min,
        tzinfo=UTC,
    )

    previous_start = recent_start - timedelta(
        days=10
    )

    recent_end_exclusive = datetime.combine(
        max_order_at.date() + timedelta(days=1),
        time.min,
        tzinfo=UTC,
    )

    effective_condition = (
        (OrderV2.paid == "T")
        & (OrderV2.canceled == "F")
    )

    canceled_condition = (
        OrderV2.canceled == "T"
    )

    uncertain_condition = (
        OrderV2.canceled == "M"
    )

    unpaid_condition = (
        (OrderV2.paid == "F")
        & (OrderV2.canceled == "F")
    )

    row = session.execute(
        select(
            func.count(
                func.distinct(OrderV2.id)
            ).label("order_count"),

            func.count(
                OrderItemV2.id
            ).label("order_item_count"),

            func.coalesce(
                func.sum(OrderItemV2.quantity),
                0,
            ).label("ordered_quantity"),

            func.count(
                func.distinct(
                    case(
                        (
                            effective_condition,
                            OrderV2.id,
                        ),
                        else_=None,
                    )
                )
            ).label(
                "effective_order_count"
            ),

            func.coalesce(
                func.sum(
                    case(
                        (
                            effective_condition,
                            OrderItemV2.quantity,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("effective_quantity"),

            func.count(
                func.distinct(
                    case(
                        (
                            canceled_condition,
                            OrderV2.id,
                        ),
                        else_=None,
                    )
                )
            ).label(
                "canceled_order_count"
            ),

            func.coalesce(
                func.sum(
                    case(
                        (
                            canceled_condition,
                            OrderItemV2.quantity,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("canceled_quantity"),

            func.count(
                func.distinct(
                    case(
                        (
                            uncertain_condition,
                            OrderV2.id,
                        ),
                        else_=None,
                    )
                )
            ).label(
                "uncertain_order_count"
            ),

            func.coalesce(
                func.sum(
                    case(
                        (
                            uncertain_condition,
                            OrderItemV2.quantity,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("uncertain_quantity"),

            func.count(
                func.distinct(
                    case(
                        (
                            unpaid_condition,
                            OrderV2.id,
                        ),
                        else_=None,
                    )
                )
            ).label(
                "unpaid_order_count"
            ),

            func.coalesce(
                func.sum(
                    case(
                        (
                            unpaid_condition,
                            OrderItemV2.quantity,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("unpaid_quantity"),

            func.coalesce(
                func.sum(
                    case(
                        (
                            effective_condition
                            & (
                                OrderV2.source_order_at
                                >= recent_start
                            )
                            & (
                                OrderV2.source_order_at
                                < recent_end_exclusive
                            ),
                            OrderItemV2.quantity,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label(
                "recent_10d_effective_quantity"
            ),

            func.coalesce(
                func.sum(
                    case(
                        (
                            effective_condition
                            & (
                                OrderV2.source_order_at
                                >= previous_start
                            )
                            & (
                                OrderV2.source_order_at
                                < recent_start
                            ),
                            OrderItemV2.quantity,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label(
                "previous_10d_effective_quantity"
            ),

            func.count(
                func.distinct(
                    case(
                        (
                            OrderV2.shipping_status
                            == "F",
                            OrderV2.id,
                        ),
                        else_=None,
                    )
                )
            ).label(
                "shipping_pending_count"
            ),

            func.count(
                func.distinct(
                    case(
                        (
                            OrderV2.shipping_status
                            == "M",
                            OrderV2.id,
                        ),
                        else_=None,
                    )
                )
            ).label(
                "shipping_partial_count"
            ),

            func.count(
                func.distinct(
                    case(
                        (
                            OrderV2.shipping_status
                            == "T",
                            OrderV2.id,
                        ),
                        else_=None,
                    )
                )
            ).label(
                "shipping_complete_count"
            ),
        )
        .select_from(OrderItemV2)
        .join(
            OrderV2,
            (
                OrderV2.tenant_id
                == OrderItemV2.tenant_id
            )
            & (
                OrderV2.id
                == OrderItemV2.order_id
            ),
        )
        .where(
            OrderItemV2.tenant_id
            == tenant_id,
            OrderItemV2.product_id
            == product_id,
            OrderV2.source_system
            == SYNTHETIC_ORDER_SOURCE,
        )
    ).one()

    order_count = int(row.order_count)
    effective_order_count = int(
        row.effective_order_count
    )

    recent = int(
        row.recent_10d_effective_quantity
    )

    previous = int(
        row.previous_10d_effective_quantity
    )

    (
        trend_direction,
        trend_delta,
        trend_ratio,
    ) = _trend(
        recent,
        previous,
    )

    return ProductDemandProjection(
        product_no=int(
            product.cafe24_product_no
        ),
        product_name=product.product_name,
        order_count=order_count,
        order_item_count=int(
            row.order_item_count
        ),
        ordered_quantity=int(
            row.ordered_quantity
        ),
        effective_order_count=(
            effective_order_count
        ),
        effective_quantity=int(
            row.effective_quantity
        ),
        canceled_order_count=int(
            row.canceled_order_count
        ),
        canceled_quantity=int(
            row.canceled_quantity
        ),
        uncertain_order_count=int(
            row.uncertain_order_count
        ),
        uncertain_quantity=int(
            row.uncertain_quantity
        ),
        unpaid_order_count=int(
            row.unpaid_order_count
        ),
        unpaid_quantity=int(
            row.unpaid_quantity
        ),
        recent_10d_effective_quantity=recent,
        previous_10d_effective_quantity=previous,
        trend_direction=trend_direction,
        trend_delta=trend_delta,
        trend_ratio=trend_ratio,
        shipping_pending_count=int(
            row.shipping_pending_count
        ),
        shipping_partial_count=int(
            row.shipping_partial_count
        ),
        shipping_complete_count=int(
            row.shipping_complete_count
        ),
        data_mode=SYNTHETIC_ORDER_SOURCE,
        quality_status=_quality(
            order_count=order_count,
            effective_order_count=(
                effective_order_count
            ),
        ),
        as_of=as_of,
    )