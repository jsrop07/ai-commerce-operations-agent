"""C24 fail-closed, per-session provider reservation boundary."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import TypeVar
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.config import Settings
from backend.app.models_v2.ai import DemoProviderUsageV2, DemoSessionV2

T = TypeVar("T")
MILLION = Decimal(1_000_000)


class DemoQuotaDenied(Exception):
    pass


@dataclass(frozen=True)
class QuotaLimits:
    priced_model: str
    max_calls: int
    max_input_tokens: int
    max_output_tokens: int
    max_cost_usd: Decimal
    input_usd_per_million_tokens: Decimal
    output_usd_per_million_tokens: Decimal

    @classmethod
    def from_settings(cls, settings: Settings) -> QuotaLimits:
        values = (
            settings.demo_quota_priced_model,
            settings.demo_quota_max_provider_calls,
            settings.demo_quota_max_input_tokens,
            settings.demo_quota_max_output_tokens,
            settings.demo_quota_max_estimated_cost_usd,
            settings.demo_quota_input_usd_per_million_tokens,
            settings.demo_quota_output_usd_per_million_tokens,
        )
        if not values[0] or any(value is None or value <= 0 for value in values[1:]):
            raise DemoQuotaDenied("C24_QUOTA_UNCONFIGURED")
        return cls(*values)

    def cost(self, input_tokens: int, output_tokens: int) -> Decimal:
        return ((Decimal(input_tokens) * self.input_usd_per_million_tokens
                 + Decimal(output_tokens) * self.output_usd_per_million_tokens) / MILLION)


def _lock_session(db: Session, *, tenant_id: UUID, session_id: UUID) -> DemoSessionV2 | None:
    # SQLite is used only for isolated tests; BEGIN IMMEDIATE provides its writer lock.
    if db.bind is not None and db.bind.dialect.name == "sqlite":
        db.execute(text("BEGIN IMMEDIATE"))
    return db.scalar(select(DemoSessionV2).where(
        DemoSessionV2.tenant_id == tenant_id, DemoSessionV2.id == session_id,
    ).with_for_update())


def reserve(
    factory: sessionmaker, *, tenant_id: UUID, session_id: UUID,
    request_id: str, model: str, calls: int, input_tokens: int, output_tokens: int,
    limits: QuotaLimits,
) -> UUID:
    if not request_id or len(request_id) > 128 or not model or len(model) > 128:
        raise DemoQuotaDenied("C24_RESERVATION_INVALID")
    if model != limits.priced_model:
        raise DemoQuotaDenied("C24_MODEL_UNPRICED")
    if min(calls, input_tokens, output_tokens) < 1:
        raise DemoQuotaDenied("C24_RESERVATION_INVALID")
    estimated_cost = limits.cost(input_tokens, output_tokens)
    with factory() as db:
        row = _lock_session(db, tenant_id=tenant_id, session_id=session_id)
        expiry = row.expires_at if row is not None else None
        if expiry is not None and expiry.tzinfo is None:  # SQLite test adapter
            expiry = expiry.replace(tzinfo=UTC)
        if row is None or row.status != "ACTIVE" or expiry <= datetime.now(UTC):
            raise DemoQuotaDenied("C24_SESSION_INVALID")
        entries = db.scalars(select(DemoProviderUsageV2).where(
            DemoProviderUsageV2.tenant_id == tenant_id,
            DemoProviderUsageV2.demo_session_id == session_id,
        )).all()
        if any(entry.request_id == request_id for entry in entries):
            raise DemoQuotaDenied("C24_DUPLICATE_REQUEST")
        # Failed/unknown calls keep their full reservation; successful calls use the
        # greater of reserved and reported usage, so a bad estimate never refunds capacity.
        used_calls = sum(max(e.reserved_calls, e.actual_calls or 0) for e in entries)
        used_input = sum(max(e.reserved_input_tokens, e.actual_input_tokens or 0) for e in entries)
        used_output = sum(
            max(e.reserved_output_tokens, e.actual_output_tokens or 0) for e in entries
        )
        used_cost = sum((max(Decimal(e.reserved_cost_usd), Decimal(e.actual_cost_usd or 0))
                         for e in entries), Decimal(0))
        if (used_calls + calls > limits.max_calls
                or used_input + input_tokens > limits.max_input_tokens
                or used_output + output_tokens > limits.max_output_tokens
                or used_cost + estimated_cost > limits.max_cost_usd):
            raise DemoQuotaDenied("C24_QUOTA_EXCEEDED")
        entry = DemoProviderUsageV2(
            tenant_id=tenant_id, demo_session_id=session_id,
            request_id=request_id, model=model, status="RESERVED",
            reserved_calls=calls, reserved_input_tokens=input_tokens,
            reserved_output_tokens=output_tokens, reserved_cost_usd=estimated_cost,
        )
        db.add(entry)
        db.commit()
        return entry.id


def settle(
    factory: sessionmaker, *, reservation_id: UUID, limits: QuotaLimits,
    receipt=None,
) -> None:
    with factory() as db:
        entry = db.scalar(select(DemoProviderUsageV2).where(
            DemoProviderUsageV2.id == reservation_id,
        ).with_for_update())
        if entry is None or entry.status != "RESERVED":
            raise DemoQuotaDenied("C24_RESERVATION_INVALID")
        if receipt is None:
            entry.status = "FAILED"  # Unknown provider billing: full reserve remains charged.
        else:
            try:
                actual_calls = int(receipt.attempts)
                actual_input = int(receipt.usage.input_tokens)
                actual_output = int(receipt.usage.output_tokens)
                valid_model = receipt.model == entry.model
            except (AttributeError, TypeError, ValueError):
                valid_model = False
            if (not valid_model or min(actual_calls, actual_input, actual_output) < 0
                    or actual_calls == 0):
                entry.status = "FAILED"
                entry.settled_at = datetime.now(UTC)
                db.commit()
                raise DemoQuotaDenied("C24_RECEIPT_INVALID")
            entry.actual_calls = actual_calls
            entry.actual_input_tokens = actual_input
            entry.actual_output_tokens = actual_output
            entry.actual_cost_usd = limits.cost(actual_input, actual_output)
            entry.status = ("OVERRUN" if actual_calls > entry.reserved_calls
                            or actual_input > entry.reserved_input_tokens
                            or actual_output > entry.reserved_output_tokens
                            or Decimal(entry.actual_cost_usd) > Decimal(entry.reserved_cost_usd)
                            else "SETTLED")
        entry.settled_at = datetime.now(UTC)
        db.commit()
        if entry.status == "OVERRUN":
            raise DemoQuotaDenied("C24_RESERVATION_OVERRUN")


def call_with_demo_quota(
    provider_call: Callable[[], T], *, factory: sessionmaker,
    tenant_id: UUID, session_id: UUID, request_id: str, model: str,
    calls: int, input_tokens: int, output_tokens: int, limits: QuotaLimits,
) -> T:
    reservation_id = reserve(
        factory, tenant_id=tenant_id, session_id=session_id,
        request_id=request_id, model=model, calls=calls,
        input_tokens=input_tokens, output_tokens=output_tokens, limits=limits,
    )
    try:
        result = provider_call()
    except BaseException:
        settle(factory, reservation_id=reservation_id, limits=limits)
        raise
    settle(factory, reservation_id=reservation_id, limits=limits,
           receipt=getattr(result, "receipt", None))
    return result
