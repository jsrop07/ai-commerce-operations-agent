"""Append-only inventory ledger service."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class LedgerEntry:
    tenant_id: str
    sku_id: str
    delta: int
    reason: str
    business_key: str
    source_event_id: str
    occurred_at: datetime


@dataclass
class InventoryLedgerService:
    entries: list[LedgerEntry] = field(default_factory=list)
    _applied: dict[tuple[str, str], tuple] = field(default_factory=dict)

    @staticmethod
    def _effect_key(
        *,
        tenant_id: str,
        sku_id: str,
        reason: str,
        business_key: str,
    ) -> tuple[str, str]:
        return tenant_id, business_key

    def append_once(
        self,
        *,
        tenant_id: str,
        sku_id: str,
        delta: int,
        reason: str,
        business_key: str,
        source_event_id: str,
        occurred_at: datetime,
    ) -> bool:
        if not tenant_id:
            raise ValueError("tenant_id is required")
        if not sku_id:
            raise ValueError("sku_id is required")
        if not reason:
            raise ValueError("reason is required")
        if not business_key:
            raise ValueError("business_key is required")
        if not source_event_id:
            raise ValueError("source_event_id is required")
        if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
            raise ValueError("occurred_at must include timezone")

        effect_key = self._effect_key(
            tenant_id=tenant_id,
            sku_id=sku_id,
            reason=reason,
            business_key=business_key,
        )

        fact = (sku_id, reason, delta, occurred_at)
        if effect_key in self._applied:
            if self._applied[effect_key] != fact:
                raise ValueError("BUSINESS_IDENTITY_COLLISION: manual review required")
            return False

        self.entries.append(
            LedgerEntry(
                tenant_id=tenant_id,
                sku_id=sku_id,
                delta=delta,
                reason=reason,
                business_key=business_key,
                source_event_id=source_event_id,
                occurred_at=occurred_at,
            )
        )
        self._applied[effect_key] = fact

        return True

    def delta_total(
        self,
        *,
        tenant_id: str,
        sku_id: str,
    ) -> int:
        return sum(
            entry.delta
            for entry in self.entries
            if entry.tenant_id == tenant_id and entry.sku_id == sku_id
        )
