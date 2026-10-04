"""C09 PRE contract tests on an isolated, ephemeral SQLite schema."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.conversations_v2 import router
from backend.app.core.config import Environment
from backend.app.db.base_v2 import BaseV2
from backend.app.models_v2.ai import AgentRunV2, ConversationV2, MessageContextV2, MessageV2
from backend.app.models_v2.catalog import ProductV2, ProductVariantV2
from backend.app.models_v2.operations import IncomingShipmentV2, TaskIncomingDependencyV2, TaskV2
from backend.app.models_v2.tenant import TenantV2
from backend.app.services.conversation_v2 import (
    C09ContractError,
    TargetInput,
    append_turn,
    create_conversation,
    read_conversation,
    recent_conversations,
    reopen_conversation,
)


@compiles(JSONB, "sqlite")
def _sqlite_jsonb(_type, _compiler, **_kw):
    return "JSON"


@pytest.fixture
def c09_db():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        execution_options={
            "schema_translate_map": {
                "public": None,
                "ai": None,
                "catalog": None,
                "operations": None,
            }
        },
    )
    tables = [
        model.__table__
        for model in (
            TenantV2,
            ProductV2,
            ProductVariantV2,
            IncomingShipmentV2,
            TaskV2,
            TaskIncomingDependencyV2,
            ConversationV2,
            MessageV2,
            MessageContextV2,
            AgentRunV2,
        )
    ]
    BaseV2.metadata.create_all(engine, tables=tables)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as session:
        tenant = TenantV2(name="commerce_ops_local", environment="LOCAL", status="ACTIVE")
        other = TenantV2(name="other", environment="LOCAL", status="ACTIVE")
        session.add_all([tenant, other])
        session.flush()
        product_a = ProductV2(
            tenant_id=tenant.id,
            cafe24_product_no=101,
            product_name="Catalog A",
            product_code="C09_A",
            custom_product_code=None,
            sale_price=None,
            display_status="T",
            selling_status="T",
            sold_out=False,
            operational=True,
            source_as_of=None,
        )
        product_b = ProductV2(
            tenant_id=tenant.id,
            cafe24_product_no=102,
            product_name="Catalog B",
            product_code="C09_B",
            custom_product_code=None,
            sale_price=None,
            display_status="T",
            selling_status="T",
            sold_out=False,
            operational=True,
            source_as_of=None,
        )
        other_product = ProductV2(
            tenant_id=other.id,
            cafe24_product_no=999,
            product_name="Other tenant",
            product_code="OTHER",
            custom_product_code=None,
            sale_price=None,
            display_status="T",
            selling_status="T",
            sold_out=False,
            operational=True,
            source_as_of=None,
        )
        session.add_all([product_a, product_b, other_product])
        session.flush()
        incoming = IncomingShipmentV2(
            tenant_id=tenant.id,
            product_id=product_a.id,
            product_variant_id=None,
            expected_quantity=5,
            expected_arrival_at=None,
            incoming_status="EXPECTED",
            confidence_status="TENTATIVE",
            source_system=None,
            external_reference=None,
        )
        task = TaskV2(
            tenant_id=tenant.id,
            task_type="REVIEW",
            task_title="Review A",
            task_status="PROPOSED",
            priority=None,
            product_id=product_a.id,
            due_at=None,
            source_reason=None,
        )
        session.add_all([incoming, task])
        session.commit()
        ids = {
            "tenant": tenant.id,
            "other": other.id,
            "a": product_a.id,
            "b": product_b.id,
            "incoming": incoming.id,
            "task": task.id,
        }
    yield factory, ids
    engine.dispose()


def product(number=101, label="Catalog A", as_of=None):
    return TargetInput("PRODUCT", str(number), label, "CAFE24_CATALOG", as_of)


def incoming_target(value):
    return TargetInput("INCOMING", str(value), f"INCOMING {value}", "OPERATIONS_INCOMING", None)


def task_target(value):
    return TargetInput("TASK", str(value), f"TASK {value}", "OPERATIONS_TASK", None)


def test_create_resolves_product_number_to_same_tenant_uuid(c09_db):
    factory, ids = c09_db
    with factory() as session:
        row = create_conversation(
            session, tenant_id=ids["tenant"], actor_id="actor.one", target=product()
        )
        view = read_conversation(
            session, tenant_id=ids["tenant"], actor_id="actor.one", conversation_id=row.id
        )
        stored = session.scalar(
            select(MessageContextV2).where(MessageContextV2.tenant_id == ids["tenant"])
        )
        assert stored.product_id == ids["a"]
        assert view["conversation_status"] == "ACTIVE"
        assert view["current_context_revision"] == 1
        assert view["context"]["target_id"] == "101"
        assert view["context"]["source_as_of"] is None
        assert view["messages"][0]["message_order"] == 0
        assert view["messages"][0]["response_status"] == "HOLD"
        assert view["messages"][0]["analysis_kind"] == "NONE"


def test_related_continuation_orders_messages_and_freezes_prior_context(c09_db):
    factory, ids = c09_db
    with factory() as session:
        row = create_conversation(
            session, tenant_id=ids["tenant"], actor_id="actor.one", target=product()
        )
        append_turn(
            session,
            tenant_id=ids["tenant"],
            actor_id="actor.one",
            conversation_id=row.id,
            target=product(),
            intent="INSPECT_TARGET",
        )
        append_turn(
            session,
            tenant_id=ids["tenant"],
            actor_id="actor.one",
            conversation_id=row.id,
            target=incoming_target(ids["incoming"]),
            intent="FOLLOW_RELATED_TARGET",
        )
        append_turn(
            session,
            tenant_id=ids["tenant"],
            actor_id="actor.one",
            conversation_id=row.id,
            target=task_target(ids["task"]),
            intent="FOLLOW_RELATED_TARGET",
        )
        view = read_conversation(
            session, tenant_id=ids["tenant"], actor_id="actor.one", conversation_id=row.id
        )
        assert [item["message_order"] for item in view["messages"]] == [0, 1, 2, 3]
        assert [item["context"]["context_revision"] for item in view["messages"]] == [1, 1, 2, 3]
        assert [item["context"]["target_type"] for item in view["messages"]] == [
            "PRODUCT",
            "PRODUCT",
            "INCOMING",
            "TASK",
        ]
        assert view["current_context_revision"] == 3
        assert view["messages"][0]["context"]["target_id"] == "101"


def test_unrelated_target_requires_new_conversation_and_recent_reopen_are_owned(c09_db):
    factory, ids = c09_db
    with factory() as session:
        first = create_conversation(
            session, tenant_id=ids["tenant"], actor_id="actor.one", target=product()
        )
        with pytest.raises(C09ContractError) as raised:
            append_turn(
                session,
                tenant_id=ids["tenant"],
                actor_id="actor.one",
                conversation_id=first.id,
                target=product(102, "Catalog B"),
                intent="FOLLOW_RELATED_TARGET",
            )
        assert raised.value.status == "CONFLICT"
        assert raised.value.code == "UNRELATED_TARGET_NEW_CONVERSATION_REQUIRED"
        second = create_conversation(
            session, tenant_id=ids["tenant"], actor_id="actor.one", target=product(102, "Catalog B")
        )
        assert second.id != first.id
        assert (
            len(recent_conversations(session, tenant_id=ids["tenant"], actor_id="actor.one")) == 2
        )
        first.conversation_status = "CLOSED"
        session.commit()
        reopened = reopen_conversation(
            session, tenant_id=ids["tenant"], actor_id="actor.one", conversation_id=first.id
        )
        assert reopened.conversation_status == "ACTIVE"
        assert (
            read_conversation(
                session, tenant_id=ids["tenant"], actor_id="actor.one", conversation_id=first.id
            )["current_context_revision"]
            == 1
        )
        for tenant_id, actor_id in ((ids["other"], "actor.one"), (ids["tenant"], "actor.two")):
            with pytest.raises(C09ContractError) as missing:
                read_conversation(
                    session, tenant_id=tenant_id, actor_id=actor_id, conversation_id=first.id
                )
            assert missing.value.status == "MISSING"


@pytest.mark.parametrize(
    "target,expected",
    [
        (product(999, "Other tenant"), "MISSING"),
        (product(101, "Wrong label"), "CONFLICT"),
        (product(101, "Catalog A", datetime(2026, 9, 1, tzinfo=UTC)), "STALE"),
        (product(101, "customer@example.com"), "HOLD"),
        (product(101, "010-1234-5678"), "HOLD"),
        (product(101, "고객 이름 홍길동"), "HOLD"),
        (product(101, "20260101-123456"), "HOLD"),
    ],
)
def test_missing_stale_and_forbidden_inputs_never_write(c09_db, target, expected):
    factory, ids = c09_db
    with factory() as session:
        before = session.scalar(select(func.count()).select_from(ConversationV2))
        with pytest.raises(C09ContractError) as raised:
            create_conversation(
                session, tenant_id=ids["tenant"], actor_id="actor.one", target=target
            )
        assert raised.value.status == expected
        assert session.scalar(select(func.count()).select_from(ConversationV2)) == before
        assert session.scalar(select(func.count()).select_from(MessageV2)) == 0


def test_api_requires_trusted_server_actor_and_rejects_extra_raw_input(c09_db):
    factory, ids = c09_db
    app = FastAPI()
    app.state.settings = type(
        "Settings", (), {"environment": Environment.TEST, "v2_tenant_id": ids["tenant"]}
    )()
    app.state.v2_db_session_factory = factory
    app.include_router(router)
    context = {
        "targetType": "PRODUCT",
        "targetId": "101",
        "targetLabel": "Catalog A",
        "source": "CAFE24_CATALOG",
        "asOf": None,
    }
    client = TestClient(app)
    assert (
        client.post(
            "/api/v1/conversations", json={"context": context}, headers={"X-Actor-ID": "actor.one"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/conversations", json={"context": context, "content": "customer name"}
        ).status_code
        == 422
    )

    trusted_app = FastAPI()
    trusted_app.state.settings = app.state.settings
    trusted_app.state.v2_db_session_factory = factory
    trusted_app.include_router(router)

    @trusted_app.middleware("http")
    async def trusted_actor(request: Request, call_next):
        request.scope["c09_trusted_actor_id"] = "actor.one"
        return await call_next(request)

    client = TestClient(trusted_app)
    response = client.post("/api/v1/conversations", json={"context": context})
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["context"]["target_id"] == "101"
    assert data["messages"][0]["response_status"] == "HOLD"
    appended = client.post(
        f"/api/v1/conversations/{data['conversation_id']}/messages",
        json={"context": context, "intent": "INSPECT_TARGET"},
    )
    assert appended.status_code == 200
    assert [message["message_order"] for message in appended.json()["data"]["messages"]] == [0, 1]
    forbidden = client.post(
        f"/api/v1/conversations/{data['conversation_id']}/messages",
        json={
            "context": {**context, "targetLabel": "customer@example.com"},
            "intent": "INSPECT_TARGET",
        },
    )
    assert forbidden.status_code == 422
    assert forbidden.json()["detail"]["status"] == "HOLD"
    assert client.get(f"/api/v1/conversations/{data['conversation_id']}").status_code == 200
    assert len(client.get("/api/v1/conversations").json()["data"]) == 1
    assert client.post(f"/api/v1/conversations/{data['conversation_id']}/reopen").status_code == 200
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(ConversationV2)) == 1
        assert session.scalar(select(func.count()).select_from(MessageV2)) == 2


def test_missing_context_reports_error_before_append(c09_db):
    factory, ids = c09_db
    with factory() as session:
        row = create_conversation(
            session, tenant_id=ids["tenant"], actor_id="actor.one", target=product()
        )
        context = session.scalar(
            select(MessageContextV2).where(MessageContextV2.tenant_id == ids["tenant"])
        )
        session.delete(context)
        session.commit()
        with pytest.raises(C09ContractError) as raised:
            append_turn(
                session,
                tenant_id=ids["tenant"],
                actor_id="actor.one",
                conversation_id=row.id,
                target=product(),
                intent="INSPECT_TARGET",
            )
        assert raised.value.status == "ERROR"
        assert session.scalar(select(func.count()).select_from(MessageV2)) == 1


def test_existing_agent_run_reference_is_read_only(c09_db):
    factory, ids = c09_db
    with factory() as session:
        row = create_conversation(
            session, tenant_id=ids["tenant"], actor_id="actor.one", target=product()
        )
        session.add(
            AgentRunV2(
                tenant_id=ids["tenant"],
                conversation_id=row.id,
                workflow_id="existing-workflow",
                thread_id="existing-thread",
                current_node="wait_for_human",
                run_status="WAITING",
                state={},
                state_schema_version=1,
                checkpoint_version=1,
                checkpoint_at=None,
                evidence_ids=[],
                model_version=None,
                prompt_version=None,
                cost=None,
                output_hash=None,
                reason=None,
            )
        )
        session.commit()
        view = read_conversation(
            session, tenant_id=ids["tenant"], actor_id="actor.one", conversation_id=row.id
        )
        assert view["agent_runs"] == [
            {
                "workflow_id": "existing-workflow",
                "thread_id": "existing-thread",
                "run_status": "WAITING",
            }
        ]
