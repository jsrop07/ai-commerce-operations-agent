from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.orm import Session

from backend.app.db.session import build_engine
from backend.app.models.agent import AgentRun
from backend.app.services.agent_run_repository import (
    UnsupportedAgentStateSchema,
    get_agent_run,
    save_agent_checkpoint,
)


POSTGRES_TEST_URL = os.getenv(
    "POSTGRES_TEST_URL"
)


@pytest.mark.skipif(
    not POSTGRES_TEST_URL,
    reason="POSTGRES_TEST_URL is not configured",
)
def test_agent_checkpoint_survives_engine_recreation() -> None:
    assert POSTGRES_TEST_URL is not None

    suffix = uuid4().hex[:8]

    tenant_id = (
        f"agent-pg-test-{suffix}"
    )
    workflow_id = (
        "reservation-replan-review"
    )
    thread_id = (
        f"thread-{suffix}"
    )

    engine_1 = build_engine(
        POSTGRES_TEST_URL
    )

    try:
        with Session(engine_1) as session:
            saved = save_agent_checkpoint(
                session,
                tenant_id=tenant_id,
                workflow_id=workflow_id,
                thread_id=thread_id,
                current_node=(
                    "proposal_saved"
                ),
                status="WAITING",
                state={
                    "reservation_id": (
                        f"reservation-{suffix}"
                    ),
                    "proposal_ready": True,
                    "approval_state": (
                        "WAITING"
                    ),
                },
                state_schema_version=1,
                expected_checkpoint_version=0,
                checkpoint_at=datetime.now(
                    UTC
                ),
                evidence_ids=(
                    f"evidence-{suffix}",
                ),
                reason=(
                    "HUMAN_CONFIRMATION_REQUIRED"
                ),
                model_version=(
                    "test-base-v1"
                ),
                prompt_version=(
                    "test-prompt-v1"
                ),
                cost={
                    "input_tokens": 12,
                    "output_tokens": 7,
                },
                output_hash=(
                    f"output-{suffix}"
                ),
            )

            assert (
                saved.checkpoint_version
                == 1
            )

    finally:
        engine_1.dispose()

    # 프로세스 재시작을 완전히 재현하지는 않지만,
    # DB connection/engine/session을 모두 새로 만든다.
    engine_2 = build_engine(
        POSTGRES_TEST_URL
    )

    try:
        with Session(engine_2) as session:
            restored = get_agent_run(
                session,
                tenant_id=tenant_id,
                workflow_id=workflow_id,
                thread_id=thread_id,
            )

            assert restored is not None

            assert (
                restored.checkpoint_version
                == 1
            )
            assert (
                restored.current_node
                == "proposal_saved"
            )
            assert (
                restored.status
                == "WAITING"
            )

            assert restored.state == {
                "reservation_id": (
                    f"reservation-{suffix}"
                ),
                "proposal_ready": True,
                "approval_state": (
                    "WAITING"
                ),
            }

            assert restored.evidence_ids == [
                f"evidence-{suffix}"
            ]

            assert (
                restored.output_hash
                == f"output-{suffix}"
            )

            assert restored.cost == {
                "input_tokens": 12,
                "output_tokens": 7,
            }

            # 테스트 데이터 정리
            session.execute(
                delete(AgentRun).where(
                    AgentRun.tenant_id
                    == tenant_id,
                    AgentRun.workflow_id
                    == workflow_id,
                    AgentRun.thread_id
                    == thread_id,
                )
            )
            session.commit()

    finally:
        engine_2.dispose()

def test_unsupported_old_state_schema_is_rejected() -> None:
    engine = build_engine(POSTGRES_TEST_URL)

    try:
        with Session(engine) as session:
            with pytest.raises(
                UnsupportedAgentStateSchema
            ):
                save_agent_checkpoint(
                    session,
                    tenant_id="version-test",
                    workflow_id="reservation-review",
                    thread_id="thread-old-version",
                    current_node="validate_input",
                    status="WAITING",
                    state={},
                    state_schema_version=0,
                    expected_checkpoint_version=0,
                    checkpoint_at=datetime.now(UTC),
                )
    finally:
        engine.dispose()