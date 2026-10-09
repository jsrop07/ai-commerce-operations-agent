"""Opaque Demo cookie issuance and V2-backed ownership resolution."""

from __future__ import annotations

import re
import secrets
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models_v2.ai import DemoSessionV2

COOKIE_NAME = "demo_session"
_TOKEN = re.compile(r"^[A-Za-z0-9_-]{43}$")


def resolve_demo_session(
    db: Session, *, tenant_id: UUID, token: str | None, now: datetime | None = None,
    touch: bool = False,
) -> DemoSessionV2 | None:
    if token is None or not _TOKEN.fullmatch(token):
        return None
    now = now or datetime.now(UTC)
    row = db.scalar(select(DemoSessionV2).where(
        DemoSessionV2.tenant_id == tenant_id,
        DemoSessionV2.token_hash == sha256(token.encode("ascii")).hexdigest(),
        DemoSessionV2.status == "ACTIVE",
        DemoSessionV2.expires_at > now,
    ))
    if row is not None and touch:
        row.last_request_at = now
        db.commit()
    return row


def issue_demo_session(
    db: Session, *, tenant_id: UUID, ttl_seconds: int, now: datetime | None = None,
) -> tuple[DemoSessionV2, str]:
    if ttl_seconds < 1:
        raise ValueError("Demo Session TTL must be positive")
    now = now or datetime.now(UTC)
    token = secrets.token_urlsafe(32)
    row = DemoSessionV2(
        tenant_id=tenant_id,
        actor_id=f"demo:{secrets.token_hex(16)}",
        token_hash=sha256(token.encode("ascii")).hexdigest(),
        created_at=now,
        expires_at=now + timedelta(seconds=ttl_seconds),
        status="ACTIVE",
        last_request_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row, token
