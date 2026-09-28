"""Synthetic canaries for the C02 customer-unlinked aggregate boundary."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from backend.app.services.current_reservation_demand import (
    CurrentReservationDemand,
    CurrentReservationDemandProjection,
    build_ai_sku_aggregate,
    build_ai_sku_aggregates,
)
from backend.app.services.inventory_projection import build_inventory_projection
from contracts.ai_sku_aggregate import AiSkuAggregate

AS_OF = datetime(2026, 9, 23, 10, 0, tzinfo=UTC)


def demand(*, sku_id: str | None = "sku-synthetic", required_qty: int | None = 3):
    return CurrentReservationDemand(
        product_no=101,
        sku_id=sku_id,
        required_qty=required_qty,
        calculation_status="CURRENT_DEMAND_CONFIRMED",
        category_evidence_ids=("category-policy-synthetic",),
        order_evidence_ids=(
            "order_id=synthetic-order",
            "order_item_id=synthetic-order-item",
            "order_line_id=synthetic-order-line",
            "customer_id=synthetic-customer",
            "shipping_address=synthetic-address",
            "payment_info=synthetic-payment",
            "inquiry_text=synthetic-inquiry",
            "free_memo=synthetic-memo",
            "transaction_timestamps=synthetic-time",
            "source_order_url=https://invalid.example/synthetic",
        ),
        source_classifications=("SYNTHETIC",),
        as_of=AS_OF,
    )


def projection(one: CurrentReservationDemand):
    return CurrentReservationDemandProjection(
        demands=(one,),
        review_items=(),
        excluded_order_item_ids=(),
        confirmed_order_count=1,
        confirmed_order_item_count=1,
        confirmed_required_qty=one.required_qty,
        as_of=AS_OF,
    )


def inventory(*, reserved: int | None = 2):
    return build_inventory_projection(
        tenant_id="tenant-synthetic",
        sku_id="sku-synthetic",
        source_on_hand=8,
        ledger_delta=-1,
        reserved=reserved,
        confirmed_incoming=None,
        quality_status="CONFIRMED",
        ttl_seconds=3600,
        age_seconds=60,
        provider="DEMO",
        as_of=AS_OF,
    )


def recursive_values(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from recursive_values(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from recursive_values(child)
    elif isinstance(value, str):
        yield value


def test_allowlist_preserves_aggregate_and_inventory_meaning() -> None:
    result = build_ai_sku_aggregate(
        demand(),
        inventory=inventory(),
        data_mode="SYNTHETIC",
    )

    assert result.sku_id == "sku-synthetic"
    assert result.product_no == 101
    assert result.required_qty == 3
    assert result.expected_inventory == 7
    assert result.available_inventory == 5
    assert result.reserved == 2
    assert result.confirmed_incoming is None
    assert result.evidence_ids == ()


def test_null_values_are_not_replaced_with_zero() -> None:
    result = build_ai_sku_aggregate(
        demand(required_qty=None),
        inventory=inventory(reserved=None),
        data_mode="SYNTHETIC",
    )

    assert result.required_qty is None
    assert result.expected_inventory == 7
    assert result.available_inventory is None
    assert result.reserved is None


def test_prohibited_order_fields_and_canary_strings_are_absent() -> None:
    result = build_ai_sku_aggregate(
        demand(),
        inventory=inventory(),
        data_mode="SYNTHETIC",
    )
    serialized = result.model_dump(mode="json")
    prohibited = {
        "order_id",
        "order_item_id",
        "order_line_id",
        "customer_id",
        "shipping_address",
        "payment_info",
        "inquiry_text",
        "free_memo",
        "transaction_timestamps",
        "source_order_url",
        "review_items",
        "excluded_order_item_ids",
    }
    values = {str(value).lower() for value in recursive_values(serialized)}
    assert prohibited.isdisjoint(values)
    assert not any("synthetic-order" in value for value in values)
    assert not any(value.endswith(".example/synthetic") for value in values)
    assert "order-level" not in values
    assert all(not isinstance(value, dict) for value in serialized.values())
    assert serialized["evidence_ids"] == []


def test_contract_forbids_extra_prohibited_keys() -> None:
    with pytest.raises(ValidationError):
        AiSkuAggregate(
            sku_id="sku-synthetic",
            product_no=101,
            required_qty=1,
            calculation_status="CURRENT_DEMAND_CONFIRMED",
            quality_status="CONFIRMED",
            data_mode="SYNTHETIC",
            as_of=AS_OF,
            order_id="synthetic-order",
        )


def test_unresolved_sku_is_not_emitted() -> None:
    result = build_ai_sku_aggregates(
        projection(demand(sku_id=None)),
        data_mode="SYNTHETIC",
        quality_status="CONFIRMED",
    )
    assert result == ()


def test_unsafe_evidence_is_rejected_if_explicitly_supplied() -> None:
    with pytest.raises(ValueError, match="C02-safe"):
        build_ai_sku_aggregate(
            demand(),
            data_mode="SYNTHETIC",
            quality_status="CONFIRMED",
            evidence_ids=("customer_id=synthetic-customer",),
        )
