"""V2 operations models."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base_v2 import (
    BaseV2,
    TenantV2Mixin,
    TimestampV2Mixin,
    UUIDIdentityMixin,
)


class OrderV2(UUIDIdentityMixin, TenantV2Mixin, TimestampV2Mixin, BaseV2):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "id",
            name="uq_operations_orders_tenant_id_id",
        ),
        UniqueConstraint(
            "tenant_id",
            "source_system",
            "external_order_id",
            name="uq_operations_orders_external",
        ),
        Index(
            "ix_operations_orders_tenant_source_order_at",
            "tenant_id",
            "source_order_at",
        ),
        CheckConstraint(
            "paid IN ('T', 'F')",
            name="ck_operations_orders_paid",
        ),
        CheckConstraint(
            "shipping_status IN ('T', 'F', 'M')",
            name="ck_operations_orders_shipping_status",
        ),
        CheckConstraint(
            "canceled IN ('T', 'F', 'M')",
            name="ck_operations_orders_canceled",
        ),
        {"schema": "operations"},
    )

    external_order_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_system: Mapped[str] = mapped_column(String(32), nullable=False)
    paid: Mapped[str] = mapped_column(
        String(1),
        nullable=False,
    )

    shipping_status: Mapped[str] = mapped_column(
        String(1),
        nullable=False,
    )

    canceled: Mapped[str] = mapped_column(
        String(1),
        nullable=False,
    )
    total_order_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2), nullable=True
    )
    total_paid_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2), nullable=True
    )

    payment_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payment_method: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_order_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class OrderItemV2(UUIDIdentityMixin, TenantV2Mixin, BaseV2):
    __tablename__ = "order_items"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "id",
            name="uq_operations_order_items_tenant_id_id",
        ),
        UniqueConstraint(
            "tenant_id",
            "order_id",
            "external_order_item_id",
            name="uq_operations_order_items_external",
        ),
        CheckConstraint(
            "quantity > 0",
            name="ck_operations_order_items_quantity_positive",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "order_id"],
            ["operations.orders.tenant_id", "operations.orders.id"],
            name="fk_operations_order_items_order_same_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "product_id"],
            ["catalog.products.tenant_id", "catalog.products.id"],
            name="fk_operations_order_items_product_same_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "product_variant_id"],
            [
                "catalog.product_variants.tenant_id",
                "catalog.product_variants.id",
            ],
            name="fk_operations_order_items_variant_same_tenant",
            ondelete="RESTRICT",
        ),
        {"schema": "operations"},
    )

    order_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    external_order_item_id: Mapped[str] = mapped_column(
        String(255), nullable=False
    )

    external_product_no: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    product_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    product_variant_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )

    source_product_name: Mapped[str] = mapped_column(String(500), nullable=False)
    source_product_name_with_option: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )

    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    source_sale_price: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class InventorySnapshotV2(
    UUIDIdentityMixin,
    TenantV2Mixin,
    BaseV2,
):
    __tablename__ = "inventory_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "id",
            name="uq_operations_inventory_snapshots_tenant_id_id",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "product_id"],
            ["catalog.products.tenant_id", "catalog.products.id"],
            name="fk_operations_inventory_snapshots_product_same_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "product_variant_id"],
            [
                "catalog.product_variants.tenant_id",
                "catalog.product_variants.id",
            ],
            name="fk_operations_inventory_snapshots_variant_same_tenant",
            ondelete="RESTRICT",
        ),
        Index(
            "ix_operations_inventory_snapshots_product_latest",
            "tenant_id",
            "product_id",
            "source_system",
            "data_as_of",
        ),
        Index(
            "ix_operations_inventory_snapshots_variant_latest",
            "tenant_id",
            "product_variant_id",
            "source_system",
            "data_as_of",
        ),
        {"schema": "operations"},
    )

    product_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    product_variant_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )

    on_hand_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reserved_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)

    data_as_of: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    source_system: Mapped[str] = mapped_column(String(32), nullable=False)
    data_quality_status: Mapped[str] = mapped_column(String(32), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class IncomingShipmentV2(
    UUIDIdentityMixin,
    TenantV2Mixin,
    TimestampV2Mixin,
    BaseV2,
):
    __tablename__ = "incoming_shipments"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "id",
            name="uq_operations_incoming_shipments_tenant_id_id",
        ),
        CheckConstraint(
            "expected_quantity > 0",
            name="ck_operations_incoming_shipments_quantity_positive",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "product_id"],
            ["catalog.products.tenant_id", "catalog.products.id"],
            name="fk_operations_incoming_shipments_product_same_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "product_variant_id"],
            [
                "catalog.product_variants.tenant_id",
                "catalog.product_variants.id",
            ],
            name="fk_operations_incoming_shipments_variant_same_tenant",
            ondelete="RESTRICT",
        ),
        Index(
            "ix_operations_incoming_shipments_tenant_expected_arrival",
            "tenant_id",
            "expected_arrival_at",
        ),
        {"schema": "operations"},
    )

    product_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    product_variant_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )

    expected_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_arrival_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    incoming_status: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence_status: Mapped[str] = mapped_column(String(32), nullable=False)

    source_system: Mapped[str | None] = mapped_column(String(32), nullable=True)
    external_reference: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )


class InventoryMovementV2(
    UUIDIdentityMixin,
    TenantV2Mixin,
    BaseV2,
):
    __tablename__ = "inventory_movements"
    __table_args__ = (
        CheckConstraint(
            "quantity_change <> 0",
            name="ck_operations_inventory_movements_nonzero",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "product_id"],
            ["catalog.products.tenant_id", "catalog.products.id"],
            name="fk_operations_inventory_movements_product_same_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "product_variant_id"],
            [
                "catalog.product_variants.tenant_id",
                "catalog.product_variants.id",
            ],
            name="fk_operations_inventory_movements_variant_same_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "order_item_id"],
            ["operations.order_items.tenant_id", "operations.order_items.id"],
            name="fk_operations_inventory_movements_order_item_same_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "incoming_shipment_id"],
            [
                "operations.incoming_shipments.tenant_id",
                "operations.incoming_shipments.id",
            ],
            name="fk_operations_inventory_movements_incoming_same_tenant",
            ondelete="RESTRICT",
        ),
        {"schema": "operations"},
    )

    product_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    product_variant_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )

    quantity_change: Mapped[int] = mapped_column(Integer, nullable=False)
    movement_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_system: Mapped[str] = mapped_column(String(32), nullable=False)

    order_item_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    incoming_shipment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )

    external_event_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ReservationV2(
    UUIDIdentityMixin,
    TenantV2Mixin,
    TimestampV2Mixin,
    BaseV2,
):
    __tablename__ = "reservations"
    __table_args__ = (
        CheckConstraint(
            "required_quantity > 0",
            name="ck_operations_reservations_required_positive",
        ),
        CheckConstraint(
            "secured_quantity IS NULL OR secured_quantity >= 0",
            name="ck_operations_reservations_secured_nonnegative",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "product_id"],
            ["catalog.products.tenant_id", "catalog.products.id"],
            name="fk_operations_reservations_product_same_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "product_variant_id"],
            [
                "catalog.product_variants.tenant_id",
                "catalog.product_variants.id",
            ],
            name="fk_operations_reservations_variant_same_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "order_id"],
            ["operations.orders.tenant_id", "operations.orders.id"],
            name="fk_operations_reservations_order_same_tenant",
            ondelete="RESTRICT",
        ),
        {"schema": "operations"},
    )

    product_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    product_variant_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )

    # 실제 예약 source 단위가 확정될 때까지 nullable 유지.
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )

    required_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    secured_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)

    promised_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    reservation_status: Mapped[str] = mapped_column(String(32), nullable=False)
    source_quality_status: Mapped[str] = mapped_column(
        String(32), nullable=False
    )


class TaskV2(UUIDIdentityMixin, TenantV2Mixin, TimestampV2Mixin, BaseV2):
    __tablename__ = "tasks"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "id",
            name="uq_operations_tasks_tenant_id_id",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "product_id"],
            ["catalog.products.tenant_id", "catalog.products.id"],
            name="fk_operations_tasks_product_same_tenant",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "priority IS NULL OR (priority >= 0 AND priority <= 100)",
            name="ck_operations_tasks_priority_range",
        ),
        CheckConstraint(
            "task_status IN ('PROPOSED','APPROVED','IN_PROGRESS','DONE','BLOCKED','DISMISSED')",
            name="ck_operations_tasks_status_allowed",
        ),
        Index(
            "ix_operations_tasks_tenant_status",
            "tenant_id",
            "task_status",
        ),
        Index(
            "ix_operations_tasks_tenant_due_at",
            "tenant_id",
            "due_at",
        ),
        {"schema": "operations"},
    )

    task_type: Mapped[str] = mapped_column(String(64), nullable=False)
    task_title: Mapped[str] = mapped_column(String(255), nullable=False)
    task_status: Mapped[str] = mapped_column(String(32), nullable=False)
    priority: Mapped[Decimal | None] = mapped_column(
        Numeric(7, 4),
        nullable=True,
    )

    product_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    source_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class TaskDependencyV2(BaseV2):
    __tablename__ = "task_dependencies"
    __table_args__ = (
        PrimaryKeyConstraint(
            "tenant_id",
            "predecessor_task_id",
            "successor_task_id",
            name="pk_operations_task_dependencies",
        ),
        CheckConstraint(
            "predecessor_task_id <> successor_task_id",
            name="ck_operations_task_dependencies_no_self",
        ),
        CheckConstraint(
            "lag_hours >= 0",
            name="ck_operations_task_dependencies_lag_nonnegative",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "predecessor_task_id"],
            ["operations.tasks.tenant_id", "operations.tasks.id"],
            name="fk_operations_task_dependencies_predecessor_same_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "successor_task_id"],
            ["operations.tasks.tenant_id", "operations.tasks.id"],
            name="fk_operations_task_dependencies_successor_same_tenant",
            ondelete="CASCADE",
        ),
        {"schema": "operations"},
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    predecessor_task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False
    )
    successor_task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False
    )

    dependency_type: Mapped[str] = mapped_column(String(32), nullable=False)
    lag_hours: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class TaskIncomingDependencyV2(BaseV2):
    __tablename__ = "task_incoming_dependencies"
    __table_args__ = (
        PrimaryKeyConstraint(
            "tenant_id",
            "task_id",
            "incoming_shipment_id",
            name="pk_operations_task_incoming_dependencies",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "task_id"],
            ["operations.tasks.tenant_id", "operations.tasks.id"],
            name="fk_operations_task_incoming_task_same_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "incoming_shipment_id"],
            [
                "operations.incoming_shipments.tenant_id",
                "operations.incoming_shipments.id",
            ],
            name="fk_operations_task_incoming_shipment_same_tenant",
            ondelete="CASCADE",
        ),
        {"schema": "operations"},
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    task_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    incoming_shipment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False
    )

    dependency_type: Mapped[str] = mapped_column(String(32), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class TaskReviewV2(
    UUIDIdentityMixin,
    TenantV2Mixin,
    BaseV2,
):
    __tablename__ = "task_reviews"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "task_id"],
            ["operations.tasks.tenant_id", "operations.tasks.id"],
            name="fk_operations_task_reviews_task_same_tenant",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "tenant_id",
            "task_id",
            "proposal_version",
            name="uq_operations_task_reviews_proposal_version",
        ),
        {"schema": "operations"},
    )

    task_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)

    proposal_source: Mapped[str] = mapped_column(String(32), nullable=False)
    proposal_type: Mapped[str] = mapped_column(String(64), nullable=False)
    proposal_version: Mapped[int] = mapped_column(Integer, nullable=False)

    decision: Mapped[str] = mapped_column(String(32), nullable=False)

    before_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    proposed_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    approved_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class LaunchScheduleV2(
    UUIDIdentityMixin,
    TenantV2Mixin,
    TimestampV2Mixin,
    BaseV2,
):
    __tablename__ = "launch_schedules"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "id",
            name="uq_operations_launch_schedules_tenant_id_id",
        ),
        {"schema": "operations"},
    )

    launch_title: Mapped[str] = mapped_column(String(255), nullable=False)
    launch_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    launch_status: Mapped[str] = mapped_column(String(32), nullable=False)


class LaunchProductV2(BaseV2):
    __tablename__ = "launch_products"
    __table_args__ = (
        PrimaryKeyConstraint(
            "tenant_id",
            "launch_schedule_id",
            "product_id",
            name="pk_operations_launch_products",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "launch_schedule_id"],
            [
                "operations.launch_schedules.tenant_id",
                "operations.launch_schedules.id",
            ],
            name="fk_operations_launch_products_schedule_same_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "product_id"],
            ["catalog.products.tenant_id", "catalog.products.id"],
            name="fk_operations_launch_products_product_same_tenant",
            ondelete="CASCADE",
        ),
        {"schema": "operations"},
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    launch_schedule_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class LaunchIncomingDependencyV2(BaseV2):
    __tablename__ = "launch_incoming_dependencies"
    __table_args__ = (
        PrimaryKeyConstraint(
            "tenant_id",
            "launch_schedule_id",
            "incoming_shipment_id",
            name="pk_operations_launch_incoming_dependencies",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "launch_schedule_id"],
            [
                "operations.launch_schedules.tenant_id",
                "operations.launch_schedules.id",
            ],
            name="fk_operations_launch_incoming_schedule_same_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "incoming_shipment_id"],
            [
                "operations.incoming_shipments.tenant_id",
                "operations.incoming_shipments.id",
            ],
            name="fk_operations_launch_incoming_shipment_same_tenant",
            ondelete="CASCADE",
        ),
        {"schema": "operations"},
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    launch_schedule_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False
    )
    incoming_shipment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False
    )

    dependency_type: Mapped[str] = mapped_column(String(32), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )