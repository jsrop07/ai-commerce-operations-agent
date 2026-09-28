"""D09-BE-04 예약 부족 Task 중복방지·aging."""

from __future__ import annotations

import hashlib
from backend.app.services.task_dedup import (
    TaskDedupService,
)
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from backend.app.services.reservation_projection import ReservationRiskProjection


@dataclass(frozen=True)
class ReservationShortageTask:
    task_id: str
    tenant_id: str
    sku_id: str
    cause: str

    status: str
    priority: int

    first_detected_at: datetime
    last_seen_at: datetime
    aging_hours: int

    priority_reason: str

    evidence_ids: tuple[str, ...]
    source_classification: str

    replay_count: int = 0


@dataclass
class ReservationTaskService:
    """같은 shortage effect를 한 번만 생성한다."""

    tasks: dict[
        str,
        ReservationShortageTask,
    ] = field(default_factory=dict)

    dedup: TaskDedupService = field(
        default_factory=TaskDedupService
    )

    def project_shortage_task(
        self,
        projection: ReservationRiskProjection,
    ) -> dict[str, object] | None:
        """확정 예약 부족을 기존 schedule Task 읽기 모델로 연결한다."""
        if projection.shortage is None or projection.shortage <= 0:
            return None

        task = self.propose_shortage_task(
            tenant_id=projection.tenant_id,
            sku_id=projection.sku_id,
            cause="RESERVATION_SHORTAGE",
            cause_id=projection.reservation_id,
            detected_at=projection.as_of,
            evidence_ids=projection.evidence,
            source_classification=projection.source_classification,
        )

        return {
            "id": task.task_id,
            "task_id": task.task_id,
            "tenant_id": task.tenant_id,
            "sku_id": task.sku_id,
            "reservation_id": projection.reservation_id,
            "task_type": task.cause,
            "title": "예약 부족 확인",
            "deadline": None,
            "risk_level": projection.delivery_risk,
            "affected_count": len(projection.affected_order_ids),
            "aging_hours": projection.aging_hours,
            "priority": projection.priority,
            "priority_reason": projection.priority_reason,
            "status": task.status,
            "source_reason": projection.calculation_status,
            "source_classification": projection.source_classification,
            "evidence_ids": task.evidence_ids,
            "as_of": projection.as_of,
            "replay_count": task.replay_count,
        }

    def propose_shortage_task(
        self,
        *,
        tenant_id: str,
        sku_id: str,
        cause: str,
        cause_id: str,
        detected_at: datetime,
        evidence_ids: tuple[str, ...],
        source_classification: str,
        dedupe_window_hours: int = 24,
    ) -> ReservationShortageTask:
        if not tenant_id:
            raise ValueError(
                "tenant_id is required"
            )

        if not sku_id:
            raise ValueError(
                "sku_id is required"
            )

        if not cause:
            raise ValueError(
                "cause is required"
            )
        
        if not cause_id:
            raise ValueError(
                "cause_id is required"
            )
        
        if dedupe_window_hours <= 0:
            raise ValueError(
                "dedupe_window_hours "
                "must be > 0"
            )

        dedup_result = self.dedup.register(
            tenant_id=tenant_id,
            sku_id=sku_id,
            risk_type=cause,
            cause_id=cause_id,
            occurred_at=detected_at,
            evidence_ids=evidence_ids,
            dedupe_window_hours=dedupe_window_hours,
        )

        task_id = dedup_result.dedupe_key

        existing = self.tasks.get(
            task_id
        )

        if existing is not None:
            aging_hours = max(
                int(
                    (
                        detected_at
                        - existing
                        .first_detected_at
                    ).total_seconds()
                    // 3600
                ),
                0,
            )

            priority, reason = (
                self._priority_for_aging(
                    aging_hours
                )
            )

            updated = (
                ReservationShortageTask(
                    task_id=(
                        existing.task_id
                    ),
                    tenant_id=(
                        existing.tenant_id
                    ),
                    sku_id=(
                        existing.sku_id
                    ),
                    cause=(
                        existing.cause
                    ),
                    status=(
                        existing.status
                    ),
                    priority=priority,
                    first_detected_at=(
                        existing
                        .first_detected_at
                    ),
                    last_seen_at=(
                        detected_at
                    ),
                    aging_hours=(
                        aging_hours
                    ),
                    priority_reason=(
                        reason
                    ),
                    evidence_ids=(
                        tuple(
                            dict.fromkeys(
                                existing
                                .evidence_ids
                                + evidence_ids
                            )
                        )
                    ),
                    source_classification=(
                        existing
                        .source_classification
                    ),
                    replay_count=(
                        existing
                        .replay_count
                        + 1
                    ),
                )
            )

            self.tasks[
                task_id
            ] = updated

            return updated
        aging_hours = 0

        priority, reason = self._priority_for_aging(
            aging_hours
        )

        task = ReservationShortageTask(
            task_id=task_id,
            tenant_id=tenant_id,
            sku_id=sku_id,
            cause=cause,
            status="PROPOSED",
            priority=priority,
            first_detected_at=(
                detected_at
            ),
            last_seen_at=(
                detected_at
            ),
            aging_hours=0,
            priority_reason=reason,
            evidence_ids=(
                tuple(
                    dict.fromkeys(
                        evidence_ids
                    )
                )
            ),
            source_classification=(
                source_classification
            ),
            replay_count=0,
        )

        self.tasks[
            task_id
        ] = task

        return task

    @staticmethod
    def _priority_for_aging(
        aging_hours: int,
    ) -> tuple[int, str]:
        if aging_hours >= 72:
            return (
                90,
                "AGING_72H_PLUS",
            )

        if aging_hours >= 48:
            return (
                70,
                "AGING_48H_PLUS",
            )

        if aging_hours >= 24:
            return (
                50,
                "AGING_24H_PLUS",
            )

        return (
            30,
            "NEW_RESERVATION_SHORTAGE",
        )

    @staticmethod
    def _task_id(
        *,
        tenant_id: str,
        sku_id: str,
        cause: str,
        bucket: int,
    ) -> str:
        raw = (
            f"{tenant_id}|"
            f"{sku_id}|"
            f"{cause}|"
            f"{bucket}"
        )

        digest = hashlib.sha256(
            raw.encode("utf-8")
        ).hexdigest()[:24]

        return f"task_{digest}"


def register_reservation_risk_projection(
    app_state: Any,
    projection: ReservationRiskProjection,
) -> dict[str, object] | None:
    """예약 위험을 등록하고 확정 부족 Task 읽기 모델을 갱신한다."""
    app_state.reservation_risk_projections.append(projection)
    task = app_state.reservation_task_service.project_shortage_task(projection)
    if task is None:
        return None

    tasks = app_state.schedule_task_projections
    for index, existing in enumerate(tasks):
        existing_id = (
            existing.get("id") or existing.get("task_id")
            if isinstance(existing, dict)
            else getattr(existing, "id", None) or getattr(existing, "task_id", None)
        )
        if existing_id == task["task_id"]:
            tasks[index] = task
            break
    else:
        tasks.append(task)

    return task
