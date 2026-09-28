"""AgentRun checkpoint PostgreSQL repository."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models.agent import AgentRun


SUPPORTED_STATE_SCHEMA_VERSIONS = {1}


class AgentCheckpointVersionConflict(Exception):
    """checkpoint optimistic version conflict."""


class UnsupportedAgentStateSchema(Exception):
    """Unsupported AgentState schema version."""


def _validate_checkpoint_input(
    *,
    tenant_id: str,
    workflow_id: str,
    thread_id: str,
    current_node: str,
    status: str,
    state_schema_version: int,
    expected_checkpoint_version: int,
    checkpoint_at: datetime,
) -> None:
    if not tenant_id:
        raise ValueError("tenant_id is required")

    if not workflow_id:
        raise ValueError("workflow_id is required")

    if not thread_id:
        raise ValueError("thread_id is required")

    if not current_node:
        raise ValueError("current_node is required")

    if not status:
        raise ValueError("status is required")

    if (
        state_schema_version
        not in SUPPORTED_STATE_SCHEMA_VERSIONS
    ):
        raise UnsupportedAgentStateSchema(
            f"unsupported state_schema_version="
            f"{state_schema_version}"
        )

    if expected_checkpoint_version < 0:
        raise ValueError(
            "expected_checkpoint_version must be >= 0"
        )

    if (
        checkpoint_at.tzinfo is None
        or checkpoint_at.utcoffset() is None
    ):
        raise ValueError(
            "checkpoint_at must be timezone-aware"
        )


def get_agent_run(
    session: Session,
    *,
    tenant_id: str,
    workflow_id: str,
    thread_id: str,
) -> AgentRun | None:
    """현재 저장된 AgentRun checkpoint 조회."""

    return session.scalar(
        select(AgentRun).where(
            AgentRun.tenant_id == tenant_id,
            AgentRun.workflow_id == workflow_id,
            AgentRun.thread_id == thread_id,
        )
    )


def save_agent_checkpoint(
    session: Session,
    *,
    tenant_id: str,
    workflow_id: str,
    thread_id: str,
    current_node: str,
    status: str,
    state: dict[str, Any],
    state_schema_version: int,
    expected_checkpoint_version: int,
    checkpoint_at: datetime,
    evidence_ids: tuple[str, ...] = (),
    reason: str | None = None,
    model_version: str | None = None,
    prompt_version: str | None = None,
    cost: dict[str, Any] | None = None,
    output_hash: str | None = None,
) -> AgentRun:
    """checkpoint를 optimistic version으로 저장한다."""

    _validate_checkpoint_input(
        tenant_id=tenant_id,
        workflow_id=workflow_id,
        thread_id=thread_id,
        current_node=current_node,
        status=status,
        state_schema_version=state_schema_version,
        expected_checkpoint_version=(
            expected_checkpoint_version
        ),
        checkpoint_at=checkpoint_at,
    )

    merged_evidence = list(
        dict.fromkeys(evidence_ids)
    )

    # 최초 checkpoint
    if expected_checkpoint_version == 0:
        row = AgentRun(
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            thread_id=thread_id,
            current_node=current_node,
            status=status,
            state_schema_version=(
                state_schema_version
            ),
            checkpoint_version=1,
            state=state,
            evidence_ids=merged_evidence,
            reason=reason,
            model_version=model_version,
            prompt_version=prompt_version,
            checkpoint_at=checkpoint_at,
            cost=cost,
            output_hash=output_hash,
        )

        session.add(row)

        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()

            raise AgentCheckpointVersionConflict(
                "checkpoint already exists"
            ) from exc

        session.refresh(row)

        return row

    # 기존 checkpoint 갱신.
    # checkpoint_version까지 WHERE에 포함해
    # stale writer가 최신 상태를 덮어쓰지 못하게 한다.
    result = session.execute(
        update(AgentRun)
        .where(
            AgentRun.tenant_id == tenant_id,
            AgentRun.workflow_id == workflow_id,
            AgentRun.thread_id == thread_id,
            AgentRun.checkpoint_version
            == expected_checkpoint_version,
        )
        .values(
            current_node=current_node,
            status=status,
            state_schema_version=(
                state_schema_version
            ),
            checkpoint_version=(
                expected_checkpoint_version + 1
            ),
            state=state,
            evidence_ids=merged_evidence,
            reason=reason,
            model_version=model_version,
            prompt_version=prompt_version,
            checkpoint_at=checkpoint_at,
            cost=cost,
            output_hash=output_hash,
        )
    )

    if result.rowcount != 1:
        session.rollback()

        current = get_agent_run(
            session,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            thread_id=thread_id,
        )

        current_version = (
            current.checkpoint_version
            if current is not None
            else 0
        )

        raise AgentCheckpointVersionConflict(
            f"expected_checkpoint_version="
            f"{expected_checkpoint_version}, "
            f"current_checkpoint_version="
            f"{current_version}"
        )

    session.commit()

    row = get_agent_run(
        session,
        tenant_id=tenant_id,
        workflow_id=workflow_id,
        thread_id=thread_id,
    )

    if row is None:
        raise RuntimeError(
            "checkpoint disappeared after commit"
        )

    return row