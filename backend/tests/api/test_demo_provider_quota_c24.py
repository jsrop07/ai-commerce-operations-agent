"""C24 tests use isolated SQLite and fake provider receipts; no network calls."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.app.core.config import Settings
from backend.app.db.base_v2 import BaseV2
from backend.app.main import create_app
from backend.app.models_v2.ai import DemoProviderUsageV2, DemoSessionV2
from backend.app.models_v2.tenant import TenantV2
from backend.app.services.demo_provider_quota import (
    DemoQuotaDenied,
    QuotaLimits,
    call_with_demo_quota,
    reserve,
)


@pytest.fixture
def quota_db(tmp_path):
    engine = create_engine(
        f"sqlite+pysqlite:///{tmp_path / 'quota.db'}",
        connect_args={"timeout": 10},
        execution_options={"schema_translate_map": {"public": None, "ai": None}},
    )
    BaseV2.metadata.create_all(engine, tables=[
        TenantV2.__table__, DemoSessionV2.__table__, DemoProviderUsageV2.__table__,
    ])
    factory = sessionmaker(engine, expire_on_commit=False)
    tenant_id, a, b = uuid4(), uuid4(), uuid4()
    with factory() as db:
        db.add(TenantV2(id=tenant_id, name="c24-test", environment="TEST", status="ACTIVE"))
        for session_id in (a, b):
            db.add(DemoSessionV2(
                id=session_id, tenant_id=tenant_id, actor_id=f"demo:{session_id.hex}",
                token_hash=session_id.hex, created_at=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(hours=1), status="ACTIVE",
            ))
        db.commit()
    yield factory, tenant_id, a, b
    engine.dispose()


def limits(**changes):
    values = dict(priced_model="fake-model", max_calls=2, max_input_tokens=20, max_output_tokens=20,
                  max_cost_usd=Decimal("3"),
                  input_usd_per_million_tokens=Decimal("100000"),
                  output_usd_per_million_tokens=Decimal("100000"))
    values.update(changes)
    return QuotaLimits(**values)


def fake_result(*, calls=1, input_tokens=5, output_tokens=5):
    return SimpleNamespace(receipt=SimpleNamespace(
        model="fake-model", attempts=calls,
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    ))


def invoke(quota_db, request_id, *, session_id=None, quota=None, provider=None,
           calls=1, input_tokens=5, output_tokens=5):
    factory, tenant_id, a, _ = quota_db
    return call_with_demo_quota(
        provider or fake_result, factory=factory, tenant_id=tenant_id,
        session_id=session_id or a, request_id=request_id, model="fake-model",
        calls=calls, input_tokens=input_tokens, output_tokens=output_tokens,
        limits=quota or limits(),
    )


def test_first_call_settles_and_second_session_isolated(quota_db):
    factory, _, a, b = quota_db
    invoke(quota_db, "first", quota=limits(max_calls=1))
    with pytest.raises(DemoQuotaDenied, match="C24_QUOTA_EXCEEDED"):
        invoke(quota_db, "second", quota=limits(max_calls=1))
    invoke(quota_db, "other-session", session_id=b, quota=limits(max_calls=1))
    with factory() as db:
        rows = db.scalars(select(DemoProviderUsageV2)).all()
        assert len(rows) == 2
        assert {r.demo_session_id for r in rows} == {a, b}
        assert all(r.status == "SETTLED" for r in rows)


@pytest.mark.parametrize("quota,expected", [
    (limits(max_input_tokens=4), "C24_QUOTA_EXCEEDED"),
    (limits(max_output_tokens=4), "C24_QUOTA_EXCEEDED"),
    (limits(max_cost_usd=Decimal("0.9")), "C24_QUOTA_EXCEEDED"),
])
def test_token_and_cost_limits_block_before_provider(quota_db, quota, expected):
    called = []
    with pytest.raises(DemoQuotaDenied, match=expected):
        invoke(quota_db, "blocked", quota=quota, provider=lambda: called.append(1))
    assert called == []


def test_concurrent_requests_cannot_both_reserve_last_slot(quota_db):
    factory, tenant_id, a, _ = quota_db
    def attempt(n):
        try:
            reserve(factory, tenant_id=tenant_id, session_id=a,
                    request_id=f"concurrent-{n}", model="fake-model", calls=1,
                    input_tokens=5, output_tokens=5, limits=limits(max_calls=1))
            return "allowed"
        except DemoQuotaDenied:
            return "denied"
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, (1, 2))) == ["allowed", "denied"]


def test_provider_failure_keeps_reservation_and_no_payload_columns(quota_db):
    factory, _, _, _ = quota_db
    def fail():
        raise TimeoutError("provider timeout")
    with pytest.raises(TimeoutError):
        invoke(quota_db, "failed", quota=limits(max_calls=1), provider=fail)
    with pytest.raises(DemoQuotaDenied, match="C24_QUOTA_EXCEEDED"):
        invoke(quota_db, "after-failure", quota=limits(max_calls=1))
    with factory() as db:
        row = db.scalar(select(DemoProviderUsageV2))
        assert row.status == "FAILED"
        assert row.actual_cost_usd is None
    names = {column.name for column in DemoProviderUsageV2.__table__.columns}
    assert not names.intersection({"prompt", "query", "evidence", "customer", "order", "inquiry"})


def test_actual_usage_overrun_is_recorded_and_held(quota_db):
    factory, _, _, _ = quota_db
    with pytest.raises(DemoQuotaDenied, match="C24_RESERVATION_OVERRUN"):
        invoke(quota_db, "overrun", provider=lambda: fake_result(input_tokens=6))
    with factory() as db:
        row = db.scalar(select(DemoProviderUsageV2))
        assert row.status == "OVERRUN"
        assert row.actual_input_tokens == 6


def test_incomplete_settings_fail_closed_and_test_injection():
    with pytest.raises(DemoQuotaDenied, match="C24_QUOTA_UNCONFIGURED"):
        QuotaLimits.from_settings(Settings(_env_file=None, environment="DEMO"))
    configured = Settings(
        _env_file=None, environment="TEST", demo_quota_max_provider_calls=1,
        demo_quota_max_input_tokens=10, demo_quota_max_output_tokens=10,
        demo_quota_max_estimated_cost_usd=Decimal("2"),
        demo_quota_priced_model="fake-model",
        demo_quota_input_usd_per_million_tokens=Decimal("100000"),
        demo_quota_output_usd_per_million_tokens=Decimal("100000"),
    )
    assert QuotaLimits.from_settings(configured).max_calls == 1


def test_invalid_or_expired_session_rejected(quota_db):
    factory, tenant_id, a, _ = quota_db
    with factory() as db:
        row = db.get(DemoSessionV2, a)
        row.created_at = datetime.now(UTC) - timedelta(hours=2)
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    with pytest.raises(DemoQuotaDenied, match="C24_SESSION_INVALID"):
        invoke(quota_db, "expired")
    with pytest.raises(DemoQuotaDenied, match="C24_SESSION_INVALID"):
        reserve(factory, tenant_id=uuid4(), session_id=a, request_id="wrong-tenant",
                model="fake-model", calls=1, input_tokens=5, output_tokens=5, limits=limits())


def test_unpriced_model_denied_before_call(quota_db):
    factory, tenant_id, a, _ = quota_db
    with pytest.raises(DemoQuotaDenied, match="C24_MODEL_UNPRICED"):
        reserve(factory, tenant_id=tenant_id, session_id=a, request_id="wrong-model",
                model="unpriced-model", calls=1, input_tokens=5, output_tokens=5,
                limits=limits())


def test_demo_c06_requires_server_resolved_session_before_provider():
    engine = create_engine("sqlite://")
    app = create_app(Settings(_env_file=None, environment="DEMO", database_url="sqlite://"),
                     db_engine=engine)
    calls = []
    app.state.c06_provider = lambda *_args, **_kwargs: calls.append(1)
    response = TestClient(app).post(
        "/api/v1/retrieval/explanations", json={"question": "예약상품은 언제 출고해?"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["warnings"] == ["C24_SESSION_REQUIRED"]
    assert calls == []
    engine.dispose()
