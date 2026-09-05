"""Synthetic eCount inventory DTO to canonical inventory event mapping."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from contracts.events import (
    EVENT_SCHEMA_VERSION,
    CanonicalCommerceEvent,
    EventType,
    Provider,
)


@dataclass(frozen=True)
class EcountInventoryMappingResult:
    status: str
    event: CanonicalCommerceEvent | None
    external_product_code: str | None
    warehouse_code: str | None
    unit: str | None
    reason: str | None = None


def _required_text(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value).strip()
    return text or None


def _event_id(source_event_id: str) -> str:
    digest = hashlib.sha256(source_event_id.encode()).hexdigest()[:24]
    return f"evt_ecount_{digest}"


def map_ecount_inventory_fixture(
    *,
    tenant_id: str,
    row: dict[str, Any],
    approved_sku_by_product_code: dict[str, str],
    ingested_at: datetime | None = None,
) -> EcountInventoryMappingResult:
    """Map one synthetic eCount inventory fixture without guessing values."""

    product_code = _required_text(row.get("product_code"))
    warehouse_code = _required_text(row.get("warehouse_code"))
    unit = _required_text(row.get("unit"))

    if product_code is None:
        return EcountInventoryMappingResult(
            status="QUARANTINED",
            event=None,
            external_product_code=None,
            warehouse_code=warehouse_code,
            unit=unit,
            reason="MISSING_PRODUCT_CODE",
        )

    if warehouse_code is None:
        return EcountInventoryMappingResult(
            status="QUARANTINED",
            event=None,
            external_product_code=product_code,
            warehouse_code=None,
            unit=unit,
            reason="MISSING_WAREHOUSE_CODE",
        )

    if unit is None:
        return EcountInventoryMappingResult(
            status="QUARANTINED",
            event=None,
            external_product_code=product_code,
            warehouse_code=warehouse_code,
            unit=None,
            reason="MISSING_UNIT",
        )

    sku_id = approved_sku_by_product_code.get(product_code)

    if sku_id is None:
        return EcountInventoryMappingResult(
            status="QUARANTINED",
            event=None,
            external_product_code=product_code,
            warehouse_code=warehouse_code,
            unit=unit,
            reason="UNKNOWN_PRODUCT_CODE",
        )

    on_hand = row.get("on_hand")

    if not isinstance(on_hand, int) or isinstance(on_hand, bool):
        return EcountInventoryMappingResult(
            status="QUARANTINED",
            event=None,
            external_product_code=product_code,
            warehouse_code=warehouse_code,
            unit=unit,
            reason="INVALID_ON_HAND",
        )

    as_of_raw = row.get("as_of")

    if as_of_raw is None:
        return EcountInventoryMappingResult(
            status="QUARANTINED",
            event=None,
            external_product_code=product_code,
            warehouse_code=warehouse_code,
            unit=unit,
            reason="MISSING_AS_OF",
        )

    try:
        as_of = datetime.fromisoformat(
            str(as_of_raw).replace("Z", "+00:00")
        )
    except ValueError:
        return EcountInventoryMappingResult(
            status="QUARANTINED",
            event=None,
            external_product_code=product_code,
            warehouse_code=warehouse_code,
            unit=unit,
            reason="INVALID_AS_OF",
        )

    if as_of.tzinfo is None or as_of.utcoffset() is None:
        return EcountInventoryMappingResult(
            status="QUARANTINED",
            event=None,
            external_product_code=product_code,
            warehouse_code=warehouse_code,
            unit=unit,
            reason="TIMEZONE_REQUIRED",
        )

    source_record_id = _required_text(row.get("source_record_id"))

    if source_record_id is None:
        return EcountInventoryMappingResult(
            status="QUARANTINED",
            event=None,
            external_product_code=product_code,
            warehouse_code=warehouse_code,
            unit=unit,
            reason="MISSING_SOURCE_RECORD_ID",
        )

    source_event_id = (
        f"{source_record_id}:{product_code}:{warehouse_code}:{unit}"
    )

    schema_version = EVENT_SCHEMA_VERSION
    now = ingested_at or datetime.now(UTC)

    event = CanonicalCommerceEvent(
        event_id=_event_id(source_event_id),
        event_type=EventType.INVENTORY_SNAPSHOT_RECEIVED,
        schema_version=schema_version,
        tenant_id=tenant_id,
        source=Provider.ECOUNT,
        source_event_id=source_event_id,
        occurred_at=as_of,
        ingested_at=now,
        idempotency_key=(
            f"{Provider.ECOUNT.value}:{source_event_id}:{schema_version}"
        ),
        correlation_id=f"corr_{_event_id(source_event_id)}",
        payload={
            "sku_id": sku_id,
            "external_product_code": product_code,
            "warehouse_code": warehouse_code,
            "unit": unit,
            "on_hand": on_hand,
            "as_of": as_of.isoformat(),
        },
    )

    return EcountInventoryMappingResult(
        status="MAPPED",
        event=event,
        external_product_code=product_code,
        warehouse_code=warehouse_code,
        unit=unit,
    )