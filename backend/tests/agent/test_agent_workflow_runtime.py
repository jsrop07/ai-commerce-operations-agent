from __future__ import annotations

import os

from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from ai.agents.reservation_replan_graph import (
    AgentState,
)
from backend.app.core.config import Settings
from backend.app.db.session import build_engine
from backend.app.main import create_app
from backend.app.models.agent import AgentRun
from backend.app.services.agent_run_repository import (
    get_agent_run,
)
from backend.app.services.agent_workflow_runtime import (
    run_and_checkpoint_reservation_replan,
)


POSTGRES_TEST_URL = os.getenv(
    "POSTGRES_TEST_URL"
)


def _initial_state() -> AgentState:
    return AgentState(
        workflow_id="wf_d16_be_01",
        thread_id="thread_d16_be_01",
        tenant_id="demo_store",
        schema_version="agent-state.v0.1",
        current_node="",
        status="RUNNING",
        trigger_event_ids=[
            "evt_d16_be_01",
        ],
        task_type=(
            "reservation_replan_review"
        ),
        risk_level="MEDIUM",
        confidence=None,
        entities={
            "reservation_id":
                "reservation_d16_be_01",
            "sku_id":
                "sku_d16_be_01",
        },
        evidence_ids=[
            "ev_rule_d16_be_01",
            "ev_incoming_d16_be_01",
        ],
        source_as_of=(
            "2026-09-13T18:30:00+09:00"
        ),
        rule_results={
            "reservation_shortage_qty": 2,
            "incoming_delay_days": 3,
            "replan_required": True,
            "requires_ai_assist": False,
        },
        retrieval_result={},
        model_result={},
        proposed_actions=[],
        approval_state=None,
        tool_receipts=[],
        retry_count={},
        deadlines={},
        errors=[],
        audit_ids=[],
        next_allowed_nodes=[],
        transition_history=[],
        provider_write_count=0,
    )


def _cleanup() -> None:
    assert POSTGRES_TEST_URL is not None

    engine = build_engine(
        POSTGRES_TEST_URL
    )

    try:
        with Session(engine) as session:
            session.execute(
                delete(AgentRun).where(
                    AgentRun.tenant_id
                    == "demo_store",
                    AgentRun.workflow_id
                    == "wf_d16_be_01",
                    AgentRun.thread_id
                    == "thread_d16_be_01",
                )
            )
            session.commit()
    finally:
        engine.dispose()


def test_langgraph_runtime_checkpoint_and_api() -> None:
    assert POSTGRES_TEST_URL is not None

    _cleanup()

    engine = build_engine(
        POSTGRES_TEST_URL
    )

    try:
        with Session(engine) as session:
            final_state = (
                run_and_checkpoint_reservation_replan(
                    session,
                    initial_state=_initial_state(),
                )
            )

        assert (
            final_state["current_node"]
            == "wait_for_human"
        )
        assert final_state["status"] == "WAITING"
        assert (
            final_state["reason"]
            == "HUMAN_REVIEW_REQUIRED"
        )
        assert (
            final_state["provider_write_count"]
            == 0
        )

        # 새 Session에서 PostgreSQL checkpoint 복원
        with Session(engine) as session:
            row = get_agent_run(
                session,
                tenant_id="demo_store",
                workflow_id="wf_d16_be_01",
                thread_id="thread_d16_be_01",
            )

            assert row is not None
            assert row.checkpoint_version == 1
            assert (
                row.current_node
                == "wait_for_human"
            )
            assert row.status == "WAITING"
            assert (
                row.reason
                == "HUMAN_REVIEW_REQUIRED"
            )
            assert row.state_schema_version == 1

            stored_state = row.state

            assert (
                stored_state["schema_version"]
                == "agent-state.v0.1"
            )
            assert (
                stored_state[
                    "provider_write_count"
                ]
                == 0
            )
            assert (
                stored_state[
                    "approval_state"
                ]
                == "PENDING"
            )

        # 기존 Backend state API에서도 조회
        settings = Settings(
            database_url=POSTGRES_TEST_URL,
            tenant_id="demo_store",
        )

        client = TestClient(
            create_app(settings)
        )

        response = client.get(
            "/api/v1/workflows/"
            "wf_d16_be_01/"
            "threads/thread_d16_be_01/state"
        )

        assert response.status_code == 200

        body = response.json()

        assert (
            body["current_node"]
            == "wait_for_human"
        )
        assert body["status"] == "WAITING"
        assert (
            body["checkpoint_version"]
            == 1
        )
        assert (
            body["reason"]
            == "HUMAN_REVIEW_REQUIRED"
        )

    finally:
        engine.dispose()
        _cleanup()