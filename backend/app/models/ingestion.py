"""Inbox identity and processed-effect uniqueness are intentionally separate."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, UniqueConstraint
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


class SyncState(Base, IdentityMixin, TenantMixin, VersionedMixin):
    """Independent checkpoint for one provider/resource/connection mode."""

    __tablename__ = "sync_states"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "provider",
            "resource",
            "connection_mode",
            name="uq_sync_state_scope",
        ),
    )

    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    resource: Mapped[str] = mapped_column(String(100), nullable=False)
    connection_mode: Mapped[str] = mapped_column(String(64), nullable=False)

    # API incremental checkpoint
    cursor: Mapped[str | None] = mapped_column(String(1000))
    watermark: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    overlap_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # File backfill checkpoint
    file_hash: Mapped[str | None] = mapped_column(String(128))
    batch_id: Mapped[str | None] = mapped_column(String(200))
    row_number: Mapped[int | None] = mapped_column(Integer)

    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(200))
    state_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
