"""Day 9 current reservation demand, separate from historical truth."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from backend.app.services.category_product_projection import (
    CatalogProductProjection,
    CategoryScopeProjection,
)
from backend.app.services.inventory_projection import InventoryProjection
from contracts.ai_sku_aggregate import AiSkuAggregate


class CurrentOrderDisposition(StrEnum):
    INCLUDE = "INCLUDE"
    EXCLUDE = "EXCLUDE"
    REVIEW = "REVIEW"


@dataclass(frozen=True)
class CurrentReservationOrderItem:
    order_id: str
    order_item_id: str
    product_no: int
    quantity: int | None
    shipping_status: str
    canceled: str
    sku_id: str | None = None
    paid: str | None = None
    confirmed_remaining_quantity: int | None = None
    remaining_quantity_evidence_ids: tuple[str, ...] = ()
    source_classification: str = "BLOCKED"
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class CurrentReservationDemand:
    product_no: int
    sku_id: str | None
    required_qty: int | None
    calculation_status: str
    category_evidence_ids: tuple[str, ...]
    order_evidence_ids: tuple[str, ...]
    source_classifications: tuple[str, ...]
    as_of: datetime


@dataclass(frozen=True)
class CurrentReservationReviewItem:
    order_id: str
    order_item_id: str
    product_no: int
    raw_quantity: int | None
    reason: str
    source_classification: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class CurrentReservationDemandProjection:
    demands: tuple[CurrentReservationDemand, ...]
    review_items: tuple[CurrentReservationReviewItem, ...]
    excluded_order_item_ids: tuple[str, ...]
    confirmed_order_count: int
    confirmed_order_item_count: int
    confirmed_required_qty: int | None
    as_of: datetime


def build_ai_sku_aggregate(
    demand: CurrentReservationDemand,
    *,
    inventory: InventoryProjection | None = None,
    quality_status: str | None = None,
    data_mode: str,
    evidence_ids: tuple[str, ...] = (),
) -> AiSkuAggregate:
    """Create a fresh C02 allowlist object from one internal SKU aggregate.

    Order-level fields and ``order_evidence_ids`` are deliberately never read.
    Inventory values are copied only when a validated inventory projection is
    explicitly supplied; absent values remain ``None``.
    """

    if not demand.sku_id:
        raise ValueError("C02 aggregate requires a resolved sku_id")
    if not data_mode:
        raise ValueError("data_mode is required")
    if inventory is not None and inventory.sku_id != demand.sku_id:
        raise ValueError("inventory sku_id does not match demand sku_id")

    effective_quality = (
        inventory.quality_status
        if inventory is not None
        else quality_status
    )
    if not effective_quality:
        raise ValueError("quality_status is required")

    return AiSkuAggregate(
        sku_id=demand.sku_id,
        product_no=demand.product_no,
        required_qty=demand.required_qty,
        expected_inventory=(
            inventory.expected_inventory
            if inventory is not None
            else None
        ),
        available_inventory=(
            inventory.available_inventory
            if inventory is not None
            else None
        ),
        reserved=(
            inventory.reserved
            if inventory is not None
            else None
        ),
        confirmed_incoming=(
            inventory.confirmed_incoming
            if inventory is not None
            else None
        ),
        calculation_status=demand.calculation_status,
        quality_status=effective_quality,
        data_mode=data_mode,
        as_of=demand.as_of,
        evidence_ids=evidence_ids,
    )


def build_ai_sku_aggregates(
    projection: CurrentReservationDemandProjection,
    *,
    inventory_by_sku: Mapping[str, InventoryProjection] | None = None,
    quality_status: str | None = None,
    data_mode: str,
    evidence_ids_by_sku: Mapping[str, tuple[str, ...]] | None = None,
) -> tuple[AiSkuAggregate, ...]:
    """Build C02 objects for resolved SKU demands only.

    Demands without a resolved SKU are not safe AI inputs and are omitted.
    Evidence is caller-supplied and never copied from order-level demand data.
    """

    aggregates: list[AiSkuAggregate] = []
    for demand in projection.demands:
        if not demand.sku_id:
            continue
        aggregates.append(
            build_ai_sku_aggregate(
                demand,
                inventory=(
                    inventory_by_sku.get(demand.sku_id)
                    if inventory_by_sku is not None
                    else None
                ),
                quality_status=quality_status,
                data_mode=data_mode,
                evidence_ids=(
                    evidence_ids_by_sku.get(demand.sku_id, ())
                    if evidence_ids_by_sku is not None
                    else ()
                ),
            )
        )
    return tuple(aggregates)


def classify_current_order(
    *,
    shipping_status: str,
    canceled: str,
) -> CurrentOrderDisposition:
    """Apply explicit Day 9 operational order rules; paid is not consulted."""

    if canceled == "T":
        return CurrentOrderDisposition.EXCLUDE
    if shipping_status in {"M", "T"}:
        return CurrentOrderDisposition.EXCLUDE
    if shipping_status == "F" and canceled == "F":
        return CurrentOrderDisposition.INCLUDE
    if shipping_status == "F" and canceled == "M":
        return CurrentOrderDisposition.REVIEW
    return CurrentOrderDisposition.REVIEW


def project_current_reservation_demand(
    *,
    catalog_products: tuple[
        CatalogProductProjection,
        ...,
    ],
    category_scope: CategoryScopeProjection,
    order_items: tuple[
        CurrentReservationOrderItem,
        ...,
    ],
    as_of: datetime | None = None,
) -> CurrentReservationDemandProjection:
    """Aggregate confirmed current demand and isolate review-required items."""

    products_by_no = {
        product.product_no: product
        for product in catalog_products
    }
    eligible_product_nos = {
        product_no
        for product_no in category_scope.recursive_product_nos
        if product_no in products_by_no
        and products_by_no[product_no].operational
    }
    aggregate: dict[
        tuple[int, str | None],
        dict[str, object],
    ] = {}
    review_items: list[
        CurrentReservationReviewItem
    ] = []
    excluded: list[str] = []
    seen_order_items: set[str] = set()
    confirmed_order_ids: set[str] = set()
    confirmed_order_item_count = 0

    for item in order_items:
        if not item.order_id or not item.order_item_id:
            raise ValueError(
                "order item identifiers are required"
            )
        if item.order_item_id in seen_order_items:
            raise ValueError(
                "duplicate order_item_id"
            )
        seen_order_items.add(item.order_item_id)
        if item.quantity is not None and item.quantity < 0:
            raise ValueError(
                "reservation demand quantity must be >= 0"
            )
        if (
            item.confirmed_remaining_quantity is not None
            and item.confirmed_remaining_quantity < 0
        ):
            raise ValueError(
                "confirmed remaining quantity must be >= 0"
            )

        disposition = classify_current_order(
            shipping_status=item.shipping_status,
            canceled=item.canceled,
        )
        if (
            disposition
            == CurrentOrderDisposition.EXCLUDE
            or item.product_no
            not in eligible_product_nos
        ):
            excluded.append(item.order_item_id)
            continue

        quantity = item.quantity
        evidence_ids = item.evidence_ids
        if disposition == CurrentOrderDisposition.REVIEW:
            is_partial_cancel = (
                item.shipping_status == "F"
                and item.canceled == "M"
            )
            if (
                is_partial_cancel
                and item.confirmed_remaining_quantity
                is not None
                and item.remaining_quantity_evidence_ids
            ):
                quantity = (
                    item.confirmed_remaining_quantity
                )
                evidence_ids = tuple(
                    dict.fromkeys(
                        item.evidence_ids
                        + item.remaining_quantity_evidence_ids
                    )
                )
            else:
                review_items.append(
                    CurrentReservationReviewItem(
                        order_id=item.order_id,
                        order_item_id=(
                            item.order_item_id
                        ),
                        product_no=item.product_no,
                        raw_quantity=item.quantity,
                        reason=(
                            "PARTIAL_CANCEL_REMAINING_"
                            "QUANTITY_UNKNOWN"
                            if is_partial_cancel
                            else "ORDER_OPERATIONAL_STATUS_UNKNOWN"
                        ),
                        source_classification=(
                            item.source_classification
                        ),
                        evidence_ids=(
                            item.evidence_ids
                        ),
                    )
                )
                continue

        key = (
            item.product_no,
            item.sku_id,
        )
        bucket = aggregate.setdefault(
            key,
            {
                "quantity": 0,
                "quantity_unknown": False,
                "order_evidence_ids": [],
                "source_classifications": [],
            },
        )
        if quantity is None:
            bucket["quantity_unknown"] = True
        else:
            bucket["quantity"] = (
                int(bucket["quantity"])
                + quantity
            )
        bucket_evidence = bucket[
            "order_evidence_ids"
        ]
        bucket_sources = bucket[
            "source_classifications"
        ]
        assert isinstance(bucket_evidence, list)
        assert isinstance(bucket_sources, list)
        bucket_evidence.extend(evidence_ids)
        bucket_sources.append(
            item.source_classification
        )
        confirmed_order_ids.add(item.order_id)
        confirmed_order_item_count += 1

    projection_as_of = as_of or datetime.now(UTC)
    demands: list[CurrentReservationDemand] = []
    for (product_no, sku_id), bucket in sorted(
        aggregate.items(),
        key=lambda entry: (
            entry[0][0],
            entry[0][1] or "",
        ),
    ):
        product = products_by_no[product_no]
        quantity_unknown = bool(
            bucket["quantity_unknown"]
        )
        order_evidence = bucket[
            "order_evidence_ids"
        ]
        sources = bucket[
            "source_classifications"
        ]
        assert isinstance(order_evidence, list)
        assert isinstance(sources, list)
        demands.append(
            CurrentReservationDemand(
                product_no=product_no,
                sku_id=sku_id,
                required_qty=(
                    None
                    if quantity_unknown
                    else int(bucket["quantity"])
                ),
                calculation_status=(
                    "ORDER_ITEM_QUANTITY_UNKNOWN"
                    if quantity_unknown
                    else "CURRENT_DEMAND_CONFIRMED"
                ),
                category_evidence_ids=tuple(
                    dict.fromkeys(
                        category_scope.evidence_ids
                        + product.evidence_ids
                    )
                ),
                order_evidence_ids=tuple(
                    dict.fromkeys(order_evidence)
                ),
                source_classifications=tuple(
                    dict.fromkeys(
                        list(
                            product.source_classifications
                        )
                        + list(
                            category_scope
                            .source_classifications
                        )
                        + sources
                    )
                ),
                as_of=projection_as_of,
            )
        )

    confirmed_required_qty = (
        None
        if any(
            demand.required_qty is None
            for demand in demands
        )
        else sum(
            demand.required_qty or 0
            for demand in demands
        )
    )
    return CurrentReservationDemandProjection(
        demands=tuple(demands),
        review_items=tuple(review_items),
        excluded_order_item_ids=tuple(excluded),
        confirmed_order_count=len(
            confirmed_order_ids
        ),
        confirmed_order_item_count=(
            confirmed_order_item_count
        ),
        confirmed_required_qty=(
            confirmed_required_qty
        ),
        as_of=projection_as_of,
    )
