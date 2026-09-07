"""Toss POS order-line DTO to canonical offline-sale mapping."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from backend.app.services.ingestion.identity import (
    build_toss_sale_business_identity,
)
from contracts.events import (
    EVENT_SCHEMA_VERSION,
    CanonicalCommerceEvent,
    EventType,
    Provider,
)


@dataclass(frozen=True)
class TossSaleMappingResult:
    status: str
    event: CanonicalCommerceEvent | None
    external_product_code: str | None
    external_product_text: str | None
    reason: str | None = None


def _required_text(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value).strip()
    return text or None


def _event_id(source_event_id: str) -> str:
    digest = hashlib.sha256(source_event_id.encode()).hexdigest()[:24]
    return f"evt_toss_{digest}"


def map_toss_order_line_to_sale(
    *,
    tenant_id: str,
    provider_account_ref: str = "legacy-default",
    order: dict[str, Any],
    line_item: dict[str, Any],
    line_index: int,
    approved_sku_by_product_code: dict[str, str],
    ingested_at: datetime | None = None,
) -> TossSaleMappingResult:
    """Map one Toss order line without guessing SKU, quantity, or timestamps."""

    order_id = _required_text(order.get("id"))
    if order_id is None:
        return TossSaleMappingResult(
            status="QUARANTINED",
            event=None,
            external_product_code=None,
            external_product_text=None,
            reason="MISSING_ORDER_ID",
        )

    item = line_item.get("item")
    if not isinstance(item, dict):
        return TossSaleMappingResult(
            status="QUARANTINED",
            event=None,
            external_product_code=None,
            external_product_text=None,
            reason="MISSING_ITEM",
        )

    product_code = _required_text(item.get("code"))
    product_text = _required_text(item.get("title"))

    if product_code is None:
        return TossSaleMappingResult(
            status="MAPPING_REQUIRED",
            event=None,
            external_product_code=None,
            external_product_text=product_text,
            reason="MISSING_PRODUCT_CODE",
        )

    sku_id = approved_sku_by_product_code.get(product_code)

    if sku_id is None:
        return TossSaleMappingResult(
            status="MAPPING_REQUIRED",
            event=None,
            external_product_code=product_code,
            external_product_text=product_text,
            reason="UNKNOWN_PRODUCT_CODE",
        )

    quantity = line_item.get("quantity")
    if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
        return TossSaleMappingResult(
            status="QUARANTINED",
            event=None,
            external_product_code=product_code,
            external_product_text=product_text,
            reason="INVALID_QUANTITY",
        )

    order_state = _required_text(order.get("orderState"))

    if order_state == "CANCELLED":
        return TossSaleMappingResult(
            status="IGNORED_CANCELLED",
            event=None,
            external_product_code=product_code,
            external_product_text=product_text,
            reason="CANCELLED_ORDER_REQUIRES_SEPARATE_POLICY",
        )

    occurred_raw = order.get("completedAt") or order.get("createdAt")
    if occurred_raw is None:
        return TossSaleMappingResult(
            status="QUARANTINED",
            event=None,
            external_product_code=product_code,
            external_product_text=product_text,
            reason="MISSING_OCCURRED_AT",
        )

    try:
        occurred_at = datetime.fromisoformat(str(occurred_raw).replace("Z", "+00:00"))
    except ValueError:
        return TossSaleMappingResult(
            status="QUARANTINED",
            event=None,
            external_product_code=product_code,
            external_product_text=product_text,
            reason="INVALID_OCCURRED_AT",
        )

    if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
        return TossSaleMappingResult(
            status="QUARANTINED",
            event=None,
            external_product_code=product_code,
            external_product_text=product_text,
            reason="TIMEZONE_REQUIRED",
        )

    amount_raw = line_item.get("amount", 0)

    try:
        amount = Decimal(str(amount_raw))
    except Exception:
        return TossSaleMappingResult(
            status="QUARANTINED",
            event=None,
            external_product_code=product_code,
            external_product_text=product_text,
            reason="INVALID_AMOUNT",
        )

    source_event_id = f"{order_id}:line:{line_index}"
    schema_version = EVENT_SCHEMA_VERSION
    now = ingested_at or datetime.now(UTC)

    business_identity = build_toss_sale_business_identity(
        tenant_id=tenant_id,
        provider_account_ref=provider_account_ref,
        order_id=order_id,
        line_id=str(line_index),
        sku_id=sku_id,
        occurred_at=occurred_at,
        schema_version=schema_version,
    )

    if business_identity.status != "RESOLVED" or business_identity.identity is None:
        return TossSaleMappingResult(
            status="QUARANTINED",
            event=None,
            external_product_code=product_code,
            external_product_text=product_text,
            reason=business_identity.reason or "BUSINESS_IDENTITY_UNRESOLVED",
        )

    business_identity_key = business_identity.identity.key()

    event = CanonicalCommerceEvent(
        event_id=_event_id(source_event_id),
        event_type=EventType.OFFLINE_SALE_RECORDED,
        schema_version=schema_version,
        tenant_id=tenant_id,
        source=Provider.TOSS_POS,
        source_event_id=source_event_id,
        occurred_at=occurred_at,
        ingested_at=now,
        idempotency_key=(f"{Provider.TOSS_POS.value}:{source_event_id}:{schema_version}"),
        correlation_id=f"corr_{_event_id(source_event_id)}",
        payload={
            "sku_id": sku_id,
            "business_identity_key": business_identity_key,
            "external_product_code": product_code,
            "external_product_text": product_text,
            "quantity": quantity,
            "amount": {
                "currency": "KRW",
                "value": str(amount),
            },
            "order_state": order_state,
        },
    )

    return TossSaleMappingResult(
        status="MAPPED",
        event=event,
        external_product_code=product_code,
        external_product_text=product_text,
    )
