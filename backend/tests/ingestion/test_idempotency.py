import pytest

from backend.app.services.demo import DEMO_SCENARIOS
from backend.app.services.ingestion.idempotency import EffectRegistry
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
