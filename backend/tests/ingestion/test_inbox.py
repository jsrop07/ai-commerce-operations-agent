import hashlib
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.db.base import Base
from backend.app.models.ingestion import EventInbox
from backend.app.services.demo import DEMO_SCENARIOS
from backend.app.services.ingestion.inbox import (
    InMemoryInbox,
    persist_accepted_event,
)


def test_inbox_tracks_protected_reference_without_raw_payload() -> None:
    inbox = InMemoryInbox()
    event, receipt = inbox.ingest(DEMO_SCENARIOS["offline_sale"])
    assert event is not None
    assert receipt.status == "ACCEPTED"
    assert receipt.protected_payload_ref.startswith("protected://payload/sha256/")
    assert "quantity" not in receipt.protected_payload_ref


def test_invalid_event_is_quarantined_and_reprocessable() -> None:
    inbox = InMemoryInbox()
    invalid = dict(DEMO_SCENARIOS["offline_sale"])
    invalid.pop("tenant_id")
    event, receipt = inbox.ingest(invalid)
    assert event is None
    assert receipt.status == "QUARANTINED"
    fixed = dict(invalid, tenant_id="demo_store")
    _, fixed_receipt = inbox.ingest(fixed)
    assert fixed_receipt.status == "ACCEPTED"


def test_accepted_event_persists_envelope_hash_and_protected_reference_only() -> None:
    raw = dict(DEMO_SCENARIOS["offline_sale"])
    raw["payload"] = {
        **raw["payload"],
        "customer_name": "CUSTOMER_NAME_SENTINEL",
        "phone": "PHONE_SENTINEL",
    }
    expected_hash = hashlib.sha256(
        json.dumps(raw, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()
    event, receipt = InMemoryInbox().ingest(raw)
    assert event is not None

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        row = persist_accepted_event(session, event, receipt)
        stored = session.get(EventInbox, row.id)
        assert stored is not None
        assert stored.tenant_id == event.tenant_id
        assert stored.event_id == event.event_id
        assert stored.source == event.source.value
        assert stored.source_event_id == event.source_event_id
        assert stored.schema_version == event.schema_version
        assert stored.event_hash == expected_hash == receipt.event_hash
        assert stored.protected_payload_ref == receipt.protected_payload_ref
        assert stored.event_hash not in stored.protected_payload_ref

        serialized_row = json.dumps(
            {column.name: getattr(stored, column.name) for column in EventInbox.__table__.columns},
            default=str,
            ensure_ascii=False,
        )
        assert "customer_name" not in serialized_row
        assert "CUSTOMER_NAME_SENTINEL" not in serialized_row
        assert "phone" not in serialized_row
        assert "PHONE_SENTINEL" not in serialized_row
        assert "payload" not in EventInbox.__table__.columns
    engine.dispose()


def test_duplicate_accepted_event_is_rejected_by_db_unique_constraint() -> None:
    event, receipt = InMemoryInbox().ingest(DEMO_SCENARIOS["offline_sale"])
    assert event is not None

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        persist_accepted_event(session, event, receipt)
        with pytest.raises(IntegrityError):
            persist_accepted_event(session, event, receipt)
        session.rollback()
        assert session.query(EventInbox).count() == 1
    engine.dispose()


def test_persistence_rejects_receipt_for_a_different_event() -> None:
    inbox = InMemoryInbox()
    first, receipt = inbox.ingest(DEMO_SCENARIOS["offline_sale"])
    second_raw = dict(DEMO_SCENARIOS["offline_sale"], event_id="evt_other")
    second_raw["idempotency_key"] = "TOSS_POS:synthetic-other:1.0"
    second_raw["source_event_id"] = "synthetic-other"
    second, _ = inbox.ingest(second_raw)
    assert first is not None and second is not None

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        with pytest.raises(ValueError, match="does not match"):
            persist_accepted_event(session, second, receipt)
        assert session.query(EventInbox).count() == 0
    engine.dispose()
