"""Read-only mapping review projection."""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.services.ingestion.mapping_queue import MappingReviewQueue

from datetime import UTC, datetime

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

@dataclass(frozen=True)
class MappingReviewItem:
    queue_id: str
    tenant_id: str
    provider: str
    object_type: str
    external_id: str | None
    reason: str
    review_status: str

    candidates: tuple[dict[str, str], ...]
    confidence: float | None
    matching_rule: str | None
    evidence: tuple[str, ...]

    quality_status: str
    as_of: datetime
    source_classification: str

    selected_sku_id: str | None


def _build_review_item(
    item,
    *,
    review_status: str,
) -> MappingReviewItem:
    candidates = tuple(
        {
            "sku_id": candidate_id,
        }
        for candidate_id
        in item.candidate_ids
    )

    # 후보가 하나여도 approved가 아니라면
    # 서버가 자동 선택하지 않는다.
    selected_sku_id = (
        item.canonical_id
        if (
            item.approved
            and item.object_type == "SKU"
            and item.canonical_id
        )
        else None
    )

    if item.quality_status:
        quality_status = (
            item.quality_status
        )
    elif candidates:
        quality_status = (
            "REVIEW_REQUIRED"
        )
    else:
        quality_status = "BLOCKED"

    evidence = (
        item.evidence_ids
        if item.evidence_ids
        else (
            item.source_identity_key,
        )
    )

    return MappingReviewItem(
        queue_id=item.queue_id,
        tenant_id=item.tenant_id,
        provider=item.provider,
        object_type=item.object_type,
        external_id=item.external_id,
        reason=item.reason,
        review_status=review_status,
        candidates=candidates,
        confidence=item.confidence,
        matching_rule=item.matching_rule,
        evidence=evidence,
        quality_status=quality_status,
        as_of=(
            item.as_of
            or datetime.now(UTC)
        ),
        source_classification=(
            item.source_classification
        ),
        selected_sku_id=(
            selected_sku_id
        ),
    )


def build_mapping_review_projection(
    *,
    queue: MappingReviewQueue,
) -> list[MappingReviewItem]:
    """PII 없는 Mapping Review 전용 projection."""

    items: list[
        MappingReviewItem
    ] = []

    for item in queue.pending.values():
        items.append(
            _build_review_item(
                item,
                review_status="PENDING",
            )
        )

    for item in queue.resolved.values():
        items.append(
            _build_review_item(
                item,
                review_status="RESOLVED",
            )
        )

    return items

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
