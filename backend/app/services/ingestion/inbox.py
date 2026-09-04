"""Validating, replay-aware inbox with protected payload references."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend.app.models.ingestion import EventInbox
from contracts.events import CanonicalCommerceEvent


@dataclass(frozen=True)
class InboxReceipt:
    status: str
    event_id: str | None
    event_hash: str
    protected_payload_ref: str | None
    reason: str | None = None


@dataclass
class InMemoryInbox:
    """C1 store interface; DB model carries the same independent constraints."""

    accepted: dict[str, InboxReceipt] = field(default_factory=dict)
    quarantined: list[InboxReceipt] = field(default_factory=list)
    accepted_count: int = 0
    replayed_count: int = 0

    def ingest(self, raw: dict[str, Any]) -> tuple[CanonicalCommerceEvent | None, InboxReceipt]:
        safe_hash = hashlib.sha256(
            json.dumps(raw, sort_keys=True, default=str, separators=(",", ":")).encode()
        ).hexdigest()
        try:
            event = CanonicalCommerceEvent.model_validate(raw)
        except ValidationError as exc:
            receipt = InboxReceipt(
                status="QUARANTINED",
                event_id=str(raw.get("event_id")) if raw.get("event_id") else None,
                event_hash=safe_hash,
                protected_payload_ref=None,
                reason=exc.errors()[0]["type"],
            )
            self.quarantined.append(receipt)
            return None, receipt

        identity = f"{event.tenant_id}:{event.idempotency_key}"
        if identity in self.accepted:
            self.replayed_count += 1
            original = self.accepted[identity]
            return event, InboxReceipt(
                status="REPLAYED",
                event_id=event.event_id,
                event_hash=original.event_hash,
                protected_payload_ref=original.protected_payload_ref,
            )

        payload_hash = hashlib.sha256(
            json.dumps(event.payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        receipt = InboxReceipt(
            status="ACCEPTED",
            event_id=event.event_id,
            event_hash=safe_hash,
            protected_payload_ref=f"protected://payload/sha256/{payload_hash}",
        )
        self.accepted[identity] = receipt
        self.accepted_count += 1
        return event, receipt

def persist_accepted_event(
    session: Session,
    event: CanonicalCommerceEvent,
    receipt: InboxReceipt,
) -> EventInbox:
    if receipt.status != "ACCEPTED":
        raise ValueError("only ACCEPTED events can be persisted")

    if receipt.protected_payload_ref is None:
        raise ValueError("accepted event requires protected payload reference")
    if receipt.event_id != event.event_id:
        raise ValueError("receipt event_id does not match event")

    row = EventInbox(
        tenant_id=event.tenant_id,
        event_id=event.event_id,
        source=event.source.value,
        source_event_id=event.source_event_id,
        event_type=event.event_type.value,
        occurred_at=event.occurred_at,
        ingested_at=event.ingested_at,
        idempotency_key=event.idempotency_key,
        correlation_id=event.correlation_id,
        event_hash=receipt.event_hash,
        protected_payload_ref=receipt.protected_payload_ref,
        status=receipt.status,
        quarantine_reason=None,
        schema_version=event.schema_version,
    )

    session.add(row)
    session.commit()
    session.refresh(row)

    return row
