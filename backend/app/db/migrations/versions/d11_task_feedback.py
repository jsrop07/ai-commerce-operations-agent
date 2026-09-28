"""D11 Task feedback append-only storage."""

from alembic import op
import sqlalchemy as sa


revision = "d11_task_feedback"
down_revision = "f38aa7ef5019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "task_feedback",
        sa.Column(
            "task_id",
            sa.String(length=36),
            nullable=False,
        ),
        sa.Column(
            "decision",
            sa.String(length=16),
            nullable=False,
        ),
        sa.Column(
            "target_field",
            sa.String(length=64),
            nullable=True,
        ),
        sa.Column(
            "before_value",
            sa.JSON(),
            nullable=True,
        ),
        sa.Column(
            "after_value",
            sa.JSON(),
            nullable=True,
        ),
        sa.Column(
            "reason",
            sa.String(length=500),
            nullable=False,
        ),
        sa.Column(
            "actor",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "idempotency_key",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "feedback_version",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "id",
            sa.String(length=36),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "schema_version",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            "decision IN ('EDIT', 'REJECT')",
            name=(
                "ck_task_feedback_"
                "decision_allowed"
            ),
        ),
        sa.CheckConstraint(
            "feedback_version > 0",
            name=(
                "ck_task_feedback_"
                "version_positive"
            ),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name=(
                "uq_task_feedback_"
                "idempotency"
            ),
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "task_id",
            "feedback_version",
            name="uq_task_feedback_version",
        ),
    )

    op.create_index(
        op.f(
            "ix_task_feedback_tenant_id"
        ),
        "task_feedback",
        ["tenant_id"],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_task_feedback_task_id"
        ),
        "task_feedback",
        ["task_id"],
        unique=False,
    )

    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        op.execute(
            """
            CREATE FUNCTION
            prevent_task_feedback_mutation()
            RETURNS trigger AS $$
            BEGIN
              RAISE EXCEPTION
              'task_feedback is append-only';
            END;
            $$ LANGUAGE plpgsql;

            CREATE TRIGGER
            task_feedback_append_only
            BEFORE UPDATE OR DELETE
            ON task_feedback
            FOR EACH ROW
            EXECUTE FUNCTION
            prevent_task_feedback_mutation();
            """
        )


def downgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        op.execute(
            """
            DROP TRIGGER IF EXISTS
            task_feedback_append_only
            ON task_feedback;
            """
        )

        op.execute(
            """
            DROP FUNCTION IF EXISTS
            prevent_task_feedback_mutation();
            """
        )

    op.drop_index(
        op.f(
            "ix_task_feedback_task_id"
        ),
        table_name="task_feedback",
    )

    op.drop_index(
        op.f(
            "ix_task_feedback_tenant_id"
        ),
        table_name="task_feedback",
    )

    op.drop_table("task_feedback")