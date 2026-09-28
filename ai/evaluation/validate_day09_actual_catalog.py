from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from ai.retrieval.catalog_filter import (
    CatalogFilter,
    build_descendant_map,
    filter_products,
)


HANDOFF_PATH = Path(
    "artifacts/integration/day09/"
    "ai_catalog_handoff.json"
)

EXPECTED_HASH = (
    "5e47ff6b09a6893ac2bf51d2f70716c5f8f7553e55d647c5ce043edbff98276c"
)


def load_handoff() -> dict[str, Any]:
    return json.loads(
        HANDOFF_PATH.read_text(
            encoding="utf-8"
        )
    )


def file_sha256() -> str:
    return hashlib.sha256(
        HANDOFF_PATH.read_bytes()
    ).hexdigest()


def require(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    handoff = load_handoff()

    products = handoff["products"]
    categories = handoff["categories"]

    descendant_map = build_descendant_map(
        categories
    )

    # -----------------------------
    # Provenance / contract
    # -----------------------------

    require(
        handoff["schema_version"]
        == "day09-ai-catalog-handoff.v1",
        "schema_version mismatch",
    )

    require(
        handoff["artifact_version"]
        == "1.0.0",
        "artifact_version mismatch",
    )

    require(
        handoff["source_classification"]
        == "SANITIZED_REAL",
        "source_classification mismatch",
    )

    require(
        handoff["artifact_hash"]
        == EXPECTED_HASH,
        "declared artifact_hash mismatch",
    )

    # artifact_hash가 파일 전체 hash와 동일하다는
    # 의미인지 여부는 Backend 계약에 따라 다를 수 있으므로
    # 실제 raw file hash도 별도로 기록한다.
    raw_file_hash = file_sha256()

    # -----------------------------
    # Product identity
    # -----------------------------

    product_nos = [
        int(product["product_no"])
        for product in products
    ]

    require(
        len(products) == 2167,
        "Full Catalog must be 2167",
    )

    require(
        len(set(product_nos)) == 2167,
        "product_no identity dedupe failed",
    )

    # -----------------------------
    # Operational rule
    # -----------------------------

    operational_rule_mismatch = []

    for product in products:
        calculated = (
            str(product["display"]).upper() == "T"
            and str(product["selling"]).upper() == "T"
        )

        if bool(product["operational"]) != calculated:
            operational_rule_mismatch.append(
                product["product_no"]
            )

    require(
        not operational_rule_mismatch,
        (
            "operational rule mismatch: "
            f"{operational_rule_mismatch[:10]}"
        ),
    )

    operational = filter_products(
        products,
        filter_=CatalogFilter(
            operational=True
        ),
        descendant_map=descendant_map,
    )

    non_operational = filter_products(
        products,
        filter_=CatalogFilter(
            operational=False
        ),
        descendant_map=descendant_map,
    )

    require(
        len(operational) == 2019,
        "Operational count must be 2019",
    )

    require(
        len(non_operational) == 148,
        "Non-operational count must be 148",
    )

    # -----------------------------
    # Category state
    # -----------------------------

    categorized = [
        product
        for product in products
        if product["category_nos"]
    ]

    uncategorized = [
        product
        for product in products
        if not product["category_nos"]
    ]

    uncategorized_operational = [
        product
        for product in uncategorized
        if product["operational"]
    ]

    require(
        len(categories) == 123,
        "Category count must be 123",
    )

    require(
        len(categorized) == 2132,
        "Categorized products must be 2132",
    )

    require(
        len(uncategorized) == 35,
        "Uncategorized products must be 35",
    )

    require(
        len(uncategorized_operational) == 8,
        (
            "Uncategorized operational "
            "products must be 8"
        ),
    )

    # Category가 없다고 상품을 corpus에서
    # 제거하면 안 된다.
    require(
        len(categorized)
        + len(uncategorized)
        == 2167,
        "Uncategorized product preservation failed",
    )

    # -----------------------------
    # 0..N category membership
    # -----------------------------

    multi_category = [
        product
        for product in products
        if len(product["category_nos"]) > 1
    ]

    max_categories = max(
        len(product["category_nos"])
        for product in products
    )

    require(
        len(multi_category) == 27,
        "Multi-category products must be 27",
    )

    require(
        max_categories == 4,
        "Max categories/product must be 4",
    )

    require(
        len(
            handoff[
                "category_product_relations"
            ]
        )
        == 2165,
        "Product-category relations must be 2165",
    )

    # -----------------------------
    # PRE-ORDER actual smoke
    # -----------------------------

    preorder_no = int(
        handoff["preorder_category_no"]
    )

    require(
        preorder_no == 56,
        "PRE-ORDER category_no must be 56",
    )

    preorder_direct = filter_products(
        products,
        filter_=CatalogFilter(
            category_no=56,
            recursive_category=False,
        ),
        descendant_map=descendant_map,
    )

    preorder_operational = filter_products(
        products,
        filter_=CatalogFilter(
            category_no=56,
            recursive_category=False,
            operational=True,
        ),
        descendant_map=descendant_map,
    )

    preorder_sold_out = filter_products(
        products,
        filter_=CatalogFilter(
            category_no=56,
            recursive_category=False,
            sold_out=True,
        ),
        descendant_map=descendant_map,
    )

    require(
        len(preorder_direct) == 48,
        "PRE-ORDER direct must be 48",
    )

    require(
        len(preorder_operational) == 46,
        (
            "PRE-ORDER operational "
            "must be 46"
        ),
    )

    require(
        len(preorder_sold_out) == 16,
        (
            "PRE-ORDER sold-out "
            "must be 16"
        ),
    )

    # sold_out은 operational 제외조건이 아님.
    sold_out_operational = [
        product
        for product in products
        if (
            product["operational"]
            and str(
                product["sold_out"]
            ).upper() == "T"
        )
    ]

    # -----------------------------
    # Recursive category smoke
    # -----------------------------

    recursive_expected = {
        46: 570,  # Games Workshop
        57: 669,  # Warhammer 40K
        67: 364,  # Paint
    }

    recursive_actual: dict[int, int] = {}

    for category_no, expected in (
        recursive_expected.items()
    ):
        result = filter_products(
            products,
            filter_=CatalogFilter(
                category_no=category_no,
                recursive_category=True,
            ),
            descendant_map=descendant_map,
        )

        recursive_actual[
            category_no
        ] = len(result)

        require(
            len(result) == expected,
            (
                f"recursive category "
                f"{category_no}: "
                f"expected={expected}, "
                f"actual={len(result)}"
            ),
        )

    # direct count도 비교용 기록
    direct_actual: dict[int, int] = {}

    for category_no in (
        46,
        57,
        67,
    ):
        direct_actual[
            category_no
        ] = len(
            filter_products(
                products,
                filter_=CatalogFilter(
                    category_no=category_no,
                    recursive_category=False,
                ),
                descendant_map=descendant_map,
            )
        )

    require(
        direct_actual[46] == 0,
        "Games Workshop direct must be 0",
    )

    require(
        direct_actual[57] == 29,
        "Warhammer 40K direct must be 29",
    )

    require(
        direct_actual[67] == 0,
        "Paint direct must be 0",
    )

    # -----------------------------
    # Brand coverage
    # -----------------------------

    brand_values = [
        product.get("brand_code")
        for product in products
    ]

    brand_null_count = sum(
        value in (
            None,
            "",
        )
        for value in brand_values
    )

    brand_counter = Counter(
        str(value)
        for value in brand_values
        if value not in (
            None,
            "",
        )
    )

    # -----------------------------
    # Safety
    # -----------------------------

    safety = handoff["safety"]

    require(
        safety["customer_pii_included"]
        is False,
        "PII must not be included",
    )

    require(
        safety["raw_data_included"]
        is False,
        "Raw provider data must not be included",
    )

    require(
        safety["cafe24_api_call_count"]
        == 0,
        "Cafe24 API calls must remain 0",
    )

    require(
        safety["oauth_call_count"]
        == 0,
        "OAuth calls must remain 0",
    )

    require(
        safety["external_network_call_count"]
        == 0,
        "External network calls must remain 0",
    )

    require(
        safety[
            "production_provider_write_count"
        ]
        == 0,
        (
            "Production provider writes "
            "must remain 0"
        ),
    )

    print(
        "DAY09_ACTUAL_CATALOG_VALIDATION_OK"
    )

    print(
        "SOURCE_CLASSIFICATION=",
        handoff["source_classification"],
    )

    print(
        "SCHEMA_VERSION=",
        handoff["schema_version"],
    )

    print(
        "ARTIFACT_VERSION=",
        handoff["artifact_version"],
    )

    print(
        "DECLARED_ARTIFACT_HASH=",
        handoff["artifact_hash"],
    )

    print(
        "RAW_FILE_SHA256=",
        raw_file_hash,
    )

    print(
        "PRODUCT_AS_OF=",
        handoff["product_snapshot_as_of"],
    )

    print(
        "CATEGORY_AS_OF=",
        handoff["category_snapshot_as_of"],
    )

    print(
        "RELATION_AS_OF=",
        handoff["relation_snapshot_as_of"],
    )

    print(
        "FULL_CATALOG=",
        len(products),
    )

    print(
        "OPERATIONAL=",
        len(operational),
    )

    print(
        "NON_OPERATIONAL=",
        len(non_operational),
    )

    print(
        "CATEGORIES=",
        len(categories),
    )

    print(
        "CATEGORIZED=",
        len(categorized),
    )

    print(
        "UNCATEGORIZED=",
        len(uncategorized),
    )

    print(
        "UNCATEGORIZED_OPERATIONAL=",
        len(
            uncategorized_operational
        ),
    )

    print(
        "MULTI_CATEGORY=",
        len(multi_category),
    )

    print(
        "MAX_CATEGORIES_PER_PRODUCT=",
        max_categories,
    )

    print(
        "RELATIONS=",
        len(
            handoff[
                "category_product_relations"
            ]
        ),
    )

    print(
        "PREORDER_DIRECT=",
        len(preorder_direct),
    )

    print(
        "PREORDER_OPERATIONAL=",
        len(preorder_operational),
    )

    print(
        "PREORDER_SOLD_OUT=",
        len(preorder_sold_out),
    )

    print(
        "OPERATIONAL_AND_SOLD_OUT=",
        len(sold_out_operational),
    )

    print(
        "GAMES_WORKSHOP_DIRECT=",
        direct_actual[46],
    )

    print(
        "GAMES_WORKSHOP_RECURSIVE=",
        recursive_actual[46],
    )

    print(
        "WARHAMMER_40K_DIRECT=",
        direct_actual[57],
    )

    print(
        "WARHAMMER_40K_RECURSIVE=",
        recursive_actual[57],
    )

    print(
        "PAINT_DIRECT=",
        direct_actual[67],
    )

    print(
        "PAINT_RECURSIVE=",
        recursive_actual[67],
    )

    print(
        "BRAND_COVERAGE=",
        len(brand_values)
        - brand_null_count,
        "/",
        len(brand_values),
    )

    print(
        "BRAND_NULL_COUNT=",
        brand_null_count,
    )

    print(
        "BRAND_DISTINCT_COUNT=",
        len(brand_counter),
    )

    print(
        "BRAND_TOP10=",
        brand_counter.most_common(10),
    )

    print(
        "LANGUAGE_METADATA="
        "NOT_ELIGIBLE"
    )

    print(
        "PRODUCTION_PROVIDER_WRITE=0"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )