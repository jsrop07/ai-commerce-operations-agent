from datetime import UTC, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.adapters.providers.base import ProviderHttpError
from backend.app.adapters.providers.mock import Cafe24MockProvider
from backend.app.core.config import Environment, Settings, WriteMode
from backend.app.db.base import Base
from backend.app.main import create_app
from backend.app.services.ingestion.identity import build_toss_sale_business_identity
from backend.app.services.inventory_projection import build_inventory_projection
from backend.app.sync.cursor_store import CursorStore
from backend.app.sync.retry_policy import RetryPolicy
from backend.app.sync.run_lock import SyncRunLock
from backend.app.sync.runner import ProviderSyncRunner, SyncBudget
from contracts.providers import ProviderReadPage


def _production_read_app():
    return create_app(
        Settings(
            tenant_id="store-a",
            environment=Environment.PRODUCTION_READ,
            write_mode=WriteMode.DISABLED,
            global_write_kill=True,
        )
    )


def test_inventory_api_filters_other_tenants() -> None:
    app = _production_read_app()
    for tenant_id in ("store-a", "store-b"):
        app.state.inventory_projections.append(
            build_inventory_projection(
                tenant_id=tenant_id,
                sku_id=f"sku-{tenant_id}",
                source_on_hand=5,
                ledger_delta=0,
                reserved=0,
                confirmed_incoming=None,
                quality_status="CONFIRMED",
                ttl_seconds=300,
                age_seconds=1,
            )
        )

    body = TestClient(app).get("/api/v1/inventory").json()

    assert [item["tenant_id"] for item in body["data"]] == ["store-a"]
    assert body["evidence_ids"] == []


def test_mapping_api_filters_other_tenants() -> None:
    app = _production_read_app()
    for tenant_id in ("store-a", "store-b"):
        app.state.mapping_queue.enqueue(
            tenant_id=tenant_id,
            provider="TOSS_POS",
            object_type="SKU",
            external_id=f"external-{tenant_id}",
            external_text="Synthetic product",
            source_identity_key=f"source-{tenant_id}",
            reason="UNKNOWN_PRODUCT_CODE",
        )

    body = TestClient(app).get("/api/v1/mappings").json()

    assert [item["tenant_id"] for item in body["data"]] == ["store-a"]
    assert body["evidence_ids"] == ["source-store-a"]


def test_business_identity_normalizes_equivalent_timezones() -> None:
    utc = build_toss_sale_business_identity(
        tenant_id="store-a",
        provider_account_ref="toss-main",
        order_id="order-1",
        line_id="0",
        sku_id="sku-1",
        occurred_at=datetime(2026, 9, 6, 1, 30, tzinfo=UTC),
        schema_version="1.0",
    )
    korea = build_toss_sale_business_identity(
        tenant_id="store-a",
        provider_account_ref="toss-main",
        order_id="order-1",
        line_id="0",
        sku_id="sku-1",
        occurred_at=datetime(2026, 9, 6, 10, 30, tzinfo=timezone(timedelta(hours=9))),
        schema_version="1.0",
    )

    assert utc.identity is not None
    assert korea.identity is not None
    assert utc.identity.key() == korea.identity.key()


def test_cursor_store_rejects_connection_mode_mixing_and_invalid_overlap() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime(2026, 9, 6, tzinfo=UTC)
    with Session(engine) as session:
        with pytest.raises(ValueError, match="API connection mode"):
            CursorStore().commit_api_checkpoint(
                session,
                tenant_id="store-a",
                provider="CAFE24",
                resource="orders",
                connection_mode="FILE_IMPORT",
                cursor="next",
                watermark=now,
                overlap_start=now,
                last_success_at=now,
                canonical_committed=True,
            )
        with pytest.raises(ValueError, match="overlap_start"):
            CursorStore().commit_api_checkpoint(
                session,
                tenant_id="store-a",
                provider="CAFE24",
                resource="orders",
                connection_mode="API_POLL",
                cursor="next",
                watermark=now,
                overlap_start=now + timedelta(seconds=1),
                last_success_at=now,
                canonical_committed=True,
            )
    engine.dispose()


def test_repeated_pagination_cursor_fails_closed_before_commit() -> None:
    commits = []
    runner = ProviderSyncRunner(
        retry_policy=RetryPolicy(max_attempts=1),
        budget=SyncBudget(max_pages=10, max_items=10, max_elapsed_seconds=10),
        sleep_fn=lambda _: None,
    )

    result = runner.run(
        provider=Cafe24MockProvider(),
        read_page=lambda _provider, _cursor: ProviderReadPage(
            provider="CAFE24",
            resource="products",
            items=[{"id": "synthetic"}],
            next_cursor="same",
            has_more=True,
            request_count=1,
        ),
        start_cursor="same",
        commit_page=lambda *_: commits.append(True),
    )

    assert result.stop_reason == "INVALID_PAGINATION_CURSOR"
    assert result.pages_succeeded == 0
    assert result.items == []
    assert commits == []


def test_retry_policy_rejects_non_finite_retry_after() -> None:
    decision = RetryPolicy().decide(
        ProviderHttpError(429, retry_after_seconds=float("nan")), attempt=1
    )

    assert decision.retry is False
    assert decision.reason == "INVALID_RETRY_AFTER"


def test_lock_keys_do_not_collide_on_separator_characters() -> None:
    lock = SyncRunLock()

    assert lock.acquire(tenant_id="a:b", provider="c", resource="d") is True
    assert lock.acquire(tenant_id="a", provider="b:c", resource="d") is True
