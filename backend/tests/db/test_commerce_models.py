from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.db.base import Base
from backend.app.models.catalog import SKU, Brand, Product
from backend.app.models.commerce import (
    InventoryLedger,
    InventorySnapshot,
    Order,
    OrderLine,
    SaleEvent,
)


def seeded_session() -> tuple[Session, SKU]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    session = Session(engine)
    brand = Brand(tenant_id="demo_store", canonical_name="Synthetic Brand", aliases=[])
    product = Product(tenant_id="demo_store", name="Synthetic Product", brand=brand)
    sku = SKU(tenant_id="demo_store", product=product, canonical_code="SKU-DEMO-1", status="ACTIVE")
    session.add(sku)
    session.commit()
    return session, sku


def test_sale_quantity_and_source_event_uniqueness() -> None:
    session, sku = seeded_session()
    now = datetime.now(UTC)
    session.add(
        SaleEvent(
            tenant_id="demo_store",
            event_id="evt-negative",
            source="TOSS_POS",
            source_event_id="sale-negative",
            channel="OFFLINE",
            sku_id=sku.id,
            quantity=-1,
            amount=1000,
            occurred_at=now,
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.close()


def test_inventory_ledger_is_append_only() -> None:
    session, sku = seeded_session()
    ledger = InventoryLedger(
        tenant_id="demo_store",
        sku_id=sku.id,
        delta=-1,
        reason="OFFLINE_SALE",
        source_event_id="sale-1",
        occurred_at=datetime.now(UTC),
    )
    session.add(ledger)
    session.commit()
    ledger.delta = -2
    with pytest.raises(ValueError, match="append-only"):
        session.commit()
    session.close()


def test_sale_source_event_is_idempotent_per_tenant_source_and_version() -> None:
    session, sku = seeded_session()
    now = datetime.now(UTC)

    first = SaleEvent(
        tenant_id="demo_store",
        event_id="evt-sale-1",
        source="TOSS_POS",
        source_event_id="source-sale-1",
        channel="OFFLINE",
        sku_id=sku.id,
        quantity=1,
        amount=1000,
        occurred_at=now,
    )
    session.add(first)
    session.commit()

    duplicate = SaleEvent(
        tenant_id="demo_store",
        event_id="evt-sale-2",
        source="TOSS_POS",
        source_event_id="source-sale-1",
        channel="OFFLINE",
        sku_id=sku.id,
        quantity=1,
        amount=1000,
        occurred_at=now,
    )
    session.add(duplicate)

    with pytest.raises(IntegrityError):
        session.commit()

    session.close()


def test_sale_canonical_event_id_is_unique_per_tenant() -> None:
    session, sku = seeded_session()
    now = datetime.now(UTC)
    session.add_all(
        [
            SaleEvent(
                tenant_id="demo_store",
                event_id="evt-canonical-1",
                source="TOSS_POS",
                source_event_id="source-1",
                channel="OFFLINE",
                sku_id=sku.id,
                quantity=1,
                amount=1000,
                occurred_at=now,
            ),
            SaleEvent(
                tenant_id="demo_store",
                event_id="evt-canonical-1",
                source="TOSS_POS",
                source_event_id="source-2",
                channel="OFFLINE",
                sku_id=sku.id,
                quantity=1,
                amount=1000,
                occurred_at=now,
            ),
        ]
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.close()


@pytest.mark.parametrize("quantity", [0, -1])
def test_order_line_quantity_must_be_positive(quantity: int) -> None:
    session, sku = seeded_session()
    order = Order(
        tenant_id="demo_store",
        provider="DEMO",
        external_id=f"order-{quantity}",
        order_type="STANDARD",
        status="CREATED",
        ordered_at=datetime.now(UTC),
    )
    session.add(order)
    session.flush()
    session.add(
        OrderLine(
            tenant_id="demo_store",
            order_id=order.id,
            sku_id=sku.id,
            quantity=quantity,
            unit_amount=1000,
            currency="KRW",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.close()


def test_commerce_sku_foreign_keys_are_tenant_scoped() -> None:
    expected = (("tenant_id", "sku_id"), ("skus.tenant_id", "skus.id"))
    for model in (OrderLine, SaleEvent, InventorySnapshot, InventoryLedger):
        foreign_keys = {
            (
                tuple(element.parent.name for element in constraint.elements),
                tuple(element.target_fullname for element in constraint.elements),
            )
            for constraint in model.__table__.foreign_key_constraints
        }
        assert expected in foreign_keys


def test_cross_tenant_sale_event_is_rejected() -> None:
    session, sku = seeded_session()
    session.add(
        SaleEvent(
            tenant_id="other_tenant",
            event_id="evt-cross-tenant",
            source="TOSS_POS",
            source_event_id="source-cross-tenant",
            channel="OFFLINE",
            sku_id=sku.id,
            quantity=1,
            amount=1000,
            occurred_at=datetime.now(UTC),
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.close()


def test_inventory_ledger_rejects_duplicate_effect_and_delete() -> None:
    session, sku = seeded_session()
    ledger = InventoryLedger(
        tenant_id="demo_store",
        sku_id=sku.id,
        delta=-1,
        reason="OFFLINE_SALE",
        source_event_id="sale-duplicate",
        occurred_at=datetime.now(UTC),
    )
    session.add(ledger)
    session.commit()

    session.add(
        InventoryLedger(
            tenant_id="demo_store",
            sku_id=sku.id,
            delta=-1,
            reason="OFFLINE_SALE",
            source_event_id="sale-duplicate",
            occurred_at=datetime.now(UTC),
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()

    with pytest.raises(ValueError, match="append-only"):
        session.execute(
            update(InventoryLedger)
            .where(InventoryLedger.id == ledger.id)
            .values(delta=-2)
        )

    session.delete(ledger)
    with pytest.raises(ValueError, match="append-only"):
        session.commit()
    session.close()
