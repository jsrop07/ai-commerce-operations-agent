"""Day 9 Cafe24 current category-product relation tests."""

import json

from backend.app.adapters.providers.cafe24.adapter import (
    Cafe24Adapter,
)
from backend.app.adapters.providers.capability_guard import (
    CAFE24_ALLOWED_READ_PATH_PATTERNS,
    CAFE24_ALLOWED_READ_PATHS,
)
from backend.app.adapters.providers.http_transport import (
    ReadOnlyHttpTransport,
)
from backend.app.sync.cafe24_category_product_snapshot import (
    run_cafe24_category_product_snapshot,
)

TOKEN_FIXTURE = "-".join(
    ("synthetic", "token")
)


def test_current_category_products_are_captured_as_current_evidence(
    tmp_path,
) -> None:
    calls: list[dict[str, object]] = []

    def request(**kwargs: object) -> dict[str, object]:
        calls.append(kwargs)
        return {
            "products": [
                {
                    "product_no": 101,
                    "product_name": "Synthetic Product",
                },
                {
                    "product_no": 202,
                    "product_name": "Synthetic Product 2",
                },
            ]
        }

    transport = ReadOnlyHttpTransport(
        request_fn=request,
        granted_scopes={
            "mall.read_product",
        },
        allowed_paths=(
            CAFE24_ALLOWED_READ_PATHS
        ),
        allowed_path_patterns=(
            CAFE24_ALLOWED_READ_PATH_PATTERNS
        ),
    )
    adapter = Cafe24Adapter(
        mall_id="synthetic-mall",
        access_token=TOKEN_FIXTURE,
        transport=transport,
    )

    result = run_cafe24_category_product_snapshot(
        adapter=adapter,
        protected_root=tmp_path,
        batch_id="day09-current-preorder",
        category_no=50,
    )

    assert result.relation_count == 2
    assert result.request_count == 1
    assert result.external_write_count == 0
    assert len(calls) == 1
    assert calls[0]["method"] == "GET"
    assert calls[0]["params"] == {
        "display_group": 1,
        "limit": 50_000,
    }

    raw = json.loads(
        result.raw_snapshot.raw_path.read_text(
            encoding="utf-8"
        )
    )
    sanitized = json.loads(
        result.sanitized_snapshot.sanitized_path.read_text(
            encoding="utf-8"
        )
    )
    assert raw["products"][0]["product_name"] == (
        "Synthetic Product"
    )
    assert {
        (
            record["category_no"],
            record["product_no"],
        )
        for record in sanitized["records"]
    } == {
        (50, 101),
        (50, 202),
    }
    assert all(
        record["evidence_type"]
        == "CURRENT_CATEGORY_EVIDENCE"
        and record["source_classification"]
        == "SANITIZED_REAL"
        and record["as_of"]
        and record["provenance"]["raw_sha256"]
        == result.raw_snapshot.raw_sha256
        for record in sanitized["records"]
    )
    assert result.manifest_path.exists()


def test_category_product_adapter_does_not_expose_product_payload() -> None:
    def request(**_: object) -> dict[str, object]:
        return {
            "products": [
                {
                    "product_no": 303,
                    "product_name": "not relation data",
                },
            ]
        }

    adapter = Cafe24Adapter(
        mall_id="synthetic-mall",
        access_token=TOKEN_FIXTURE,
        transport=ReadOnlyHttpTransport(
            request_fn=request,
            granted_scopes={
                "mall.read_product",
            },
            allowed_paths=(
                CAFE24_ALLOWED_READ_PATHS
            ),
            allowed_path_patterns=(
                CAFE24_ALLOWED_READ_PATH_PATTERNS
            ),
        ),
    )

    page = adapter.read_category_products(50)

    assert page.resource == (
        "category_product_relations"
    )
    assert page.items == [
        {
            "category_no": 50,
            "product_no": 303,
        }
    ]


def test_empty_category_snapshot_records_success_metadata(
    tmp_path,
) -> None:
    def request(**_: object) -> dict[str, object]:
        return {"products": []}

    adapter = Cafe24Adapter(
        mall_id="synthetic-mall",
        access_token=TOKEN_FIXTURE,
        transport=ReadOnlyHttpTransport(
            request_fn=request,
            granted_scopes={
                "mall.read_product",
            },
            allowed_paths=(
                CAFE24_ALLOWED_READ_PATHS
            ),
            allowed_path_patterns=(
                CAFE24_ALLOWED_READ_PATH_PATTERNS
            ),
        ),
    )

    result = run_cafe24_category_product_snapshot(
        adapter=adapter,
        protected_root=tmp_path,
        batch_id="empty-category-read",
        category_no=999,
        source_classification="LIVE_READ",
    )
    payload = json.loads(
        result.sanitized_snapshot
        .sanitized_path.read_text(
            encoding="utf-8"
        )
    )

    assert payload["records"] == []
    assert payload["snapshot_metadata"] == {
        "category_no": 999,
        "display_group": 1,
        "read_succeeded": True,
        "relation_count": 0,
        "as_of": result.as_of.isoformat(),
        "source_classification": "LIVE_READ",
        "evidence_type": (
            "CURRENT_CATEGORY_EVIDENCE"
        ),
        "external_write_count": 0,
    }
    assert result.read_succeeded is True
    assert result.external_write_count == 0
