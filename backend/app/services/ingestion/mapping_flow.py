"""Mapping-required routing from provider mapper results into review queue."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from functools import wraps
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.adapters.providers.toss_pos.mapper import (
    TossSaleMappingResult,
    map_toss_order_line_to_sale,
)
from backend.app.models.catalog import SKU, ProviderMapping
from backend.app.services.ingestion.mapping_queue import (
    MappingQueueItem,
    MappingReviewQueue,
    ReprocessAudit,
)


@dataclass(frozen=True)
class MappingFlowResult:
    status: str
    queue_item: MappingQueueItem | None = None


@dataclass(frozen=True)
class ReprocessResult:
    status: str
    mapping_result: TossSaleMappingResult | None


def route_toss_mapping_result(
    *,
    result: TossSaleMappingResult,
    queue: MappingReviewQueue,
    tenant_id: str,
    source_identity_key: str,
) -> MappingFlowResult:
    if result.status != "MAPPING_REQUIRED":
        return MappingFlowResult(status="NOT_REQUIRED")

    item = queue.enqueue(
        tenant_id=tenant_id,
        provider="TOSS_POS",
        object_type="SKU",
        external_id=result.external_product_code,
        external_text=result.external_product_text,
        source_identity_key=source_identity_key,
        reason=result.reason or "MAPPING_REQUIRED",
    )

    return MappingFlowResult(
        status="QUEUED",
        queue_item=item,
    )


def _audit_reprocess(function):
    @wraps(function)
    def audited(**kwargs):
        queue = kwargs["queue"]
        queue_id = kwargs["queue_id"]
        status = "REPROCESS_EXCEPTION"
        try:
            result = function(**kwargs)
            status = result.status
            return result
        finally:
            item = queue.resolved.get(queue_id)
            same_tenant = item is not None and item.tenant_id == kwargs["tenant_id"]
            queue.audit.append(
                ReprocessAudit(
                    queue_id=queue_id,
                    tenant_id=kwargs["tenant_id"],
                    status=status,
                    attempted_at=datetime.now(UTC),
                    canonical_id=item.canonical_id if same_tenant else None,
                    mapping_version=item.mapping_version if same_tenant else None,
                )
            )

    return audited


@_audit_reprocess
def reprocess_toss_mapping_item(
    *,
    queue_id: str,
    queue: MappingReviewQueue,
    tenant_id: str,
    provider_account_ref: str,
    order: dict[str, Any],
    line_item: dict[str, Any],
    line_index: int,
    approved_sku_by_product_code: dict[str, str] | None = None,
    session: Session | None = None,
    ingested_at: datetime | None = None,
) -> ReprocessResult:
    item = queue.pending.get(queue_id)

    if item is None:
        return ReprocessResult(
            status="NOT_PENDING",
            mapping_result=None,
        )

    if item.tenant_id != tenant_id:
        return ReprocessResult(
            status="TENANT_MISMATCH",
            mapping_result=None,
        )

    if item.provider != "TOSS_POS":
        return ReprocessResult(
            status="PROVIDER_MISMATCH",
            mapping_result=None,
        )

    if item.object_type != "SKU":
        return ReprocessResult(status="OBJECT_TYPE_MISMATCH", mapping_result=None)
    product = line_item.get("item")
    code = str(product.get("code", "")).strip() if isinstance(product, dict) else None
    if code != item.external_id:
        return ReprocessResult(status="SOURCE_MISMATCH", mapping_result=None)
    # Caller-supplied dictionaries are not proof of approval.
    if session is None or item.external_id is None:
        return ReprocessResult(status="APPROVED_MAPPING_REQUIRED", mapping_result=None)
    with session.no_autoflush:
        candidates = list(
            session.scalars(
                select(ProviderMapping)
                .where(
                    ProviderMapping.tenant_id == tenant_id,
                    ProviderMapping.provider == item.provider,
                    ProviderMapping.object_type == "SKU",
                    ProviderMapping.external_id == item.external_id,
                )
                .execution_options(populate_existing=True)
            )
        )
        if any(row.status == "AMBIGUOUS" for row in candidates):
            return ReprocessResult(status="AMBIGUOUS_MAPPING", mapping_result=None)
        approved = [row for row in candidates if row.approved]
        if len({row.canonical_id for row in approved}) > 1:
            return ReprocessResult(status="MAPPING_COLLISION", mapping_result=None)
        latest = max(candidates, key=lambda row: row.version, default=None)
        if latest is None or not latest.approved or latest.status != "VERIFIED":
            return ReprocessResult(status="APPROVED_MAPPING_REQUIRED", mapping_result=None)
        sku = session.scalar(
            select(SKU).where(
                SKU.tenant_id == tenant_id,
                SKU.id == latest.canonical_id,
            )
        )
        if sku is None:
            return ReprocessResult(status="CANONICAL_TENANT_MISMATCH", mapping_result=None)
    approved_sku_by_product_code = {item.external_id: latest.canonical_id}

    mapping_result = map_toss_order_line_to_sale(
        tenant_id=tenant_id,
        provider_account_ref=provider_account_ref,
        order=order,
        line_item=line_item,
        line_index=line_index,
        approved_sku_by_product_code=approved_sku_by_product_code,
        ingested_at=ingested_at,
    )

    if mapping_result.status != "MAPPED" or mapping_result.event is None:
        return ReprocessResult(
            status="REPROCESS_FAILED",
            mapping_result=mapping_result,
        )

    queue.resolve(
        queue_id,
        canonical_id=latest.canonical_id,
        approved=True,
        confidence=latest.confidence,
        mapping_version=latest.version,
    )

    return ReprocessResult(
        status="REPROCESSED",
        mapping_result=mapping_result,
    )
