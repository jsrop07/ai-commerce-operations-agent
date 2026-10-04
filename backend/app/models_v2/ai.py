"""V2 AI storage models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base_v2 import (
    BaseV2,
    TenantV2Mixin,
    TimestampV2Mixin,
    UUIDIdentityMixin,
)


class RagChunkV2(
    UUIDIdentityMixin,
    TenantV2Mixin,
    TimestampV2Mixin,
    BaseV2,
):
    __tablename__ = "rag_chunks"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "source_type",
            "source_id",
            "source_version",
            "chunk_no",
            name="uq_ai_rag_chunks_source_version_chunk",
        ),
        CheckConstraint(
            "chunk_no >= 0",
            name="ck_ai_rag_chunks_chunk_no_nonnegative",
        ),
        Index(
            "ix_ai_rag_chunks_current_source",
            "tenant_id",
            "source_type",
            "is_current",
        ),
        {"schema": "ai"},
    )

    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_version: Mapped[str] = mapped_column(String(64), nullable=False)

    chunk_no: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    embedding_model: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    embedding_version: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    metadata_json: Mapped[dict | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
    )

    is_current: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )


class ConversationV2(
    UUIDIdentityMixin,
    TenantV2Mixin,
    TimestampV2Mixin,
    BaseV2,
):
    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "id",
            name="uq_ai_conversations_tenant_id_id",
        ),
        Index("ix_ai_conversations_owner_recent", "tenant_id", "owner_actor_id", "updated_at"),
        {"schema": "ai"},
    )

    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    owner_actor_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    conversation_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )


class MessageV2(
    UUIDIdentityMixin,
    TenantV2Mixin,
    BaseV2,
):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "id",
            name="uq_ai_messages_tenant_id_id",
        ),
        UniqueConstraint(
            "tenant_id",
            "conversation_id",
            "message_order",
            name="uq_ai_messages_conversation_order",
        ),
        CheckConstraint(
            "message_order >= 0",
            name="ck_ai_messages_order_nonnegative",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "conversation_id"],
            ["ai.conversations.tenant_id", "ai.conversations.id"],
            name="fk_ai_messages_conversation_same_tenant",
            ondelete="RESTRICT",
        ),
        {"schema": "ai"},
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )

    message_order: Mapped[int] = mapped_column(Integer, nullable=False)

    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    analysis_kind: Mapped[str | None] = mapped_column(String(64), nullable=True)
    response_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class MessageContextV2(
    UUIDIdentityMixin,
    TenantV2Mixin,
    BaseV2,
):
    __tablename__ = "message_contexts"
    __table_args__ = (
        UniqueConstraint(
            "message_id",
            name="uq_ai_message_contexts_message_id",
        ),
        CheckConstraint(
            "context_revision > 0",
            name="ck_ai_message_contexts_revision_positive",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "message_id"],
            ["ai.messages.tenant_id", "ai.messages.id"],
            name="fk_ai_message_contexts_message_same_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "product_id"],
            ["catalog.products.tenant_id", "catalog.products.id"],
            name="fk_ai_message_contexts_product_same_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "product_variant_id"],
            [
                "catalog.product_variants.tenant_id",
                "catalog.product_variants.id",
            ],
            name="fk_ai_message_contexts_variant_same_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "incoming_shipment_id"],
            [
                "operations.incoming_shipments.tenant_id",
                "operations.incoming_shipments.id",
            ],
            name="fk_ai_message_contexts_incoming_same_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "task_id"],
            ["operations.tasks.tenant_id", "operations.tasks.id"],
            name="fk_ai_message_contexts_task_same_tenant",
            ondelete="RESTRICT",
        ),
        {"schema": "ai"},
    )

    message_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )

    page_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)

    product_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    product_variant_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    incoming_shipment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )

    data_mode: Mapped[str | None] = mapped_column(String(64), nullable=True)

    source_versions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    evidence_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    data_as_of: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    context_revision: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class AgentRunV2(
    UUIDIdentityMixin,
    TenantV2Mixin,
    TimestampV2Mixin,
    BaseV2,
):
    __tablename__ = "agent_runs"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "workflow_id",
            "thread_id",
            name="uq_ai_agent_runs_workflow_thread",
        ),
        CheckConstraint(
            "state_schema_version > 0",
            name="ck_ai_agent_runs_state_schema_version_positive",
        ),
        CheckConstraint(
            "checkpoint_version > 0",
            name="ck_ai_agent_runs_checkpoint_version_positive",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "conversation_id"],
            ["ai.conversations.tenant_id", "ai.conversations.id"],
            name="fk_ai_agent_runs_conversation_same_tenant",
            ondelete="RESTRICT",
        ),
        {"schema": "ai"},
    )

    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )

    workflow_id: Mapped[str] = mapped_column(String(128), nullable=False)
    thread_id: Mapped[str] = mapped_column(String(128), nullable=False)

    current_node: Mapped[str] = mapped_column(String(128), nullable=False)
    run_status: Mapped[str] = mapped_column(String(32), nullable=False)

    state: Mapped[dict] = mapped_column(JSONB, nullable=False)

    state_schema_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )

    checkpoint_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )

    checkpoint_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    evidence_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    model_version: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    prompt_version: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    cost: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
