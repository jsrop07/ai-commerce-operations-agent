from backend.app.services.inventory_projection import (
    build_inventory_projection,
)


def test_expected_inventory_is_snapshot_plus_delta_minus_reserved() -> None:
    result = build_inventory_projection(
        tenant_id="store-a",
        sku_id="sku-001",
        source_on_hand=10,
        ledger_delta=-2,
        reserved=3,
        confirmed_incoming=5,
        quality_status="CONFIRMED",
        ttl_seconds=300,
        age_seconds=120,
    )

    assert result.expected_inventory == 5
    assert result.confirmed_for_total is True
    assert result.freshness_reason == "FRESH"

    assert result.calculation == {
        "source_on_hand": 10,
        "ledger_delta": -2,
        "reserved": 3,
        "expected_inventory": 5,
    }


def test_source_on_hand_none_is_not_converted_to_zero() -> None:
    result = build_inventory_projection(
        tenant_id="store-a",
        sku_id="sku-001",
        source_on_hand=None,
        ledger_delta=-2,
        reserved=1,
        confirmed_incoming=None,
        quality_status="CONFIRMED",
        ttl_seconds=300,
        age_seconds=30,
    )

    assert result.expected_inventory is None
    assert result.confirmed_for_total is False
    assert result.freshness_reason == "SOURCE_ON_HAND_UNKNOWN"


def test_reserved_none_is_not_converted_to_zero() -> None:
    result = build_inventory_projection(
        tenant_id="store-a",
        sku_id="sku-001",
        source_on_hand=10,
        ledger_delta=-2,
        reserved=None,
        confirmed_incoming=None,
        quality_status="CONFIRMED",
        ttl_seconds=300,
        age_seconds=30,
    )

    assert result.expected_inventory is None
    assert result.confirmed_for_total is False
    assert result.freshness_reason == "RESERVED_UNKNOWN"


def test_stale_projection_is_not_confirmed_for_total() -> None:
    result = build_inventory_projection(
        tenant_id="store-a",
        sku_id="sku-001",
        source_on_hand=10,
        ledger_delta=-2,
        reserved=1,
        confirmed_incoming=3,
        quality_status="CONFIRMED",
        ttl_seconds=300,
        age_seconds=301,
    )

    assert result.expected_inventory == 7
    assert result.freshness_reason == "STALE"
    assert result.confirmed_for_total is False


def test_unconfirmed_quality_is_excluded() -> None:
    result = build_inventory_projection(
        tenant_id="store-a",
        sku_id="sku-001",
        source_on_hand=10,
        ledger_delta=-2,
        reserved=1,
        confirmed_incoming=None,
        quality_status="SOURCE_QUALITY_BLOCKED",
        ttl_seconds=300,
        age_seconds=100,
    )

    assert result.expected_inventory is None
    assert result.confirmed_for_total is False
    assert result.freshness_reason == "SOURCE_QUALITY_NOT_CONFIRMED"
