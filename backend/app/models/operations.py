"""D02-BE-03 reservation, incoming stock, launch, and task models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, IdentityMixin, TenantMixin, VersionedMixin


class ReservationOrder(Base, IdentityMixin, TenantMixin, VersionedMixin):
    __tablename__ = "reservation_orders"
    __table_args__ = (
        UniqueConstraint("tenant_id", "order_id"),
        CheckConstraint("required_quantity > 0", name="ck_reservation_required_positive"),
        CheckConstraint("secured_quantity >= 0", name="ck_reservation_secured_nonnegative"),
        CheckConstraint("aging_hours >= 0", name="ck_reservation_aging_nonnegative"),
        ForeignKeyConstraint(
            ["tenant_id", "order_id"],
            ["orders.tenant_id", "orders.id"],
            name="fk_reservation_orders_order_same_tenant",
        ),
    )

    order_id: Mapped[str] = mapped_column(String(36), nullable=False)
    promised_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    required_quantity: Mapped[int] = mapped_column(nullable=False)
    secured_quantity: Mapped[int] = mapped_column(nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    aging_hours: Mapped[int] = mapped_column(nullable=False, default=0)


class IncomingStock(Base, IdentityMixin, TenantMixin, VersionedMixin):
    __tablename__ = "incoming_stock"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_incoming_qty_positive"),
        ForeignKeyConstraint(
            ["tenant_id", "sku_id"],
            ["skus.tenant_id", "skus.id"],
            name="fk_incoming_stock_sku_same_tenant",
        ),
    )

    sku_id: Mapped[str] = mapped_column(String(36), nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    expected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confidence_status: Mapped[str] = mapped_column(String(32), nullable=False)


class LaunchEvent(Base, IdentityMixin, TenantMixin, VersionedMixin):
    __tablename__ = "launch_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "product_id"],
            ["products.tenant_id", "products.id"],
            name="fk_launch_events_product_same_tenant",
        ),
    )

    product_id: Mapped[str] = mapped_column(String(36), nullable=False)
    launch_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    flow_template: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)


class Task(Base, IdentityMixin, TenantMixin, VersionedMixin):
    __tablename__ = "tasks"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint(
            "status IN ('PROPOSED', 'APPROVED', 'IN_PROGRESS', 'DONE', 'BLOCKED', 'DISMISSED')",
            name="ck_task_status_allowed",
        ),
    )

    task_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    priority: Mapped[int] = mapped_column(nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PROPOSED")
    source_reason: Mapped[str] = mapped_column(String(255), nullable=False)


class TaskDependency(Base, IdentityMixin, TenantMixin, VersionedMixin):
    __tablename__ = "task_dependencies"
    __table_args__ = (
        UniqueConstraint("tenant_id", "predecessor_id", "successor_id"),
        CheckConstraint("predecessor_id <> successor_id", name="ck_task_no_self_dependency"),
        ForeignKeyConstraint(
            ["tenant_id", "predecessor_id"],
            ["tasks.tenant_id", "tasks.id"],
            name="fk_task_dependencies_predecessor_same_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "successor_id"],
            ["tasks.tenant_id", "tasks.id"],
            name="fk_task_dependencies_successor_same_tenant",
        ),
    )

    predecessor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    successor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    lag_hours: Mapped[int] = mapped_column(nullable=False, default=0)
