"""Inbox identity and processed-effect uniqueness are intentionally separate."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, IdentityMixin, TenantMixin, VersionedMixin


class EventInbox(Base, IdentityMixin, TenantMixin, VersionedMixin):
    __tablename__ = "event_inbox"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source", "source_event_id", "schema_version"),
        UniqueConstraint("tenant_id", "idempotency_key"),
    )

    event_id: Mapped[str] = mapped_column(String(200), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(500), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(200), nullable=False)
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    protected_payload_ref: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACCEPTED")
    quarantine_reason: Mapped[dict | None] = mapped_column(JSON)


class ProcessedEffect(Base, IdentityMixin, TenantMixin, VersionedMixin):
    __tablename__ = "processed_effects"
    __table_args__ = (UniqueConstraint("tenant_id", "consumer", "idempotency_key"),)

    consumer: Mapped[str] = mapped_column(String(100), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(500), nullable=False)
    effect_ref: Mapped[str] = mapped_column(String(255), nullable=False)
