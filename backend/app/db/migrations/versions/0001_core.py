"""Initial tenant-aware core schema."""

from alembic import op

import backend.app.models  # noqa: F401
from backend.app.db.base import Base

revision = "0001_core"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)
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
    Base.metadata.drop_all(bind=bind)
