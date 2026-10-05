"""C09 safe aggregate boundaries for operational demand."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from backend.app.services.current_reservation_demand import (
    CurrentReservationDemandProjection,
)
from backend.app.services.product_demand_projection import (
    ProductDemandProjection,
)


@dataclass(frozen=True)
class SafeReservationAggregate:
    product_no: int | None
    required_qty: int
    calculation_status: str
    as_of: datetime


@dataclass(frozen=True)
class SafeProductDemandAggregate:
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


def safe_reservation_aggregate(
    projection: CurrentReservationDemandProjection,
    *,
    product_no: int | None,
) -> SafeReservationAggregate | None:
    """Expose aggregate reservation scalars only."""

    if product_no is None:
        quantity = (
            projection.confirmed_required_qty
        )
        status = (
            "CURRENT_DEMAND_CONFIRMED"
            if quantity is not None
            else "UNKNOWN"
        )
    else:
        demands = [
            item
            for item in projection.demands
            if item.product_no == product_no
        ]

        if len(demands) != 1:
            return None

        quantity = demands[0].required_qty
        status = demands[0].calculation_status

    if (
        quantity is None
        or quantity < 0
        or status
        != "CURRENT_DEMAND_CONFIRMED"
    ):
        return None

    return SafeReservationAggregate(
        product_no,
        quantity,
        status,
        projection.as_of,
    )


def safe_product_demand_aggregate(
    projection: ProductDemandProjection,
) -> SafeProductDemandAggregate:
    """Copy only product-level aggregate values across C09."""

    if projection.data_mode != "SYNTHETIC_DEMO":
        raise ValueError(
            "C09 product demand requires "
            "SYNTHETIC_DEMO"
        )

    if projection.order_count < 0:
        raise ValueError(
            "invalid order_count"
        )

    if projection.ordered_quantity < 0:
        raise ValueError(
            "invalid ordered_quantity"
        )

    return SafeProductDemandAggregate(
        product_no=projection.product_no,
        product_name=projection.product_name,
        order_count=projection.order_count,
        order_item_count=(
            projection.order_item_count
        ),
        ordered_quantity=(
            projection.ordered_quantity
        ),
        effective_order_count=(
            projection.effective_order_count
        ),
        effective_quantity=(
            projection.effective_quantity
        ),
        canceled_order_count=(
            projection.canceled_order_count
        ),
        canceled_quantity=(
            projection.canceled_quantity
        ),
        uncertain_order_count=(
            projection.uncertain_order_count
        ),
        uncertain_quantity=(
            projection.uncertain_quantity
        ),
        unpaid_order_count=(
            projection.unpaid_order_count
        ),
        unpaid_quantity=(
            projection.unpaid_quantity
        ),
        recent_10d_effective_quantity=(
            projection
            .recent_10d_effective_quantity
        ),
        previous_10d_effective_quantity=(
            projection
            .previous_10d_effective_quantity
        ),
        trend_direction=(
            projection.trend_direction
        ),
        trend_delta=projection.trend_delta,
        trend_ratio=projection.trend_ratio,
        shipping_pending_count=(
            projection.shipping_pending_count
        ),
        shipping_partial_count=(
            projection.shipping_partial_count
        ),
        shipping_complete_count=(
            projection.shipping_complete_count
        ),
        data_mode=projection.data_mode,
        quality_status=(
            projection.quality_status
        ),
        as_of=projection.as_of,
    )