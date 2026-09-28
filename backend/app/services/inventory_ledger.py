"""Append-only inventory ledger service."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models.commerce import InventoryLedger, InventorySnapshot


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
        snapshot_as_of: datetime | None = None,
    ) -> int:
        if snapshot_as_of is not None and (
            snapshot_as_of.tzinfo is None
            or snapshot_as_of.utcoffset() is None
        ):
            raise ValueError("snapshot_as_of must include timezone")

        return sum(
            entry.delta
            for entry in self.entries
            if entry.tenant_id == tenant_id
            and entry.sku_id == sku_id
            and (
                snapshot_as_of is None
                or entry.occurred_at > snapshot_as_of
            )
        )


class BusinessIdentityCollision(ValueError):
    """A business key was reused for a different business fact."""


class AmbiguousInventorySnapshot(ValueError):
    """A provider is required when snapshots span multiple providers."""


def _validate_append_input(
    *,
    tenant_id: str,
    sku_id: str,
    reason: str,
    business_key: str,
    source_event_id: str,
    occurred_at: datetime,
) -> None:
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


def _utc_datetime(value: datetime) -> datetime:
    """Normalize aware datetimes, including SQLite's timezone-less readback."""

    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _fact_matches(
    row: InventoryLedger,
    *,
    sku_id: str,
    reason: str,
    delta: int,
    occurred_at: datetime,
) -> bool:
    return (
        row.sku_id == sku_id
        and row.reason == reason
        and row.delta == delta
        and _utc_datetime(row.occurred_at) == _utc_datetime(occurred_at)
    )


@dataclass
class InventoryLedgerRepository:
    """SQLAlchemy-backed inventory ledger and source snapshot boundary."""

    session: Session

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
        _validate_append_input(
            tenant_id=tenant_id,
            sku_id=sku_id,
            reason=reason,
            business_key=business_key,
            source_event_id=source_event_id,
            occurred_at=occurred_at,
        )

        existing = self.session.scalar(
            select(InventoryLedger).where(
                InventoryLedger.tenant_id == tenant_id,
                InventoryLedger.business_key == business_key,
            )
        )
        if existing is not None:
            if not _fact_matches(
                existing,
                sku_id=sku_id,
                reason=reason,
                delta=delta,
                occurred_at=occurred_at,
            ):
                raise BusinessIdentityCollision(
                    "BUSINESS_IDENTITY_COLLISION: manual review required"
                )
            return False

        row = InventoryLedger(
            tenant_id=tenant_id,
            sku_id=sku_id,
            delta=delta,
            reason=reason,
            business_key=business_key,
            source_event_id=source_event_id,
            occurred_at=occurred_at,
        )
        self.session.add(row)

        try:
            self.session.commit()
        except IntegrityError as exc:
            # A concurrent insert may win the business-key constraint.  Roll
            # back this transaction, then classify the committed row by fact.
            self.session.rollback()
            existing = self.session.scalar(
                select(InventoryLedger).where(
                    InventoryLedger.tenant_id == tenant_id,
                    InventoryLedger.business_key == business_key,
                )
            )
            if existing is None:
                raise
            if not _fact_matches(
                existing,
                sku_id=sku_id,
                reason=reason,
                delta=delta,
                occurred_at=occurred_at,
            ):
                raise BusinessIdentityCollision(
                    "BUSINESS_IDENTITY_COLLISION: manual review required"
                ) from exc
            return False

        self.session.refresh(row)
        return True

    def latest_snapshot(
        self,
        *,
        tenant_id: str,
        sku_id: str,
        provider: str | None = None,
    ) -> InventorySnapshot | None:
        if not tenant_id:
            raise ValueError("tenant_id is required")
        if not sku_id:
            raise ValueError("sku_id is required")
        if provider is not None and not provider:
            raise ValueError("provider must be non-empty when provided")

        base_filters = (
            InventorySnapshot.tenant_id == tenant_id,
            InventorySnapshot.sku_id == sku_id,
        )
        if provider is None:
            providers = tuple(
                self.session.scalars(
                    select(InventorySnapshot.provider)
                    .where(*base_filters)
                    .distinct()
                )
            )
            if len(providers) > 1:
                raise AmbiguousInventorySnapshot(
                    "provider is required for multiple inventory snapshot providers"
                )
        else:
            base_filters = base_filters + (
                InventorySnapshot.provider == provider,
            )

        return self.session.scalar(
            select(InventorySnapshot)
            .where(*base_filters)
            .order_by(InventorySnapshot.as_of.desc())
            .limit(1)
        )

    def delta_total_after_snapshot(
        self,
        *,
        tenant_id: str,
        sku_id: str,
        snapshot_as_of: datetime,
    ) -> int:
        if not tenant_id:
            raise ValueError("tenant_id is required")
        if not sku_id:
            raise ValueError("sku_id is required")
        if snapshot_as_of.tzinfo is None or snapshot_as_of.utcoffset() is None:
            raise ValueError("snapshot_as_of must include timezone")

        total = self.session.scalar(
            select(func.coalesce(func.sum(InventoryLedger.delta), 0)).where(
                InventoryLedger.tenant_id == tenant_id,
                InventoryLedger.sku_id == sku_id,
                InventoryLedger.occurred_at > snapshot_as_of,
            )
        )
        return int(total or 0)


# Keep a service-named entry point available without duplicating the repository.
PersistentInventoryLedgerService = InventoryLedgerRepository
