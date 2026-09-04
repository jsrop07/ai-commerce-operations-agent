"""Provider capability and read-page contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from contracts.events import Provider

T = TypeVar("T")


class CapabilityStatus(StrEnum):
    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    VERIFY = "VERIFY"
    UNKNOWN = "UNKNOWN"
    DISABLED_CORE = "DISABLED_CORE"


class ConnectionMode(StrEnum):
    API_POLL = "API_POLL"
    WEBHOOK_PLUS_RECONCILIATION = "WEBHOOK_PLUS_RECONCILIATION"
    FILE_IMPORT = "FILE_IMPORT"
    MANUAL_PROTECTED_IMPORT = "MANUAL_PROTECTED_IMPORT"
    CONTRACT_ONLY = "CONTRACT_ONLY"
    UNSUPPORTED = "UNSUPPORTED"


class CapabilityMatrix(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Provider
    connection_mode: ConnectionMode = ConnectionMode.CONTRACT_ONLY
    products_read: CapabilityStatus
    orders_read: CapabilityStatus
    inventory_read: CapabilityStatus
    inquiries_read: CapabilityStatus
    incoming_stock_read: CapabilityStatus
    inventory_write: CapabilityStatus = CapabilityStatus.DISABLED_CORE
    checked_at: datetime | None = None
    evidence_ref: str | None = None


class ProviderReadPage(BaseModel, Generic[T]):
    model_config = ConfigDict(extra="forbid")

    provider: Provider
    resource: str = Field(min_length=1)
    items: list[T]
    next_cursor: str | None = None
    watermark: datetime | None = None
    has_more: bool = False
    request_count: int = Field(ge=1)
    source_as_of: datetime | None = None
    schema_version: str = "provider-read-page.v1"
