from datetime import UTC, datetime

import pytest

from backend.app.adapters.providers.ecount.mapper import (
    map_ecount_inventory_fixture,
)
from backend.app.services.ingestion.idempotency import EffectRegistry
from backend.app.services.ingestion.inbox import InMemoryInbox

FIXED_INGESTED_AT = datetime(2026, 9, 5, 0, 0, tzinfo=UTC)


def _row() -> dict[str, object]:
    return {
        "source_record_id": "fixture-inventory-001",
        "product_code": "ECOUNT-P001",
        "warehouse_code": "WH-SEOUL",
        "unit": "EA",
        "on_hand": 12,
        "as_of": "2026-09-05T09:00:00+09:00",
    }


def test_ecount_inventory_maps_to_canonical_event() -> None:
    result = map_ecount_inventory_fixture(
        tenant_id="demo_store",
        row=_row(),
        approved_sku_by_product_code={
            "ECOUNT-P001": "sku_demo_001",
        },
        ingested_at=FIXED_INGESTED_AT,
    )

    assert result.status == "MAPPED"
    assert result.event is not None

    assert result.event.source.value == "ECOUNT"
    assert result.event.event_type.value == "inventory.snapshot_received"

    assert result.event.payload["sku_id"] == "sku_demo_001"
    assert result.event.payload["warehouse_code"] == "WH-SEOUL"
    assert result.event.payload["unit"] == "EA"
    assert result.event.payload["on_hand"] == 12


@pytest.mark.parametrize(
    ("field", "expected_reason"),
    [
        ("product_code", "MISSING_PRODUCT_CODE"),
        ("warehouse_code", "MISSING_WAREHOUSE_CODE"),
        ("unit", "MISSING_UNIT"),
    ],
)
def test_missing_required_identity_is_quarantined(
    field: str,
    expected_reason: str,
) -> None:
    row = _row()
    row[field] = ""

    result = map_ecount_inventory_fixture(
        tenant_id="demo_store",
        row=row,
        approved_sku_by_product_code={
            "ECOUNT-P001": "sku_demo_001",
        },
        ingested_at=FIXED_INGESTED_AT,
    )

    assert result.status == "QUARANTINED"
    assert result.reason == expected_reason
    assert result.event is None


def test_unknown_product_code_is_quarantined() -> None:
    result = map_ecount_inventory_fixture(
        tenant_id="demo_store",
        row=_row(),
        approved_sku_by_product_code={},
        ingested_at=FIXED_INGESTED_AT,
    )

    assert result.status == "QUARANTINED"
    assert result.reason == "UNKNOWN_PRODUCT_CODE"
    assert result.event is None


def test_same_ecount_inventory_has_one_business_effect() -> None:
    result = map_ecount_inventory_fixture(
        tenant_id="demo_store",
        row=_row(),
        approved_sku_by_product_code={
            "ECOUNT-P001": "sku_demo_001",
        },
        ingested_at=FIXED_INGESTED_AT,
    )

    assert result.event is not None

    raw = result.event.model_dump(mode="json")

    inbox = InMemoryInbox()
    effects = EffectRegistry()

    first_event, first_receipt = inbox.ingest(raw)
    second_event, second_receipt = inbox.ingest(raw)

    assert first_event is not None
    assert second_event is not None

    assert first_receipt.status == "ACCEPTED"
    assert second_receipt.status == "REPLAYED"

    assert (
        effects.apply_once(
            first_event.tenant_id,
            "inventory_snapshot",
            first_event.idempotency_key,
        )
        is True
    )

    assert (
        effects.apply_once(
            second_event.tenant_id,
            "inventory_snapshot",
            second_event.idempotency_key,
        )
        is False
    )

    assert effects.business_effect_count == 1
    assert inbox.accepted_count == 1
    assert inbox.replayed_count == 1


def _map(
    *,
    row: dict[str, object] | None = None,
    tenant_id: str = "demo_store",
):
    return map_ecount_inventory_fixture(
        tenant_id=tenant_id,
        row=row if row is not None else _row(),
        approved_sku_by_product_code={"ECOUNT-P001": "sku_demo_001"},
        ingested_at=FIXED_INGESTED_AT,
    )


@pytest.mark.parametrize("on_hand", ["twelve", 1.5, True])
def test_malformed_or_bool_on_hand_is_quarantined(on_hand: object) -> None:
    row = _row()
    row["on_hand"] = on_hand

    result = _map(row=row)

    assert result.status == "QUARANTINED"
    assert result.reason == "INVALID_ON_HAND"
    assert result.event is None


@pytest.mark.parametrize(
    ("as_of", "reason"),
    [
        ("not-a-timestamp", "INVALID_AS_OF"),
        ("2026-09-05T09:00:00", "TIMEZONE_REQUIRED"),
    ],
)
def test_invalid_or_naive_as_of_is_quarantined(as_of: str, reason: str) -> None:
    row = _row()
    row["as_of"] = as_of

    result = _map(row=row)

    assert result.status == "QUARANTINED"
    assert result.reason == reason
    assert result.event is None


def test_missing_source_record_id_is_quarantined() -> None:
    row = _row()
    row["source_record_id"] = ""

    result = _map(row=row)

    assert result.status == "QUARANTINED"
    assert result.reason == "MISSING_SOURCE_RECORD_ID"
    assert result.event is None


def test_same_fixture_identity_is_distinct_across_tenants() -> None:
    first = _map(tenant_id="store_a")
    second = _map(tenant_id="store_b")
    assert first.event is not None
    assert second.event is not None

    inbox = InMemoryInbox()
    effects = EffectRegistry()
    first_event, first_receipt = inbox.ingest(first.event.model_dump(mode="json"))
    second_event, second_receipt = inbox.ingest(second.event.model_dump(mode="json"))

    assert first_event is not None
    assert second_event is not None
    assert first_receipt.status == second_receipt.status == "ACCEPTED"
    assert effects.apply_once("store_a", "inventory_snapshot", first_event.idempotency_key)
    assert effects.apply_once("store_b", "inventory_snapshot", second_event.idempotency_key)
    assert effects.business_effect_count == 2


def test_unselected_nested_pii_is_not_copied_to_canonical_payload() -> None:
    row = _row()
    row["contact"] = {"phone": "SYNTHETIC_PHONE_VALUE"}

    result = _map(row=row)

    assert result.event is not None
    assert "SYNTHETIC_PHONE_VALUE" not in str(result.event.payload)
