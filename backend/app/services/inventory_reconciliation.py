"""Inventory reconciliation between expected and observed stock."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReconciliationResult:
    status: str
    expected_inventory: int | None
    observed_on_hand: int | None
    difference: int | None
    tolerance: int
    actionable: bool
    reason: str


def reconcile_inventory(
    *,
    expected_inventory: int | None,
    observed_on_hand: int | None,
    tolerance: int,
    expected_confirmed: bool,
    observed_quality_status: str,
    observed_is_stale: bool,
) -> ReconciliationResult:
    if tolerance < 0:
        raise ValueError("tolerance must be >= 0")

    if expected_inventory is None:
        return ReconciliationResult(
            status="UNKNOWN",
            expected_inventory=None,
            observed_on_hand=observed_on_hand,
            difference=None,
            tolerance=tolerance,
            actionable=False,
            reason="EXPECTED_INVENTORY_UNKNOWN",
        )

    if observed_on_hand is None:
        return ReconciliationResult(
            status="UNKNOWN",
            expected_inventory=expected_inventory,
            observed_on_hand=None,
            difference=None,
            tolerance=tolerance,
            actionable=False,
            reason="OBSERVED_ON_HAND_UNKNOWN",
        )

    difference = observed_on_hand - expected_inventory

    if not expected_confirmed:
        return ReconciliationResult(
            status="UNCONFIRMED",
            expected_inventory=expected_inventory,
            observed_on_hand=observed_on_hand,
            difference=difference,
            tolerance=tolerance,
            actionable=False,
            reason="EXPECTED_NOT_CONFIRMED",
        )

    if observed_quality_status != "CONFIRMED":
        return ReconciliationResult(
            status="UNCONFIRMED",
            expected_inventory=expected_inventory,
            observed_on_hand=observed_on_hand,
            difference=difference,
            tolerance=tolerance,
            actionable=False,
            reason="OBSERVED_QUALITY_NOT_CONFIRMED",
        )

    if observed_is_stale:
        return ReconciliationResult(
            status="STALE",
            expected_inventory=expected_inventory,
            observed_on_hand=observed_on_hand,
            difference=difference,
            tolerance=tolerance,
            actionable=False,
            reason="OBSERVED_STALE",
        )

    if abs(difference) <= tolerance:
        return ReconciliationResult(
            status="MATCHED",
            expected_inventory=expected_inventory,
            observed_on_hand=observed_on_hand,
            difference=difference,
            tolerance=tolerance,
            actionable=False,
            reason="WITHIN_TOLERANCE",
        )

    return ReconciliationResult(
        status="DISCREPANCY",
        expected_inventory=expected_inventory,
        observed_on_hand=observed_on_hand,
        difference=difference,
        tolerance=tolerance,
        actionable=True,
        reason="OUTSIDE_TOLERANCE",
    )
