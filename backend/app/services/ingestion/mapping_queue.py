"""Fail-closed mapping review queue for unresolved provider objects."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class MappingQueueItem:
    queue_id: str
    tenant_id: str
    provider: str
    object_type: str
    external_id: str | None
    external_text: str | None
    source_identity_key: str
    reason: str
    status: str = "PENDING"
    canonical_id: str | None = None
    approved: bool = False
    confidence: float | None = None
    mapping_version: int | None = None
    candidate_ids: tuple[str, ...] = ()
    matching_rule: str | None = None
    evidence_ids: tuple[str, ...] = ()
    quality_status: str = "BLOCKED"
    source_classification: str = "BLOCKED"
    as_of: datetime | None = None


@dataclass(frozen=True)
class ReprocessAudit:
    queue_id: str
    tenant_id: str
    status: str
    attempted_at: datetime
    canonical_id: str | None = None
    mapping_version: int | None = None


@dataclass
class MappingReviewQueue:
    pending: dict[str, MappingQueueItem] = field(default_factory=dict)
    resolved: dict[str, MappingQueueItem] = field(default_factory=dict)
    enqueued_count: int = 0
    replayed_count: int = 0
    resolved_count: int = 0
    audit: list[ReprocessAudit] = field(default_factory=list)

    def enqueue(
        self,
        *,
        tenant_id: str,
        provider: str,
        object_type: str,
        external_id: str | None,
        external_text: str | None,
        source_identity_key: str,
        reason: str,
        candidate_ids: tuple[str, ...] = (),
        confidence: float | None = None,
        matching_rule: str | None = None,
        evidence_ids: tuple[str, ...] = (),
        quality_status: str = "BLOCKED",
        source_classification: str = "BLOCKED",
        as_of: datetime | None = None,
    ) -> MappingQueueItem:
        if not tenant_id:
            raise ValueError("tenant_id is required")
        if not provider:
            raise ValueError("provider is required")
        if not object_type:
            raise ValueError("object_type is required")
        if not source_identity_key:
            raise ValueError("source_identity_key is required")
        if not reason:
            raise ValueError("reason is required")

        queue_id = self._queue_id(
            tenant_id=tenant_id,
            provider=provider,
            object_type=object_type,
            external_id=external_id,
            source_identity_key=source_identity_key,
        )

        existing = self.pending.get(queue_id) or self.resolved.get(queue_id)
        if existing is not None:
            self.replayed_count += 1
            return existing

        item = MappingQueueItem(
            queue_id=queue_id,
            tenant_id=tenant_id,
            provider=provider,
            object_type=object_type,
            external_id=external_id,
            external_text=external_text,
            source_identity_key=source_identity_key,
            reason=reason,
            candidate_ids=tuple(candidate_ids),
            confidence=confidence,
            matching_rule=matching_rule,
            evidence_ids=tuple(evidence_ids),
            quality_status=quality_status,
            source_classification=source_classification,
            as_of=as_of,
        )

        self.pending[queue_id] = item
        self.enqueued_count += 1
        return item

    @staticmethod
    def _queue_id(
        *,
        tenant_id: str,
        provider: str,
        object_type: str,
        external_id: str | None,
        source_identity_key: str,
    ) -> str:
        raw = {
            "tenant_id": tenant_id,
            "provider": provider,
            "object_type": object_type,
            "external_id": external_id,
            "source_identity_key": source_identity_key,
        }

        canonical = json.dumps(
            raw,
            sort_keys=True,
            separators=(",", ":"),
        )

        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]

        return f"mapq_{digest}"

    def resolve(
        self,
        queue_id: str,
        *,
        canonical_id: str | None = None,
        approved: bool = False,
        confidence: float | None = None,
        mapping_version: int | None = None,
    ) -> MappingQueueItem:
        item = self.pending.get(queue_id)

        if item is None:
            if queue_id in self.resolved:
                return self.resolved[queue_id]
            raise KeyError(f"unknown mapping queue item: {queue_id}")

        resolved_item = MappingQueueItem(
            queue_id=item.queue_id,
            tenant_id=item.tenant_id,
            provider=item.provider,
            object_type=item.object_type,
            external_id=item.external_id,
            external_text=item.external_text,
            source_identity_key=item.source_identity_key,
            reason=item.reason,
            status="RESOLVED",
            canonical_id=canonical_id,
            approved=approved,
            confidence=confidence,
            mapping_version=mapping_version,
            candidate_ids=item.candidate_ids,
            matching_rule=item.matching_rule,
            evidence_ids=item.evidence_ids,
            quality_status=item.quality_status,
            source_classification=item.source_classification,
            as_of=item.as_of,
        )

        del self.pending[queue_id]
        self.resolved[queue_id] = resolved_item
        self.resolved_count += 1

        return resolved_item
