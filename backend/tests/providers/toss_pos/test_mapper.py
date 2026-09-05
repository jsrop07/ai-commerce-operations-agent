from datetime import UTC, datetime

import pytest

from backend.app.adapters.providers.toss_pos.mapper import (
    map_toss_order_line_to_sale,
)
from backend.app.services.offline_sale import OfflineSalePipeline

FIXED_INGESTED_AT = datetime(2026, 9, 5, 0, 0, tzinfo=UTC)


def _order() -> dict[str, object]:
    return {
        "id": "order-test-001",
        "orderState": "COMPLETED",
        "createdAt": "2026-09-05T10:00:00+09:00",
        "completedAt": "2026-09-05T10:05:00+09:00",
    }


def _line() -> dict[str, object]:
    return {
        "item": {
            "code": "TOSS-P001",
            "title": "테스트 보드게임",
        },
        "quantity": 2,
        "amount": 39000,
    }


def test_toss_line_maps_to_canonical_offline_sale() -> None:
    result = map_toss_order_line_to_sale(
        tenant_id="demo_store",
        order=_order(),
        line_item=_line(),
        line_index=0,
        approved_sku_by_product_code={
            "TOSS-P001": "sku_demo_001",
        },
        ingested_at=FIXED_INGESTED_AT,
    )

    assert result.status == "MAPPED"
    assert result.event is not None
    assert result.event.source.value == "TOSS_POS"
    assert result.event.event_type.value == "offline_sale.recorded"
    assert result.event.payload["sku_id"] == "sku_demo_001"
    assert result.event.payload["quantity"] == 2
    assert result.event.payload["external_product_code"] == "TOSS-P001"


def test_missing_product_code_goes_to_mapping_required() -> None:
    line = _line()
    line["item"] = {"code": "", "title": "코드 없는 상품"}

    result = map_toss_order_line_to_sale(
        tenant_id="demo_store",
        order=_order(),
        line_item=line,
        line_index=0,
        approved_sku_by_product_code={},
        ingested_at=FIXED_INGESTED_AT,
    )

    assert result.status == "MAPPING_REQUIRED"
    assert result.reason == "MISSING_PRODUCT_CODE"
    assert result.event is None


def test_unknown_product_code_goes_to_mapping_required() -> None:
    result = map_toss_order_line_to_sale(
        tenant_id="demo_store",
        order=_order(),
        line_item=_line(),
        line_index=0,
        approved_sku_by_product_code={},
        ingested_at=FIXED_INGESTED_AT,
    )

    assert result.status == "MAPPING_REQUIRED"
    assert result.reason == "UNKNOWN_PRODUCT_CODE"
    assert result.event is None


def test_same_toss_line_has_one_business_effect() -> None:
    result = map_toss_order_line_to_sale(
        tenant_id="demo_store",
        order=_order(),
        line_item=_line(),
        line_index=0,
        approved_sku_by_product_code={
            "TOSS-P001": "sku_demo_001",
        },
        ingested_at=FIXED_INGESTED_AT,
    )

    assert result.event is not None

    pipeline = OfflineSalePipeline()

    first = pipeline.process(result.event.model_dump(mode="json"))
    second = pipeline.process(result.event.model_dump(mode="json"))

    assert first.status == "ACCEPTED"
    assert second.status == "REPLAYED"

    assert pipeline.inbox.accepted_count == 1
    assert pipeline.inbox.replayed_count == 1
    assert pipeline.effects.business_effect_count == 1
    assert len(pipeline.insights) == 1


def _map(
    *,
    order: dict[str, object] | None = None,
    line: dict[str, object] | None = None,
    tenant_id: str = "demo_store",
):
    return map_toss_order_line_to_sale(
        tenant_id=tenant_id,
        order=order if order is not None else _order(),
        line_item=line if line is not None else _line(),
        line_index=0,
        approved_sku_by_product_code={"TOSS-P001": "sku_demo_001"},
        ingested_at=FIXED_INGESTED_AT,
    )


def test_malformed_item_object_is_quarantined() -> None:
    line = _line()
    line["item"] = ["not", "an", "object"]

    result = _map(line=line)

    assert result.status == "QUARANTINED"
    assert result.reason == "MISSING_ITEM"
    assert result.event is None


def test_missing_order_id_is_quarantined() -> None:
    order = _order()
    order["id"] = ""

    result = _map(order=order)

    assert result.status == "QUARANTINED"
    assert result.reason == "MISSING_ORDER_ID"
    assert result.event is None


@pytest.mark.parametrize("quantity", [0, -1, True])
def test_non_positive_or_bool_quantity_is_not_inferred(quantity: object) -> None:
    line = _line()
    line["quantity"] = quantity

    result = _map(line=line)

    assert result.status == "QUARANTINED"
    assert result.reason == "INVALID_QUANTITY"
    assert result.event is None


@pytest.mark.parametrize(
    ("timestamp", "reason"),
    [
        ("not-a-timestamp", "INVALID_OCCURRED_AT"),
        ("2026-09-05T10:05:00", "TIMEZONE_REQUIRED"),
    ],
)
def test_invalid_or_naive_timestamp_is_quarantined(timestamp: str, reason: str) -> None:
    order = _order()
    order["completedAt"] = timestamp

    result = _map(order=order)

    assert result.status == "QUARANTINED"
    assert result.reason == reason
    assert result.event is None


def test_unknown_order_state_is_preserved_without_guessing() -> None:
    order = _order()
    order["orderState"] = "FUTURE_PROVIDER_STATE"

    result = _map(order=order)

    assert result.event is not None
    assert result.event.payload["order_state"] == "FUTURE_PROVIDER_STATE"


def test_cancelled_order_does_not_create_negative_or_sale_effect() -> None:
    order = _order()
    order["orderState"] = "CANCELLED"

    result = _map(order=order)

    assert result.status == "IGNORED_CANCELLED"
    assert result.event is None


def test_same_source_event_is_distinct_across_tenants() -> None:
    first = _map(tenant_id="store_a")
    second = _map(tenant_id="store_b")
    assert first.event is not None
    assert second.event is not None

    pipeline = OfflineSalePipeline()
    assert pipeline.process(first.event.model_dump(mode="json")).status == "ACCEPTED"
    assert pipeline.process(second.event.model_dump(mode="json")).status == "ACCEPTED"
    assert pipeline.effects.business_effect_count == 2


def test_unapproved_code_is_not_merged_from_matching_product_text() -> None:
    result = map_toss_order_line_to_sale(
        tenant_id="demo_store",
        order=_order(),
        line_item=_line(),
        line_index=0,
        approved_sku_by_product_code={"OTHER-CODE": "sku_demo_001"},
        ingested_at=FIXED_INGESTED_AT,
    )

    assert result.status == "MAPPING_REQUIRED"
    assert result.reason == "UNKNOWN_PRODUCT_CODE"
    assert result.event is None


def test_unselected_nested_pii_is_not_copied_to_canonical_payload() -> None:
    order = _order()
    order["buyer"] = {"email": "SYNTHETIC_EMAIL_VALUE"}
    line = _line()
    line["receiver"] = {"address": "SYNTHETIC_ADDRESS_VALUE"}

    result = _map(order=order, line=line)

    assert result.event is not None
    payload_text = str(result.event.payload)
    assert "SYNTHETIC_EMAIL_VALUE" not in payload_text
    assert "SYNTHETIC_ADDRESS_VALUE" not in payload_text
