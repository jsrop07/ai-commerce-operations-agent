"""D11-BE-04 PostgreSQL feedback persistence 검증."""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from backend.app.services.task_feedback import (
    append_task_feedback,
    list_task_feedback,
)


@pytest.mark.postgres
def test_feedback_survives_reconnect_and_is_append_only() -> None:
    url = os.getenv("POSTGRES_TEST_URL")

    if not url:
        pytest.skip(
            "BLOCKED_BY_LOCAL_DB: "
            "POSTGRES_TEST_URL is not configured"
        )

    suffix = uuid.uuid4().hex[:8]

    task_id = f"task-{suffix}"
    idempotency_key = f"feedback-{suffix}"

    # 1. 첫 DB 연결에서 실제 INSERT
    engine = create_engine(url)

    with Session(engine) as session:
        created = append_task_feedback(
            session,
            tenant_id="demo_store",
            task_id=task_id,
            decision="EDIT",
            target_field="deadline",
            before_value=None,
            after_value="2026-09-20T12:00:00Z",
            reason="PostgreSQL persistence test",
            idempotency_key=idempotency_key,
            expected_version=0,
        )

        feedback_id = created.id

        assert created.feedback_version == 1
        assert created.actor == "DEMO_OPERATOR"

    # 기존 연결을 완전히 버린다.
    engine.dispose()

    # 2. 새 Engine + 새 Session 생성
    #    프로세스 재연결 후에도 DB row가 남는지 확인
    restarted_engine = create_engine(url)

    with Session(restarted_engine) as session:
        rows = list_task_feedback(
            session,
            tenant_id="demo_store",
            task_id=task_id,
        )

        assert len(rows) == 1

        restored = rows[0]

        assert restored.id == feedback_id
        assert restored.task_id == task_id
        assert restored.feedback_version == 1
        assert restored.actor == "DEMO_OPERATOR"
        assert (
            restored.reason
            == "PostgreSQL persistence test"
        )

    # 3. PostgreSQL trigger가 UPDATE 자체를 거부해야 한다.
    with pytest.raises(DBAPIError):
        with restarted_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    UPDATE task_feedback
                    SET reason = 'MUTATED'
                    WHERE id = :feedback_id
                    """
                ),
                {
                    "feedback_id": feedback_id,
                },
            )

    # 4. DELETE도 DB 수준에서 거부해야 한다.
    with pytest.raises(DBAPIError):
        with restarted_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    DELETE FROM task_feedback
                    WHERE id = :feedback_id
                    """
                ),
                {
                    "feedback_id": feedback_id,
                },
            )

    # 5. 차단 실패 과정에서도 원본 row가 남아 있어야 한다.
    with Session(restarted_engine) as session:
        rows = list_task_feedback(
            session,
            tenant_id="demo_store",
            task_id=task_id,
        )

        assert len(rows) == 1
        assert rows[0].id == feedback_id
        assert (
            rows[0].reason
            == "PostgreSQL persistence test"
        )

    restarted_engine.dispose()