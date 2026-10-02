"""V2 SQLAlchemy base for commerce_ops."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Uuid, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class BaseV2(DeclarativeBase):
    """commerce_ops V2 전용 SQLAlchemy metadata."""

    pass


class UUIDIdentityMixin:
    """모든 V2 엔티티의 UUID PK."""

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )


class TenantV2Mixin:
    """tenant 단위 데이터 격리용 FK."""

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("public.tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )


class TimestampV2Mixin:
    """V2 공통 생성/수정 시각."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )