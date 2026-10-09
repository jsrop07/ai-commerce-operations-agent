"""최근 주문 API: 빈 데이터, KST 경계, 환경 차단, Tenant 격리."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api import orders_summary
from backend.app.core.config import Environment


TENANT_A = uuid4()
TENANT_B = uuid4()


@pytest.fixture
def order_db():
    """운영 DB가 아닌 독립적인 SQLite 메모리 DB."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    with engine.begin() as conn:
        # OrderV2가 사용하는 operations 스키마를 SQLite에 구성
        conn.exec_driver_sql(
            "ATTACH DATABASE ':memory:' AS operations"
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE operations.orders (
                id VARCHAR(32) PRIMARY KEY,
                tenant_id VARCHAR(32) NOT NULL,
                source_system VARCHAR(64) NOT NULL,
                source_order_at DATETIME
            )
            """
        )

    factory = sessionmaker(bind=engine, expire_on_commit=False)

    yield engine, factory
    engine.dispose()


def insert_order(
    engine,
    tenant_id,
    at: datetime,
    source_system="SYNTHETIC_DEMO",
):
    # SQLite 테스트 DB에만 데이터를 삽입
    with engine.begin() as conn:
        conn.exec_driver_sql(
            """
            INSERT INTO operations.orders
            (id, tenant_id, source_system, source_order_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                uuid4().hex,
                tenant_id.hex,
                source_system,
                at.astimezone(UTC)
                  .replace(tzinfo=None)
                  .strftime("%Y-%m-%d %H:%M:%S.%f"),
            ),
        )


def make_request(environment=Environment.DEMO):
    return SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                settings=SimpleNamespace(
                    environment=environment,
                    tenant_id="demo_store",
                )
            )
        )
    )


def configure_runtime(monkeypatch, factory):
    monkeypatch.setattr(
        orders_summary,
        "_require_v2_runtime",
        lambda request: (factory, TENANT_A, Environment.DEMO),
    )

    def check_tenant(db, tenant_id, environment):
        assert tenant_id == TENANT_A
        assert environment == Environment.DEMO

    monkeypatch.setattr(
        orders_summary,
        "_require_catalog_tenant",
        check_tenant,
    )


def test_no_orders_returns_no_data(order_db, monkeypatch):
    """주문이 없으면 0건이 아니라 NO_DATA를 표시한다."""
    _, factory = order_db
    configure_runtime(monkeypatch, factory)

    response = orders_summary.get_recent_order_summary(
        make_request()
    )

    assert response["data"]["status"] == "NO_DATA"
    assert response["data"]["order_count"] is None
    assert response["data"]["reference_date"] is None
    assert "RECENT_ORDERS_EMPTY" in response["warnings"]


def test_kst_boundary(order_db, monkeypatch):
    """KST 00:00 경계부터 최근 주문일 건수를 집계한다."""
    engine, factory = order_db
    configure_runtime(monkeypatch, factory)

    # 10월 4일 23:59:59 KST -> 제외
    insert_order(
        engine, TENANT_A,
        datetime(2026, 10, 4, 14, 59, 59, tzinfo=UTC),
    )

    # 10월 5일 00:00:00 KST -> 포함
    insert_order(
        engine, TENANT_A,
        datetime(2026, 10, 4, 15, 0, 0, tzinfo=UTC),
    )

    # 10월 5일 04:58:33 KST -> 포함
    insert_order(
        engine, TENANT_A,
        datetime(2026, 10, 4, 19, 58, 33, tzinfo=UTC),
    )

    response = orders_summary.get_recent_order_summary(
        make_request()
    )

    assert response["data"]["status"] == "AVAILABLE"
    assert response["data"]["reference_date"] == "2026-10-05"
    assert response["data"]["order_count"] == 2
    assert response["data"]["timezone"] == "Asia/Seoul"


def test_non_demo_environment_forbidden(
    order_db, monkeypatch
):
    """DEMO 이외 환경에서는 API 접근을 차단한다."""
    _, factory = order_db
    configure_runtime(monkeypatch, factory)

    with pytest.raises(HTTPException) as exc:
        orders_summary.get_recent_order_summary(
            make_request(Environment.LOCAL)
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == "RECENT_ORDERS_DEMO_ONLY"


def test_tenant_and_source_isolation(
    order_db, monkeypatch
):
    """다른 Tenant 및 실제 출처 주문은 집계하지 않는다."""
    engine, factory = order_db
    configure_runtime(monkeypatch, factory)

    insert_order(
        engine, TENANT_A,
        datetime(2026, 10, 4, 18, 0, tzinfo=UTC),
    )

    # 다른 Tenant는 더 늦은 주문이어도 제외
    insert_order(
        engine, TENANT_B,
        datetime(2026, 10, 6, 18, 0, tzinfo=UTC),
    )

    # 같은 Tenant라도 Synthetic Demo 이외 출처는 제외
    insert_order(
        engine, TENANT_A,
        datetime(2026, 10, 7, 18, 0, tzinfo=UTC),
        source_system="CAFE24",
    )

    response = orders_summary.get_recent_order_summary(
        make_request()
    )

    assert response["data"]["status"] == "AVAILABLE"
    assert response["data"]["reference_date"] == "2026-10-05"
    assert response["data"]["order_count"] == 1
    assert response["data"]["source_system"] == "SYNTHETIC_DEMO"