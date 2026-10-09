from types import SimpleNamespace
from uuid import UUID

import pytest

from backend.app.models_v2.operations import (
    IncomingShipmentV2,
    TaskIncomingDependencyV2,
    TaskV2,
)
from backend.app.services.demo import (
    DEMO_HERO_INCOMING_ID,
    DEMO_HERO_INCOMING_REFERENCE,
    DEMO_HERO_TASK_ID,
    DEMO_HERO_TASK_INCOMING_DEPENDENCY_TYPE,
    _ensure_demo_hero_task_incoming_dependency,
)


TENANT_ID = UUID(
    "35556e27-4200-4712-8ac5-e5a569a91c47"
)
PRODUCT_ID = UUID(
    "dd5e08e7-a9a7-5a91-a34b-e9e0bf3b9e09"
)


class FakeSession:
    def __init__(self):
        self.incoming = SimpleNamespace(
            id=DEMO_HERO_INCOMING_ID,
            tenant_id=TENANT_ID,
            product_id=PRODUCT_ID,
            external_reference=DEMO_HERO_INCOMING_REFERENCE,
        )
        self.task = SimpleNamespace(
            id=DEMO_HERO_TASK_ID,
            tenant_id=TENANT_ID,
            product_id=PRODUCT_ID,
            task_type="RESERVATION_SHORTAGE",
        )
        self.dependency = None
        self.commits = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def scalar(self, statement):
        model = statement.column_descriptions[0]["entity"]

        if model is IncomingShipmentV2:
            return self.incoming
        if model is TaskV2:
            return self.task
        if model is TaskIncomingDependencyV2:
            return self.dependency

        raise AssertionError(model)

    def add(self, row):
        self.dependency = row

    def commit(self):
        self.commits += 1


def _state(session):
    return SimpleNamespace(
        settings=SimpleNamespace(
            v2_tenant_id=TENANT_ID,
        ),
        v2_db_session_factory=lambda: session,
    )


def test_demo_hero_dependency_is_created_once():
    session = FakeSession()
    state = _state(session)

    first = _ensure_demo_hero_task_incoming_dependency(
        state
    )
    second = _ensure_demo_hero_task_incoming_dependency(
        state
    )

    assert first == 1
    assert second == 0
    assert session.commits == 1

    assert session.dependency.tenant_id == TENANT_ID
    assert session.dependency.task_id == DEMO_HERO_TASK_ID
    assert (
        session.dependency.incoming_shipment_id
        == DEMO_HERO_INCOMING_ID
    )
    assert (
        session.dependency.dependency_type
        == DEMO_HERO_TASK_INCOMING_DEPENDENCY_TYPE
    )


def test_demo_hero_dependency_fails_closed_on_wrong_identity():
    session = FakeSession()
    session.incoming.external_reference = "WRONG-INCOMING"

    with pytest.raises(
        ValueError,
        match="SYNTHETIC_RESERVATION_V2_RELATION_IDENTITY_CONFLICT",
    ):
        _ensure_demo_hero_task_incoming_dependency(
            _state(session)
        )


def test_demo_hero_dependency_keeps_old_in_memory_mode():
    state = SimpleNamespace(
        settings=SimpleNamespace(
            v2_tenant_id=None,
        ),
        v2_db_session_factory=None,
    )

    assert (
        _ensure_demo_hero_task_incoming_dependency(state)
        == 0
    )