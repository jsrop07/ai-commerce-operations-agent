"""Sync schedule policy.

Production scheduling remains disabled until explicitly approved.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SyncSchedulePolicy:
    enabled: bool
    reason: str


PRODUCTION_SYNC_SCHEDULE = SyncSchedulePolicy(
    enabled=False,
    reason="PRODUCTION_SCHEDULE_DISABLED_UNTIL_APPROVAL",
)
