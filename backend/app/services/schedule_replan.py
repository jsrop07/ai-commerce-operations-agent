"""D10-BE-04 일정 재계획 Proposal과 before/after diff."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
import json
from typing import Iterable

from backend.app.services.delay_impact import (
    DelayImpactResult,
    ImpactPathItem,
)


class ReplanStatus(StrEnum):
    """일정 재계획 Proposal 상태."""

    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EDITED = "EDITED"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True)
class ScheduleItem:
    """재계획 대상이 되는 현재 일정 Projection."""

    item_type: str
    item_id: str
    scheduled_at: datetime


@dataclass(frozen=True)
class ScheduleDiffItem:
    """원본 일정과 제안 일정의 차이."""

    item_type: str
    item_id: str
    before: datetime
    proposed_after: datetime
    reason: str


@dataclass(frozen=True)
class ReplanProposal:
    """승인 전에는 원본을 변경하지 않는 일정 변경 제안."""

    proposal_id: str
    status: ReplanStatus
    created_at: datetime

    source_incoming_id: str
    reason: str
    confidence: float

    before_schedule: tuple[ScheduleItem, ...]
    proposed_schedule: tuple[ScheduleItem, ...]
    diff: tuple[ScheduleDiffItem, ...]

    downstream_impact: tuple[str, ...]
    evidence_ids: tuple[str, ...]

    external_execution_allowed: bool = False


def _canonical_schedule(
    schedule: Iterable[ScheduleItem],
) -> tuple[ScheduleItem, ...]:
    """재현 가능한 순서로 일정 Projection을 고정한다."""

    return tuple(
        sorted(
            schedule,
            key=lambda item: (
                item.item_type,
                item.item_id,
                item.scheduled_at.isoformat(),
            ),
        )
    )


def _proposal_identity_payload(
    *,
    source_incoming_id: str,
    before_schedule: tuple[ScheduleItem, ...],
    proposed_schedule: tuple[ScheduleItem, ...],
    evidence_ids: tuple[str, ...],
) -> str:
    """동일 입력 재시도 시 동일 proposal_id를 만들기 위한 payload."""

    payload = {
        "source_incoming_id": source_incoming_id,
        "before_schedule": [
            {
                "item_type": item.item_type,
                "item_id": item.item_id,
                "scheduled_at": item.scheduled_at.isoformat(),
            }
            for item in before_schedule
        ],
        "proposed_schedule": [
            {
                "item_type": item.item_type,
                "item_id": item.item_id,
                "scheduled_at": item.scheduled_at.isoformat(),
            }
            for item in proposed_schedule
        ],
        "evidence_ids": list(evidence_ids),
    }

    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _build_proposal_id(
    *,
    source_incoming_id: str,
    before_schedule: tuple[ScheduleItem, ...],
    proposed_schedule: tuple[ScheduleItem, ...],
    evidence_ids: tuple[str, ...],
) -> str:
    """Proposal identity를 결정론적으로 생성한다."""

    payload = _proposal_identity_payload(
        source_incoming_id=source_incoming_id,
        before_schedule=before_schedule,
        proposed_schedule=proposed_schedule,
        evidence_ids=evidence_ids,
    )

    digest = sha256(payload.encode("utf-8")).hexdigest()[:20]

    return f"replan-{digest}"


def _impact_by_target(
    impact_path: Iterable[ImpactPathItem],
) -> dict[tuple[str, str], ImpactPathItem]:
    return {
        (item.target_type, item.target_id): item
        for item in impact_path
        if item.after is not None
    }


def build_replan_proposal(
    *,
    current_schedule: Iterable[ScheduleItem],
    impact: DelayImpactResult,
    created_at: datetime,
    confidence: float,
) -> ReplanProposal:
    """
    DelayImpact를 기반으로 일정 변경 Proposal을 만든다.

    원본 current_schedule 객체는 절대 변경하지 않는다.
    """

    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise ValueError("created_at must be timezone-aware")

    if not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be between 0.0 and 1.0")

    before_schedule = _canonical_schedule(current_schedule)

    impact_map = _impact_by_target(impact.impact_path)

    proposed_items: list[ScheduleItem] = []
    diff_items: list[ScheduleDiffItem] = []

    for original in before_schedule:
        impact_item = impact_map.get(
            (original.item_type, original.item_id)
        )

        if impact_item is None or impact_item.after is None:
            proposed_items.append(original)
            continue

        proposed = ScheduleItem(
            item_type=original.item_type,
            item_id=original.item_id,
            scheduled_at=impact_item.after,
        )

        proposed_items.append(proposed)

        if proposed.scheduled_at != original.scheduled_at:
            diff_items.append(
                ScheduleDiffItem(
                    item_type=original.item_type,
                    item_id=original.item_id,
                    before=original.scheduled_at,
                    proposed_after=proposed.scheduled_at,
                    reason=impact_item.reason,
                )
            )

    proposed_schedule = _canonical_schedule(proposed_items)

    evidence_ids = tuple(sorted(set(impact.evidence_ids)))

    proposal_id = _build_proposal_id(
        source_incoming_id=impact.incoming_id,
        before_schedule=before_schedule,
        proposed_schedule=proposed_schedule,
        evidence_ids=evidence_ids,
    )

    downstream_impact = tuple(
        sorted(
            {
                *impact.impacted_task_ids,
                *impact.impacted_reservation_ids,
                *impact.impacted_launch_event_ids,
            }
        )
    )

    return ReplanProposal(
        proposal_id=proposal_id,
        status=ReplanStatus.PROPOSED,
        created_at=created_at,
        source_incoming_id=impact.incoming_id,
        reason=impact.reason,
        confidence=confidence,
        before_schedule=before_schedule,
        proposed_schedule=proposed_schedule,
        diff=tuple(diff_items),
        downstream_impact=downstream_impact,
        evidence_ids=evidence_ids,
        external_execution_allowed=False,
    )


def decide_replan_proposal(
    proposal: ReplanProposal,
    decision: ReplanStatus,
) -> ReplanProposal:
    """
    Proposal 상태만 변경한다.

    Day10에서는 APPROVED도 외부 Calendar/Cafe24/eCount/Gmail
    또는 원본 일정에 자동 적용하지 않는다.
    """

    allowed = {
        ReplanStatus.APPROVED,
        ReplanStatus.REJECTED,
        ReplanStatus.EDITED,
        ReplanStatus.EXPIRED,
    }

    if decision not in allowed:
        raise ValueError("invalid replan decision")

    return replace(
        proposal,
        status=decision,
        external_execution_allowed=False,
    )