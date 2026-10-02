"""V2 tenant model."""

from __future__ import annotations

import uuid

from sqlalchemy import String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base_v2 import BaseV2, TimestampV2Mixin, UUIDIdentityMixin


class TenantV2(UUIDIdentityMixin, TimestampV2Mixin, BaseV2):
    __tablename__ = "tenants"
    __table_args__ = {"schema": "public"}

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    environment: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )