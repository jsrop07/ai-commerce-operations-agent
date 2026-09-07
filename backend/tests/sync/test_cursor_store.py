from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.db.base import Base
from backend.app.sync.cursor_store import CheckpointCommitError, CursorStore


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        yield db


def test_api_checkpoint_advances_only_after_canonical_commit(
    session: Session,
) -> None:
    store = CursorStore()
    now = datetime.now(UTC)

    with pytest.raises(CheckpointCommitError):
        store.commit_api_checkpoint(
            session,
            tenant_id="tenant-a",
            provider="CAFE24",
            resource="products",
            connection_mode="API_POLL",
            cursor="offset:25",
            watermark=now,
            overlap_start=now - timedelta(minutes=5),
            last_success_at=now,
            canonical_committed=False,
        )

    assert (
        store.get(
            session,
            tenant_id="tenant-a",
            provider="CAFE24",
            resource="products",
            connection_mode="API_POLL",
        )
        is None
    )

    state = store.commit_api_checkpoint(
        session,
        tenant_id="tenant-a",
        provider="CAFE24",
        resource="products",
        connection_mode="API_POLL",
        cursor="offset:25",
        watermark=now,
        overlap_start=now - timedelta(minutes=5),
        last_success_at=now,
        canonical_committed=True,
    )

    assert state.cursor == "offset:25"
    assert state.state_version == 1
    assert state.file_hash is None


def test_failed_page_does_not_advance_cursor(session: Session) -> None:
    store = CursorStore()
    now = datetime.now(UTC)

    store.commit_api_checkpoint(
        session,
        tenant_id="tenant-a",
        provider="CAFE24",
        resource="orders",
        connection_mode="API_POLL",
        cursor="offset:50",
        watermark=now,
        overlap_start=now - timedelta(minutes=5),
        last_success_at=now,
        canonical_committed=True,
    )

    failed = store.record_error(
        session,
        tenant_id="tenant-a",
        provider="CAFE24",
        resource="orders",
        connection_mode="API_POLL",
        error_code="TIMEOUT",
    )

    assert failed.cursor == "offset:50"
    assert failed.last_error == "TIMEOUT"
    assert failed.state_version == 1


def test_file_checkpoint_is_independent_from_api_checkpoint(
    session: Session,
) -> None:
    store = CursorStore()
    now = datetime.now(UTC)

    api_state = store.commit_api_checkpoint(
        session,
        tenant_id="tenant-a",
        provider="CAFE24",
        resource="products",
        connection_mode="API_POLL",
        cursor="offset:100",
        watermark=now,
        overlap_start=now - timedelta(minutes=10),
        last_success_at=now,
        canonical_committed=True,
    )

    file_state = store.commit_file_checkpoint(
        session,
        tenant_id="tenant-a",
        provider="CAFE24",
        resource="products",
        connection_mode="FILE_IMPORT",
        file_hash="sha256:test-file",
        batch_id="batch-001",
        row_number=500,
        last_success_at=now,
        canonical_committed=True,
    )

    assert api_state.id != file_state.id

    assert api_state.cursor == "offset:100"
    assert api_state.file_hash is None

    assert file_state.cursor is None
    assert file_state.file_hash == "sha256:test-file"
    assert file_state.batch_id == "batch-001"
    assert file_state.row_number == 500


def test_failed_file_row_does_not_advance_row_number(
    session: Session,
) -> None:
    store = CursorStore()
    now = datetime.now(UTC)

    store.commit_file_checkpoint(
        session,
        tenant_id="tenant-a",
        provider="CAFE24",
        resource="products",
        connection_mode="FILE_IMPORT",
        file_hash="sha256:test-file",
        batch_id="batch-001",
        row_number=100,
        last_success_at=now,
        canonical_committed=True,
    )

    failed = store.record_error(
        session,
        tenant_id="tenant-a",
        provider="CAFE24",
        resource="products",
        connection_mode="FILE_IMPORT",
        error_code="ROW_QUARANTINED",
    )

    assert failed.row_number == 100
    assert failed.last_error == "ROW_QUARANTINED"
