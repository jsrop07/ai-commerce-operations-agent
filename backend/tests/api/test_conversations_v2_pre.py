"""C09 PRE contract tests on an isolated, ephemeral SQLite schema."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from typing import get_args, get_type_hints
from uuid import UUID

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from ai.evaluation.r09_conversation_contract import ConversationStatus
from backend.app.api.conversations_v2 import AppendTurnInput, MessageView, router
from backend.app.core.config import Environment, Settings
from backend.app.db.base_v2 import BaseV2
from backend.app.main import create_app
from backend.app.models_v2.ai import (
    AgentRunV2, ConversationV2, MessageContextV2, MessageV2, RagChunkV2,
)
from backend.app.models_v2.catalog import CategoryV2, ProductV2, ProductVariantV2
from backend.app.models_v2.operations import (
    IncomingShipmentV2,
    OrderItemV2,
    OrderV2,
    TaskIncomingDependencyV2,
    TaskV2,
)
from backend.app.models_v2.tenant import TenantV2
from backend.app.services.c04_lookup import C04LookupService
from backend.app.services.c09_order_aggregate import safe_reservation_aggregate
from backend.app.services.conversation_v2 import (
    AnalysisKind,
    C09ContractError,
    ContractErrorStatus,
    Intent,
    MessageResponseStatus,
    TargetInput,
    analyze_turn,
    append_turn,
    begin_analysis_request,
    complete_analysis_request,
    create_conversation,
    message_status_for_ai,
    read_conversation,
    recent_conversations,
    reopen_conversation,
)
from backend.app.services.current_reservation_demand import (
    CurrentReservationDemand,
    CurrentReservationDemandProjection,
    CurrentReservationReviewItem,
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
            CategoryV2,
            OrderV2,
            OrderItemV2,
            IncomingShipmentV2,
            TaskV2,
            TaskIncomingDependencyV2,
            ConversationV2,
            MessageV2,
            MessageContextV2,
            AgentRunV2,
            RagChunkV2,
        )
    ]
    BaseV2.metadata.create_all(engine, tables=tables)
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE rag_chunks ADD COLUMN embedding TEXT"))
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
        session.add(CategoryV2(
            tenant_id=tenant.id, cafe24_category_no=1,
            category_name="Games Workshop", parent_category_id=None,
            category_depth=1, source_as_of=None,
        ))
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


def test_c09_message_type_contract():
    assert get_args(Intent) == ("INSPECT_TARGET", "FOLLOW_RELATED_TARGET")
    assert get_args(AnalysisKind) == ("NONE", "DETERMINISTIC", "HYBRID", "RELATION_DOCUMENT")
    assert get_args(MessageResponseStatus) == ("ANSWER", "NO_EDGE", "HOLD")
    assert get_args(ContractErrorStatus) == ("HOLD", "MISSING", "STALE", "ERROR", "CONFLICT")
    assert MessageResponseStatus is not ContractErrorStatus
    assert get_type_hints(C09ContractError.__init__)["status"] is ContractErrorStatus
    assert MessageView.model_fields["response_status"].annotation is MessageResponseStatus
    assert MessageView.model_fields["analysis_kind"].annotation == AnalysisKind | None
    assert MessageView.model_fields["evidence_ids"].annotation == list[str]
    assert set(AppendTurnInput.model_fields) == {
        "context", "intent", "analysis_kind", "request_revision",
    }


class ProductSearchStub:
    def __init__(self, ids):
        self.ids = ids
        self.calls = []

    def resolve_product_ids(self, *, session, tenant_id, query):
        self.calls.append((tenant_id, query))
        return self.ids


def _product_search_payload(query, revision=1):
    return {"query": query, "intent": "INSPECT_TARGET", "request_revision": revision}


def test_product_search_resolves_before_context_freeze_without_saving_query(c09_db, monkeypatch):
    factory, ids = c09_db
    client = _configured_app(c09_db, Environment.TEST, "actor.one")
    search = ProductSearchStub([ids["a"]])
    client.app.state.product_search_service = search
    monkeypatch.setattr("openai.OpenAI", lambda *a, **kw: pytest.fail("provider called"))
    created = client.post("/api/v1/conversations", json={"context": _CONTEXT})
    cid = created.json()["data"]["conversation_id"]
    query = "가벼운 보드게임 추천"
    response = client.post(
        f"/api/v1/conversations/{cid}/product-search/messages",
        json=_product_search_payload(query),
    )
    assert response.status_code == 200, response.text
    assert search.calls == [(ids["tenant"], query)]
    messages = response.json()["data"]["messages"]
    assert messages[-2]["context"]["target_id"] == "101"
    assert messages[-2]["analysis_kind"] == "HYBRID"
    assert messages[-1]["response_status"] == "HOLD"  # no C16 chunk in this fixture
    with factory() as session:
        stored = session.scalars(select(MessageV2).where(
            MessageV2.conversation_id == UUID(cid),
        )).all()
        contexts = session.scalars(select(MessageContextV2).join(
            MessageV2, MessageV2.id == MessageContextV2.message_id,
        ).where(MessageV2.conversation_id == UUID(cid))).all()
    assert all(query not in row.content for row in stored)
    assert all(query not in str(row.source_versions) for row in contexts)
    frozen = next(row for row in contexts if row.message_id == UUID(messages[-2]["message_id"]))
    assert frozen.product_id == ids["a"]


def test_product_search_exact_code_and_id_work_without_search_service(c09_db):
    _, ids = c09_db
    client = _configured_app(c09_db, Environment.TEST, "actor.one")
    cid = client.post("/api/v1/conversations", json={"context": _CONTEXT}).json()[
        "data"
    ]["conversation_id"]
    path = f"/api/v1/conversations/{cid}/product-search/messages"
    assert client.post(path, json=_product_search_payload("product_code:C09_A")).status_code == 200
    assert client.post(path, json=_product_search_payload(f"product_id:{ids['a']}")).status_code == 200
    assert client.post(path, json=_product_search_payload("가벼운 보드게임")).json()["detail"] == {
        "status": "HOLD", "code": "PRODUCT_SEARCH_UNAVAILABLE",
    }


def test_product_search_can_open_new_conversation_after_resolution(c09_db):
    factory, ids = c09_db
    client = _configured_app(c09_db, Environment.TEST, "actor.one")
    search = ProductSearchStub([ids["b"]])
    client.app.state.product_search_service = search
    query = "다른 보드게임 찾아줘"
    created = client.post("/api/v1/conversations/product-search", json={"query": query})
    assert created.status_code == 201, created.text
    view = created.json()["data"]
    assert view["context"]["target_id"] == "102"
    assert view["messages"][-2]["analysis_kind"] == "HYBRID"
    assert search.calls == [(ids["tenant"], query)]
    assert all(query not in item["content"] for item in view["messages"])
    with factory() as session:
        rows = session.scalars(select(MessageContextV2).join(
            MessageV2, MessageV2.id == MessageContextV2.message_id,
        ).where(MessageV2.conversation_id == UUID(view["conversation_id"]))).all()
    assert all(query not in str(row.source_versions) for row in rows)
    assert {row.product_id for row in rows} == {ids["b"]}

    search.ids = []
    missing = client.post("/api/v1/conversations/product-search", json={"query": "없는 상품"})
    assert missing.status_code == 404
    assert len(client.get("/api/v1/conversations").json()["data"]) == 1


@pytest.mark.parametrize("query", [
    "customer@example.com", "order_id=123", "고객 이름 홍길동", "payment details 123",
    "배송지 서울", "문의 원문", "010-1234-5678", "보드게임\n주문 목록",
])
def test_product_search_sensitive_input_fails_closed_without_writes(c09_db, query):
    client = _configured_app(c09_db, Environment.TEST, "actor.one")
    search = ProductSearchStub([])
    client.app.state.product_search_service = search
    cid = client.post("/api/v1/conversations", json={"context": _CONTEXT}).json()[
        "data"
    ]["conversation_id"]
    response = client.post(
        f"/api/v1/conversations/{cid}/product-search/messages",
        json=_product_search_payload(query),
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "PRODUCT_SEARCH_INPUT_FORBIDDEN"
    assert search.calls == []
    assert len(client.get(f"/api/v1/conversations/{cid}").json()["data"]["messages"]) == 1


def test_product_search_missing_ambiguous_stale_and_other_actor_do_not_change_context(c09_db):
    _, ids = c09_db
    owner = _configured_app(c09_db, Environment.TEST, "actor.one")
    search = ProductSearchStub([])
    owner.app.state.product_search_service = search
    cid = owner.post("/api/v1/conversations", json={"context": _CONTEXT}).json()[
        "data"
    ]["conversation_id"]
    path = f"/api/v1/conversations/{cid}/product-search/messages"
    assert owner.post(path, json=_product_search_payload("보드게임")).status_code == 404
    search.ids = [ids["a"], ids["b"]]
    assert owner.post(path, json=_product_search_payload("보드게임")).status_code == 409
    search.ids = [ids["a"]]
    stale = owner.post(path, json=_product_search_payload("보드게임", revision=2))
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "REQUEST_REVISION_MISMATCH"
    other = _configured_app(c09_db, Environment.TEST, "actor.two")
    other.app.state.product_search_service = search
    before = len(search.calls)
    assert other.post(path, json=_product_search_payload("보드게임")).status_code == 404
    assert len(search.calls) == before
    view = owner.get(f"/api/v1/conversations/{cid}").json()["data"]
    assert len(view["messages"]) == 1
    assert view["context"]["target_id"] == "101"

def _configured_app(c09_db, environment, actor_id):
    factory, ids = c09_db
    settings = Settings(
        _env_file=None,
        environment=environment,
        database_url="sqlite://",
        v2_tenant_id=ids["tenant"],
        c09_dev_actor_id=actor_id,
    )
    app = create_app(
        settings,
        db_engine=factory.kw["bind"],
        v2_db_engine=factory.kw["bind"],
        c04_lookup_service=C04LookupService(),
    )

    @app.get("/c09-scope-probe")
    def scope_probe(request: Request):
        return {"actor": request.scope.get("c09_trusted_actor_id")}

    return TestClient(app)


_CONTEXT = {
    "targetType": "PRODUCT",
    "targetId": "101",
    "targetLabel": "Catalog A",
    "source": "CAFE24_CATALOG",
    "asOf": None,
}


def test_dev_actor_default_off_and_client_assertions_do_not_authorize(
    c09_db,
    monkeypatch,
):
    monkeypatch.delenv(
        "C09_DEV_ACTOR_ID",
        raising=False,
    )

    assert Settings(
        _env_file=None,
        environment=Environment.LOCAL,
    ).c09_dev_actor_id is None
    client = _configured_app(c09_db, Environment.LOCAL, None)
    assert client.get("/c09-scope-probe").json() == {"actor": None}
    post = client.post(
        "/api/v1/conversations?actor_id=actor.one",
        json={"context": _CONTEXT},
        headers={"X-Actor-Id": "actor.one"},
    )
    assert (post.status_code, post.json()["detail"]) == (403, "C09_TRUSTED_ACTOR_REQUIRED")
    listing = client.get("/api/v1/conversations")
    assert (listing.status_code, listing.json()["detail"]) == (403, "C09_TRUSTED_ACTOR_REQUIRED")
    body = client.request("GET", "/api/v1/conversations", json={"actor_id": "actor.one"})
    assert (body.status_code, body.json()["detail"]) == (403, "C09_TRUSTED_ACTOR_REQUIRED")
    asserted_body = client.post(
        "/api/v1/conversations", json={"context": _CONTEXT, "actor_id": "actor.one"}
    )
    assert asserted_body.status_code == 422


@pytest.mark.parametrize("environment", [Environment.LOCAL, Environment.TEST])
def test_dev_actor_injected_only_from_server_settings(c09_db, environment):
    client = _configured_app(c09_db, environment, "actor.one")
    assert client.get("/c09-scope-probe").json() == {"actor": "actor.one"}
    response = client.post("/api/v1/conversations", json={"context": _CONTEXT})
    assert response.status_code == 201
    assert response.json()["data"]["messages"][0]["analysis_kind"] == "NONE"
    assert response.json()["data"]["messages"][0]["response_status"] == "HOLD"


@pytest.mark.parametrize("environment", [Environment.DEMO, Environment.PRODUCTION_READ])
def test_dev_actor_is_inactive_outside_local_and_test(c09_db, environment):
    client = _configured_app(c09_db, environment, "actor.one")
    assert client.get("/c09-scope-probe").json() == {"actor": None}
    response = client.post("/api/v1/conversations", json={"context": _CONTEXT})
    assert (response.status_code, response.json()["detail"]) == (403, "C09_TRUSTED_ACTOR_REQUIRED")


@pytest.mark.parametrize("actor_id", ["", "bad actor", "actor/one", "a" * 129])
def test_invalid_dev_actor_setting_fails_closed(actor_id):
    with pytest.raises(ValidationError, match="invalid C09 actor format"):
        Settings(_env_file=None, environment=Environment.LOCAL, c09_dev_actor_id=actor_id)


def _analysis_payload(context=None, revision=1, kind="DETERMINISTIC"):
    return {
        "context": context or _CONTEXT,
        "intent": "INSPECT_TARGET",
        "analysis_kind": kind,
        "request_revision": revision,
    }


def test_ai_status_mapping_is_explicit_and_error_fails_closed():
    assert message_status_for_ai(ConversationStatus.ANSWER) == "ANSWER"
    assert message_status_for_ai(ConversationStatus.NO_EDGE) == "NO_EDGE"
    assert message_status_for_ai(ConversationStatus.HOLD) == "HOLD"
    with pytest.raises(C09ContractError, match="UNSUPPORTED_AI_STATUS"):
        message_status_for_ai(ConversationStatus.ERROR)


@pytest.mark.parametrize("kind", ["DETERMINISTIC", "HYBRID", "RELATION_DOCUMENT"])
def test_analysis_persists_ordered_user_and_assistant_with_snapshot(c09_db, kind):
    factory, _ = c09_db
    client = _configured_app(c09_db, Environment.TEST, "actor.one")
    created = client.post("/api/v1/conversations", json={"context": _CONTEXT}).json()["data"]
    conversation_id = created["conversation_id"]
    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json=_analysis_payload(kind=kind),
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["current_context_revision"] == 1
    assert [m["message_order"] for m in data["messages"]] == [0, 1, 2]
    assert [m["role"] for m in data["messages"]] == ["USER", "USER", "ASSISTANT"]
    assert [m["context"]["context_revision"] for m in data["messages"]] == [1, 1, 1]
    assistant = data["messages"][2]
    assert assistant["analysis_kind"] == kind
    assert assistant["response_status"] == "HOLD"
    assert assistant["context"] == data["messages"][1]["context"]
    assert assistant["content"].splitlines()[0].startswith("결론:")
    assert [line.split(":", 1)[0] for line in assistant["content"].splitlines()] == [
        "결론", "핵심 수치/상태", "근거", "다음 확인/조치"
    ]
    assert all(token not in assistant["content"] for token in ("재고 수량:", "입고 예정:", "Task:"))
    assert client.get(f"/api/v1/conversations/{conversation_id}").json()["data"] == data
    with factory() as session:
        rows = session.scalars(
            select(MessageV2).where(MessageV2.conversation_id == UUID(data["conversation_id"]))
        ).all()
        assert len(rows) == 3
    


@pytest.mark.parametrize("kind", ["HYBRID", "RELATION_DOCUMENT"])
def test_unwired_analysis_dispatch_holds_without_running_deterministic(
    c09_db, monkeypatch, kind,
):
    factory, ids = c09_db
    calls = []

    def forbidden_analysis(*args, **kwargs):
        calls.append("analysis")
        raise AssertionError("unwired analysis called")

    monkeypatch.setattr(
        "backend.app.services.conversation_v2._safe_analysis", forbidden_analysis,
    )
    with factory() as session:
        conversation = create_conversation(
            session, tenant_id=ids["tenant"], actor_id="actor.one", target=product(),
        )
        request = begin_analysis_request(
            session, tenant_id=ids["tenant"], actor_id="actor.one",
            conversation_id=conversation.id, target=product(), intent="INSPECT_TARGET",
            analysis_kind=kind, request_revision=1,
        )
        complete_analysis_request(
            session, tenant_id=ids["tenant"], actor_id="actor.one",
            conversation_id=conversation.id, request_message_id=request.id,
        )
        view = read_conversation(
            session, tenant_id=ids["tenant"], actor_id="actor.one",
            conversation_id=conversation.id,
        )
    assert calls == []
    assert view["messages"][-1]["response_status"] == "HOLD"
    assert view["messages"][-1]["evidence_ids"] == []
    assert f"분석 방식: {kind}" in view["messages"][-1]["content"]
    assert view["messages"][-1]["request_message_id"] == str(request.id)
    

def test_hybrid_uses_exact_frozen_product_chunk_without_provider(c09_db, monkeypatch):
    factory, ids = c09_db
    calls = []

    def forbidden_provider(*args, **kwargs):
        calls.append("provider")
        raise AssertionError("HYBRID evidence lookup invoked a provider")

    monkeypatch.setattr("openai.OpenAI", forbidden_provider)
    with factory() as session:
        product_row = session.get(ProductV2, ids["a"])
        chunk_text = f"상품명: {product_row.product_name}\n상품 코드: {product_row.product_code}"
        session.add(RagChunkV2(
            tenant_id=ids["tenant"], source_type="PRODUCT",
            source_id=str(product_row.id), source_version="c15-test-v1",
            chunk_no=0, chunk_text=chunk_text,
            content_hash=sha256(chunk_text.encode()).hexdigest(),
            metadata_json={"data_mode": "SYNTHETIC_DEMO", "product_code": product_row.product_code},
            is_current=True,
        ))
        session.commit()
        session.execute(text(
            "UPDATE rag_chunks SET embedding = 'stored-vector' WHERE source_id = :source_id"
        ), {"source_id": str(product_row.id)})
        session.commit()
    client = _configured_app(c09_db, Environment.TEST, "actor.one")
    created = client.post("/api/v1/conversations", json={"context": _CONTEXT})
    cid = created.json()["data"]["conversation_id"]
    response = client.post(
        f"/api/v1/conversations/{cid}/messages",
        json=_analysis_payload(kind="HYBRID"),
    )
    assert response.status_code == 200, response.text
    assistant = response.json()["data"]["messages"][-1]
    assert assistant["response_status"] == "ANSWER"
    assert assistant["evidence_ids"] == [
        f"rag:PRODUCT:{ids['a']}:c15-test-v1:0"
    ]
    assert "상품 코드: C09_A" in assistant["content"]
    assert calls == []
    with factory() as session:
        context = session.scalar(select(MessageContextV2).where(
            MessageContextV2.message_id == UUID(assistant["message_id"]),
        ))
        assert context.source_versions["c18_retrieval"] == [{
            "evidence_id": assistant["evidence_ids"][0],
            "source_type": "PRODUCT", "source_id": str(ids["a"]),
            "source_version": "c15-test-v1", "chunk_no": 0,
            "method": "EXACT_PRODUCT_ID", "rank": 1, "score": None,
        }]
        assert "c18_retrieval" in context.source_versions
        assert "c17_relation_evidence" not in context.source_versions

def test_hybrid_without_frozen_product_context_holds(c09_db):
    factory, ids = c09_db
    with factory() as session:
        target = incoming_target(ids["incoming"])
        conversation = create_conversation(
            session, tenant_id=ids["tenant"], actor_id="actor.one", target=target,
        )
        analyze_turn(
            session, tenant_id=ids["tenant"], actor_id="actor.one",
            conversation_id=conversation.id, target=target,
            intent="INSPECT_TARGET", analysis_kind="HYBRID", request_revision=1,
        )
        view = read_conversation(
            session, tenant_id=ids["tenant"], actor_id="actor.one",
            conversation_id=conversation.id,
        )
    assert view["messages"][-1]["response_status"] == "HOLD"
    assert view["messages"][-1]["evidence_ids"] == []


def test_analysis_requires_actor_and_owner_without_leaking_content(c09_db):
    owner = _configured_app(c09_db, Environment.TEST, "actor.one")
    conversation_id = owner.post("/api/v1/conversations", json={"context": _CONTEXT}).json()[
        "data"
    ]["conversation_id"]
    path = f"/api/v1/conversations/{conversation_id}/messages"
    anonymous = _configured_app(c09_db, Environment.TEST, None)
    denied = anonymous.post(path, json=_analysis_payload(), headers={"X-Actor-ID": "actor.one"})
    assert (denied.status_code, denied.json()["detail"]) == (403, "C09_TRUSTED_ACTOR_REQUIRED")
    other = _configured_app(c09_db, Environment.TEST, "actor.two")
    missing = other.post(path, json=_analysis_payload())
    assert missing.status_code == 404
    assert missing.json()["detail"] == {"status": "MISSING", "code": "CONVERSATION_NOT_FOUND"}
    owner_view = owner.get(f"/api/v1/conversations/{conversation_id}").json()["data"]
    owner_messages = owner_view["messages"]
    assert len(owner_messages) == 1


def test_analysis_rejects_stale_revision_and_forbidden_input_before_write(c09_db):
    client = _configured_app(c09_db, Environment.TEST, "actor.one")
    conversation_id = client.post("/api/v1/conversations", json={"context": _CONTEXT}).json()[
        "data"
    ]["conversation_id"]
    path = f"/api/v1/conversations/{conversation_id}/messages"
    stale = client.post(path, json=_analysis_payload(revision=2))
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "REQUEST_REVISION_MISMATCH"
    forbidden = client.post(
        path,
        json=_analysis_payload(context={**_CONTEXT, "targetLabel": "customer@example.com"}),
    )
    assert forbidden.status_code == 422
    assert forbidden.json()["detail"]["code"] == "FORBIDDEN_INPUT"
    messages = client.get(f"/api/v1/conversations/{conversation_id}").json()["data"]["messages"]
    assert len(messages) == 1


def test_analysis_rejects_incomplete_contract_and_raw_content(c09_db):
    client = _configured_app(c09_db, Environment.TEST, "actor.one")
    conversation_id = client.post("/api/v1/conversations", json={"context": _CONTEXT}).json()[
        "data"
    ]["conversation_id"]
    path = f"/api/v1/conversations/{conversation_id}/messages"
    incomplete = client.post(path, json={**_analysis_payload(), "request_revision": None})
    assert incomplete.status_code == 422
    assert incomplete.json()["detail"]["code"] == "INCOMPLETE_ANALYSIS_REQUEST"
    none_kind = client.post(path, json={**_analysis_payload(), "analysis_kind": "NONE"})
    assert none_kind.status_code == 422
    assert none_kind.json()["detail"]["code"] == "INCOMPLETE_ANALYSIS_REQUEST"
    raw = client.post(path, json={**_analysis_payload(), "content": "order_id=123"})
    assert raw.status_code == 422
    view = client.get(f"/api/v1/conversations/{conversation_id}").json()["data"]
    assert len(view["messages"]) == 1


def test_related_analysis_increments_revision_without_changing_old_snapshot(c09_db):
    _, ids = c09_db
    client = _configured_app(c09_db, Environment.TEST, "actor.one")
    conversation_id = client.post("/api/v1/conversations", json={"context": _CONTEXT}).json()[
        "data"
    ]["conversation_id"]
    incoming_context = {
        "targetType": "INCOMING",
        "targetId": str(ids["incoming"]),
        "targetLabel": f"INCOMING {ids['incoming']}",
        "source": "OPERATIONS_INCOMING",
        "asOf": None,
    }
    path = f"/api/v1/conversations/{conversation_id}/messages"
    payload = _analysis_payload(context=incoming_context, kind="DETERMINISTIC")
    payload["intent"] = "FOLLOW_RELATED_TARGET"
    response = client.post(path, json=payload)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["current_context_revision"] == 2
    assert [m["context"]["context_revision"] for m in data["messages"]] == [1, 2, 2]
    assert data["messages"][0]["context"]["target_type"] == "PRODUCT"
    late = client.post(path, json=_analysis_payload(revision=1))
    assert late.status_code == 409
    assert late.json()["detail"]["code"] == "REQUEST_REVISION_MISMATCH"
    final_view = client.get(f"/api/v1/conversations/{conversation_id}").json()["data"]
    final_messages = final_view["messages"]
    assert len(final_messages) == 3


def test_view_context_empty_and_structured_filters_round_trip(c09_db):
    client = _configured_app(c09_db, Environment.TEST, "actor.one")
    empty = {"scope": "VIEW", "page": "PRODUCT_INVENTORY", "filters": {}}
    created = client.post("/api/v1/conversations", json={"context": empty})
    assert created.status_code == 201
    data = created.json()["data"]
    assert data["context"]["scope"] == "VIEW"
    assert data["context"]["page"] == "PRODUCT_INVENTORY"
    assert data["context"]["filters"] == {}
    structured = {
        "scope": "VIEW", "page": "PRODUCT_INVENTORY",
        "filters": {"selling": True, "sold_out": True, "major_category": "Games Workshop"},
        "search": "warhammer", "sort": {"by": "sale_price", "direction": "desc"},
        "date_range": {
            "from_date": "2026-10-01T00:00:00Z",
            "to_date": "2026-10-04T00:00:00Z",
        },
    }
    path = f"/api/v1/conversations/{data['conversation_id']}/messages"
    payload = _analysis_payload(context=structured)
    payload["intent"] = "FOLLOW_RELATED_TARGET"
    response = client.post(path, json=payload)
    assert response.status_code == 200
    view = response.json()["data"]
    assert view["current_context_revision"] == 2
    assert view["context"]["filters"] == structured["filters"]
    assert view["messages"][-1]["context"]["search"] == "warhammer"
    assert view["messages"][-1]["context"]["date_range"] == structured["date_range"]
    assert view["messages"][-1]["response_status"] == "HOLD"
    assert view["messages"][-1]["request_message_id"] == view["messages"][-2]["message_id"]


@pytest.mark.parametrize("filters", [
    {"order_id": "raw"}, {"customer_id": "raw"}, {"major_category": "customer_id"},
])
def test_view_unknown_or_forbidden_filters_fail_closed(c09_db, filters):
    client = _configured_app(c09_db, Environment.TEST, "actor.one")
    response = client.post(
        "/api/v1/conversations",
        json={"context": {"scope": "VIEW", "page": "ORDERS_SALES", "filters": filters}},
    )
    assert response.status_code == 422
    assert client.get("/api/v1/conversations").json()["data"] == []


def test_view_category_must_be_known_for_same_tenant(c09_db):
    client = _configured_app(c09_db, Environment.TEST, "actor.one")
    response = client.post(
        "/api/v1/conversations",
        json={"context": {
            "scope": "VIEW", "page": "PRODUCT_INVENTORY",
            "filters": {"major_category": "Unknown Category"},
        }},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "UNKNOWN_VIEW_CATEGORY"


def test_view_without_filters_is_canonical_empty_map(c09_db):
    client = _configured_app(c09_db, Environment.TEST, "actor.one")
    response = client.post(
        "/api/v1/conversations",
        json={"context": {"scope": "VIEW", "page": "ORDERS_SALES"}},
    )
    assert response.status_code == 201
    assert response.json()["data"]["context"]["filters"] == {}


def test_late_result_stays_in_original_conversation_and_identity_differs(c09_db):
    factory, ids = c09_db
    with factory() as session:
        first = create_conversation(
            session, tenant_id=ids["tenant"], actor_id="actor.one", target=product()
        )
        request = begin_analysis_request(
            session, tenant_id=ids["tenant"], actor_id="actor.one",
            conversation_id=first.id, target=product(), intent="INSPECT_TARGET",
            analysis_kind="DETERMINISTIC", request_revision=1,
        )
        second = create_conversation(
            session, tenant_id=ids["tenant"], actor_id="actor.one",
            target=product(102, "Catalog B"),
        )
        complete_analysis_request(
            session, tenant_id=ids["tenant"], actor_id="actor.one",
            conversation_id=first.id, request_message_id=request.id,
        )
        a = read_conversation(
            session, tenant_id=ids["tenant"], actor_id="actor.one", conversation_id=first.id
        )
        b = read_conversation(
            session, tenant_id=ids["tenant"], actor_id="actor.one", conversation_id=second.id
        )
        assert a["messages"][-1]["role"] == "ASSISTANT"
        assert a["messages"][-1]["request_message_id"] == str(request.id)
        assert len(b["messages"]) == 1
        assert (a["conversation_id"], a["context"]["target_id"]) != (
            b["conversation_id"], b["context"]["target_id"]
        )


def test_late_result_keeps_historical_revision_without_replacing_current(c09_db):
    factory, ids = c09_db
    with factory() as session:
        row = create_conversation(
            session, tenant_id=ids["tenant"], actor_id="actor.one", target=product()
        )
        request = begin_analysis_request(
            session, tenant_id=ids["tenant"], actor_id="actor.one",
            conversation_id=row.id, target=product(), intent="INSPECT_TARGET",
            analysis_kind="HYBRID", request_revision=1,
        )
        append_turn(
            session, tenant_id=ids["tenant"], actor_id="actor.one",
            conversation_id=row.id, target=incoming_target(ids["incoming"]),
            intent="FOLLOW_RELATED_TARGET",
        )
        complete_analysis_request(
            session, tenant_id=ids["tenant"], actor_id="actor.one",
            conversation_id=row.id, request_message_id=request.id,
        )
        view = read_conversation(
            session, tenant_id=ids["tenant"], actor_id="actor.one", conversation_id=row.id
        )
        assert [m["context"]["context_revision"] for m in view["messages"]] == [1, 1, 2, 1]
        assert view["current_context_revision"] == 2
        assert view["context"]["target_type"] == "INCOMING"
        assert view["messages"][-1]["request_message_id"] == str(request.id)
        append_turn(
            session, tenant_id=ids["tenant"], actor_id="actor.one",
            conversation_id=row.id, target=incoming_target(ids["incoming"]),
            intent="INSPECT_TARGET",
        )
        after = read_conversation(
            session, tenant_id=ids["tenant"], actor_id="actor.one", conversation_id=row.id
        )
        assert [m["message_order"] for m in after["messages"]] == [0, 1, 2, 3, 4]
        assert after["current_context_revision"] == 2


def test_late_result_rejects_missing_context_and_owner_change(c09_db):
    factory, ids = c09_db
    with factory() as session:
        row = create_conversation(
            session, tenant_id=ids["tenant"], actor_id="actor.one", target=product()
        )
        request = begin_analysis_request(
            session, tenant_id=ids["tenant"], actor_id="actor.one",
            conversation_id=row.id, target=product(), intent="INSPECT_TARGET",
            analysis_kind="DETERMINISTIC", request_revision=1,
        )
        row.owner_actor_id = "actor.two"
        session.commit()
        with pytest.raises(C09ContractError) as missing:
            complete_analysis_request(
                session, tenant_id=ids["tenant"], actor_id="actor.one",
                conversation_id=row.id, request_message_id=request.id,
            )
        assert missing.value.status == "MISSING"
        row.owner_actor_id = "actor.one"
        session.commit()
        context = session.scalar(
            select(MessageContextV2).where(MessageContextV2.message_id == request.id)
        )
        session.delete(context)
        session.commit()
        with pytest.raises(C09ContractError) as invalid:
            complete_analysis_request(
                session, tenant_id=ids["tenant"], actor_id="actor.one",
                conversation_id=row.id, request_message_id=request.id,
            )
        assert invalid.value.status == "MISSING"


def test_order_aggregate_boundary_omits_raw_identifiers():
    as_of = datetime(2026, 10, 4, tzinfo=UTC)
    projection = CurrentReservationDemandProjection(
        demands=(CurrentReservationDemand(
            product_no=101, sku_id="SKU-A", required_qty=7,
            calculation_status="CURRENT_DEMAND_CONFIRMED", category_evidence_ids=(),
            order_evidence_ids=("order_id=secret",), source_classifications=("ACTUAL",),
            as_of=as_of,
        ),),
        review_items=(CurrentReservationReviewItem(
            order_id="secret", order_item_id="line-secret", product_no=101,
            raw_quantity=1, reason="review", source_classification="BLOCKED",
            evidence_ids=("customer_id=secret",),
        ),),
        excluded_order_item_ids=("line-secret",), confirmed_order_count=1,
        confirmed_order_item_count=1, confirmed_required_qty=7, as_of=as_of,
    )
    product_safe = safe_reservation_aggregate(projection, product_no=101)
    view_safe = safe_reservation_aggregate(projection, product_no=None)
    assert product_safe.required_qty == view_safe.required_qty == 7
    assert "secret" not in repr(product_safe)
    assert "secret" not in repr(view_safe)


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

def test_product_analysis_answers_from_safe_synthetic_demand(c09_db, monkeypatch):
    provider_calls = []

    def forbidden_provider(*args, **kwargs):
        provider_calls.append("OpenAI")
        raise AssertionError("C18 deterministic dispatch must not call a provider")

    monkeypatch.setattr("openai.OpenAI", forbidden_provider)
    factory, ids = c09_db

    with factory() as session:
        product_row = session.get(
            ProductV2,
            ids["a"],
        )
        assert product_row is not None

        orders = [
            OrderV2(
                tenant_id=ids["tenant"],
                external_order_id="SYN-C09-001",
                source_system="SYNTHETIC_DEMO",
                total_order_amount=None,
                total_paid_amount=None,
                payment_type=None,
                payment_method=None,
                source_order_at=datetime(
                    2026, 10, 4, 12, 0, tzinfo=UTC
                ),
                paid="T",
                shipping_status="F",
                canceled="F",
            ),
            OrderV2(
                tenant_id=ids["tenant"],
                external_order_id="SYN-C09-002",
                source_system="SYNTHETIC_DEMO",
                total_order_amount=None,
                total_paid_amount=None,
                payment_type=None,
                payment_method=None,
                source_order_at=datetime(
                    2026, 10, 3, 12, 0, tzinfo=UTC
                ),
                paid="T",
                shipping_status="T",
                canceled="F",
            ),
            OrderV2(
                tenant_id=ids["tenant"],
                external_order_id="SYN-C09-003",
                source_system="SYNTHETIC_DEMO",
                total_order_amount=None,
                total_paid_amount=None,
                payment_type=None,
                payment_method=None,
                source_order_at=datetime(
                    2026, 9, 20, 12, 0, tzinfo=UTC
                ),
                paid="T",
                shipping_status="T",
                canceled="F",
            ),
            OrderV2(
                tenant_id=ids["tenant"],
                external_order_id="SYN-C09-004",
                source_system="SYNTHETIC_DEMO",
                total_order_amount=None,
                total_paid_amount=None,
                payment_type=None,
                payment_method=None,
                source_order_at=datetime(
                    2026, 10, 2, 12, 0, tzinfo=UTC
                ),
                paid="T",
                shipping_status="F",
                canceled="T",
            ),
        ]

        session.add_all(orders)
        session.flush()

        items = [
            OrderItemV2(
                tenant_id=ids["tenant"],
                order_id=orders[0].id,
                external_order_item_id="SYN-C09-I001",
                external_product_no=101,
                product_id=product_row.id,
                product_variant_id=None,
                source_product_name="Catalog A",
                source_product_name_with_option=None,
                quantity=2,
                source_sale_price=None,
            ),
            OrderItemV2(
                tenant_id=ids["tenant"],
                order_id=orders[1].id,
                external_order_item_id="SYN-C09-I002",
                external_product_no=101,
                product_id=product_row.id,
                product_variant_id=None,
                source_product_name="Catalog A",
                source_product_name_with_option=None,
                quantity=1,
                source_sale_price=None,
            ),
            OrderItemV2(
                tenant_id=ids["tenant"],
                order_id=orders[2].id,
                external_order_item_id="SYN-C09-I003",
                external_product_no=101,
                product_id=product_row.id,
                product_variant_id=None,
                source_product_name="Catalog A",
                source_product_name_with_option=None,
                quantity=1,
                source_sale_price=None,
            ),
            OrderItemV2(
                tenant_id=ids["tenant"],
                order_id=orders[3].id,
                external_order_item_id="SYN-C09-I004",
                external_product_no=101,
                product_id=product_row.id,
                product_variant_id=None,
                source_product_name="Catalog A",
                source_product_name_with_option=None,
                quantity=4,
                source_sale_price=None,
            ),
        ]

        session.add_all(items)
        session.commit()

        conversation = create_conversation(
            session,
            tenant_id=ids["tenant"],
            actor_id="actor.one",
            target=product(),
        )

        analyzed = analyze_turn(
            session,
            tenant_id=ids["tenant"],
            actor_id="actor.one",
            conversation_id=conversation.id,
            target=product(),
            intent="INSPECT_TARGET",
            analysis_kind="DETERMINISTIC",
            request_revision=1,
        )

        assert analyzed.id == conversation.id

        result = read_conversation(
            session,
            tenant_id=ids["tenant"],
            actor_id="actor.one",
            conversation_id=conversation.id,
        )
        assistant_context = session.execute(
            select(MessageContextV2)
            .join(
                MessageV2,
                MessageV2.id == MessageContextV2.message_id,
            )
            .where(
                MessageV2.tenant_id == ids["tenant"],
                MessageV2.conversation_id == conversation.id,
                MessageV2.role == "ASSISTANT",
            )
        ).scalar_one()

        assert assistant_context.evidence_ids == [
            "product-demand:SYNTHETIC_DEMO:101:2026-10-04"
        ]
    assistant_messages = [
        message
        for message in result["messages"]
        if message["role"] == "ASSISTANT"
    ]

    assert len(assistant_messages) == 1

    assistant = assistant_messages[0]

    assert assistant["response_status"] == "ANSWER"
    assert assistant["analysis_kind"] == "DETERMINISTIC"
    assert assistant["evidence_ids"] == [
        "product-demand:SYNTHETIC_DEMO:101:2026-10-04"
    ]
    assert provider_calls == []

    user_messages = [
        message
        for message in result["messages"]
        if message["role"] == "USER"
    ]

    assert all(
        message["evidence_ids"] == []
        for message in user_messages
    )
    content = assistant["content"]

    assert "상품번호: 101" in content
    assert "상품명: Catalog A" in content

    assert "전체 주문건수: 4" in content
    assert "전체 주문수량: 8" in content

    assert "유효 주문건수: 3" in content
    assert "유효 주문수량: 4" in content

    assert "최근 10일 유효수량: 3" in content
    assert "직전 10일 유효수량: 1" in content

    assert "추세: UP" in content
    assert "취소/불확실/미결제 수량: 4/0/0" in content

    assert "데이터 모드: SYNTHETIC_DEMO" in content

    # C09 safe boundary 밖의 주문 단위 식별자는
    # Assistant 응답에 노출되면 안 된다.
    assert "SYN-C09-001" not in content
    assert "SYN-C09-002" not in content
    assert "SYN-C09-003" not in content
    assert "SYN-C09-004" not in content

    assert "SYN-C09-I001" not in content
    assert "SYN-C09-I002" not in content
    assert "SYN-C09-I003" not in content
    assert "SYN-C09-I004" not in content
