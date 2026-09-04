from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.db.base import Base
from backend.app.models.catalog import SKU, Brand, Product
from backend.app.models.commerce import Order
from backend.app.models.operations import (
    IncomingStock,
    LaunchEvent,
    ReservationOrder,
    Task,
    TaskDependency,
)


def sqlite_engine():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    return engine


def add_catalog_and_order(session: Session, tenant_id: str = "demo_store") -> tuple[SKU, Order]:
    brand = Brand(tenant_id=tenant_id, canonical_name=f"Brand {tenant_id}", aliases=[])
    product = Product(tenant_id=tenant_id, name=f"Product {tenant_id}", brand=brand)
    sku = SKU(tenant_id=tenant_id, product=product, canonical_code=f"SKU-{tenant_id}")
    order = Order(
        tenant_id=tenant_id,
        provider="DEMO",
        external_id=f"ORDER-{tenant_id}",
        order_type="RESERVATION",
        status="CREATED",
        ordered_at=datetime.now(UTC),
    )
    session.add_all([sku, order])
    session.commit()
    return sku, order


def test_task_dependency_rejects_self_reference() -> None:
    engine = sqlite_engine()
    with Session(engine) as session:
        task = Task(
            tenant_id="demo_store",
            task_type="REVIEW",
            title="Review synthetic shortage",
            priority=10,
            status="PROPOSED",
            source_reason="reservation_shortage",
        )
        session.add(task)
        session.commit()
        session.add(
            TaskDependency(
                tenant_id="demo_store",
                predecessor_id=task.id,
                successor_id=task.id,
                lag_hours=0,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


@pytest.mark.parametrize(
    ("required_quantity", "secured_quantity", "aging_hours"),
    [(0, 0, 0), (1, -1, 0), (1, 0, -1)],
)
def test_reservation_quantity_and_aging_constraints(
    required_quantity: int, secured_quantity: int, aging_hours: int
) -> None:
    engine = sqlite_engine()
    with Session(engine) as session:
        _, order = add_catalog_and_order(session)
        session.add(
            ReservationOrder(
                tenant_id="demo_store",
                order_id=order.id,
                required_quantity=required_quantity,
                secured_quantity=secured_quantity,
                aging_hours=aging_hours,
                status="OPEN",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_reservation_allows_secured_quantity_above_required() -> None:
    engine = sqlite_engine()
    with Session(engine) as session:
        _, order = add_catalog_and_order(session)
        session.add(
            ReservationOrder(
                tenant_id="demo_store",
                order_id=order.id,
                required_quantity=1,
                secured_quantity=2,
                aging_hours=0,
                status="OPEN",
            )
        )
        session.commit()


def test_incoming_stock_quantity_must_be_positive() -> None:
    engine = sqlite_engine()
    with Session(engine) as session:
        sku, _ = add_catalog_and_order(session)
        session.add(
            IncomingStock(
                tenant_id="demo_store",
                sku_id=sku.id,
                quantity=0,
                expected_at=datetime.now(UTC),
                confidence_status="CONFIRMED",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_task_status_is_limited_to_the_official_contract() -> None:
    engine = sqlite_engine()
    with Session(engine) as session:
        session.add(
            Task(
                tenant_id="demo_store",
                task_type="REVIEW",
                title="Invalid status",
                priority=0,
                status="INVENTED",
                source_reason="contract_test",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_task_dependency_rejects_duplicate_and_cross_tenant_links() -> None:
    engine = sqlite_engine()
    with Session(engine) as session:
        predecessor = Task(
            tenant_id="tenant-a",
            task_type="REVIEW",
            title="Predecessor",
            status="PROPOSED",
            source_reason="dependency_test",
        )
        successor = Task(
            tenant_id="tenant-a",
            task_type="REVIEW",
            title="Successor",
            status="PROPOSED",
            source_reason="dependency_test",
        )
        other_tenant = Task(
            tenant_id="tenant-b",
            task_type="REVIEW",
            title="Other tenant",
            status="PROPOSED",
            source_reason="dependency_test",
        )
        session.add_all([predecessor, successor, other_tenant])
        session.commit()

        dependency = TaskDependency(
            tenant_id="tenant-a",
            predecessor_id=predecessor.id,
            successor_id=successor.id,
        )
        session.add(dependency)
        session.commit()
        session.add(
            TaskDependency(
                tenant_id="tenant-a",
                predecessor_id=predecessor.id,
                successor_id=successor.id,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        session.add(
            TaskDependency(
                tenant_id="tenant-a",
                predecessor_id=predecessor.id,
                successor_id=other_tenant.id,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_operations_foreign_keys_are_tenant_scoped() -> None:
    expected = {
        ReservationOrder: {(('tenant_id', 'order_id'), ('orders.tenant_id', 'orders.id'))},
        IncomingStock: {(('tenant_id', 'sku_id'), ('skus.tenant_id', 'skus.id'))},
        LaunchEvent: {(('tenant_id', 'product_id'), ('products.tenant_id', 'products.id'))},
        TaskDependency: {
            (('tenant_id', 'predecessor_id'), ('tasks.tenant_id', 'tasks.id')),
            (('tenant_id', 'successor_id'), ('tasks.tenant_id', 'tasks.id')),
        },
    }
    for model, required in expected.items():
        actual = {
            (
                tuple(element.parent.name for element in constraint.elements),
                tuple(element.target_fullname for element in constraint.elements),
            )
            for constraint in model.__table__.foreign_key_constraints
        }
        assert required <= actual
