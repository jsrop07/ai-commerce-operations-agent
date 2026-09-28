from __future__ import annotations

import hashlib
import json
import socket
from pathlib import Path

import pytest

from backend.app.sync.day09_ai_catalog_handoff import (
    ARTIFACT_VERSION,
    HISTORICAL_RESERVATION_WARNING,
    SCHEMA_VERSION,
    _latest_by_identity,
    _Observation,
    build_day09_ai_catalog_handoff,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PROTECTED_ROOT = Path(r"C:\ai-commerce-private\cafe24")
DAY08_GENERATOR = REPOSITORY_ROOT / "backend/app/sync/day08_ai_handoff.py"
DAY08_ARTIFACT = REPOSITORY_ROOT / "artifacts/integration/day08/ai_handoff.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_hash(payload: dict[str, object]) -> str:
    without_hash = dict(payload)
    without_hash.pop("artifact_hash")
    encoded = json.dumps(
        without_hash,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def test_latest_product_observation_is_selected_before_identity_projection() -> None:
    older = _Observation(
        record={"product_no": 7, "updated_date": "2026-01-01T00:00:00+00:00"},
        batch_id="product-full-000000-20260101T000000000000Z",
        file_name="older.sanitized.json",
        file_sha256="a" * 64,
        sequence=0,
    )
    newer = _Observation(
        record={"product_no": 7, "updated_date": "2026-02-01T00:00:00+00:00"},
        batch_id="product-full-000000-20260201T000000000000Z",
        file_name="newer.sanitized.json",
        file_sha256="b" * 64,
        sequence=0,
    )

    selected = _latest_by_identity((newer, older), identity_field="product_no")

    assert len(selected) == 1
    assert selected[7] == newer


@pytest.fixture(scope="module")
def generated(tmp_path_factory: pytest.TempPathFactory) -> tuple[dict, dict, bytes]:
    required = PROTECTED_ROOT / "cafe24/sanitized/category_product_relations"
    if not required.exists():
        pytest.skip("SANITIZED_REAL Cafe24 snapshot is not available")

    day08_before = (_sha256(DAY08_GENERATOR), _sha256(DAY08_ARTIFACT))
    first_dir = tmp_path_factory.mktemp("day09-ai-catalog-first")
    second_dir = tmp_path_factory.mktemp("day09-ai-catalog-second")

    original_connect = socket.socket.connect

    def reject_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("external network access is forbidden")

    socket.socket.connect = reject_network  # type: ignore[method-assign]
    try:
        first = build_day09_ai_catalog_handoff(
            protected_root=PROTECTED_ROOT,
            output_dir=first_dir,
        )
        second = build_day09_ai_catalog_handoff(
            protected_root=PROTECTED_ROOT,
            output_dir=second_dir,
        )
    finally:
        socket.socket.connect = original_connect  # type: ignore[method-assign]

    assert day08_before == (_sha256(DAY08_GENERATOR), _sha256(DAY08_ARTIFACT))
    first_bytes = first.artifact_path.read_bytes()
    assert first_bytes == second.artifact_path.read_bytes()
    payload = json.loads(first_bytes)
    validation = json.loads(first.validation_path.read_text(encoding="utf-8"))
    return payload, validation, first_bytes


def test_real_counts_and_recursive_scopes(generated: tuple[dict, dict, bytes]) -> None:
    payload, validation, _ = generated

    expected = {
        "product_observation_count": 2167,
        "product_count": 2167,
        "operational_product_count": 2019,
        "non_operational_product_count": 148,
        "categorized_product_count": 2132,
        "uncategorized_product_count": 35,
        "uncategorized_operational_product_count": 8,
        "multi_category_product_count": 27,
        "max_categories_per_product": 4,
        "category_count": 123,
        "preorder_relation_product_count": 48,
        "preorder_operational_product_count": 46,
        "preorder_sold_out_product_count": 16,
    }
    for key, value in expected.items():
        assert payload[key] == value

    scopes = payload["recursive_category_scopes"]
    assert scopes["46"]["recursive_product_count"] == 570
    assert scopes["57"]["recursive_product_count"] == 669
    assert scopes["67"]["recursive_product_count"] == 364
    assert validation["status"] == "PASSED"


def test_product_contract_and_current_evidence_safety(
    generated: tuple[dict, dict, bytes],
) -> None:
    payload, _, _ = generated
    products = payload["products"]

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["artifact_version"] == ARTIFACT_VERSION
    assert payload["historical_reservation_warning"] == HISTORICAL_RESERVATION_WARNING
    assert all("language" not in product for product in products)
    assert len({product["product_no"] for product in products}) == len(products)
    assert all("brand_code" in product for product in products)
    assert all(product["as_of"] for product in products)
    assert all(product["source_classification"] == "SANITIZED_REAL" for product in products)
    assert all(product["evidence_ids"] and product["provenance"] for product in products)

    uncategorized = [product for product in products if not product["category_nos"]]
    assert len(uncategorized) == 35
    assert all(product["category_status"] == "UNCATEGORIZED" for product in uncategorized)
    assert any(len(product["category_nos"]) == 1 for product in products)
    assert any(len(product["category_nos"]) > 1 for product in products)

    sold_out_operational = [
        product
        for product in products
        if product["sold_out"] == "T" and product["operational"]
    ]
    assert sold_out_operational
    assert all(
        product["display"] == "T" and product["selling"] == "T"
        for product in sold_out_operational
    )
    assert all(
        relation["evidence_type"] == "CURRENT_CATEGORY_EVIDENCE"
        for relation in payload["category_product_relations"]
    )


def test_hierarchy_provenance_privacy_and_hash(
    generated: tuple[dict, dict, bytes],
) -> None:
    payload, validation, _ = generated
    categories = payload["categories"]

    assert len({item["category_no"] for item in categories}) == 123
    assert all("parent_category_no" in item for item in categories)
    assert all(item["as_of"] and item["evidence_ids"] and item["provenance"] for item in categories)
    assert payload["artifact_hash"] == _canonical_hash(payload)
    assert validation["pii_scan"] == {"match_count": 0, "passed": True}
    assert validation["secret_scan"] == {"match_count": 0, "passed": True}
    assert validation["external_network_call_count"] == 0
    assert validation["production_provider_write_count"] == 0
    assert payload["safety"]["external_network_call_count"] == 0
    assert payload["safety"]["production_provider_write_count"] == 0
