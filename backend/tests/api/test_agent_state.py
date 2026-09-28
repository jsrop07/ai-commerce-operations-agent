from __future__ import annotations

import os
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.db.session import build_engine
from backend.app.main import create_app
from backend.app.models.agent import AgentRun
from backend.app.services.agent_run_repository import (
    save_agent_checkpoint,
)


POSTGRES_TEST_URL = os.getenv("POSTGRES_TEST_URL")


def _client(
    *,
    tenant_id: str,
) -> TestClient:
    assert POSTGRES_TEST_URL is not None

    settings = Settings(
        database_url=POSTGRES_TEST_URL,
        tenant_id=tenant_id,
    )

    return TestClient(
        create_app(settings)
    )


def _cleanup(
    *,
    tenant_id: str,
    workflow_id: str,
    thread_id: str,
) -> None:
    assert POSTGRES_TEST_URL is not None

    engine = build_engine(
        POSTGRES_TEST_URL
    )

    try:
        with Session(engine) as session:
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
        engine.dispose()


def test_agent_state_not_found() -> None:
    client = _client(
        tenant_id="demo_store"
    )

    response = client.get(
        "/api/v1/workflows/"
        "missing-workflow/"
        "threads/missing-thread/state"
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "AGENT_STATE_NOT_FOUND"
    }


def test_agent_state_read_and_raw_fields_hidden() -> None:
    assert POSTGRES_TEST_URL is not None

    tenant_id = "demo_store"
    workflow_id = "api-contract-workflow"
    thread_id = "api-contract-thread"

    engine = build_engine(
        POSTGRES_TEST_URL
    )

    try:
        with Session(engine) as session:
            save_agent_checkpoint(
                session,
                tenant_id=tenant_id,
                workflow_id=workflow_id,
                thread_id=thread_id,
                current_node="proposal_saved",
                status="WAITING",
                state={
                    "private_internal":
                    "SHOULD_NOT_BE_EXPOSED"
                },
                state_schema_version=1,
                expected_checkpoint_version=0,
                checkpoint_at=datetime.now(
                    UTC
                ),
                evidence_ids=(
                    "evidence-api-001",
                ),
                reason=(
                    "HUMAN_CONFIRMATION_REQUIRED"
                ),
                model_version=(
                    "internal-model-v1"
                ),
                prompt_version=(
                    "internal-prompt-v1"
                ),
                cost={"tokens": 99},
                output_hash="internal-hash",
            )

        client = _client(
            tenant_id=tenant_id
        )

        response = client.get(
            f"/api/v1/workflows/"
            f"{workflow_id}/threads/"
            f"{thread_id}/state"
        )

        assert response.status_code == 200

        body = response.json()

        assert body["workflow_id"] == workflow_id
        assert body["thread_id"] == thread_id
        assert (
            body["current_node"]
            == "proposal_saved"
        )
        assert body["status"] == "WAITING"
        assert (
            body["checkpoint_version"]
            == 1
        )
        assert body["evidence_ids"] == [
            "evidence-api-001"
        ]
        assert (
            body["reason"]
            == "HUMAN_CONFIRMATION_REQUIRED"
        )

        for hidden_field in (
            "state",
            "cost",
            "model_version",
            "prompt_version",
            "output_hash",
            "tenant_id",
        ):
            assert (
                hidden_field
                not in body
            )

    finally:
        engine.dispose()

        _cleanup(
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            thread_id=thread_id,
        )


def test_agent_state_is_tenant_isolated() -> None:
    assert POSTGRES_TEST_URL is not None

    tenant_id = "tenant-a"
    workflow_id = "tenant-workflow"
    thread_id = "tenant-thread"

    engine = build_engine(
        POSTGRES_TEST_URL
    )

    try:
        with Session(engine) as session:
            save_agent_checkpoint(
                session,
                tenant_id=tenant_id,
                workflow_id=workflow_id,
                thread_id=thread_id,
                current_node="proposal_saved",
                status="WAITING",
                state={},
                state_schema_version=1,
                expected_checkpoint_version=0,
                checkpoint_at=datetime.now(
                    UTC
                ),
            )

        other_tenant_client = _client(
            tenant_id="tenant-b"
        )

        response = other_tenant_client.get(
            f"/api/v1/workflows/"
            f"{workflow_id}/threads/"
            f"{thread_id}/state"
        )

        assert response.status_code == 404
        assert response.json() == {
            "detail": "AGENT_STATE_NOT_FOUND"
        }

    finally:
        engine.dispose()

        _cleanup(
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            thread_id=thread_id,
        )


def test_agent_state_openapi_contract() -> None:
    client = _client(
        tenant_id="demo_store"
    )

    openapi = client.get(
        "/openapi.json"
    ).json()

    path = (
        "/api/v1/workflows/"
        "{workflow_id}/threads/"
        "{thread_id}/state"
    )

    assert path in openapi["paths"]
    assert (
        "get"
        in openapi["paths"][path]
    )