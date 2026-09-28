from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from backend.app.db.session import build_engine
from backend.app.models.agent import AgentRun
from backend.app.services.agent_run_repository import (
    AgentCheckpointVersionConflict,
    UnsupportedAgentStateSchema,
    get_agent_run,
    save_agent_checkpoint,
)


DB_URL = "sqlite+pysqlite:///:memory:"


def _engine():
    engine = build_engine(DB_URL)
    AgentRun.__table__.create(
        bind=engine,
        checkfirst=True,
    )
    return engine


def test_save_and_read_checkpoint() -> None:
    engine = _engine()

    with Session(engine) as session:
        saved = save_agent_checkpoint(
            session,
            tenant_id="tenant-001",
            workflow_id="reservation-review",
            thread_id="thread-001",
            current_node="validate_input",
            status="WAITING",
            state={
                "reservation_id": "reservation-001",
            },
            state_schema_version=1,
            expected_checkpoint_version=0,
            checkpoint_at=datetime.now(UTC),
            evidence_ids=("evidence-001",),
            reason="HUMAN_REVIEW_REQUIRED",
            model_version="base-v1",
            prompt_version="prompt-v1",
            cost={
                "input_tokens": 10,
                "output_tokens": 5,
            },
            output_hash="hash-001",
        )

        assert saved.checkpoint_version == 1

    with Session(engine) as session:
        loaded = get_agent_run(
            session,
            tenant_id="tenant-001",
            workflow_id="reservation-review",
            thread_id="thread-001",
        )

        assert loaded is not None
        assert loaded.current_node == "validate_input"
        assert loaded.status == "WAITING"
        assert loaded.state == {
            "reservation_id": "reservation-001",
        }
        assert loaded.evidence_ids == [
            "evidence-001",
        ]
        assert loaded.output_hash == "hash-001"


def test_checkpoint_update_increments_version() -> None:
    engine = _engine()

    with Session(engine) as session:
        save_agent_checkpoint(
            session,
            tenant_id="tenant-001",
            workflow_id="reservation-review",
            thread_id="thread-001",
            current_node="validate_input",
            status="RUNNING",
            state={"step": 1},
            state_schema_version=1,
            expected_checkpoint_version=0,
            checkpoint_at=datetime.now(UTC),
        )

        updated = save_agent_checkpoint(
            session,
            tenant_id="tenant-001",
            workflow_id="reservation-review",
            thread_id="thread-001",
            current_node="rule_lookup",
            status="WAITING",
            state={"step": 2},
            state_schema_version=1,
            expected_checkpoint_version=1,
            checkpoint_at=datetime.now(UTC),
        )

        assert updated.checkpoint_version == 2
        assert updated.current_node == "rule_lookup"
        assert updated.state == {"step": 2}


def test_stale_checkpoint_version_is_rejected() -> None:
    engine = _engine()

    with Session(engine) as session:
        save_agent_checkpoint(
            session,
            tenant_id="tenant-001",
            workflow_id="reservation-review",
            thread_id="thread-001",
            current_node="validate_input",
            status="RUNNING",
            state={"step": 1},
            state_schema_version=1,
            expected_checkpoint_version=0,
            checkpoint_at=datetime.now(UTC),
        )

        save_agent_checkpoint(
            session,
            tenant_id="tenant-001",
            workflow_id="reservation-review",
            thread_id="thread-001",
            current_node="rule_lookup",
            status="WAITING",
            state={"step": 2},
            state_schema_version=1,
            expected_checkpoint_version=1,
            checkpoint_at=datetime.now(UTC),
        )

        with pytest.raises(
            AgentCheckpointVersionConflict
        ):
            save_agent_checkpoint(
                session,
                tenant_id="tenant-001",
                workflow_id="reservation-review",
                thread_id="thread-001",
                current_node="stale_node",
                status="WAITING",
                state={"step": 999},
                state_schema_version=1,
                expected_checkpoint_version=1,
                checkpoint_at=datetime.now(UTC),
            )


def test_other_tenant_is_isolated() -> None:
    engine = _engine()

    with Session(engine) as session:
        save_agent_checkpoint(
            session,
            tenant_id="tenant-001",
            workflow_id="reservation-review",
            thread_id="thread-001",
            current_node="validate_input",
            status="WAITING",
            state={"tenant": "a"},
            state_schema_version=1,
            expected_checkpoint_version=0,
            checkpoint_at=datetime.now(UTC),
        )

        assert (
            get_agent_run(
                session,
                tenant_id="tenant-002",
                workflow_id="reservation-review",
                thread_id="thread-001",
            )
            is None
        )


def test_unsupported_state_schema_is_rejected() -> None:
    engine = _engine()

    with Session(engine) as session:
        with pytest.raises(
            UnsupportedAgentStateSchema
        ):
            save_agent_checkpoint(
                session,
                tenant_id="tenant-001",
                workflow_id="reservation-review",
                thread_id="thread-001",
                current_node="validate_input",
                status="WAITING",
                state={},
                state_schema_version=999,
                expected_checkpoint_version=0,
                checkpoint_at=datetime.now(UTC),
            )