from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.db.base import Base
from backend.app.models.catalog import SKU, Brand, Product
from backend.app.models.commerce import InventoryLedger, InventorySnapshot
from backend.app.services.inventory_ledger import (
    AmbiguousInventorySnapshot,
    BusinessIdentityCollision,
    InventoryLedgerRepository,
    InventoryLedgerService,
)


def _db_session() -> tuple[Session, dict[str, SKU]]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    session = Session(engine)
    skus: dict[str, SKU] = {}
    for tenant_id in ("store-a", "store-b"):
        brand = Brand(
            tenant_id=tenant_id,
            canonical_name=f"Synthetic Brand {tenant_id}",
            aliases=[],
        )
        product = Product(
            tenant_id=tenant_id,
            name=f"Synthetic Product {tenant_id}",
            brand=brand,
        )
        sku = SKU(
            tenant_id=tenant_id,
            product=product,
            canonical_code=f"SKU-{tenant_id}",
            status="ACTIVE",
        )
        session.add(sku)
        skus[tenant_id] = sku
    session.commit()
    return session, skus


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


def test_delta_total_uses_strict_snapshot_cutoff() -> None:
    ledger = InventoryLedgerService()
    snapshot_as_of = datetime(2026, 9, 23, 10, 0, tzinfo=UTC)

    for business_key, minute in (
        ("before", 59),
        ("after", 10),
    ):
        hour = 9 if business_key == "before" else 10
        ledger.append_once(
            tenant_id="store-a",
            sku_id="sku-001",
            delta=-1,
            reason="OFFLINE_SALE",
            business_key=business_key,
            source_event_id=business_key,
            occurred_at=datetime(2026, 9, 23, hour, minute, tzinfo=UTC),
        )
    ledger.append_once(
        tenant_id="store-a",
        sku_id="sku-001",
        delta=-1,
        reason="OFFLINE_SALE",
        business_key="equal",
        source_event_id="equal",
        occurred_at=snapshot_as_of,
    )

    assert ledger.delta_total(
        tenant_id="store-a",
        sku_id="sku-001",
        snapshot_as_of=snapshot_as_of,
    ) == -1
    assert ledger.delta_total(
        tenant_id="store-a",
        sku_id="sku-001",
    ) == -3


def test_delta_total_rejects_naive_snapshot_cutoff() -> None:
    ledger = InventoryLedgerService()

    with pytest.raises(ValueError, match="snapshot_as_of must include timezone"):
        ledger.delta_total(
            tenant_id="store-a",
            sku_id="sku-001",
            snapshot_as_of=datetime(2026, 9, 23, 10, 0),
        )


def test_db_append_once_replays_by_business_key_across_source_events() -> None:
    session, skus = _db_session()
    repository = InventoryLedgerRepository(session)
    occurred_at = datetime(2026, 9, 23, 10, 0, tzinfo=UTC)

    assert repository.append_once(
        tenant_id="store-a",
        sku_id=skus["store-a"].id,
        delta=-1,
        reason="OFFLINE_SALE",
        business_key="business-a",
        source_event_id="evt-1",
        occurred_at=occurred_at,
    ) is True
    assert repository.append_once(
        tenant_id="store-a",
        sku_id=skus["store-a"].id,
        delta=-1,
        reason="OFFLINE_SALE",
        business_key="business-a",
        source_event_id="evt-2",
        occurred_at=occurred_at,
    ) is False
    assert session.query(InventoryLedger).count() == 1
    session.close()


@pytest.mark.parametrize(
    "field, value",
    [
        ("sku_id", "other-sku"),
        ("reason", "INCOMING_STOCK"),
        ("delta", 2),
        ("occurred_at", datetime(2026, 9, 23, 10, 1, tzinfo=UTC)),
    ],
)
def test_db_append_once_rejects_business_identity_collision(
    field: str,
    value: object,
) -> None:
    session, skus = _db_session()
    repository = InventoryLedgerRepository(session)
    occurred_at = datetime(2026, 9, 23, 10, 0, tzinfo=UTC)
    first = {
        "tenant_id": "store-a",
        "sku_id": skus["store-a"].id,
        "delta": -1,
        "reason": "OFFLINE_SALE",
        "business_key": "business-a",
        "source_event_id": "evt-1",
        "occurred_at": occurred_at,
    }
    repository.append_once(**first)
    first[field] = skus["store-b"].id if field == "sku_id" else value

    with pytest.raises(BusinessIdentityCollision, match="BUSINESS_IDENTITY_COLLISION"):
        repository.append_once(**first)
    session.close()


def test_db_business_key_is_tenant_scoped_and_required() -> None:
    session, skus = _db_session()
    repository = InventoryLedgerRepository(session)
    occurred_at = datetime(2026, 9, 23, 10, 0, tzinfo=UTC)
    for tenant_id in ("store-a", "store-b"):
        assert repository.append_once(
            tenant_id=tenant_id,
            sku_id=skus[tenant_id].id,
            delta=-1,
            reason="OFFLINE_SALE",
            business_key="same-business-key",
            source_event_id=f"evt-{tenant_id}",
            occurred_at=occurred_at,
        ) is True

    with pytest.raises(ValueError, match="business_key is required"):
        repository.append_once(
            tenant_id="store-a",
            sku_id=skus["store-a"].id,
            delta=-1,
            reason="OFFLINE_SALE",
            business_key="",
            source_event_id="evt-empty",
            occurred_at=occurred_at,
        )
    with pytest.raises(ValueError, match="occurred_at must include timezone"):
        repository.append_once(
            tenant_id="store-a",
            sku_id=skus["store-a"].id,
            delta=-1,
            reason="OFFLINE_SALE",
            business_key="business-naive",
            source_event_id="evt-naive",
            occurred_at=datetime(2026, 9, 23, 10, 0),
        )
    assert session.query(InventoryLedger).count() == 2
    session.close()


def test_db_business_key_unique_constraint_rejects_same_tenant_duplicate() -> None:
    session, skus = _db_session()
    occurred_at = datetime(2026, 9, 23, 10, 0, tzinfo=UTC)
    session.add(
        InventoryLedger(
            tenant_id="store-a",
            sku_id=skus["store-a"].id,
            delta=-1,
            reason="OFFLINE_SALE",
            business_key="business-a",
            source_event_id="evt-1",
            occurred_at=occurred_at,
        )
    )
    session.commit()
    session.add(
        InventoryLedger(
            tenant_id="store-a",
            sku_id=skus["store-a"].id,
            delta=-1,
            reason="OFFLINE_SALE",
            business_key="business-a",
            source_event_id="evt-2",
            occurred_at=occurred_at,
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
    session.close()


def test_db_cutoff_is_strict_and_latest_snapshot_is_provider_scoped() -> None:
    session, skus = _db_session()
    repository = InventoryLedgerRepository(session)
    snapshot_as_of = datetime(2026, 9, 23, 10, 0, tzinfo=UTC)
    for business_key, occurred_at in (
        ("before", datetime(2026, 9, 23, 9, 59, tzinfo=UTC)),
        ("equal", snapshot_as_of),
        ("after", datetime(2026, 9, 23, 10, 1, tzinfo=UTC)),
    ):
        repository.append_once(
            tenant_id="store-a",
            sku_id=skus["store-a"].id,
            delta=-1,
            reason="OFFLINE_SALE",
            business_key=business_key,
            source_event_id=f"evt-{business_key}",
            occurred_at=occurred_at,
        )

    session.add_all(
        [
            InventorySnapshot(
                tenant_id="store-a",
                provider="DEMO",
                sku_id=skus["store-a"].id,
                on_hand=8,
                reserved=0,
                as_of=datetime(2026, 9, 23, 9, 0, tzinfo=UTC),
            ),
            InventorySnapshot(
                tenant_id="store-a",
                provider="DEMO",
                sku_id=skus["store-a"].id,
                on_hand=7,
                reserved=0,
                as_of=snapshot_as_of,
            ),
        ]
    )
    session.commit()

    latest = repository.latest_snapshot(
        tenant_id="store-a",
        sku_id=skus["store-a"].id,
        provider="DEMO",
    )
    assert latest is not None
    assert latest.on_hand == 7
    latest_without_provider = repository.latest_snapshot(
        tenant_id="store-a",
        sku_id=skus["store-a"].id,
    )
    assert latest_without_provider is not None
    assert latest_without_provider.on_hand == 7
    assert repository.delta_total_after_snapshot(
        tenant_id="store-a",
        sku_id=skus["store-a"].id,
        snapshot_as_of=snapshot_as_of,
    ) == -1
    session.close()


def test_db_latest_snapshot_requires_provider_for_multiple_providers() -> None:
    session, skus = _db_session()
    session.add_all(
        [
            InventorySnapshot(
                tenant_id="store-a",
                provider="DEMO",
                sku_id=skus["store-a"].id,
                on_hand=8,
                reserved=0,
                as_of=datetime(2026, 9, 23, 10, 0, tzinfo=UTC),
            ),
            InventorySnapshot(
                tenant_id="store-a",
                provider="ECOUNT",
                sku_id=skus["store-a"].id,
                on_hand=8,
                reserved=0,
                as_of=datetime(2026, 9, 23, 10, 1, tzinfo=UTC),
            ),
        ]
    )
    session.commit()
    repository = InventoryLedgerRepository(session)

    with pytest.raises(AmbiguousInventorySnapshot, match="provider is required"):
        repository.latest_snapshot(
            tenant_id="store-a",
            sku_id=skus["store-a"].id,
        )
    assert repository.latest_snapshot(
        tenant_id="store-a",
        sku_id=skus["store-a"].id,
        provider="DEMO",
    ).provider == "DEMO"
    session.close()
