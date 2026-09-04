"""Canonical Commerce Event v1 shared contract."""

from __future__ import annotations

import json
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

EVENT_SCHEMA_VERSION = "1.0"


class Provider(StrEnum):
    CAFE24 = "CAFE24"
    TOSS_POS = "TOSS_POS"
    ECOUNT = "ECOUNT"
    DEMO = "DEMO"


class EventType(StrEnum):
    ORDER_CREATED = "order.created"
    ORDER_UPDATED = "order.updated"
    OFFLINE_SALE_RECORDED = "offline_sale.recorded"
    RETURN_RECORDED = "return.recorded"
    INVENTORY_SNAPSHOT_RECEIVED = "inventory.snapshot_received"
    EXPECTED_CHANGED = "expected_changed"
    DISCREPANCY_DETECTED = "discrepancy_detected"
    RESERVATION_CREATED = "reservation.created"
    RESERVATION_SHORTAGE_DETECTED = "reservation.shortage_detected"
    INCOMING_UPDATED = "incoming.updated"
    INQUIRY_RECEIVED = "inquiry.received"
    INCOMING_DELAYED = "incoming.delayed"
    ACTION_DENIED = "action.denied"


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")
    return value


class CanonicalCommerceEvent(BaseModel):
    """Immutable fact envelope defined by 05 Data/API specification section 5."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str = Field(min_length=1, max_length=200)
    event_type: EventType
    schema_version: str = Field(pattern=r"^1(?:\.\d+)?$")
    tenant_id: str = Field(min_length=1, max_length=100)
    source: Provider
    source_event_id: str = Field(min_length=1, max_length=255)
    occurred_at: datetime
    ingested_at: datetime
    idempotency_key: str = Field(min_length=1, max_length=500)
    correlation_id: str = Field(min_length=1, max_length=200)
    payload: dict[str, Any]

    _occurred_aware = field_validator("occurred_at")(_aware)
    _ingested_aware = field_validator("ingested_at")(_aware)

    @field_validator("payload")
    @classmethod
    def payload_must_not_be_empty(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not value:
            raise ValueError("payload must not be empty")
        return value

    @classmethod
    def model_validate_json_unique(cls, raw: str | bytes) -> CanonicalCommerceEvent:
        """Reject duplicate JSON object keys before Pydantic validation."""

        def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError(f"duplicate JSON key: {key}")
                result[key] = value
            return result

        return cls.model_validate(json.loads(raw, object_pairs_hook=unique_object))
