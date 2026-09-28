"""Synthetic physical-warehouse deduplication boundary tests."""

from datetime import UTC, datetime

from backend.app.services.inventory_projection import (
    InventorySelectionStatus,
    InventorySnapshotCandidate,
    select_inventory_snapshot_candidates,
)

AS_OF_09 = datetime(2026, 9, 23, 9, 0, tzinfo=UTC)
AS_OF_10 = datetime(2026, 9, 23, 10, 0, tzinfo=UTC)


def candidate(
    *,
    tenant_id: str = "tenant-synthetic",
    provider: str = "CAFE24",
    sku_id: str = "sku-synthetic",
    warehouse_key: str | None = "DEMO_PHYSICAL_WH_001",
    on_hand: int | None = 8,
    as_of: datetime = AS_OF_09,
    quality_status: str = "CONFIRMED",
    usable: bool = True,
    authoritative: bool = False,
) -> InventorySnapshotCandidate:
    return InventorySnapshotCandidate(
        tenant_id=tenant_id,
        provider=provider,
        sku_id=sku_id,
        canonical_warehouse_key=warehouse_key,
        on_hand=on_hand,
        reserved=0,
        as_of=as_of,
        quality_status=quality_status,
        usable=usable,
        authoritative=authoritative,
    )


def test_same_physical_warehouse_sources_are_not_summed() -> None:
    result = select_inventory_snapshot_candidates(
        (
            candidate(provider="CAFE24", on_hand=8),
            candidate(provider="ECOUNT", on_hand=8),
        )
    )

    assert len(result) == 1
    assert result[0].status == InventorySelectionStatus.SELECTED
    assert result[0].on_hand == 8
    assert result[0].on_hand != 16


def test_latest_usable_snapshot_is_selected() -> None:
    result = select_inventory_snapshot_candidates(
        (
            candidate(provider="CAFE24", on_hand=8, as_of=AS_OF_09),
            candidate(provider="CAFE24", on_hand=7, as_of=AS_OF_10),
        )
    )

    assert result[0].status == InventorySelectionStatus.SELECTED
    assert result[0].on_hand == 7


def test_provider_difference_does_not_make_same_warehouse_additive() -> None:
    result = select_inventory_snapshot_candidates(
        (
            candidate(provider="CAFE24", on_hand=8, as_of=AS_OF_09),
            candidate(provider="ECOUNT", on_hand=7, as_of=AS_OF_10),
        )
    )

    assert result[0].status == InventorySelectionStatus.SELECTED
    assert result[0].on_hand == 7


def test_different_canonical_warehouses_remain_separate_groups() -> None:
    result = select_inventory_snapshot_candidates(
        (
            candidate(warehouse_key="DEMO_PHYSICAL_WH_001", on_hand=8),
            candidate(warehouse_key="DEMO_PHYSICAL_WH_002", on_hand=8),
        )
    )

    assert len(result) == 2
    assert {item.on_hand for item in result} == {8}


def test_missing_mapping_is_unresolved_without_quantity() -> None:
    result = select_inventory_snapshot_candidates(
        (candidate(warehouse_key=None, on_hand=8),)
    )

    assert result[0].status == InventorySelectionStatus.UNRESOLVED
    assert result[0].on_hand is None


def test_tied_authoritative_sources_are_ambiguous() -> None:
    result = select_inventory_snapshot_candidates(
        (
            candidate(provider="CAFE24", authoritative=True),
            candidate(provider="ECOUNT", on_hand=7, authoritative=True),
        )
    )

    assert result[0].status == InventorySelectionStatus.AMBIGUOUS
    assert result[0].selected is None


def test_null_or_unknown_source_is_not_zero() -> None:
    result = select_inventory_snapshot_candidates(
        (
            candidate(on_hand=None),
            candidate(
                provider="ECOUNT",
                on_hand=8,
                quality_status="UNKNOWN",
                usable=False,
            ),
        )
    )

    assert result[0].status == InventorySelectionStatus.UNKNOWN
    assert result[0].on_hand is None


def test_tenant_boundary_is_preserved() -> None:
    result = select_inventory_snapshot_candidates(
        (
            candidate(tenant_id="tenant-a", on_hand=8),
            candidate(tenant_id="tenant-b", on_hand=8),
        )
    )

    assert len(result) == 2
    assert {
        (item.tenant_id, item.on_hand)
        for item in result
    } == {("tenant-a", 8), ("tenant-b", 8)}


def test_candidate_as_of_requires_timezone() -> None:
    result = candidate(as_of=datetime(2026, 9, 23, 10, 0))

    try:
        select_inventory_snapshot_candidates((result,))
    except ValueError as exc:
        assert str(exc) == "as_of must include timezone"
    else:
        raise AssertionError("naive snapshot timestamp must be rejected")
