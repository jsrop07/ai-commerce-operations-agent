from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.adapters.providers.toss_pos.mapper import TossSaleMappingResult
from backend.app.db.base import Base
from backend.app.models.catalog import SKU, Brand, Product, ProviderMapping
from backend.app.services.ingestion.mapping_flow import (
    reprocess_toss_mapping_item,
    route_toss_mapping_result,
)
from backend.app.services.ingestion.mapping_queue import MappingReviewQueue


@pytest.fixture
def approved_session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        brand = Brand(tenant_id="store-a", canonical_name="Synthetic Brand", aliases=[])
        product = Product(tenant_id="store-a", name="Synthetic Product", brand=brand)
        session.add(
            SKU(id="sku-001", tenant_id="store-a", canonical_code="SYN-001", product=product)
        )
        session.add(
            ProviderMapping(
                tenant_id="store-a",
                provider="TOSS_POS",
                object_type="SKU",
                external_id="TOSS-P999",
                canonical_id="sku-001",
                confidence=1.0,
                status="VERIFIED",
                approved=True,
            )
        )
        session.commit()
        yield session
    engine.dispose()


def test_toss_mapping_required_is_routed_to_queue() -> None:
    queue = MappingReviewQueue()

    mapper_result = TossSaleMappingResult(
        status="MAPPING_REQUIRED",
        event=None,
        external_product_code="TOSS-P999",
        external_product_text="미매핑 상품",
        reason="UNKNOWN_PRODUCT_CODE",
    )

    result = route_toss_mapping_result(
        result=mapper_result,
        queue=queue,
        tenant_id="store-a",
        source_identity_key="source-key-001",
    )

    assert result.status == "QUEUED"
    assert result.queue_item is not None
    assert result.queue_item.external_id == "TOSS-P999"
    assert result.queue_item.reason == "UNKNOWN_PRODUCT_CODE"
    assert queue.enqueued_count == 1


def test_non_mapping_required_result_is_not_queued() -> None:
    queue = MappingReviewQueue()

    mapper_result = TossSaleMappingResult(
        status="QUARANTINED",
        event=None,
        external_product_code="TOSS-P999",
        external_product_text="잘못된 데이터",
        reason="INVALID_QUANTITY",
    )

    result = route_toss_mapping_result(
        result=mapper_result,
        queue=queue,
        tenant_id="store-a",
        source_identity_key="source-key-002",
    )

    assert result.status == "NOT_REQUIRED"
    assert result.queue_item is None
    assert queue.enqueued_count == 0


def test_repeated_mapping_required_source_is_not_duplicated() -> None:
    queue = MappingReviewQueue()

    mapper_result = TossSaleMappingResult(
        status="MAPPING_REQUIRED",
        event=None,
        external_product_code="TOSS-P999",
        external_product_text="미매핑 상품",
        reason="UNKNOWN_PRODUCT_CODE",
    )

    first = route_toss_mapping_result(
        result=mapper_result,
        queue=queue,
        tenant_id="store-a",
        source_identity_key="source-key-001",
    )

    second = route_toss_mapping_result(
        result=mapper_result,
        queue=queue,
        tenant_id="store-a",
        source_identity_key="source-key-001",
    )

    assert first.queue_item is not None
    assert second.queue_item is not None
    assert first.queue_item.queue_id == second.queue_item.queue_id

    assert queue.enqueued_count == 1
    assert queue.replayed_count == 1


def test_approved_mapping_reprocesses_and_resolves_queue(approved_session) -> None:
    queue = MappingReviewQueue()

    mapper_result = TossSaleMappingResult(
        status="MAPPING_REQUIRED",
        event=None,
        external_product_code="TOSS-P999",
        external_product_text="미매핑 상품",
        reason="UNKNOWN_PRODUCT_CODE",
    )

    queued = route_toss_mapping_result(
        result=mapper_result,
        queue=queue,
        tenant_id="store-a",
        source_identity_key="source-key-001",
    )

    assert queued.queue_item is not None

    result = reprocess_toss_mapping_item(
        queue_id=queued.queue_item.queue_id,
        queue=queue,
        tenant_id="store-a",
        provider_account_ref="toss-main",
        order={
            "id": "order-100",
            "orderState": "COMPLETED",
            "completedAt": "2026-09-06T10:30:00+00:00",
        },
        line_item={
            "item": {
                "code": "TOSS-P999",
                "title": "미매핑 상품",
            },
            "quantity": 1,
            "amount": "15000",
        },
        line_index=0,
        session=approved_session,
        approved_sku_by_product_code={
            "TOSS-P999": "sku-001",
        },
        ingested_at=datetime(2026, 9, 6, 10, 31, tzinfo=UTC),
    )

    assert result.status == "REPROCESSED"
    assert result.mapping_result is not None
    assert result.mapping_result.status == "MAPPED"
    assert result.mapping_result.event is not None

    assert queued.queue_item.queue_id not in queue.pending
    assert queued.queue_item.queue_id in queue.resolved
    assert queue.resolved_count == 1


def test_reprocess_without_approved_mapping_stays_pending() -> None:
    queue = MappingReviewQueue()

    queued = route_toss_mapping_result(
        result=TossSaleMappingResult(
            status="MAPPING_REQUIRED",
            event=None,
            external_product_code="TOSS-P999",
            external_product_text="미매핑 상품",
            reason="UNKNOWN_PRODUCT_CODE",
        ),
        queue=queue,
        tenant_id="store-a",
        source_identity_key="source-key-002",
    )

    assert queued.queue_item is not None

    result = reprocess_toss_mapping_item(
        queue_id=queued.queue_item.queue_id,
        queue=queue,
        tenant_id="store-a",
        provider_account_ref="toss-main",
        order={
            "id": "order-101",
            "orderState": "COMPLETED",
            "completedAt": "2026-09-06T10:30:00+00:00",
        },
        line_item={
            "item": {
                "code": "TOSS-P999",
                "title": "미매핑 상품",
            },
            "quantity": 1,
            "amount": "15000",
        },
        line_index=0,
        approved_sku_by_product_code={},
    )

    assert result.status == "APPROVED_MAPPING_REQUIRED"

    assert queued.queue_item.queue_id in queue.pending
    assert queued.queue_item.queue_id not in queue.resolved
    assert queue.resolved_count == 0


def test_failed_reprocess_stays_pending(approved_session) -> None:
    queue = MappingReviewQueue()

    queued = route_toss_mapping_result(
        result=TossSaleMappingResult(
            status="MAPPING_REQUIRED",
            event=None,
            external_product_code="TOSS-P999",
            external_product_text="미매핑 상품",
            reason="UNKNOWN_PRODUCT_CODE",
        ),
        queue=queue,
        tenant_id="store-a",
        source_identity_key="source-key-003",
    )

    assert queued.queue_item is not None

    result = reprocess_toss_mapping_item(
        queue_id=queued.queue_item.queue_id,
        queue=queue,
        tenant_id="store-a",
        provider_account_ref="toss-main",
        order={
            "id": "order-102",
            "orderState": "COMPLETED",
            # completedAt / createdAt 없음 → mapper quarantine
        },
        line_item={
            "item": {
                "code": "TOSS-P999",
                "title": "미매핑 상품",
            },
            "quantity": 1,
            "amount": "15000",
        },
        line_index=0,
        session=approved_session,
        approved_sku_by_product_code={
            "TOSS-P999": "sku-001",
        },
    )

    assert result.status == "REPROCESS_FAILED"
    assert result.mapping_result is not None
    assert result.mapping_result.status == "QUARANTINED"

    assert queued.queue_item.queue_id in queue.pending
    assert queue.resolved_count == 0


def _queued_item(queue: MappingReviewQueue, source_key: str):
    result = route_toss_mapping_result(
        result=TossSaleMappingResult(
            status="MAPPING_REQUIRED",
            event=None,
            external_product_code="TOSS-P999",
            external_product_text="Synthetic unmapped product",
            reason="UNKNOWN_PRODUCT_CODE",
        ),
        queue=queue,
        tenant_id="store-a",
        source_identity_key=source_key,
    )
    assert result.queue_item is not None
    return result.queue_item


def _reprocess(queue, item, session):
    return reprocess_toss_mapping_item(
        queue_id=item.queue_id,
        queue=queue,
        tenant_id="store-a",
        provider_account_ref="toss-main",
        order={
            "id": "order-review",
            "orderState": "COMPLETED",
            "completedAt": "2026-09-06T10:30:00+00:00",
        },
        line_item={
            "item": {"code": "TOSS-P999", "title": "Synthetic product"},
            "quantity": 1,
            "amount": "1000",
        },
        line_index=0,
        session=session,
        ingested_at=datetime(2026, 9, 6, 10, 31, tzinfo=UTC),
    )


def test_reprocess_is_audited_and_repeated_call_is_safe(approved_session) -> None:
    queue = MappingReviewQueue()
    item = _queued_item(queue, "audit-source")

    assert _reprocess(queue, item, approved_session).status == "REPROCESSED"
    assert _reprocess(queue, item, approved_session).status == "NOT_PENDING"

    assert [entry.status for entry in queue.audit] == ["REPROCESSED", "NOT_PENDING"]
    assert queue.audit[0].canonical_id == "sku-001"
    assert queue.audit[0].mapping_version == 1
    assert queue.resolved_count == 1


def test_ambiguous_mapping_reprocess_fails_closed(approved_session) -> None:
    approved_session.add(
        ProviderMapping(
            tenant_id="store-a",
            provider="TOSS_POS",
            object_type="SKU",
            external_id="TOSS-P999",
            canonical_id=None,
            confidence=0.5,
            status="AMBIGUOUS",
            approved=False,
            version=2,
        )
    )
    approved_session.commit()
    queue = MappingReviewQueue()
    item = _queued_item(queue, "ambiguous-source")

    result = _reprocess(queue, item, approved_session)

    assert result.status == "AMBIGUOUS_MAPPING"
    assert item.queue_id in queue.pending
    assert queue.audit[-1].status == "AMBIGUOUS_MAPPING"


def test_mapping_collision_reprocess_fails_closed(approved_session) -> None:
    original_sku = approved_session.get(SKU, "sku-001")
    assert original_sku is not None
    approved_session.add(
        SKU(
            id="sku-002",
            tenant_id="store-a",
            canonical_code="SYN-002",
            product_id=original_sku.product_id,
        )
    )
    approved_session.add(
        ProviderMapping(
            tenant_id="store-a",
            provider="TOSS_POS",
            object_type="SKU",
            external_id="TOSS-P999",
            canonical_id="sku-002",
            confidence=1.0,
            status="VERIFIED",
            approved=True,
            version=2,
        )
    )
    approved_session.commit()
    queue = MappingReviewQueue()
    item = _queued_item(queue, "collision-source")

    result = _reprocess(queue, item, approved_session)

    assert result.status == "MAPPING_COLLISION"
    assert item.queue_id in queue.pending
    assert queue.audit[-1].status == "MAPPING_COLLISION"
