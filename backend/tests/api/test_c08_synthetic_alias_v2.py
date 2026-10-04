"""C08 alias contract is deterministic and isolated from Actual V2."""

from dataclasses import replace
from uuid import UUID, uuid4

import pytest

from backend.app.models_v2.tenant import TenantV2
from backend.app.services.c08_synthetic_alias_v2 import (
    GOLDEN_GRAPH_SHA256,
    MAPPING_VERSION,
    SNAPSHOT_ID,
    SNAPSHOT_SHA256,
    SyntheticAliasBoundaryError,
    alias_uuid,
    build_alias_mapping,
    resolve_existing_alias,
)


def demo_tenant():
    return TenantV2(
        id=UUID("00000000-0000-0000-0000-000000000008"),
        name="c08_synthetic",
        environment="DEMO",
        status="ACTIVE",
    )


def mapping(aliases):
    return build_alias_mapping(
        tenant=demo_tenant(),
        actual_tenant_id=uuid4(),
        demo_database_identity="isolated-c08-demo-db",
        actual_database_identity="actual-v2-db",
        aliases=aliases,
    )


def test_mapping_is_order_independent_versioned_and_pinned_to_unchanged_c08_inputs():
    aliases = [
        ("PRODUCT", "product_demo_001"),
        ("INCOMING", "incoming_demo_001"),
        ("TASK", "task_demo_001"),
    ]
    first = mapping(aliases)
    second = mapping(list(reversed(aliases)))
    assert first == second
    assert first.mapping_version == MAPPING_VERSION == "c08-v2-alias-v1"
    assert len(first.mapping_hash) == 64
    assert first.mapping_hash == second.mapping_hash
    assert first.entries[0][2] == alias_uuid(first.tenant_id, *first.entries[0][:2])
    assert SNAPSHOT_ID == "c08-r08-synthetic-v1"
    assert SNAPSHOT_SHA256 == "aefc694a5c3364752934f2a33616500b464f3e1e21a27413b6f7420a56b45d40"
    assert GOLDEN_GRAPH_SHA256 == "3e42a5f5f2d5e8074932320ee2dc24c7b11ae6a19a923f9078555dad7a6466c5"


@pytest.mark.parametrize("change", ["same_tenant", "same_database", "non_demo"])
def test_actual_boundary_is_rejected(change):
    tenant = demo_tenant()
    if change == "non_demo":
        tenant.environment = "LOCAL"
    kwargs = {
        "tenant": tenant,
        "actual_tenant_id": tenant.id if change == "same_tenant" else uuid4(),
        "demo_database_identity": "db",
        "actual_database_identity": "db" if change == "same_database" else "other",
        "aliases": [("PRODUCT", "product_demo_001")],
    }
    with pytest.raises(SyntheticAliasBoundaryError):
        build_alias_mapping(**kwargs)


def test_mapping_requires_materialized_same_tenant_row_and_never_falls_through():
    current = mapping([("PRODUCT", "product_demo_001")])

    class EmptySession:
        def scalar(self, _statement):
            return None

    with pytest.raises(SyntheticAliasBoundaryError, match="SYNTHETIC_TARGET_NOT_MATERIALIZED"):
        resolve_existing_alias(
            EmptySession(), mapping=current, entity_kind="PRODUCT", alias="product_demo_001"
        )
    with pytest.raises(SyntheticAliasBoundaryError, match="ALIAS_NOT_IN_MAPPING"):
        resolve_existing_alias(
            EmptySession(), mapping=current, entity_kind="PRODUCT", alias="product_demo_002"
        )


def test_bad_alias_and_duplicates_fail_closed():
    with pytest.raises(SyntheticAliasBoundaryError):
        alias_uuid(demo_tenant().id, "ORDER", "order_demo_001")
    with pytest.raises(SyntheticAliasBoundaryError):
        mapping([("PRODUCT", "product_demo_001"), ("PRODUCT", "product_demo_001")])


@pytest.mark.parametrize("field", ["mapping_version", "mapping_hash", "tenant_id"])
def test_mapping_metadata_tampering_fails_before_lookup(field):
    current = mapping([("PRODUCT", "product_demo_001")])
    replacement = uuid4() if field == "tenant_id" else "altered"
    tampered = replace(current, **{field: replacement})

    class UnusedSession:
        def scalar(self, _statement):
            pytest.fail("untrusted mapping must be rejected before a database query")

    with pytest.raises(SyntheticAliasBoundaryError, match="SYNTHETIC_MAPPING_INTEGRITY_ERROR"):
        resolve_existing_alias(
            UnusedSession(), mapping=tampered, entity_kind="PRODUCT", alias="product_demo_001"
        )
