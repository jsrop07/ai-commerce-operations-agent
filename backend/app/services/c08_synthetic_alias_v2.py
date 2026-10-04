"""C08 synthetic aliases to V2 UUIDs; contract only, with no materialization."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from uuid import UUID, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models_v2.catalog import ProductV2
from backend.app.models_v2.operations import (
    IncomingShipmentV2,
    LaunchScheduleV2,
    ReservationV2,
    TaskV2,
)
from backend.app.models_v2.tenant import TenantV2

SNAPSHOT_ID = "c08-r08-synthetic-v1"
SNAPSHOT_SHA256 = "aefc694a5c3364752934f2a33616500b464f3e1e21a27413b6f7420a56b45d40"
GOLDEN_GRAPH_SHA256 = "3e42a5f5f2d5e8074932320ee2dc24c7b11ae6a19a923f9078555dad7a6466c5"
MAPPING_VERSION = "c08-v2-alias-v1"
_NAMESPACE = UUID("63fd4fbb-cd84-5d72-8ac0-d8de5282e8a9")
_ALIAS = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_MODELS = {
    "PRODUCT": ProductV2,
    "INCOMING": IncomingShipmentV2,
    "TASK": TaskV2,
    "RESERVATION": ReservationV2,
    "LAUNCH": LaunchScheduleV2,
}


class SyntheticAliasBoundaryError(Exception):
    pass


@dataclass(frozen=True)
class AliasMapping:
    mapping_version: str
    mapping_hash: str
    tenant_id: UUID
    entries: tuple[tuple[str, str, UUID], ...]


def _mapping_hash(tenant_id: UUID, entries: tuple[tuple[str, str, UUID], ...]) -> str:
    payload = {
        "mapping_version": MAPPING_VERSION,
        "snapshot_id": SNAPSHOT_ID,
        "snapshot_sha256": SNAPSHOT_SHA256,
        "golden_graph_sha256": GOLDEN_GRAPH_SHA256,
        "tenant_id": str(tenant_id),
        "entries": [(kind, alias, str(value)) for kind, alias, value in entries],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def require_isolated_demo_boundary(
    *,
    tenant: TenantV2,
    actual_tenant_id: UUID,
    demo_database_identity: str,
    actual_database_identity: str,
) -> None:
    """Database identities must come from trusted connection configuration, never a request."""
    if (
        tenant.environment != "DEMO"
        or tenant.id == actual_tenant_id
        or not demo_database_identity
        or demo_database_identity == actual_database_identity
    ):
        raise SyntheticAliasBoundaryError("ISOLATED_SYNTHETIC_TENANT_REQUIRED")


def alias_uuid(tenant_id: UUID, entity_kind: str, alias: str) -> UUID:
    if entity_kind not in _MODELS or not _ALIAS.fullmatch(alias):
        raise SyntheticAliasBoundaryError("INVALID_SYNTHETIC_ALIAS")
    return uuid5(
        _NAMESPACE, f"{MAPPING_VERSION}:{SNAPSHOT_SHA256}:{tenant_id}:{entity_kind}:{alias}"
    )


def build_alias_mapping(
    *,
    tenant: TenantV2,
    actual_tenant_id: UUID,
    demo_database_identity: str,
    actual_database_identity: str,
    aliases: list[tuple[str, str]],
) -> AliasMapping:
    require_isolated_demo_boundary(
        tenant=tenant,
        actual_tenant_id=actual_tenant_id,
        demo_database_identity=demo_database_identity,
        actual_database_identity=actual_database_identity,
    )
    if len(set(aliases)) != len(aliases):
        raise SyntheticAliasBoundaryError("DUPLICATE_SYNTHETIC_ALIAS")
    entries = tuple(
        (kind, alias, alias_uuid(tenant.id, kind, alias)) for kind, alias in sorted(aliases)
    )
    return AliasMapping(MAPPING_VERSION, _mapping_hash(tenant.id, entries), tenant.id, entries)


def resolve_existing_alias(
    session: Session, *, mapping: AliasMapping, entity_kind: str, alias: str
) -> UUID:
    """Return only a materialized same-tenant row; never fall through to Actual V2 data."""
    if mapping.mapping_version != MAPPING_VERSION or mapping.mapping_hash != _mapping_hash(
        mapping.tenant_id, mapping.entries
    ):
        raise SyntheticAliasBoundaryError("SYNTHETIC_MAPPING_INTEGRITY_ERROR")
    expected = alias_uuid(mapping.tenant_id, entity_kind, alias)
    if (entity_kind, alias, expected) not in mapping.entries:
        raise SyntheticAliasBoundaryError("ALIAS_NOT_IN_MAPPING")
    model = _MODELS[entity_kind]
    row_id = session.scalar(
        select(model.id).where(
            model.tenant_id == mapping.tenant_id,
            model.id == expected,
        )
    )
    if row_id is None:
        raise SyntheticAliasBoundaryError("SYNTHETIC_TARGET_NOT_MATERIALIZED")
    return row_id
