"""D11-BE-04 Task feedback append/readback service."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models.feedback import TaskFeedback


SERVER_DEMO_ACTOR = "DEMO_OPERATOR"


class FeedbackVersionConflict(Exception):
    """expected_version이 현재 feedback version과 다름."""


class FeedbackIdempotencyConflict(Exception):
    """같은 idempotency key가 다른 요청에 재사용됨."""


def _same_request(
    row: TaskFeedback,
    *,
    task_id: str,
    decision: str,
    target_field: str | None,
    before_value: Any | None,
    after_value: Any | None,
    reason: str,
) -> bool:
    return (
        row.task_id == task_id
        and row.decision == decision
        and row.target_field == target_field
        and row.before_value == before_value
        and row.after_value == after_value
        and row.reason == reason
    )


def append_task_feedback(
    session: Session,
    *,
    tenant_id: str,
    task_id: str,
    decision: str,
    target_field: str | None,
    before_value: Any | None,
    after_value: Any | None,
    reason: str,
    idempotency_key: str,
    expected_version: int,
) -> TaskFeedback:
    """Task feedback 한 건을 append-only로 저장한다."""

    if not tenant_id:
        raise ValueError("tenant_id is required")

    if not task_id:
        raise ValueError("task_id is required")

    if decision not in {
        "EDIT",
        "REJECT",
    }:
        raise ValueError(
            "decision must be EDIT or REJECT"
        )

    if not reason.strip():
        raise ValueError("reason is required")

    if not idempotency_key:
        raise ValueError(
            "idempotency_key is required"
        )

    if expected_version < 0:
        raise ValueError(
            "expected_version must be >= 0"
        )

    if decision == "EDIT" and not target_field:
        raise ValueError(
            "EDIT requires target_field"
        )

    if decision == "REJECT" and target_field is not None:
        raise ValueError(
            "REJECT must not set target_field"
        )

    existing = session.scalar(
        select(TaskFeedback).where(
            TaskFeedback.tenant_id
            == tenant_id,
            TaskFeedback.idempotency_key
            == idempotency_key,
        )
    )

    if existing is not None:
        if _same_request(
            existing,
            task_id=task_id,
            decision=decision,
            target_field=target_field,
            before_value=before_value,
            after_value=after_value,
            reason=reason,
        ):
            return existing

        raise FeedbackIdempotencyConflict(
            "idempotency key was already used "
            "for a different feedback request"
        )

    current_version = session.scalar(
        select(
            func.max(
                TaskFeedback.feedback_version
            )
        ).where(
            TaskFeedback.tenant_id
            == tenant_id,
            TaskFeedback.task_id
            == task_id,
        )
    )

    current_version = (
        int(current_version)
        if current_version is not None
        else 0
    )

    if expected_version != current_version:
        raise FeedbackVersionConflict(
            f"expected_version={expected_version}, "
            f"current_version={current_version}"
        )

    row = TaskFeedback(
        tenant_id=tenant_id,
        task_id=task_id,
        decision=decision,
        target_field=target_field,
        before_value=before_value,
        after_value=after_value,
        reason=reason.strip(),
        actor=SERVER_DEMO_ACTOR,
        idempotency_key=idempotency_key,
        feedback_version=(
            current_version + 1
        ),
    )

    session.add(row)

    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()

        replay = session.scalar(
            select(TaskFeedback).where(
                TaskFeedback.tenant_id
                == tenant_id,
                TaskFeedback.idempotency_key
                == idempotency_key,
            )
        )

        if (
            replay is not None
            and _same_request(
                replay,
                task_id=task_id,
                decision=decision,
                target_field=target_field,
                before_value=before_value,
                after_value=after_value,
                reason=reason,
            )
        ):
            return replay

        raise FeedbackVersionConflict(
            "feedback version changed "
            "during append"
        ) from exc

    session.refresh(row)

    return row


def list_task_feedback(
    session: Session,
    *,
    tenant_id: str,
    task_id: str,
) -> list[TaskFeedback]:
    """Task feedback을 append 순서대로 조회한다."""

    return list(
        session.scalars(
            select(TaskFeedback)
            .where(
                TaskFeedback.tenant_id
                == tenant_id,
                TaskFeedback.task_id
                == task_id,
            )
            .order_by(
                TaskFeedback.feedback_version.asc()
            )
        )
    )