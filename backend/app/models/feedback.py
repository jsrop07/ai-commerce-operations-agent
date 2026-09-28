"""D11-BE-04 내부 Task feedback 영속 모델."""

from __future__ import annotations

from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import (
    Base,
    IdentityMixin,
    TenantMixin,
    VersionedMixin,
)


class TaskFeedback(
    Base,
    IdentityMixin,
    TenantMixin,
    VersionedMixin,
):
    """운영자의 Task 수정/거절 feedback append-only 기록."""

    __tablename__ = "task_feedback"

    __table_args__ = (
        CheckConstraint(
            "decision IN ('EDIT', 'REJECT')",
            name="ck_task_feedback_decision_allowed",
        ),
        CheckConstraint(
            "feedback_version > 0",
            name="ck_task_feedback_version_positive",
        ),
        UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_task_feedback_idempotency",
        ),
        UniqueConstraint(
            "tenant_id",
            "task_id",
            "feedback_version",
            name="uq_task_feedback_version",
        ),
    )

    task_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )

    decision: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )

    target_field: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    before_value: Mapped[Any | None] = mapped_column(
        JSON,
        nullable=True,
    )

    after_value: Mapped[Any | None] = mapped_column(
        JSON,
        nullable=True,
    )

    reason: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    actor: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    feedback_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )