from pathlib import Path

from backend.app.sync.cafe24_commerce_integrity import (
    run_cafe24_commerce_integrity,
)
from backend.app.sync.cafe24_product_full_runner import (
    _find_first_missing_product_offset,
)


PROTECTED_ROOT = Path(
    r"C:\ai-commerce-private\cafe24"
)

SANITIZED_ORDER_CSV = (
    PROTECTED_ROOT
    / "cafe24"
    / "sanitized_order_export.csv"
)


def test_day08_product_pagination_has_no_gap() -> None:
    missing_offset = (
        _find_first_missing_product_offset(
            root=PROTECTED_ROOT,
            page_size=25,
        )
    )

    assert missing_offset is None


def test_day08_order_file_api_reconciliation() -> None:
    result = run_cafe24_commerce_integrity(
        protected_root=PROTECTED_ROOT,
        csv_path=SANITIZED_ORDER_CSV,
    )

    assert result.api_order_record_count == 1402
    assert result.api_unique_order_count == 1402
    assert result.api_duplicate_order_count == 0

    assert result.csv_unique_order_count == 1319
    assert result.csv_order_intersection_count == 1319
    assert result.csv_order_only_count == 0
    assert result.api_order_only_count == 83

    assert result.api_order_item_record_count == 3934
    assert result.api_unique_order_item_count == 3934
    assert result.api_duplicate_order_item_count == 0

    assert result.csv_unique_order_item_count == 3679
    assert result.csv_item_intersection_count == 3679
    assert result.csv_item_only_count == 0
    assert result.api_item_only_count == 255

    assert result.blocking_finding_count == 0
    assert result.warning_count == 338
    assert result.passed is True


def test_day08_order_relations_are_not_orphaned() -> None:
    result = run_cafe24_commerce_integrity(
        protected_root=PROTECTED_ROOT,
        csv_path=SANITIZED_ORDER_CSV,
    )

    assert result.order_item_missing_parent_count == 0
    assert result.refund_missing_parent_count == 0


def test_day08_order_manifests_are_valid() -> None:
    result = run_cafe24_commerce_integrity(
        protected_root=PROTECTED_ROOT,
        csv_path=SANITIZED_ORDER_CSV,
    )

    assert result.order_manifest_missing_count == 0
    assert result.order_item_manifest_missing_count == 0
    assert result.refund_manifest_missing_count == 0
    assert result.manifest_invalid_count == 0

from backend.app.services.ingestion.idempotency import (
    EffectRegistry,
)


def test_day08_file_and_api_same_business_fact_apply_once() -> None:
    registry = EffectRegistry()

    tenant_id = "day08-store"
    consumer = "commerce-order"

    business_identity = (
        "CAFE24:ORDER:"
        "day08-synthetic-order:"
        "item-1"
    )

    file_applied = (
        registry.apply_business_effect_once(
            tenant_id,
            consumer,
            business_identity,
        )
    )

    api_applied = (
        registry.apply_business_effect_once(
            tenant_id,
            consumer,
            business_identity,
        )
    )

    assert file_applied is True
    assert api_applied is False
    assert registry.business_effect_count == 1