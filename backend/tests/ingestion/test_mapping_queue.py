from backend.app.services.ingestion.mapping_queue import MappingReviewQueue


def test_mapping_required_item_is_queued() -> None:
    queue = MappingReviewQueue()

    item = queue.enqueue(
        tenant_id="store-a",
        provider="TOSS_POS",
        object_type="SKU",
        external_id="TOSS-P999",
        external_text="알 수 없는 테스트 상품",
        source_identity_key="source-key-001",
        reason="UNKNOWN_PRODUCT_CODE",
    )

    assert item.status == "PENDING"
    assert item.external_id == "TOSS-P999"
    assert item.reason == "UNKNOWN_PRODUCT_CODE"

    assert queue.enqueued_count == 1
    assert queue.replayed_count == 0
    assert len(queue.pending) == 1


def test_same_source_mapping_request_is_not_queued_twice() -> None:
    queue = MappingReviewQueue()

    first = queue.enqueue(
        tenant_id="store-a",
        provider="TOSS_POS",
        object_type="SKU",
        external_id="TOSS-P999",
        external_text="테스트 상품",
        source_identity_key="source-key-001",
        reason="UNKNOWN_PRODUCT_CODE",
    )

    second = queue.enqueue(
        tenant_id="store-a",
        provider="TOSS_POS",
        object_type="SKU",
        external_id="TOSS-P999",
        external_text="테스트 상품",
        source_identity_key="source-key-001",
        reason="UNKNOWN_PRODUCT_CODE",
    )

    assert first.queue_id == second.queue_id
    assert queue.enqueued_count == 1
    assert queue.replayed_count == 1
    assert len(queue.pending) == 1


def test_different_source_records_are_separate_review_items() -> None:
    queue = MappingReviewQueue()

    first = queue.enqueue(
        tenant_id="store-a",
        provider="TOSS_POS",
        object_type="SKU",
        external_id="TOSS-P999",
        external_text="테스트 상품",
        source_identity_key="source-key-001",
        reason="UNKNOWN_PRODUCT_CODE",
    )

    second = queue.enqueue(
        tenant_id="store-a",
        provider="TOSS_POS",
        object_type="SKU",
        external_id="TOSS-P999",
        external_text="테스트 상품",
        source_identity_key="source-key-002",
        reason="UNKNOWN_PRODUCT_CODE",
    )

    assert first.queue_id != second.queue_id
    assert queue.enqueued_count == 2


def test_missing_external_id_can_still_be_reviewed_fail_closed() -> None:
    queue = MappingReviewQueue()

    item = queue.enqueue(
        tenant_id="store-a",
        provider="TOSS_POS",
        object_type="SKU",
        external_id=None,
        external_text="상품명만 존재",
        source_identity_key="source-key-003",
        reason="MISSING_PRODUCT_CODE",
    )

    assert item.status == "PENDING"
    assert item.external_id is None
    assert item.reason == "MISSING_PRODUCT_CODE"


def test_resolved_source_replay_is_not_reopened() -> None:
    queue = MappingReviewQueue()
    item = queue.enqueue(
        tenant_id="store-a",
        provider="TOSS_POS",
        object_type="SKU",
        external_id="TOSS-P999",
        external_text="Synthetic product",
        source_identity_key="resolved-source",
        reason="UNKNOWN_PRODUCT_CODE",
    )
    queue.resolve(item.queue_id)

    replay = queue.enqueue(
        tenant_id="store-a",
        provider="TOSS_POS",
        object_type="SKU",
        external_id="TOSS-P999",
        external_text="Synthetic product",
        source_identity_key="resolved-source",
        reason="UNKNOWN_PRODUCT_CODE",
    )

    assert replay.status == "RESOLVED"
    assert item.queue_id not in queue.pending
    assert queue.enqueued_count == 1
    assert queue.resolved_count == 1
    assert queue.replayed_count == 1
