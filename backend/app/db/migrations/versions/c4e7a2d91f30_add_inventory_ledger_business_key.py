"""add inventory ledger business identity key

Revision ID: c4e7a2d91f30
Revises: 50fdb89e2a1b
"""

import sqlalchemy as sa
from alembic import op

revision = "c4e7a2d91f30"
down_revision = "50fdb89e2a1b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "inventory_ledger",
        sa.Column("business_key", sa.String(length=255), nullable=True),
    )
    op.create_unique_constraint(
        "uq_inventory_ledger_business_key",
        "inventory_ledger",
        ["tenant_id", "business_key"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_inventory_ledger_business_key",
        "inventory_ledger",
        type_="unique",
    )
    op.drop_column("inventory_ledger", "business_key")
