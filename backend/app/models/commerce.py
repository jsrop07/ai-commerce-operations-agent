"""D02-BE-02 commerce and append-only inventory models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Numeric,
    String,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from backend.app.db.base import Base, IdentityMixin, TenantMixin, VersionedMixin


class Order(Base, IdentityMixin, TenantMixin, VersionedMixin):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("tenant_id", "provider", "external_id"),
        UniqueConstraint("tenant_id", "id"),
    )

    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    order_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    ordered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    customer_ref: Mapped[str | None] = mapped_column(String(255))
    lines: Mapped[list[OrderLine]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class OrderLine(Base, IdentityMixin, TenantMixin, VersionedMixin):
    __tablename__ = "order_lines"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_order_line_qty_positive"),
        ForeignKeyConstraint(
            ["tenant_id", "order_id"],
            ["orders.tenant_id", "orders.id"],
            name="fk_order_lines_order_same_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "sku_id"],
            ["skus.tenant_id", "skus.id"],
            name="fk_order_lines_sku_same_tenant",
        ),
    )

    order_id: Mapped[str] = mapped_column(String(36), nullable=False)
    sku_id: Mapped[str | None] = mapped_column(String(36))
    external_sku_text: Mapped[str | None] = mapped_column(String(255))
    quantity: Mapped[int] = mapped_column(nullable=False)
    unit_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="KRW")
    order: Mapped[Order] = relationship(back_populates="lines")


class SaleEvent(Base, IdentityMixin, TenantMixin, VersionedMixin):
    __tablename__ = "sale_events"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source", "source_event_id", "schema_version"),
        UniqueConstraint("tenant_id", "event_id"),
        CheckConstraint("quantity > 0", name="ck_sale_qty_positive"),
        ForeignKeyConstraint(
            ["tenant_id", "sku_id"],
            ["skus.tenant_id", "skus.id"],
            name="fk_sale_events_sku_same_tenant",
        ),
    )

    event_id: Mapped[str] = mapped_column(String(200), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    sku_id: Mapped[str] = mapped_column(String(36), nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class InventorySnapshot(Base, IdentityMixin, TenantMixin, VersionedMixin):
    __tablename__ = "inventory_snapshots"
    __table_args__ = (
        UniqueConstraint("tenant_id", "provider", "sku_id", "as_of"),
        ForeignKeyConstraint(
            ["tenant_id", "sku_id"],
            ["skus.tenant_id", "skus.id"],
            name="fk_inventory_snapshots_sku_same_tenant",
        ),
    )

    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    sku_id: Mapped[str] = mapped_column(String(36), nullable=False)
    on_hand: Mapped[int] = mapped_column(nullable=False)
    reserved: Mapped[int] = mapped_column(nullable=False, default=0)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class InventoryLedger(Base, IdentityMixin, TenantMixin, VersionedMixin):
    __tablename__ = "inventory_ledger"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source_event_id", "sku_id", "reason"),
        ForeignKeyConstraint(
            ["tenant_id", "sku_id"],
            ["skus.tenant_id", "skus.id"],
            name="fk_inventory_ledger_sku_same_tenant",
        ),
    )

    sku_id: Mapped[str] = mapped_column(String(36), nullable=False)
    delta: Mapped[int] = mapped_column(nullable=False)
    reason: Mapped[str] = mapped_column(String(80), nullable=False)
    source_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


@event.listens_for(InventoryLedger, "before_update")
@event.listens_for(InventoryLedger, "before_delete")
def _prevent_ledger_mutation(*_: object) -> None:
    raise ValueError("InventoryLedger is append-only; write a correction event")


@event.listens_for(Session, "do_orm_execute")
def _prevent_bulk_ledger_mutation(execute_state: object) -> None:
    if not (execute_state.is_update or execute_state.is_delete):
        return
    mapper = execute_state.bind_mapper
    if mapper is not None and mapper.class_ is InventoryLedger:
        raise ValueError("InventoryLedger is append-only; write a correction event")
