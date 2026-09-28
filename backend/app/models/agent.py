"""Agent 실행 상태와 checkpoint 영속 모델."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import (
    Base,
    IdentityMixin,
    TenantMixin,
    VersionedMixin,
)


class AgentRun(
    Base,
    IdentityMixin,
    TenantMixin,
    VersionedMixin,
):
    """하나의 Agent workflow 실행 상태."""

    __tablename__ = "agent_runs"

    __table_args__ = (
        CheckConstraint(
            "state_schema_version > 0",
            name="ck_agent_runs_state_schema_version_positive",
        ),
        CheckConstraint(
            "checkpoint_version > 0",
            name="ck_agent_runs_checkpoint_version_positive",
        ),
        UniqueConstraint(
            "tenant_id",
            "workflow_id",
            "thread_id",
            name="uq_agent_runs_tenant_workflow_thread",
        ),
    )

    workflow_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )

    thread_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )

    current_node: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    state_schema_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    checkpoint_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    state: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )

    evidence_ids: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    model_version: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    prompt_version: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    checkpoint_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    cost: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    output_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
