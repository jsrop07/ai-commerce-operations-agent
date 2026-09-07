"""Inventory read projection calculations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InventoryProjection:
    tenant_id: str
    sku_id: str
    source_on_hand: int | None
    ledger_delta: int
    reserved: int | None
    expected_inventory: int | None
    confirmed_incoming: int | None
    quality_status: str
    ttl_seconds: int
    age_seconds: int
    freshness_reason: str
    confirmed_for_total: bool
    calculation: dict[str, int | None]
    risk_level: str
    evidence: tuple[str, ...]


def build_inventory_projection(
    *,
    tenant_id: str,
    sku_id: str,
    source_on_hand: int | None,
    ledger_delta: int,
    reserved: int | None,
    confirmed_incoming: int | None,
    quality_status: str,
    ttl_seconds: int,
    age_seconds: int,
    risk_level: str = "UNKNOWN",
    evidence: tuple[str, ...] = (),
) -> InventoryProjection:
    if not tenant_id:
        raise ValueError("tenant_id is required")
    if not sku_id:
        raise ValueError("sku_id is required")
    if ttl_seconds < 0:
        raise ValueError("ttl_seconds must be >= 0")
    if age_seconds < 0:
        raise ValueError("age_seconds must be >= 0")

    is_stale = age_seconds > ttl_seconds

    if source_on_hand is None:
        expected_inventory = None
        freshness_reason = "SOURCE_ON_HAND_UNKNOWN"
        confirmed_for_total = False
    elif reserved is None:
        expected_inventory = None
        freshness_reason = "RESERVED_UNKNOWN"
        confirmed_for_total = False
    elif quality_status != "CONFIRMED":
        expected_inventory = None
        freshness_reason = "SOURCE_QUALITY_NOT_CONFIRMED"
        confirmed_for_total = False
    elif is_stale:
        expected_inventory = source_on_hand + ledger_delta - reserved
        freshness_reason = "STALE"
        confirmed_for_total = False
    else:
        expected_inventory = source_on_hand + ledger_delta - reserved
        freshness_reason = "FRESH"
        confirmed_for_total = True

    return InventoryProjection(
        tenant_id=tenant_id,
        sku_id=sku_id,
        source_on_hand=source_on_hand,
        ledger_delta=ledger_delta,
        reserved=reserved,
        expected_inventory=expected_inventory,
        confirmed_incoming=confirmed_incoming,
        quality_status=quality_status,
        ttl_seconds=ttl_seconds,
        age_seconds=age_seconds,
        freshness_reason=freshness_reason,
        confirmed_for_total=confirmed_for_total,
        calculation={
            "source_on_hand": source_on_hand,
            "ledger_delta": ledger_delta,
            "reserved": reserved,
            "expected_inventory": expected_inventory,
        },
        risk_level=risk_level,
        evidence=evidence,
    )
