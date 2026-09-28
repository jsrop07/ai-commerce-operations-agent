"""Inventory read projection calculations."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class InventorySelectionStatus(StrEnum):
    """Resolution state for a canonical physical-warehouse group."""

    SELECTED = "SELECTED"
    UNRESOLVED = "UNRESOLVED"
    AMBIGUOUS = "AMBIGUOUS"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class InventorySnapshotCandidate:
    """Synthetic/provider snapshot candidate before warehouse deduplication."""

    tenant_id: str
    provider: str
    sku_id: str
    canonical_warehouse_key: str | None
    on_hand: int | None
    reserved: int | None
    as_of: datetime
    quality_status: str
    usable: bool
    authoritative: bool = False


@dataclass(frozen=True)
class InventorySnapshotSelection:
    """One selected source, or an explicit non-selected resolution state."""

    tenant_id: str
    sku_id: str
    canonical_warehouse_key: str | None
    status: InventorySelectionStatus
    selected: InventorySnapshotCandidate | None = None

    @property
    def on_hand(self) -> int | None:
        """Selected on-hand quantity; unresolved states never become zero."""

        return self.selected.on_hand if self.selected is not None else None


def _validate_snapshot_candidate(candidate: InventorySnapshotCandidate) -> None:
    if not candidate.tenant_id:
        raise ValueError("tenant_id is required")
    if not candidate.provider:
        raise ValueError("provider is required")
    if not candidate.sku_id:
        raise ValueError("sku_id is required")
    if candidate.as_of.tzinfo is None or candidate.as_of.utcoffset() is None:
        raise ValueError("as_of must include timezone")


def select_inventory_snapshot_candidates(
    candidates: Sequence[InventorySnapshotCandidate],
) -> tuple[InventorySnapshotSelection, ...]:
    """Select at most one source per tenant/SKU/canonical warehouse.

    Provider snapshots sharing one explicit canonical warehouse key are
    alternatives, never additive quantities. Missing mapping, unusable
    quality, and tied authority remain explicit states instead of falling back
    to a summed or zero quantity.
    """

    groups: dict[
        tuple[str, str, str | None],
        list[InventorySnapshotCandidate],
    ] = defaultdict(list)
    for candidate in candidates:
        _validate_snapshot_candidate(candidate)
        groups[
            (
                candidate.tenant_id,
                candidate.sku_id,
                candidate.canonical_warehouse_key,
            )
        ].append(candidate)

    selections: list[InventorySnapshotSelection] = []
    for (tenant_id, sku_id, warehouse_key), group in sorted(
        groups.items(),
        key=lambda entry: (
            entry[0][0],
            entry[0][1],
            entry[0][2] or "",
        ),
    ):
        if not warehouse_key:
            selections.append(
                InventorySnapshotSelection(
                    tenant_id=tenant_id,
                    sku_id=sku_id,
                    canonical_warehouse_key=None,
                    status=InventorySelectionStatus.UNRESOLVED,
                )
            )
            continue

        usable = [
            candidate
            for candidate in group
            if candidate.usable
            and candidate.quality_status == "CONFIRMED"
            and candidate.on_hand is not None
        ]
        if not usable:
            selections.append(
                InventorySnapshotSelection(
                    tenant_id=tenant_id,
                    sku_id=sku_id,
                    canonical_warehouse_key=warehouse_key,
                    status=InventorySelectionStatus.UNKNOWN,
                )
            )
            continue

        authoritative = [
            candidate for candidate in usable if candidate.authoritative
        ]
        pool = authoritative or usable
        latest_as_of = max(candidate.as_of for candidate in pool)
        latest = [
            candidate
            for candidate in pool
            if candidate.as_of == latest_as_of
        ]
        if len(latest) > 1:
            equivalent = {
                (
                    candidate.on_hand,
                    candidate.reserved,
                    candidate.quality_status,
                )
                for candidate in latest
            }
            if len(equivalent) == 1:
                # Identical source facts are a duplicate representation of
                # one physical quantity.  Pick deterministically without
                # adding the candidates together.
                latest = [
                    sorted(latest, key=lambda candidate: candidate.provider)[0]
                ]
        if len(latest) != 1:
            selections.append(
                InventorySnapshotSelection(
                    tenant_id=tenant_id,
                    sku_id=sku_id,
                    canonical_warehouse_key=warehouse_key,
                    status=InventorySelectionStatus.AMBIGUOUS,
                )
            )
            continue

        selections.append(
            InventorySnapshotSelection(
                tenant_id=tenant_id,
                sku_id=sku_id,
                canonical_warehouse_key=warehouse_key,
                status=InventorySelectionStatus.SELECTED,
                selected=latest[0],
            )
        )

    return tuple(selections)


@dataclass(frozen=True)
class InventoryProjection:
    tenant_id: str
    sku_id: str
    source_on_hand: int | None
    ledger_delta: int
    reserved: int | None
    expected_inventory: int | None
    available_inventory: int | None
    confirmed_incoming: int | None
    quality_status: str
    ttl_seconds: int
    age_seconds: int
    freshness_reason: str
    confirmed_for_total: bool
    calculation: dict[str, int | None]
    risk_level: str
    evidence: tuple[str, ...]
    provider: str = "UNKNOWN"
    as_of: datetime | None = None
    freshness: str = "UNKNOWN"


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
    provider: str = "UNKNOWN",
    as_of: datetime | None = None,
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

    if as_of is not None and (
        as_of.tzinfo is None or as_of.utcoffset() is None
    ):
        raise ValueError("as_of must include timezone")

    if source_on_hand is None:
        expected_inventory = None
        available_inventory = None
        freshness_reason = "SOURCE_ON_HAND_UNKNOWN"
        freshness = "UNKNOWN"
        confirmed_for_total = False
    elif quality_status != "CONFIRMED":
        expected_inventory = None
        available_inventory = None
        freshness_reason = "SOURCE_QUALITY_NOT_CONFIRMED"
        freshness = "UNKNOWN"
        confirmed_for_total = False
    elif is_stale:
        expected_inventory = source_on_hand + ledger_delta
        available_inventory = (
            None
            if reserved is None
            else expected_inventory - reserved
        )
        freshness_reason = "STALE"
        freshness = "STALE"
        confirmed_for_total = False
    else:
        expected_inventory = source_on_hand + ledger_delta
        available_inventory = (
            None
            if reserved is None
            else expected_inventory - reserved
        )
        freshness = "FRESH"
        if reserved is None:
            freshness_reason = "RESERVED_UNKNOWN"
            confirmed_for_total = False
        else:
            freshness_reason = "FRESH"
            confirmed_for_total = True

    return InventoryProjection(
        tenant_id=tenant_id,
        sku_id=sku_id,
        source_on_hand=source_on_hand,
        ledger_delta=ledger_delta,
        reserved=reserved,
        expected_inventory=expected_inventory,
        available_inventory=available_inventory,
        confirmed_incoming=confirmed_incoming,
        quality_status=quality_status,
        ttl_seconds=ttl_seconds,
        age_seconds=age_seconds,
        freshness_reason=freshness_reason,
        confirmed_for_total=confirmed_for_total,
        calculation={
            "source_on_hand": source_on_hand,
            "ledger_delta": ledger_delta,
            "expected_inventory": expected_inventory,
            "reserved": reserved,
            "available_inventory": available_inventory,
        },
        risk_level=risk_level,
        evidence=evidence,
        provider=provider,
        as_of=as_of,
        freshness=freshness,
    )
