"""C22 cookie ownership checks on an isolated SQLite model boundary."""

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.catalog_v2 import DEMO_CATALOG_TENANT_ID
from backend.app.core.config import Environment, Settings
from backend.app.db.base_v2 import BaseV2
from backend.app.main import create_app
from backend.app.models_v2.ai import (
    AgentRunV2,
    ConversationV2,
    DemoSessionV2,
    MessageContextV2,
    MessageV2,
)
from backend.app.models_v2.catalog import ProductV2
from backend.app.models_v2.tenant import TenantV2
from backend.app.services.c04_lookup import C04LookupService
from backend.app.services.demo_session import COOKIE_NAME, resolve_demo_session


@compiles(JSONB, "sqlite")
def _jsonb(_type, _compiler, **_kw):
    return "JSON"


@pytest.fixture
def demo_db():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        execution_options={"schema_translate_map": {"public": None, "ai": None, "catalog": None}},
    )
    BaseV2.metadata.create_all(engine, tables=[model.__table__ for model in (
        TenantV2, ProductV2, DemoSessionV2, ConversationV2, MessageV2,
        MessageContextV2, AgentRunV2,
    )])
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as db:
        db.add(TenantV2(
            id=DEMO_CATALOG_TENANT_ID, name="demo_store", environment="DEMO", status="ACTIVE",
        ))
        db.add(ProductV2(
            tenant_id=DEMO_CATALOG_TENANT_ID, cafe24_product_no=101,
            product_name="Demo product", product_code="C22_PRODUCT",
            custom_product_code=None, sale_price=None, display_status="T",
            selling_status="T", sold_out=False, operational=True, source_as_of=None,
        ))
        db.commit()
    settings = Settings(
        _env_file=None, environment=Environment.DEMO, database_url="sqlite://",
        v2_tenant_id=DEMO_CATALOG_TENANT_ID, demo_session_ttl_seconds=2,
        demo_session_cookie_secure=False,
    )
    app = create_app(
        settings, db_engine=engine, v2_db_engine=engine,
        c04_lookup_service=C04LookupService(),
    )
    yield factory, app
    engine.dispose()


CONTEXT = {"context": {
    "targetType": "PRODUCT", "targetId": "101", "targetLabel": "Demo product",
    "source": "CAFE24_CATALOG", "asOf": None,
}}


def test_separate_sessions_own_separate_conversations(demo_db, monkeypatch):
    factory, app = demo_db
    def unexpected_ai_call(*args, **kwargs):
        raise AssertionError("AI runtime called during session bootstrap/status")

    monkeypatch.setattr(
        "backend.app.services.conversation_v2._safe_analysis", unexpected_ai_call,
    )
    a, b = TestClient(app), TestClient(app)
    assert a.get("/api/v1/demo/session").status_code == 401
    first = a.post("/api/v1/demo/session")
    second = b.post("/api/v1/demo/session")
    assert first.status_code == second.status_code == 201
    assert first.json()["session_id"] != second.json()["session_id"]
    assert "httponly" in first.headers["set-cookie"].lower()
    assert "samesite=lax" in first.headers["set-cookie"].lower()
    assert a.post("/api/v1/demo/session").status_code == 200
    assert a.get("/api/v1/demo/session").json()["session_id"] == first.json()["session_id"]
    with factory() as db:
        rows = db.scalars(select(DemoSessionV2)).all()
        assert len(rows) == 2
        assert rows[0].actor_id != rows[1].actor_id
        assert all(row.token_hash != sha256(row.actor_id.encode()).hexdigest() for row in rows)
        assert resolve_demo_session(
            db, tenant_id=uuid4(), token=a.cookies.get(COOKIE_NAME),
        ) is None
        assert all(row.token_hash != a.cookies.get(COOKIE_NAME) for row in rows)
    created = a.post("/api/v1/conversations", json=CONTEXT)
    assert created.status_code == 201, created.text
    cid = created.json()["data"]["conversation_id"]
    assert b.get("/api/v1/conversations").json()["data"] == []
    assert b.get(f"/api/v1/conversations/{cid}").status_code == 404
    assert b.post(f"/api/v1/conversations/{cid}/reopen").status_code == 404
    append = {"context": CONTEXT["context"], "intent": "INSPECT_TARGET"}
    assert b.post(f"/api/v1/conversations/{cid}/messages", json=append).status_code == 404
    assert a.get(f"/api/v1/conversations/{cid}").status_code == 200


def test_forgery_expiry_inactive_and_new_session_do_not_recover_owner(demo_db):
    factory, app = demo_db
    a = TestClient(app)
    assert a.post("/api/v1/demo/session").status_code == 201
    cid = a.post("/api/v1/conversations", json=CONTEXT).json()["data"]["conversation_id"]
    token = a.cookies.get(COOKIE_NAME)
    assert token is not None
    forged = TestClient(app)
    forged.cookies.set(COOKIE_NAME, token[:-1] + ("A" if token[-1] != "A" else "B"))
    assert forged.get(f"/api/v1/conversations/{cid}").status_code == 403
    assert forged.get("/api/v1/demo/session").status_code == 401
    assert forged.get(
        "/api/v1/conversations", headers={"X-Actor-Id": "demo:forged"}
    ).status_code == 403
    with factory() as db:
        row = db.scalar(select(DemoSessionV2).where(
            DemoSessionV2.token_hash == sha256(token.encode()).hexdigest(),
        ))
        row.status = "INACTIVE"
        db.commit()
    assert a.get(f"/api/v1/conversations/{cid}").status_code == 403
    with factory() as db:
        row = db.scalar(select(DemoSessionV2).where(
            DemoSessionV2.token_hash == sha256(token.encode()).hexdigest(),
        ))
        row.status = "ACTIVE"
        row.created_at = datetime.now(UTC) - timedelta(seconds=10)
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    assert a.get(f"/api/v1/conversations/{cid}").status_code == 403
    assert a.get("/api/v1/demo/session").status_code == 401
    assert a.post("/api/v1/demo/session").status_code == 201
    assert a.get(f"/api/v1/conversations/{cid}").status_code == 404


def test_bootstrap_rejects_client_identity_and_non_demo(demo_db):
    _, app = demo_db
    client = TestClient(app)
    assert client.post(
        "/api/v1/conversations/product-search", json={"query": "보드게임"},
    ).status_code == 403
    assert client.post("/api/v1/demo/session?tenant_id=anything").status_code == 422
    assert client.post("/api/v1/demo/session", json={"actor_id": "chosen"}).status_code == 422
    app.state.settings.environment = Environment.PRODUCTION_READ
    assert client.post("/api/v1/demo/session").status_code == 403
    assert client.get("/api/v1/conversations").status_code == 403
