from datetime import UTC, datetime

import pytest

from backend.app.services.demo import DEMO_SCENARIOS
from backend.app.services.ingestion.idempotency import EffectRegistry
from backend.app.services.ingestion.identity import (
    SourceIdentity,
    build_toss_sale_business_identity,
)
from backend.app.services.offline_sale import OfflineSalePipeline


@pytest.mark.parametrize("replays", [2, 10])
def test_replayed_offline_sale_has_one_business_effect(replays: int) -> None:
    pipeline = OfflineSalePipeline()
    receipts = [pipeline.process(DEMO_SCENARIOS["offline_sale"]) for _ in range(replays)]
    assert sum(receipt.status == "ACCEPTED" for receipt in receipts) == 1
    assert sum(receipt.status == "REPLAYED" for receipt in receipts) == replays - 1
    assert pipeline.effects.business_effect_count == 1
    assert len(pipeline.insights) == 1
    assert pipeline.inbox.accepted_count == 1
    assert pipeline.inbox.replayed_count == replays - 1


def test_same_source_event_with_different_schema_version_is_distinct() -> None:
    pipeline = OfflineSalePipeline()

    first = dict(DEMO_SCENARIOS["offline_sale"])
    second = dict(DEMO_SCENARIOS["offline_sale"])

    first["schema_version"] = "1.0"
    first["idempotency_key"] = (
        f"{first['source']}:{first['source_event_id']}:{first['schema_version']}"
    )

    second["schema_version"] = "1.1"
    second["idempotency_key"] = (
        f"{second['source']}:{second['source_event_id']}:{second['schema_version']}"
    )

    first_receipt = pipeline.process(first)
    second_receipt = pipeline.process(second)

    assert first_receipt.status == "ACCEPTED"
    assert second_receipt.status == "ACCEPTED"
    assert pipeline.effects.business_effect_count == 2


def test_same_event_identity_is_distinct_across_tenants() -> None:
    pipeline = OfflineSalePipeline()
    first = dict(DEMO_SCENARIOS["offline_sale"])
    second = dict(first, tenant_id="another_store")

    assert pipeline.process(first).status == "ACCEPTED"
    assert pipeline.process(second).status == "ACCEPTED"
    assert pipeline.inbox.accepted_count == 2
    assert pipeline.effects.business_effect_count == 2


def test_processed_effect_identity_is_distinct_across_consumers() -> None:
    registry = EffectRegistry()
    key = str(DEMO_SCENARIOS["offline_sale"]["idempotency_key"])

    assert registry.apply_once("demo_store", "shadow_inventory", key) is True
    assert registry.apply_once("demo_store", "shadow_inventory", key) is False
    assert registry.apply_once("demo_store", "analytics", key) is True
    assert registry.business_effect_count == 2


def test_file_and_api_sources_have_different_source_identity() -> None:
    file_source = SourceIdentity(
        tenant_id="store-a",
        provider="TOSS_POS",
        resource="offline_sale",
        source_mode="FILE_IMPORT",
        source_record_id="sha256:file-a:row:100",
        schema_version="1.0",
    )

    api_source = SourceIdentity(
        tenant_id="store-a",
        provider="TOSS_POS",
        resource="offline_sale",
        source_mode="API_POLL",
        source_record_id="order-100:line:0",
        schema_version="1.0",
    )

    assert file_source.key() != api_source.key()


def test_file_and_api_same_business_fact_have_same_business_identity() -> None:
    occurred_at = datetime(2026, 9, 6, 10, 30, tzinfo=UTC)

    file_result = build_toss_sale_business_identity(
        tenant_id="store-a",
        provider_account_ref="toss-main",
        order_id="order-100",
        line_id="0",
        sku_id="sku-001",
        occurred_at=occurred_at,
        schema_version="1.0",
    )

    api_result = build_toss_sale_business_identity(
        tenant_id="store-a",
        provider_account_ref="toss-main",
        order_id="order-100",
        line_id="0",
        sku_id="sku-001",
        occurred_at=occurred_at,
        schema_version="1.0",
    )

    assert file_result.status == "RESOLVED"
    assert api_result.status == "RESOLVED"
    assert file_result.identity is not None
    assert api_result.identity is not None

    assert file_result.identity.key() == api_result.identity.key()


def test_different_sale_line_has_different_business_identity() -> None:
    occurred_at = datetime(2026, 9, 6, 10, 30, tzinfo=UTC)

    first = build_toss_sale_business_identity(
        tenant_id="store-a",
        provider_account_ref="toss-main",
        order_id="order-100",
        line_id="0",
        sku_id="sku-001",
        occurred_at=occurred_at,
        schema_version="1.0",
    )

    second = build_toss_sale_business_identity(
        tenant_id="store-a",
        provider_account_ref="toss-main",
        order_id="order-100",
        line_id="1",
        sku_id="sku-001",
        occurred_at=occurred_at,
        schema_version="1.0",
    )

    assert first.identity is not None
    assert second.identity is not None
    assert first.identity.key() != second.identity.key()


def test_missing_business_identity_field_is_quarantined() -> None:
    result = build_toss_sale_business_identity(
        tenant_id="store-a",
        provider_account_ref="toss-main",
        order_id="order-100",
        line_id=None,
        sku_id="sku-001",
        occurred_at=datetime(2026, 9, 6, 10, 30, tzinfo=UTC),
        schema_version="1.0",
    )

    assert result.status == "QUARANTINED"
    assert result.identity is None
    assert result.reason == "MISSING_BUSINESS_IDENTITY_FIELDS:line_id"


def test_file_and_api_same_business_fact_apply_effect_once() -> None:
    occurred_at = datetime(2026, 9, 6, 10, 30, tzinfo=UTC)

    file_result = build_toss_sale_business_identity(
        tenant_id="store-a",
        provider_account_ref="toss-main",
        order_id="order-100",
        line_id="0",
        sku_id="sku-001",
        occurred_at=occurred_at,
        schema_version="1.0",
    )

    api_result = build_toss_sale_business_identity(
        tenant_id="store-a",
        provider_account_ref="toss-main",
        order_id="order-100",
        line_id="0",
        sku_id="sku-001",
        occurred_at=occurred_at,
        schema_version="1.0",
    )

    assert file_result.identity is not None
    assert api_result.identity is not None

    file_key = file_result.identity.key()
    api_key = api_result.identity.key()

    assert file_key == api_key

    registry = EffectRegistry()

    assert (
        registry.apply_business_effect_once(
            "store-a",
            "shadow_inventory",
            file_key,
        )
        is True
    )

    assert (
        registry.apply_business_effect_once(
            "store-a",
            "shadow_inventory",
            api_key,
        )
        is False
    )

    assert registry.business_effect_count == 1


def test_different_business_fact_applies_separate_effect() -> None:
    occurred_at = datetime(2026, 9, 6, 10, 30, tzinfo=UTC)

    first = build_toss_sale_business_identity(
        tenant_id="store-a",
        provider_account_ref="toss-main",
        order_id="order-100",
        line_id="0",
        sku_id="sku-001",
        occurred_at=occurred_at,
        schema_version="1.0",
    )

    second = build_toss_sale_business_identity(
        tenant_id="store-a",
        provider_account_ref="toss-main",
        order_id="order-100",
        line_id="1",
        sku_id="sku-001",
        occurred_at=occurred_at,
        schema_version="1.0",
    )

    assert first.identity is not None
    assert second.identity is not None

    registry = EffectRegistry()

    assert (
        registry.apply_business_effect_once(
            "store-a",
            "shadow_inventory",
            first.identity.key(),
        )
        is True
    )

    assert (
        registry.apply_business_effect_once(
            "store-a",
            "shadow_inventory",
            second.identity.key(),
        )
        is True
    )

    assert registry.business_effect_count == 2


def test_cross_mode_same_business_fact_has_one_pipeline_effect() -> None:
    pipeline = OfflineSalePipeline()

    occurred_at = datetime(2026, 9, 6, 10, 30, tzinfo=UTC)

    identity_result = build_toss_sale_business_identity(
        tenant_id="store-a",
        provider_account_ref="toss-main",
        order_id="order-100",
        line_id="0",
        sku_id="sku-001",
        occurred_at=occurred_at,
        schema_version="1.0",
    )

    assert identity_result.identity is not None
    business_key = identity_result.identity.key()

    api_event = {
        "event_id": "evt-api-001",
        "event_type": "offline_sale.recorded",
        "schema_version": "1.0",
        "tenant_id": "store-a",
        "source": "TOSS_POS",
        "source_event_id": "order-100:line:0",
        "occurred_at": occurred_at.isoformat(),
        "ingested_at": occurred_at.isoformat(),
        "idempotency_key": "TOSS_POS:order-100:line:0:1.0",
        "correlation_id": "corr-api-001",
        "payload": {
            "sku_id": "sku-001",
            "quantity": 1,
            "business_identity_key": business_key,
        },
    }

    file_event = {
        "event_id": "evt-file-001",
        "event_type": "offline_sale.recorded",
        "schema_version": "1.0",
        "tenant_id": "store-a",
        "source": "TOSS_POS",
        "source_event_id": "file-abc:row:100",
        "occurred_at": occurred_at.isoformat(),
        "ingested_at": occurred_at.isoformat(),
        "idempotency_key": "TOSS_POS:file-abc:row:100:1.0",
        "correlation_id": "corr-file-001",
        "payload": {
            "sku_id": "sku-001",
            "quantity": 1,
            "business_identity_key": business_key,
        },
    }

    api_receipt = pipeline.process(api_event)
    file_receipt = pipeline.process(file_event)

    # Source identity는 다르므로 둘 다 Inbox에 들어온다.
    assert api_receipt.status == "ACCEPTED"
    assert file_receipt.status == "ACCEPTED"
    assert pipeline.inbox.accepted_count == 2

    # 하지만 실제 판매 사실은 하나이므로 effect는 한 번뿐이다.
    assert pipeline.effects.business_effect_count == 1
    assert len(pipeline.insights) == 1

    assert any("effect_replayed" in record for record in pipeline.trace)


def test_production_sale_without_business_identity_has_no_effect() -> None:
    from copy import deepcopy

    raw = deepcopy(DEMO_SCENARIOS["offline_sale"])
    pipeline = OfflineSalePipeline()

    receipt = pipeline.process(raw, environment="PRODUCTION_READ")

    assert receipt.status == "ACCEPTED"
    assert pipeline.effects.business_effect_count == 0
    assert pipeline.insights == []
    assert any("business_identity_required" in record for record in pipeline.trace)


def test_business_identity_collision_has_no_second_effect() -> None:
    from copy import deepcopy

    first = deepcopy(DEMO_SCENARIOS["offline_sale"])
    first["payload"]["business_identity_key"] = "business-key-1"
    second = deepcopy(first)
    second["event_id"] = "evt-collision-2"
    second["source_event_id"] = "source-collision-2"
    second["idempotency_key"] = "TOSS_POS:source-collision-2:1.0"
    second["correlation_id"] = "corr-collision-2"
    second["payload"]["quantity"] = first["payload"]["quantity"] + 1
    pipeline = OfflineSalePipeline()

    assert pipeline.process(first).status == "ACCEPTED"
    assert pipeline.process(second).status == "ACCEPTED"

    assert pipeline.effects.business_effect_count == 1
    assert len(pipeline.insights) == 1
    assert any("business_identity_collision" in record for record in pipeline.trace)
