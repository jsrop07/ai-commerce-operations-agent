"""Persistent provider sync checkpoints.

Checkpoint advancement is deliberately separated from provider reads.
A caller may advance a checkpoint only after its canonical transaction
has succeeded.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.ingestion import SyncState


class CheckpointCommitError(RuntimeError):
    """Checkpoint advancement attempted before canonical commit."""


class CursorStore:
    def get(
        self,
        session: Session,
        *,
        tenant_id: str,
        provider: str,
        resource: str,
        connection_mode: str,
    ) -> SyncState | None:
        statement = select(SyncState).where(
            SyncState.tenant_id == tenant_id,
            SyncState.provider == provider,
            SyncState.resource == resource,
            SyncState.connection_mode == connection_mode,
        )
        return session.scalar(statement)

    def commit_api_checkpoint(
        self,
        session: Session,
        *,
        tenant_id: str,
        provider: str,
        resource: str,
        connection_mode: str,
        cursor: str | None,
        watermark: datetime | None,
        overlap_start: datetime | None,
        last_success_at: datetime,
        canonical_committed: bool,
    ) -> SyncState:
        if not canonical_committed:
            raise CheckpointCommitError(
                "checkpoint cannot advance before canonical transaction commit"
            )

        if connection_mode not in {"API_POLL", "WEBHOOK_PLUS_RECONCILIATION"}:
            raise ValueError("API checkpoint requires an API connection mode")
        for timestamp in (watermark, overlap_start, last_success_at):
            if timestamp is not None and (
                timestamp.tzinfo is None or timestamp.utcoffset() is None
            ):
                raise ValueError("checkpoint timestamps must include timezone")
        if overlap_start is not None and (watermark is None or overlap_start > watermark):
            raise ValueError("overlap_start must not exceed watermark")

        state = self.get(
            session,
            tenant_id=tenant_id,
            provider=provider,
            resource=resource,
            connection_mode=connection_mode,
        )

        if state is None:
            state = SyncState(
                tenant_id=tenant_id,
                provider=provider,
                resource=resource,
                connection_mode=connection_mode,
                state_version=0,
            )
            session.add(state)

        state.cursor = cursor
        state.watermark = watermark
        state.overlap_start = overlap_start

        # API checkpoint must not silently become a file checkpoint.
        state.file_hash = None
        state.batch_id = None
        state.row_number = None

        state.last_success_at = last_success_at
        state.last_error = None
        state.state_version = (state.state_version or 0) + 1

        session.commit()
        session.refresh(state)
        return state

    def commit_file_checkpoint(
        self,
        session: Session,
        *,
        tenant_id: str,
        provider: str,
        resource: str,
        connection_mode: str,
        file_hash: str,
        batch_id: str,
        row_number: int,
        last_success_at: datetime,
        canonical_committed: bool,
    ) -> SyncState:
        if not canonical_committed:
            raise CheckpointCommitError(
                "checkpoint cannot advance before canonical transaction commit"
            )

        if connection_mode not in {"FILE_IMPORT", "MANUAL_PROTECTED_IMPORT"}:
            raise ValueError("file checkpoint requires a file connection mode")
        if last_success_at.tzinfo is None or last_success_at.utcoffset() is None:
            raise ValueError("checkpoint timestamps must include timezone")

        if not file_hash:
            raise ValueError("file_hash is required")

        if not batch_id:
            raise ValueError("batch_id is required")

        if row_number < 1:
            raise ValueError("row_number must be >= 1")

        state = self.get(
            session,
            tenant_id=tenant_id,
            provider=provider,
            resource=resource,
            connection_mode=connection_mode,
        )

        if state is None:
            state = SyncState(
                tenant_id=tenant_id,
                provider=provider,
                resource=resource,
                connection_mode=connection_mode,
                state_version=0,
            )
            session.add(state)

        state.file_hash = file_hash
        state.batch_id = batch_id
        state.row_number = row_number

        # File checkpoint must not silently inherit API cursor state.
        state.cursor = None
        state.watermark = None
        state.overlap_start = None

        state.last_success_at = last_success_at
        state.last_error = None
        state.state_version = (state.state_version or 0) + 1

        session.commit()
        session.refresh(state)
        return state

    def record_error(
        self,
        session: Session,
        *,
        tenant_id: str,
        provider: str,
        resource: str,
        connection_mode: str,
        error_code: str,
    ) -> SyncState:
        state = self.get(
            session,
            tenant_id=tenant_id,
            provider=provider,
            resource=resource,
            connection_mode=connection_mode,
        )

        if state is None:
            state = SyncState(
                tenant_id=tenant_id,
                provider=provider,
                resource=resource,
                connection_mode=connection_mode,
                state_version=0,
            )
            session.add(state)

        # 중요:
        # 실패를 기록할 뿐 cursor/file checkpoint는 변경하지 않는다.
        state.last_error = error_code

        session.commit()
        session.refresh(state)
        return state
