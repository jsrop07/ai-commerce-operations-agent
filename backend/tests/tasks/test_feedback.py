from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import pytest

import backend.app.models  # noqa: F401
from backend.app.db.base import Base
from backend.app.services.task_feedback import (
    FeedbackIdempotencyConflict,
    FeedbackVersionConflict,
    append_task_feedback,
    list_task_feedback,
)


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:"
    )

    Base.metadata.create_all(engine)

    with Session(engine) as db:
        yield db

    engine.dispose()


def test_first_feedback_version_is_one(
    session: Session,
) -> None:
    row = append_task_feedback(
        session,
        tenant_id="demo_store",
        task_id="task-001",
        decision="EDIT",
        target_field="deadline",
        before_value=None,
        after_value="2026-09-20T12:00:00Z",
        reason="입고 일정 확인 후 수정",
        idempotency_key="feedback-001",
        expected_version=0,
    )

    assert row.feedback_version == 1
    assert row.actor == "DEMO_OPERATOR"


def test_same_request_is_idempotent(
    session: Session,
) -> None:
    first = append_task_feedback(
        session,
        tenant_id="demo_store",
        task_id="task-001",
        decision="REJECT",
        target_field=None,
        before_value={
            "status": "PROPOSED",
        },
        after_value={
            "status": "DISMISSED",
        },
        reason="운영자가 불필요 판단",
        idempotency_key="feedback-001",
        expected_version=0,
    )

    second = append_task_feedback(
        session,
        tenant_id="demo_store",
        task_id="task-001",
        decision="REJECT",
        target_field=None,
        before_value={
            "status": "PROPOSED",
        },
        after_value={
            "status": "DISMISSED",
        },
        reason="운영자가 불필요 판단",
        idempotency_key="feedback-001",
        expected_version=0,
    )

    assert first.id == second.id

    rows = list_task_feedback(
        session,
        tenant_id="demo_store",
        task_id="task-001",
    )

    assert len(rows) == 1


def test_stale_version_is_rejected(
    session: Session,
) -> None:
    append_task_feedback(
        session,
        tenant_id="demo_store",
        task_id="task-001",
        decision="EDIT",
        target_field="deadline",
        before_value=None,
        after_value="2026-09-20",
        reason="첫 수정",
        idempotency_key="feedback-001",
        expected_version=0,
    )

    with pytest.raises(
        FeedbackVersionConflict
    ):
        append_task_feedback(
            session,
            tenant_id="demo_store",
            task_id="task-001",
            decision="EDIT",
            target_field="deadline",
            before_value="2026-09-20",
            after_value="2026-09-21",
            reason="오래된 화면에서 수정",
            idempotency_key="feedback-002",
            expected_version=0,
        )


def test_next_version_is_appended(
    session: Session,
) -> None:
    append_task_feedback(
        session,
        tenant_id="demo_store",
        task_id="task-001",
        decision="EDIT",
        target_field="deadline",
        before_value=None,
        after_value="2026-09-20",
        reason="첫 수정",
        idempotency_key="feedback-001",
        expected_version=0,
    )

    second = append_task_feedback(
        session,
        tenant_id="demo_store",
        task_id="task-001",
        decision="EDIT",
        target_field="deadline",
        before_value="2026-09-20",
        after_value="2026-09-21",
        reason="두 번째 수정",
        idempotency_key="feedback-002",
        expected_version=1,
    )

    assert second.feedback_version == 2


def test_idempotency_key_cannot_change_payload(
    session: Session,
) -> None:
    append_task_feedback(
        session,
        tenant_id="demo_store",
        task_id="task-001",
        decision="REJECT",
        target_field=None,
        before_value=None,
        after_value=None,
        reason="원래 이유",
        idempotency_key="feedback-001",
        expected_version=0,
    )

    with pytest.raises(
        FeedbackIdempotencyConflict
    ):
        append_task_feedback(
            session,
            tenant_id="demo_store",
            task_id="task-001",
            decision="REJECT",
            target_field=None,
            before_value=None,
            after_value=None,
            reason="다른 이유",
            idempotency_key="feedback-001",
            expected_version=0,
        )


def test_feedback_is_tenant_scoped(
    session: Session,
) -> None:
    first = append_task_feedback(
        session,
        tenant_id="tenant-a",
        task_id="task-001",
        decision="REJECT",
        target_field=None,
        before_value=None,
        after_value=None,
        reason="A tenant",
        idempotency_key="same-key",
        expected_version=0,
    )

    second = append_task_feedback(
        session,
        tenant_id="tenant-b",
        task_id="task-001",
        decision="REJECT",
        target_field=None,
        before_value=None,
        after_value=None,
        reason="B tenant",
        idempotency_key="same-key",
        expected_version=0,
    )

    assert first.id != second.id
    tenant_a_rows = list_task_feedback(
        session, tenant_id="tenant-a", task_id="task-001"
    )
    tenant_b_rows = list_task_feedback(
        session, tenant_id="tenant-b", task_id="task-001"
    )
    assert [row.id for row in tenant_a_rows] == [first.id]
    assert [row.id for row in tenant_b_rows] == [second.id]


def test_edit_requires_target_field(
    session: Session,
) -> None:
    with pytest.raises(
        ValueError,
        match="target_field",
    ):
        append_task_feedback(
            session,
            tenant_id="demo_store",
            task_id="task-001",
            decision="EDIT",
            target_field=None,
            before_value=None,
            after_value=None,
            reason="invalid",
            idempotency_key="feedback-001",
            expected_version=0,
        )


@pytest.mark.parametrize("reason", ["", " "])
def test_reason_is_required(session: Session, reason: str) -> None:
    with pytest.raises(ValueError, match="reason is required"):
        append_task_feedback(
            session,
            tenant_id="demo_store",
            task_id="task-001",
            decision="REJECT",
            target_field=None,
            before_value=None,
            after_value=None,
            reason=reason,
            idempotency_key="feedback-001",
            expected_version=0,
        )


def test_reject_forbids_target_field(session: Session) -> None:
    with pytest.raises(ValueError, match="REJECT must not set target_field"):
        append_task_feedback(
            session,
            tenant_id="demo_store",
            task_id="task-001",
            decision="REJECT",
            target_field="title",
            before_value=None,
            after_value=None,
            reason="invalid",
            idempotency_key="feedback-001",
            expected_version=0,
        )
