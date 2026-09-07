"""add sync state

Revision ID: f38aa7ef5019
Revises: 0001_core
"""

import sqlalchemy as sa
from alembic import op

revision = "f38aa7ef5019"
down_revision = "0001_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sync_states",
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("resource", sa.String(length=100), nullable=False),
        sa.Column("connection_mode", sa.String(length=64), nullable=False),
        sa.Column("cursor", sa.String(length=1000), nullable=True),
        sa.Column("watermark", sa.DateTime(timezone=True), nullable=True),
        sa.Column("overlap_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("file_hash", sa.String(length=128), nullable=True),
        sa.Column("batch_id", sa.String(length=200), nullable=True),
        sa.Column("row_number", sa.Integer(), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=200), nullable=True),
        sa.Column("state_version", sa.Integer(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "provider",
            "resource",
            "connection_mode",
            name="uq_sync_state_scope",
        ),
    )

    op.create_index(
        op.f("ix_sync_states_tenant_id"),
        "sync_states",
        ["tenant_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_sync_states_tenant_id"),
        table_name="sync_states",
    )
    op.drop_table("sync_states")
