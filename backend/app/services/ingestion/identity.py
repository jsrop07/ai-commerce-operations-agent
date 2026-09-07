"""Source and business identity boundaries for ingestion."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class SourceIdentity:
    """Identity of one transport/source record."""

    tenant_id: str
    provider: str
    resource: str
    source_mode: str
    source_record_id: str
    schema_version: str

    def key(self) -> str:
        return _stable_key(
            {
                "tenant_id": self.tenant_id,
                "provider": self.provider,
                "resource": self.resource,
                "source_mode": self.source_mode,
                "source_record_id": self.source_record_id,
                "schema_version": self.schema_version,
            }
        )


@dataclass(frozen=True)
class BusinessIdentity:
    """Source-mode-independent identity of one business fact."""

    tenant_id: str
    provider: str
    provider_account_ref: str
    resource: str
    external_fact_id: str
    line_id: str
    sku_id: str
    occurred_at: datetime
    schema_version: str

    def key(self) -> str:
        return _stable_key(
            {
                "tenant_id": self.tenant_id,
                "provider": self.provider,
                "provider_account_ref": self.provider_account_ref,
                "resource": self.resource,
                "external_fact_id": self.external_fact_id,
                "line_id": self.line_id,
                "sku_id": self.sku_id,
                "occurred_at": self.occurred_at.astimezone(UTC).isoformat(),
                "schema_version": self.schema_version,
            }
        )


@dataclass(frozen=True)
class BusinessIdentityResult:
    status: str
    identity: BusinessIdentity | None
    reason: str | None = None


def build_toss_sale_business_identity(
    *,
    tenant_id: str,
    provider_account_ref: str,
    order_id: str | None,
    line_id: str | None,
    sku_id: str | None,
    occurred_at: datetime | None,
    schema_version: str,
) -> BusinessIdentityResult:
    missing: list[str] = []

    if not tenant_id:
        missing.append("tenant_id")
    if not provider_account_ref:
        missing.append("provider_account_ref")
    if not order_id:
        missing.append("order_id")
    if not line_id:
        missing.append("line_id")
    if not sku_id:
        missing.append("sku_id")
    if occurred_at is None:
        missing.append("occurred_at")
    elif occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
        return BusinessIdentityResult(
            status="QUARANTINED",
            identity=None,
            reason="TIMEZONE_REQUIRED",
        )
    if not schema_version:
        missing.append("schema_version")

    if missing:
        return BusinessIdentityResult(
            status="QUARANTINED",
            identity=None,
            reason=f"MISSING_BUSINESS_IDENTITY_FIELDS:{','.join(sorted(missing))}",
        )

    return BusinessIdentityResult(
        status="RESOLVED",
        identity=BusinessIdentity(
            tenant_id=tenant_id,
            provider="TOSS_POS",
            provider_account_ref=provider_account_ref,
            resource="offline_sale",
            external_fact_id=order_id,
            line_id=line_id,
            sku_id=sku_id,
            occurred_at=occurred_at,
            schema_version=schema_version,
        ),
    )


def _stable_key(parts: dict[str, str]) -> str:
    canonical = json.dumps(
        parts,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
