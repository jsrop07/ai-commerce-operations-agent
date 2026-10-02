"""D10-BE-03 입고 지연의 일정·Task·예약주문 영향 계산."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Iterable


class SourceClassification(StrEnum):
    """일정 계산에 사용한 Source의 실제 검증 수준."""

    LIVE_READ = "LIVE_READ"
    FILE_IMPORT = "FILE_IMPORT"
    SANITIZED_REAL = "SANITIZED_REAL"
    FIXTURE = "FIXTURE"
    CONTRACT_ONLY = "CONTRACT_ONLY"
    SOURCE_QUALITY_BLOCKED = "SOURCE_QUALITY_BLOCKED"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


class FreshnessStatus(StrEnum):
    FRESH = "FRESH"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class SourceQuality(StrEnum):
    CONFIRMED = "CONFIRMED"
    TENTATIVE = "TENTATIVE"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


class ImpactStatus(StrEnum):
    CALCULATED = "CALCULATED"
    CONTRACT_ONLY = "CONTRACT_ONLY"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class IncomingDateEvidence:
    """입고예정일의 출처와 신뢰 경계."""

    source_id: str
    source_classification: SourceClassification
    as_of: datetime | None
    freshness: FreshnessStatus
    quality: SourceQuality
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class IncomingDateChange:
    """입고예정일 before/after."""

    incoming_id: str
    before_expected_at: datetime | None
    after_expected_at: datetime | None
    evidence: IncomingDateEvidence


@dataclass(frozen=True)
class ScheduledTask:
    """지연 영향을 계산하기 위한 최소 Task Projection."""

    task_id: str
    deadline: datetime
    depends_on_incoming: bool
    lag_hours: int = 0
    incoming_id: str | None = None


@dataclass(frozen=True)
class ReservationImpactCandidate:
    """입고와 연결된 예약주문 최소 Projection."""

    reservation_id: str
    incoming_id: str


@dataclass(frozen=True)
class LaunchImpactCandidate:
    """입고와 연결된 출시 일정 최소 Projection."""

    launch_event_id: str
    launch_at: datetime
    depends_on_incoming: bool
    incoming_id: str | None = None


@dataclass(frozen=True)
class ImpactPathItem:
    """지연이 전달되는 한 단계의 근거."""

    target_type: str
    target_id: str
    source_id: str
    before: datetime | None
    after: datetime | None
    lag_hours: int
    reason: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class DelayImpactResult:
    """입고 지연 영향 계산 결과."""

    status: ImpactStatus
    actual_delay_confirmed: bool
    incoming_id: str
    delay_hours: int | None

    source_id: str
    source_classification: SourceClassification
    as_of: datetime | None
    freshness: FreshnessStatus
    quality: SourceQuality
    evidence_ids: tuple[str, ...]

    impacted_task_ids: tuple[str, ...]
    impacted_reservation_ids: tuple[str, ...]
    impacted_launch_event_ids: tuple[str, ...]
    critical_path: tuple[str, ...]
    impact_path: tuple[ImpactPathItem, ...]
    reason: str


def _is_actual_confirmable(
    evidence: IncomingDateEvidence,
) -> bool:
    """실제 확정 일정으로 취급 가능한 Source인지 판정한다."""

    return (
        evidence.source_classification
        in {
            SourceClassification.LIVE_READ,
            SourceClassification.FILE_IMPORT,
            SourceClassification.SANITIZED_REAL,
        }
        and evidence.quality == SourceQuality.CONFIRMED
        and evidence.as_of is not None
        and evidence.freshness == FreshnessStatus.FRESH
        and bool(evidence.evidence_ids)
    )


def _blocked_result(
    change: IncomingDateChange,
    reason: str,
) -> DelayImpactResult:
    """날짜를 추정하지 않고 차단 상태를 그대로 반환한다."""

    evidence = change.evidence

    return DelayImpactResult(
        status=ImpactStatus.BLOCKED,
        actual_delay_confirmed=False,
        incoming_id=change.incoming_id,
        delay_hours=None,
        source_id=evidence.source_id,
        source_classification=evidence.source_classification,
        as_of=evidence.as_of,
        freshness=evidence.freshness,
        quality=evidence.quality,
        evidence_ids=evidence.evidence_ids,
        impacted_task_ids=(),
        impacted_reservation_ids=(),
        impacted_launch_event_ids=(),
        critical_path=(),
        impact_path=(),
        reason=reason,
    )


def calculate_delay_impact(
    *,
    change: IncomingDateChange,
    tasks: Iterable[ScheduledTask],
    reservations: Iterable[ReservationImpactCandidate],
    launch_events: Iterable[LaunchImpactCandidate],
) -> DelayImpactResult:
    """
    입고예정일 변경이 후속 Task/예약/출시에 미치는 영향을 계산한다.

    Fixture는 기능 검증에 사용할 수 있지만 actual 확정으로 승격하지 않는다.
    null/UNKNOWN/BLOCKED 날짜는 임의의 날짜로 대체하지 않는다.
    """

    before = change.before_expected_at
    after = change.after_expected_at
    evidence = change.evidence

    if before is None or after is None:
        return _blocked_result(
            change,
            "입고예정일 before/after가 없어 지연을 확정할 수 없습니다.",
        )

    if before.tzinfo is None or before.utcoffset() is None:
        raise ValueError("before_expected_at must be timezone-aware")

    if after.tzinfo is None or after.utcoffset() is None:
        raise ValueError("after_expected_at must be timezone-aware")

    if evidence.source_classification in {
        SourceClassification.BLOCKED,
        SourceClassification.UNKNOWN,
        SourceClassification.SOURCE_QUALITY_BLOCKED,
    }:
        return _blocked_result(
            change,
            "authoritative incoming source가 없어 Actual 지연을 확정할 수 없습니다.",
        )

    delay = after - before
    delay_hours = int(delay.total_seconds() // 3600)

    if delay_hours <= 0:
        return DelayImpactResult(
            status=(
                ImpactStatus.CALCULATED
                if _is_actual_confirmable(evidence)
                else ImpactStatus.CONTRACT_ONLY
            ),
            actual_delay_confirmed=False,
            incoming_id=change.incoming_id,
            delay_hours=delay_hours,
            source_id=evidence.source_id,
            source_classification=evidence.source_classification,
            as_of=evidence.as_of,
            freshness=evidence.freshness,
            quality=evidence.quality,
            evidence_ids=evidence.evidence_ids,
            impacted_task_ids=(),
            impacted_reservation_ids=(),
            impacted_launch_event_ids=(),
            critical_path=(),
            impact_path=(),
            reason="after_expected_at이 before_expected_at보다 늦지 않습니다.",
        )

    task_items: list[ImpactPathItem] = []
    impacted_task_ids: list[str] = []

    for task in sorted(tasks, key=lambda item: item.task_id):
        if task.depends_on_incoming is not True or task.incoming_id != change.incoming_id:
            continue

        impacted_task_ids.append(task.task_id)

        task_items.append(
            ImpactPathItem(
                target_type="TASK",
                target_id=task.task_id,
                source_id=evidence.source_id,
                before=task.deadline,
                after=task.deadline + timedelta(hours=delay_hours),
                lag_hours=task.lag_hours,
                reason=f"입고가 {delay_hours}시간 지연되어 후속 Task가 영향을 받습니다.",
                evidence_ids=evidence.evidence_ids,
            )
        )

    impacted_reservation_ids = sorted(
        reservation.reservation_id
        for reservation in reservations
        if reservation.incoming_id == change.incoming_id
    )

    reservation_items = [
        ImpactPathItem(
            target_type="RESERVATION",
            target_id=reservation_id,
            source_id=evidence.source_id,
            before=before,
            after=after,
            lag_hours=delay_hours,
            reason="연결된 입고예정일 지연으로 예약주문이 영향을 받을 수 있습니다.",
            evidence_ids=evidence.evidence_ids,
        )
        for reservation_id in impacted_reservation_ids
    ]

    impacted_launch_ids: list[str] = []
    launch_items: list[ImpactPathItem] = []

    for launch in sorted(launch_events, key=lambda item: item.launch_event_id):
        if launch.depends_on_incoming is not True or launch.incoming_id != change.incoming_id:
            continue

        impacted_launch_ids.append(launch.launch_event_id)

        launch_items.append(
            ImpactPathItem(
                target_type="LAUNCH_EVENT",
                target_id=launch.launch_event_id,
                source_id=evidence.source_id,
                before=launch.launch_at,
                after=launch.launch_at + timedelta(hours=delay_hours),
                lag_hours=delay_hours,
                reason="입고 지연으로 출시 일정 재검토가 필요합니다.",
                evidence_ids=evidence.evidence_ids,
            )
        )

    # 현재 Day 10에서는 dependency graph 기반의 결정론적 영향 순서만 반환한다.
    critical_path = tuple(impacted_task_ids)

    is_actual = _is_actual_confirmable(evidence)

    return DelayImpactResult(
        status=(
            ImpactStatus.CALCULATED
            if is_actual
            else ImpactStatus.CONTRACT_ONLY
        ),
        actual_delay_confirmed=is_actual,
        incoming_id=change.incoming_id,
        delay_hours=delay_hours,
        source_id=evidence.source_id,
        source_classification=evidence.source_classification,
        as_of=evidence.as_of,
        freshness=evidence.freshness,
        quality=evidence.quality,
        evidence_ids=evidence.evidence_ids,
        impacted_task_ids=tuple(impacted_task_ids),
        impacted_reservation_ids=tuple(impacted_reservation_ids),
        impacted_launch_event_ids=tuple(impacted_launch_ids),
        critical_path=critical_path,
        impact_path=tuple(
            task_items + reservation_items + launch_items
        ),
        reason=(
            "입고 지연 영향 계산 완료."
            if is_actual
            else "Fixture/계약 Source를 사용한 기능 검증 결과이며 Actual 확정값이 아닙니다."
        ),
    )
