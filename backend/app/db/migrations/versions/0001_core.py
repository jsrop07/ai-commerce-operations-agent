"""Initial tenant-aware core schema.

This migration owns a frozen schema snapshot. It must not import the current
ORM metadata: later model changes belong in their own revisions.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_core"
down_revision = None
branch_labels = None
depends_on = None

CORE_TABLE_NAMES = (
    "brands",
    "event_inbox",
    "incoming_stock",
    "inventory_ledger",
    "inventory_snapshots",
    "launch_events",
    "order_lines",
    "orders",
    "processed_effects",
    "products",
    "provider_accounts",
    "provider_mappings",
    "reservation_orders",
    "sale_events",
    "skus",
    "task_dependencies",
    "tasks",
    "tenants",
)


_CORE_METADATA = sa.MetaData()

sa.Table(
    "tenants",
    _CORE_METADATA,
    sa.Column("name", sa.String(length=200), nullable=False),
    sa.Column("environment", sa.String(length=32), nullable=False),
    sa.Column("status", sa.String(length=32), nullable=False),
    sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
    sa.Column("schema_version", sa.String(length=32), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

sa.Table(
    "provider_accounts",
    _CORE_METADATA,
    sa.Column("provider", sa.String(length=32), nullable=False),
    sa.Column("account_ref", sa.String(length=255), nullable=False),
    sa.Column("capability", sa.JSON(), nullable=False),
    sa.Column("credential_ref", sa.String(length=255)),
    sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
    sa.Column("tenant_id", sa.String(length=100), nullable=False, index=True),
    sa.Column("schema_version", sa.String(length=32), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint("tenant_id", "provider", "account_ref"),
)

sa.Table(
    "brands",
    _CORE_METADATA,
    sa.Column("canonical_name", sa.String(length=255), nullable=False),
    sa.Column("aliases", sa.JSON(), nullable=False),
    sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
    sa.Column("tenant_id", sa.String(length=100), nullable=False, index=True),
    sa.Column("schema_version", sa.String(length=32), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint("tenant_id", "canonical_name"),
    sa.UniqueConstraint("tenant_id", "id"),
)

sa.Table(
    "products",
    _CORE_METADATA,
    sa.Column("name", sa.String(length=255), nullable=False),
    sa.Column("brand_id", sa.String(length=36), nullable=False),
    sa.Column("category", sa.String(length=100)),
    sa.Column("language", sa.String(length=32)),
    sa.Column("player_count", sa.String(length=32)),
    sa.Column("play_time", sa.Integer()),
    sa.Column("difficulty", sa.Float()),
    sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
    sa.Column("tenant_id", sa.String(length=100), nullable=False, index=True),
    sa.Column("schema_version", sa.String(length=32), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint("tenant_id", "name", "brand_id"),
    sa.UniqueConstraint("tenant_id", "id"),
    sa.ForeignKeyConstraint(
        ["tenant_id", "brand_id"],
        ["brands.tenant_id", "brands.id"],
        name="fk_products_brand_same_tenant",
    ),
)

sa.Table(
    "skus",
    _CORE_METADATA,
    sa.Column("product_id", sa.String(length=36), nullable=False),
    sa.Column("canonical_code", sa.String(length=120), nullable=False),
    sa.Column("option", sa.String(length=255)),
    sa.Column("barcode", sa.String(length=100)),
    sa.Column("status", sa.String(length=32), nullable=False),
    sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
    sa.Column("tenant_id", sa.String(length=100), nullable=False, index=True),
    sa.Column("schema_version", sa.String(length=32), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint("tenant_id", "canonical_code"),
    sa.UniqueConstraint("tenant_id", "barcode"),
    sa.UniqueConstraint("tenant_id", "id"),
    sa.ForeignKeyConstraint(
        ["tenant_id", "product_id"],
        ["products.tenant_id", "products.id"],
        name="fk_skus_product_same_tenant",
    ),
)

sa.Table(
    "provider_mappings",
    _CORE_METADATA,
    sa.Column("provider", sa.String(length=32), nullable=False),
    sa.Column("object_type", sa.String(length=50), nullable=False),
    sa.Column("external_id", sa.String(length=255), nullable=False),
    sa.Column("canonical_id", sa.String(length=36)),
    sa.Column("confidence", sa.Float(), nullable=False),
    sa.Column("status", sa.String(length=32), nullable=False),
    sa.Column("version", sa.Integer(), nullable=False),
    sa.Column("approved", sa.Boolean(), nullable=False),
    sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
    sa.Column("tenant_id", sa.String(length=100), nullable=False, index=True),
    sa.Column("schema_version", sa.String(length=32), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint(
        "tenant_id",
        "provider",
        "object_type",
        "external_id",
        "version",
    ),
    sa.CheckConstraint(
        "NOT (status = 'AMBIGUOUS' AND approved = true)",
        name="ck_ambiguous_mapping_not_approved",
    ),
)

sa.Table(
    "orders",
    _CORE_METADATA,
    sa.Column("provider", sa.String(length=32), nullable=False),
    sa.Column("external_id", sa.String(length=255), nullable=False),
    sa.Column("order_type", sa.String(length=32), nullable=False),
    sa.Column("status", sa.String(length=32), nullable=False),
    sa.Column("ordered_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("customer_ref", sa.String(length=255)),
    sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
    sa.Column("tenant_id", sa.String(length=100), nullable=False, index=True),
    sa.Column("schema_version", sa.String(length=32), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint("tenant_id", "provider", "external_id"),
    sa.UniqueConstraint("tenant_id", "id"),
)

sa.Table(
    "order_lines",
    _CORE_METADATA,
    sa.Column("order_id", sa.String(length=36), nullable=False),
    sa.Column("sku_id", sa.String(length=36)),
    sa.Column("external_sku_text", sa.String(length=255)),
    sa.Column("quantity", sa.Integer(), nullable=False),
    sa.Column("unit_amount", sa.Numeric(18, 2), nullable=False),
    sa.Column("currency", sa.String(length=3), nullable=False),
    sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
    sa.Column("tenant_id", sa.String(length=100), nullable=False, index=True),
    sa.Column("schema_version", sa.String(length=32), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("quantity > 0", name="ck_order_line_qty_positive"),
    sa.ForeignKeyConstraint(
        ["tenant_id", "order_id"],
        ["orders.tenant_id", "orders.id"],
        name="fk_order_lines_order_same_tenant",
    ),
    sa.ForeignKeyConstraint(
        ["tenant_id", "sku_id"],
        ["skus.tenant_id", "skus.id"],
        name="fk_order_lines_sku_same_tenant",
    ),
)

sa.Table(
    "sale_events",
    _CORE_METADATA,
    sa.Column("event_id", sa.String(length=200), nullable=False),
    sa.Column("source", sa.String(length=32), nullable=False),
    sa.Column("source_event_id", sa.String(length=255), nullable=False),
    sa.Column("channel", sa.String(length=32), nullable=False),
    sa.Column("sku_id", sa.String(length=36), nullable=False),
    sa.Column("quantity", sa.Integer(), nullable=False),
    sa.Column("amount", sa.Numeric(18, 2), nullable=False),
    sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
    sa.Column("tenant_id", sa.String(length=100), nullable=False, index=True),
    sa.Column("schema_version", sa.String(length=32), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint("tenant_id", "source", "source_event_id", "schema_version"),
    sa.UniqueConstraint("tenant_id", "event_id"),
    sa.CheckConstraint("quantity > 0", name="ck_sale_qty_positive"),
    sa.ForeignKeyConstraint(
        ["tenant_id", "sku_id"],
        ["skus.tenant_id", "skus.id"],
        name="fk_sale_events_sku_same_tenant",
    ),
)

sa.Table(
    "inventory_snapshots",
    _CORE_METADATA,
    sa.Column("provider", sa.String(length=32), nullable=False),
    sa.Column("sku_id", sa.String(length=36), nullable=False),
    sa.Column("on_hand", sa.Integer(), nullable=False),
    sa.Column("reserved", sa.Integer(), nullable=False),
    sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
    sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
    sa.Column("tenant_id", sa.String(length=100), nullable=False, index=True),
    sa.Column("schema_version", sa.String(length=32), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint("tenant_id", "provider", "sku_id", "as_of"),
    sa.ForeignKeyConstraint(
        ["tenant_id", "sku_id"],
        ["skus.tenant_id", "skus.id"],
        name="fk_inventory_snapshots_sku_same_tenant",
    ),
)

sa.Table(
    "inventory_ledger",
    _CORE_METADATA,
    sa.Column("sku_id", sa.String(length=36), nullable=False),
    sa.Column("delta", sa.Integer(), nullable=False),
    sa.Column("reason", sa.String(length=80), nullable=False),
    sa.Column("source_event_id", sa.String(length=255), nullable=False),
    sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
    sa.Column("tenant_id", sa.String(length=100), nullable=False, index=True),
    sa.Column("schema_version", sa.String(length=32), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint("tenant_id", "source_event_id", "sku_id", "reason"),
    sa.ForeignKeyConstraint(
        ["tenant_id", "sku_id"],
        ["skus.tenant_id", "skus.id"],
        name="fk_inventory_ledger_sku_same_tenant",
    ),
)

sa.Table(
    "event_inbox",
    _CORE_METADATA,
    sa.Column("event_id", sa.String(length=200), nullable=False),
    sa.Column("source", sa.String(length=32), nullable=False),
    sa.Column("source_event_id", sa.String(length=255), nullable=False),
    sa.Column("event_type", sa.String(length=100), nullable=False),
    sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("idempotency_key", sa.String(length=500), nullable=False),
    sa.Column("correlation_id", sa.String(length=200), nullable=False),
    sa.Column("event_hash", sa.String(length=64), nullable=False),
    sa.Column("protected_payload_ref", sa.String(length=500), nullable=False),
    sa.Column("status", sa.String(length=32), nullable=False),
    sa.Column("quarantine_reason", sa.JSON()),
    sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
    sa.Column("tenant_id", sa.String(length=100), nullable=False, index=True),
    sa.Column("schema_version", sa.String(length=32), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint("tenant_id", "source", "source_event_id", "schema_version"),
    sa.UniqueConstraint("tenant_id", "idempotency_key"),
)

sa.Table(
    "processed_effects",
    _CORE_METADATA,
    sa.Column("consumer", sa.String(length=100), nullable=False),
    sa.Column("idempotency_key", sa.String(length=500), nullable=False),
    sa.Column("effect_ref", sa.String(length=255), nullable=False),
    sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
    sa.Column("tenant_id", sa.String(length=100), nullable=False, index=True),
    sa.Column("schema_version", sa.String(length=32), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint("tenant_id", "consumer", "idempotency_key"),
)

sa.Table(
    "reservation_orders",
    _CORE_METADATA,
    sa.Column("order_id", sa.String(length=36), nullable=False),
    sa.Column("promised_date", sa.DateTime(timezone=True)),
    sa.Column("required_quantity", sa.Integer(), nullable=False),
    sa.Column("secured_quantity", sa.Integer(), nullable=False),
    sa.Column("status", sa.String(length=32), nullable=False),
    sa.Column("aging_hours", sa.Integer(), nullable=False),
    sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
    sa.Column("tenant_id", sa.String(length=100), nullable=False, index=True),
    sa.Column("schema_version", sa.String(length=32), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint("tenant_id", "order_id"),
    sa.CheckConstraint("required_quantity > 0", name="ck_reservation_required_positive"),
    sa.CheckConstraint("secured_quantity >= 0", name="ck_reservation_secured_nonnegative"),
    sa.CheckConstraint("aging_hours >= 0", name="ck_reservation_aging_nonnegative"),
    sa.ForeignKeyConstraint(
        ["tenant_id", "order_id"],
        ["orders.tenant_id", "orders.id"],
        name="fk_reservation_orders_order_same_tenant",
    ),
)

sa.Table(
    "incoming_stock",
    _CORE_METADATA,
    sa.Column("sku_id", sa.String(length=36), nullable=False),
    sa.Column("quantity", sa.Integer(), nullable=False),
    sa.Column("expected_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("confidence_status", sa.String(length=32), nullable=False),
    sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
    sa.Column("tenant_id", sa.String(length=100), nullable=False, index=True),
    sa.Column("schema_version", sa.String(length=32), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("quantity > 0", name="ck_incoming_qty_positive"),
    sa.ForeignKeyConstraint(
        ["tenant_id", "sku_id"],
        ["skus.tenant_id", "skus.id"],
        name="fk_incoming_stock_sku_same_tenant",
    ),
)

sa.Table(
    "launch_events",
    _CORE_METADATA,
    sa.Column("product_id", sa.String(length=36), nullable=False),
    sa.Column("launch_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("flow_template", sa.String(length=32), nullable=False),
    sa.Column("status", sa.String(length=32), nullable=False),
    sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
    sa.Column("tenant_id", sa.String(length=100), nullable=False, index=True),
    sa.Column("schema_version", sa.String(length=32), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(
        ["tenant_id", "product_id"],
        ["products.tenant_id", "products.id"],
        name="fk_launch_events_product_same_tenant",
    ),
)

sa.Table(
    "tasks",
    _CORE_METADATA,
    sa.Column("task_type", sa.String(length=64), nullable=False),
    sa.Column("title", sa.String(length=255), nullable=False),
    sa.Column("deadline", sa.DateTime(timezone=True)),
    sa.Column("priority", sa.Integer(), nullable=False),
    sa.Column("status", sa.String(length=32), nullable=False),
    sa.Column("source_reason", sa.String(length=255), nullable=False),
    sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
    sa.Column("tenant_id", sa.String(length=100), nullable=False, index=True),
    sa.Column("schema_version", sa.String(length=32), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint("tenant_id", "id"),
    sa.CheckConstraint(
        "status IN ('PROPOSED', 'APPROVED', 'IN_PROGRESS', 'DONE', 'BLOCKED', 'DISMISSED')",
        name="ck_task_status_allowed",
    ),
)

sa.Table(
    "task_dependencies",
    _CORE_METADATA,
    sa.Column("predecessor_id", sa.String(length=36), nullable=False),
    sa.Column("successor_id", sa.String(length=36), nullable=False),
    sa.Column("lag_hours", sa.Integer(), nullable=False),
    sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
    sa.Column("tenant_id", sa.String(length=100), nullable=False, index=True),
    sa.Column("schema_version", sa.String(length=32), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint("tenant_id", "predecessor_id", "successor_id"),
    sa.CheckConstraint("predecessor_id <> successor_id", name="ck_task_no_self_dependency"),
    sa.ForeignKeyConstraint(
        ["tenant_id", "predecessor_id"],
        ["tasks.tenant_id", "tasks.id"],
        name="fk_task_dependencies_predecessor_same_tenant",
    ),
    sa.ForeignKeyConstraint(
        ["tenant_id", "successor_id"],
        ["tasks.tenant_id", "tasks.id"],
        name="fk_task_dependencies_successor_same_tenant",
    ),
)


def _core_tables() -> list[sa.Table]:
    return [_CORE_METADATA.tables[name] for name in CORE_TABLE_NAMES]


def upgrade() -> None:
    bind = op.get_bind()
    _CORE_METADATA.create_all(bind=bind, tables=_core_tables())
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            CREATE FUNCTION prevent_inventory_ledger_mutation() RETURNS trigger AS $$
            BEGIN
              RAISE EXCEPTION 'inventory_ledger is append-only';
            END;
            $$ LANGUAGE plpgsql;
            CREATE TRIGGER inventory_ledger_append_only
            BEFORE UPDATE OR DELETE ON inventory_ledger
            FOR EACH ROW EXECUTE FUNCTION prevent_inventory_ledger_mutation();
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS inventory_ledger_append_only ON inventory_ledger")
        op.execute("DROP FUNCTION IF EXISTS prevent_inventory_ledger_mutation()")
    _CORE_METADATA.drop_all(bind=bind, tables=_core_tables())
