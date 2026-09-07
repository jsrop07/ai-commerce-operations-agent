"""Read-only mapping review projection."""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.services.ingestion.mapping_queue import MappingReviewQueue


@dataclass(frozen=True)
class MappingReadItem:
    queue_id: str
    tenant_id: str
    provider: str
    object_type: str
    external_id: str | None
    external_text: str | None
    reason: str
    review_status: str
    source_identity_key: str
    confidence: float | None
    matching_rule: str | None
    canonical_id: str | None
    approved: bool


def build_mapping_read_projection(
    *,
    queue: MappingReviewQueue,
) -> list[MappingReadItem]:
    items: list[MappingReadItem] = []

    for item in queue.pending.values():
        items.append(
            MappingReadItem(
                queue_id=item.queue_id,
                tenant_id=item.tenant_id,
                provider=item.provider,
                object_type=item.object_type,
                external_id=item.external_id,
                external_text=item.external_text,
                reason=item.reason,
                review_status="PENDING",
                source_identity_key=item.source_identity_key,
                confidence=item.confidence,
                matching_rule=None,
                canonical_id=item.canonical_id,
                approved=False,
            )
        )

    for item in queue.resolved.values():
        items.append(
            MappingReadItem(
                queue_id=item.queue_id,
                tenant_id=item.tenant_id,
                provider=item.provider,
                object_type=item.object_type,
                external_id=item.external_id,
                external_text=item.external_text,
                reason=item.reason,
                review_status="RESOLVED",
                source_identity_key=item.source_identity_key,
                confidence=item.confidence,
                matching_rule=None,
                canonical_id=item.canonical_id,
                approved=item.approved,
            )
        )

    return items
