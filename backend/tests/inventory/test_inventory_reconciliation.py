from backend.app.services.inventory_reconciliation import (
    reconcile_inventory,
)


def test_matching_inventory_within_tolerance() -> None:
    result = reconcile_inventory(
        expected_inventory=10,
        observed_on_hand=11,
        tolerance=1,
        expected_confirmed=True,
        observed_quality_status="CONFIRMED",
        observed_is_stale=False,
    )

    assert result.status == "MATCHED"
    assert result.difference == 1
    assert result.actionable is False


def test_difference_outside_tolerance_is_discrepancy() -> None:
    result = reconcile_inventory(
        expected_inventory=10,
        observed_on_hand=13,
        tolerance=1,
        expected_confirmed=True,
        observed_quality_status="CONFIRMED",
        observed_is_stale=False,
    )

    assert result.status == "DISCREPANCY"
    assert result.difference == 3
    assert result.actionable is True
    assert result.reason == "OUTSIDE_TOLERANCE"


def test_unknown_expected_inventory_is_not_zero() -> None:
    result = reconcile_inventory(
        expected_inventory=None,
        observed_on_hand=10,
        tolerance=1,
        expected_confirmed=False,
        observed_quality_status="CONFIRMED",
        observed_is_stale=False,
    )

    assert result.status == "UNKNOWN"
    assert result.difference is None
    assert result.actionable is False
    assert result.reason == "EXPECTED_INVENTORY_UNKNOWN"


def test_stale_observation_is_not_actionable_discrepancy() -> None:
    result = reconcile_inventory(
        expected_inventory=10,
        observed_on_hand=15,
        tolerance=1,
        expected_confirmed=True,
        observed_quality_status="CONFIRMED",
        observed_is_stale=True,
    )

    assert result.status == "STALE"
    assert result.difference == 5
    assert result.actionable is False


def test_blocked_source_quality_is_not_actionable() -> None:
    result = reconcile_inventory(
        expected_inventory=10,
        observed_on_hand=15,
        tolerance=1,
        expected_confirmed=True,
        observed_quality_status="SOURCE_QUALITY_BLOCKED",
        observed_is_stale=False,
    )

    assert result.status == "UNCONFIRMED"
    assert result.actionable is False
    assert result.reason == "OBSERVED_QUALITY_NOT_CONFIRMED"


def test_unconfirmed_expected_projection_is_not_actionable() -> None:
    result = reconcile_inventory(
        expected_inventory=10,
        observed_on_hand=15,
        tolerance=1,
        expected_confirmed=False,
        observed_quality_status="CONFIRMED",
        observed_is_stale=False,
    )

    assert result.status == "UNCONFIRMED"
    assert result.actionable is False
    assert result.reason == "EXPECTED_NOT_CONFIRMED"
