"""V2 external integration models."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKeyConstraint,
    CheckConstraint,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base_v2 import (
    BaseV2,
    TenantV2Mixin,
    TimestampV2Mixin,
    UUIDIdentityMixin,
)


class ExternalAccountV2(
    UUIDIdentityMixin,
    TenantV2Mixin,
    TimestampV2Mixin,
    BaseV2,
):
    __tablename__ = "external_accounts"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "provider",
            "account_reference",
            name="uq_integrations_external_accounts_scope",
        ),
        {"schema": "integrations"},
    )

    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    account_reference: Mapped[str] = mapped_column(String(255), nullable=False)

    capabilities: Mapped[dict] = mapped_column(JSONB, nullable=False)
    credential_reference: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )


class ProductExternalMappingV2(
    UUIDIdentityMixin,
    TenantV2Mixin,
    TimestampV2Mixin,
    BaseV2,
):
    __tablename__ = "product_external_mappings"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "provider",
            "external_product_id",
            name="uq_integrations_product_external_mapping",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "product_id"],
            ["catalog.products.tenant_id", "catalog.products.id"],
            name="fk_integrations_product_mapping_product_same_tenant",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_integrations_product_mapping_confidence_range",
        ),
        {"schema": "integrations"},
    )

    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    external_product_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )

    mapping_status: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True,
    )
    approved: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )


class VariantExternalMappingV2(
    UUIDIdentityMixin,
    TenantV2Mixin,
    TimestampV2Mixin,
    BaseV2,
):
    __tablename__ = "variant_external_mappings"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "provider",
            "external_variant_id",
            name="uq_integrations_variant_external_mapping",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "product_variant_id"],
            [
                "catalog.product_variants.tenant_id",
                "catalog.product_variants.id",
            ],
            name="fk_integrations_variant_mapping_variant_same_tenant",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_integrations_variant_mapping_confidence_range",
        ),
        {"schema": "integrations"},
    )

    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    external_variant_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    product_variant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )

    mapping_status: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True,
    )

    approved: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )


class SyncStatusV2(
    UUIDIdentityMixin,
    TenantV2Mixin,
    TimestampV2Mixin,
    BaseV2,
):
    __tablename__ = "sync_status"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "provider",
            "resource",
            "connection_mode",
            name="uq_integrations_sync_status_scope",
        ),
        {"schema": "integrations"},
    )

    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    resource: Mapped[str] = mapped_column(String(100), nullable=False)
    connection_mode: Mapped[str] = mapped_column(String(64), nullable=False)

    cursor: Mapped[str | None] = mapped_column(Text, nullable=True)
    watermark: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    overlap_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    file_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    batch_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    row_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    last_success_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    state_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )


class IncomingEventV2(
    UUIDIdentityMixin,
    TenantV2Mixin,
    BaseV2,
):
    __tablename__ = "incoming_events"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_integrations_incoming_events_idempotency",
        ),
        UniqueConstraint(
            "tenant_id",
            "provider",
            "external_event_id",
            "schema_version",
            name="uq_integrations_incoming_events_source_identity",
        ),
        {"schema": "integrations"},
    )

    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    external_event_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)

    occurred_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    idempotency_key: Mapped[str] = mapped_column(String(500), nullable=False)
    payload_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    protected_payload_reference: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    event_status: Mapped[str] = mapped_column(String(32), nullable=False)
    quarantine_reason: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    schema_version: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ProcessedActionV2(
    UUIDIdentityMixin,
    TenantV2Mixin,
    BaseV2,
):
    __tablename__ = "processed_actions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "consumer",
            "idempotency_key",
            name="uq_integrations_processed_actions_idempotency",
        ),
        {"schema": "integrations"},
    )

    consumer: Mapped[str] = mapped_column(String(100), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(500), nullable=False)

    action_reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )