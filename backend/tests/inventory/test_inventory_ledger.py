from datetime import UTC, datetime

import pytest

from backend.app.services.inventory_ledger import InventoryLedgerService


def test_sale_delta_is_appended() -> None:
    ledger = InventoryLedgerService()

    applied = ledger.append_once(
        tenant_id="store-a",
        sku_id="sku-001",
        delta=-2,
        reason="OFFLINE_SALE",
        business_key="business-sale-001",
        source_event_id="order-100:line:0",
        occurred_at=datetime(2026, 9, 6, 10, 30, tzinfo=UTC),
    )

    assert applied is True
    assert len(ledger.entries) == 1
    assert (
        ledger.delta_total(
            tenant_id="store-a",
            sku_id="sku-001",
        )
        == -2
    )


def test_same_business_fact_is_not_appended_twice() -> None:
    ledger = InventoryLedgerService()
    occurred_at = datetime(2026, 9, 6, 10, 30, tzinfo=UTC)

    first = ledger.append_once(
        tenant_id="store-a",
        sku_id="sku-001",
        delta=-1,
        reason="OFFLINE_SALE",
        business_key="business-sale-001",
        source_event_id="order-100:line:0",
        occurred_at=occurred_at,
    )

    second = ledger.append_once(
        tenant_id="store-a",
        sku_id="sku-001",
        delta=-1,
        reason="OFFLINE_SALE",
        business_key="business-sale-001",
        source_event_id="file-a:row:100",
        occurred_at=occurred_at,
    )

    assert first is True
    assert second is False
    assert len(ledger.entries) == 1

    assert (
        ledger.delta_total(
            tenant_id="store-a",
            sku_id="sku-001",
        )
        == -1
    )


def test_different_business_facts_are_accumulated() -> None:
    ledger = InventoryLedgerService()
    occurred_at = datetime(2026, 9, 6, 10, 30, tzinfo=UTC)

    assert (
        ledger.append_once(
            tenant_id="store-a",
            sku_id="sku-001",
            delta=-2,
            reason="OFFLINE_SALE",
            business_key="sale-001",
            source_event_id="event-001",
            occurred_at=occurred_at,
        )
        is True
    )

    assert (
        ledger.append_once(
            tenant_id="store-a",
            sku_id="sku-001",
            delta=5,
            reason="INCOMING_STOCK",
            business_key="incoming-001",
            source_event_id="event-002",
            occurred_at=occurred_at,
        )
        is True
    )

    assert (
        ledger.delta_total(
            tenant_id="store-a",
            sku_id="sku-001",
        )
        == 3
    )


def test_same_business_key_different_sku_is_collision() -> None:
    ledger = InventoryLedgerService()
    occurred_at = datetime(2026, 9, 6, 10, 30, tzinfo=UTC)

    assert (
        ledger.append_once(
            tenant_id="store-a",
            sku_id="sku-001",
            delta=-1,
            reason="OFFLINE_SALE",
            business_key="sale-001",
            source_event_id="event-001",
            occurred_at=occurred_at,
        )
        is True
    )

    with pytest.raises(ValueError, match="BUSINESS_IDENTITY_COLLISION"):
        ledger.append_once(
            tenant_id="store-a",
            sku_id="sku-002",
            delta=-1,
            reason="OFFLINE_SALE",
            business_key="sale-001",
            source_event_id="event-001",
            occurred_at=occurred_at,
        )

    assert len(ledger.entries) == 1


def test_naive_occurred_at_is_rejected() -> None:
    ledger = InventoryLedgerService()

    try:
        ledger.append_once(
            tenant_id="store-a",
            sku_id="sku-001",
            delta=-1,
            reason="OFFLINE_SALE",
            business_key="sale-001",
            source_event_id="event-001",
            occurred_at=datetime(2026, 9, 6, 10, 30),
        )
    except ValueError as exc:
        assert str(exc) == "occurred_at must include timezone"
    else:
        raise AssertionError("naive occurred_at must be rejected")
