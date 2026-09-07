"""Initial tenant-aware core schema."""

from alembic import op

import backend.app.models  # noqa: F401
from backend.app.db.base import Base

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


def _core_tables():
    return [Base.metadata.tables[name] for name in CORE_TABLE_NAMES]


revision = "0001_core"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, tables=_core_tables())
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
    Base.metadata.drop_all(bind=bind, tables=_core_tables())
