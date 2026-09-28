"""Day 9 current reservation demand tests."""

from datetime import UTC, datetime

import pytest

from backend.app.services.category_product_projection import (
    CategoryProductMembership,
    CategoryRecord,
    ProductRecord,
    project_catalog_products,
    project_category_scope,
)
from backend.app.services.current_reservation_demand import (
    CurrentReservationOrderItem,
    project_current_reservation_demand,
)

AS_OF = datetime(2026, 9, 10, tzinfo=UTC)


def products_and_scope(
    *,
    inactive_product_nos: tuple[int, ...] = (),
    product_count: int = 1,
):
    products = tuple(
        ProductRecord(
            product_no=number,
            display=(
                "F"
                if number in inactive_product_nos
                else "T"
            ),
            selling=(
                "F"
                if number in inactive_product_nos
                else "T"
            ),
            sold_out=(
                "T" if number % 3 == 0 else "F"
            ),
            as_of=AS_OF,
            source_classification="SANITIZED_REAL",
            evidence_ids=(f"product-{number}",),
        )
        for number in range(1, product_count + 1)
    )
    memberships = tuple(
        CategoryProductMembership(
            category_no=56,
            product_no=number,
            as_of=AS_OF,
            source_classification="LIVE_READ",
            evidence_ids=(
                f"preorder-membership-{number}",
            ),
        )
        for number in range(1, product_count + 1)
    )
    catalog = project_catalog_products(
        products=products,
        memberships=memberships,
    )
    scope = project_category_scope(
        category_no=56,
        categories=(
            CategoryRecord(
                category_no=56,
                parent_category_no=None,
                as_of=AS_OF,
                source_classification=(
                    "SANITIZED_REAL"
                ),
                evidence_ids=("category-56",),
            ),
        ),
        memberships=memberships,
    )
    return catalog, scope


def item(
    order_item_id: str,
    *,
    order_id: str | None = None,
    product_no: int = 1,
    quantity: int | None = 1,
    shipping_status: str = "F",
    canceled: str = "F",
    paid: str | None = None,
) -> CurrentReservationOrderItem:
    return CurrentReservationOrderItem(
        order_id=(
            order_id
            or f"order-{order_item_id}"
        ),
        order_item_id=order_item_id,
        product_no=product_no,
        quantity=quantity,
        shipping_status=shipping_status,
        canceled=canceled,
        sku_id=f"sku-{product_no}",
        paid=paid,
        source_classification="SANITIZED_REAL",
        evidence_ids=(f"order-item-{order_item_id}",),
    )


def test_operational_preorder_item_is_included() -> None:
    catalog, scope = products_and_scope()
    result = project_current_reservation_demand(
        catalog_products=catalog,
        category_scope=scope,
        order_items=(
            item("included", quantity=8),
        ),
        as_of=AS_OF,
    )

    assert len(result.demands) == 1
    assert result.demands[0].required_qty == 8
    assert result.review_items == ()


@pytest.mark.parametrize(
    ("shipping_status", "canceled"),
    (
        ("F", "T"),
        ("M", "F"),
        ("T", "F"),
    ),
)
def test_non_operational_orders_are_excluded(
    shipping_status: str,
    canceled: str,
) -> None:
    catalog, scope = products_and_scope()
    result = project_current_reservation_demand(
        catalog_products=catalog,
        category_scope=scope,
        order_items=(
            item(
                "excluded",
                shipping_status=shipping_status,
                canceled=canceled,
            ),
        ),
    )

    assert result.demands == ()
    assert result.excluded_order_item_ids == (
        "excluded",
    )


def test_partial_cancel_raw_quantity_requires_review() -> None:
    catalog, scope = products_and_scope()
    result = project_current_reservation_demand(
        catalog_products=catalog,
        category_scope=scope,
        order_items=(
            item(
                "partial",
                quantity=9,
                canceled="M",
            ),
        ),
    )

    assert result.demands == ()
    assert len(result.review_items) == 1
    assert result.review_items[0].raw_quantity == 9
    assert result.review_items[0].reason == (
        "PARTIAL_CANCEL_REMAINING_QUANTITY_UNKNOWN"
    )


def test_paid_is_not_a_required_operational_filter() -> None:
    catalog, scope = products_and_scope()
    result = project_current_reservation_demand(
        catalog_products=catalog,
        category_scope=scope,
        order_items=(
            item("paid-t", paid="T"),
            item("paid-f", paid="F"),
        ),
    )

    assert result.demands[0].required_qty == 2


def test_preorder_48_relations_have_46_operational_products() -> None:
    catalog, scope = products_and_scope(
        product_count=48,
        inactive_product_nos=(47, 48),
    )

    assert scope.recursive_product_count == 48
    assert sum(
        product.operational
        for product in catalog
    ) == 46


def test_actual_shape_six_orders_seven_items_required_eight() -> None:
    catalog, scope = products_and_scope()
    order_items = (
        item("1-a", order_id="order-1"),
        item("1-b", order_id="order-1"),
        item("2", order_id="order-2"),
        item("3", order_id="order-3"),
        item("4", order_id="order-4"),
        item("5", order_id="order-5"),
        item(
            "6",
            order_id="order-6",
            quantity=2,
        ),
    )

    result = project_current_reservation_demand(
        catalog_products=catalog,
        category_scope=scope,
        order_items=order_items,
        as_of=AS_OF,
    )

    assert result.confirmed_order_count == 6
    assert result.confirmed_order_item_count == 7
    assert result.confirmed_required_qty == 8


def test_inactive_preorder_items_do_not_change_confirmed_demand() -> None:
    catalog, scope = products_and_scope(
        product_count=48,
        inactive_product_nos=(47, 48),
    )
    baseline = project_current_reservation_demand(
        catalog_products=catalog,
        category_scope=scope,
        order_items=(
            item("active", quantity=8),
        ),
        as_of=AS_OF,
    )
    with_inactive = project_current_reservation_demand(
        catalog_products=catalog,
        category_scope=scope,
        order_items=(
            item("active", quantity=8),
            item(
                "inactive",
                product_no=47,
                quantity=100,
            ),
        ),
        as_of=AS_OF,
    )

    assert with_inactive.demands == (
        baseline.demands
    )


def test_unknown_order_item_quantity_is_not_zero() -> None:
    catalog, scope = products_and_scope()
    result = project_current_reservation_demand(
        catalog_products=catalog,
        category_scope=scope,
        order_items=(
            item("unknown", quantity=None),
        ),
    )

    assert result.demands[0].required_qty is None
    assert result.demands[0].calculation_status == (
        "ORDER_ITEM_QUANTITY_UNKNOWN"
    )
