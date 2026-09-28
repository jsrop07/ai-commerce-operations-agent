from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sentence_transformers import SentenceTransformer

from ai.evaluation.run_day09_actual_filter_eval import (
    EMBEDDING_MODEL,
    run_search_suite,
)
from ai.retrieval.catalog_filter import (
    CatalogFilter,
    build_descendant_map,
    filter_products,
)


HANDOFF_PATH = Path(
    "artifacts/integration/day09/"
    "ai_catalog_handoff.json"
)

OUTPUT_PATH = Path(
    "artifacts/experiments/day09/"
    "actual_filter_stratified_eval.json"
)


def load_handoff() -> dict[str, Any]:
    return json.loads(
        HANDOFF_PATH.read_text(
            encoding="utf-8"
        )
    )


def category_counts(
    *,
    products: list[dict[str, Any]],
    categories: list[dict[str, Any]],
    descendant_map: dict[int, set[int]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for category in categories:
        category_no = int(
            category["category_no"]
        )

        direct = filter_products(
            products,
            filter_=CatalogFilter(
                category_no=category_no,
                recursive_category=False,
            ),
            descendant_map=descendant_map,
        )

        recursive = filter_products(
            products,
            filter_=CatalogFilter(
                category_no=category_no,
                recursive_category=True,
            ),
            descendant_map=descendant_map,
        )

        rows.append(
            {
                "category_no": category_no,
                "category_name": str(
                    category["category_name"]
                ),
                "depth": int(
                    category["category_depth"]
                ),
                "parent_category_no": (
                    category.get(
                        "parent_category_no"
                    )
                ),
                "direct_count": len(direct),
                "recursive_count": len(
                    recursive
                ),
                "is_leaf": (
                    len(
                        descendant_map.get(
                            category_no,
                            {category_no},
                        )
                    )
                    == 1
                ),
            }
        )

    return rows


def choose_stratified_cases(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    실제 category hierarchy에서 대표 사례를 뽑는다.

    구성:
    - depth 1 대형/중형/소형
    - depth 2 대형/중형/소형
    - depth 3 leaf 대형/중형/소형
    - 비-Warhammer 명시 사례
    """

    selected: dict[
        int,
        dict[str, Any],
    ] = {}

    def add(
        row: dict[str, Any] | None,
    ) -> None:
        if row is None:
            return

        selected[
            int(row["category_no"])
        ] = row

    def pick_by_size(
        *,
        depth: int,
        leaf_only: bool = False,
    ) -> None:
        candidates = [
            row
            for row in rows
            if (
                row["depth"] == depth
                and row[
                    "recursive_count"
                ] > 0
                and (
                    not leaf_only
                    or row["is_leaf"]
                )
            )
        ]

        if not candidates:
            return

        candidates = sorted(
            candidates,
            key=lambda row: (
                row["recursive_count"],
                row["category_no"],
            ),
        )

        # 소형
        add(candidates[0])

        # 중형
        add(
            candidates[
                len(candidates) // 2
            ]
        )

        # 대형
        add(candidates[-1])

    pick_by_size(
        depth=1,
    )

    pick_by_size(
        depth=2,
    )

    pick_by_size(
        depth=3,
        leaf_only=True,
    )

    # 실제 상점의 비-Warhammer 계열도 반드시 포함한다.
    required_names = {
        "Ember: Obsidian Protocol",
        "WARMACHINE",
        "Hobby",
        "Tools",
    }

    for row in rows:
        if (
            row["category_name"]
            in required_names
            and row[
                "recursive_count"
            ] > 0
        ):
            add(row)

    # 기존 Day9 핵심 smoke도 포함
    required_nos = {
        46,  # Games Workshop
        56,  # PRE-ORDER
        57,  # Warhammer 40K
        67,  # Paint
    }

    for row in rows:
        if (
            row["category_no"]
            in required_nos
        ):
            add(row)

    return sorted(
        selected.values(),
        key=lambda row: (
            row["depth"],
            -row["recursive_count"],
            row["category_no"],
        ),
    )


def main() -> int:
    handoff = load_handoff()

    products = handoff[
        "products"
    ]

    categories = handoff[
        "categories"
    ]

    descendant_map = (
        build_descendant_map(
            categories
        )
    )

    rows = category_counts(
        products=products,
        categories=categories,
        descendant_map=descendant_map,
    )

    selected = (
        choose_stratified_cases(
            rows
        )
    )

    model = SentenceTransformer(
        EMBEDDING_MODEL,
        device="cpu",
    )

    results: list[
        dict[str, Any]
    ] = []

    pre_better_count = 0
    post_better_count = 0
    tie_count = 0

    pre_zero_count = 0
    post_zero_count = 0

    for row in selected:
        category_no = int(
            row["category_no"]
        )

        filter_ = CatalogFilter(
            category_no=category_no,
            recursive_category=True,
        )

        filtered_products = (
            filter_products(
                products,
                filter_=filter_,
                descendant_map=(
                    descendant_map
                ),
            )
        )

        query = row[
            "category_name"
        ]

        pre = run_search_suite(
            query=query,
            products=filtered_products,
            all_products=products,
            filter_=filter_,
            descendant_map=(
                descendant_map
            ),
            model=model,
            mode="PRE",
        )

        post = run_search_suite(
            query=query,
            products=products,
            all_products=products,
            filter_=filter_,
            descendant_map=(
                descendant_map
            ),
            model=model,
            mode="POST",
        )

        pre_rrf_count = (
            pre[
                "returned_count"
            ][
                "rrf"
            ]
        )

        post_rrf_count = (
            post[
                "returned_count"
            ][
                "rrf"
            ]
        )

        pre_latency = (
            pre[
                "search_latency_ms"
            ][
                "rrf_end_to_end_serial"
            ]
        )

        post_latency = (
            post[
                "search_latency_ms"
            ][
                "rrf_end_to_end_serial"
            ]
        )

        if pre_rrf_count == 0:
            pre_zero_count += 1

        if post_rrf_count == 0:
            post_zero_count += 1

        # Day9 우선 판단:
        # candidate retention이 우선,
        # 동일하면 latency가 낮은 쪽.
        if (
            pre_rrf_count
            > post_rrf_count
        ):
            decision = "PRE"
            pre_better_count += 1

        elif (
            post_rrf_count
            > pre_rrf_count
        ):
            decision = "POST"
            post_better_count += 1

        else:
            if (
                pre_latency
                < post_latency
            ):
                decision = "PRE"
                pre_better_count += 1

            elif (
                post_latency
                < pre_latency
            ):
                decision = "POST"
                post_better_count += 1

            else:
                decision = "TIE"
                tie_count += 1

        results.append(
            {
                "category_no": (
                    category_no
                ),
                "category_name": (
                    query
                ),
                "depth": (
                    row["depth"]
                ),
                "is_leaf": (
                    row["is_leaf"]
                ),
                "direct_count": (
                    row[
                        "direct_count"
                    ]
                ),
                "recursive_count": (
                    row[
                        "recursive_count"
                    ]
                ),
                "pre_rrf_returned": (
                    pre_rrf_count
                ),
                "post_rrf_returned": (
                    post_rrf_count
                ),
                "pre_rrf_e2e_ms": (
                    pre_latency
                ),
                "post_rrf_e2e_ms": (
                    post_latency
                ),
                "preferred": (
                    decision
                ),
            }
        )

    output = {
        "schema_version": (
            "day09-actual-filter-stratified-eval.v1"
        ),
        "day": 9,
        "source_classification": (
            "SANITIZED_REAL"
        ),
        "input": {
            "path": str(
                HANDOFF_PATH
            ),
            "artifact_hash": (
                handoff[
                    "artifact_hash"
                ]
            ),
            "product_count": (
                len(products)
            ),
            "category_count": (
                len(categories)
            ),
        },
        "sampling": {
            "strategy": (
                "STRATIFIED_ACTUAL_CATEGORY"
            ),
            "selected_case_count": (
                len(selected)
            ),
            "dimensions": [
                "depth",
                "recursive_size",
                "leaf_status",
                "warhammer_and_non_warhammer",
            ],
        },
        "summary": {
            "pre_preferred": (
                pre_better_count
            ),
            "post_preferred": (
                post_better_count
            ),
            "tie": tie_count,
            "pre_zero_result_cases": (
                pre_zero_count
            ),
            "post_zero_result_cases": (
                post_zero_count
            ),
        },
        "cases": results,
        "cost": {
            "openai_api_used": False,
            "external_llm_calls": 0,
            "external_embedding_api_calls": 0,
            "api_cost_usd": 0.0,
        },
    }

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        "DAY09_ACTUAL_FILTER_STRATIFIED_EVAL_OK"
    )

    print(
        "TOTAL_CATEGORIES=",
        len(categories),
    )

    print(
        "SELECTED_CASES=",
        len(selected),
    )

    print()

    for row in results:
        print(
            row[
                "category_no"
            ],
            "|",
            row[
                "category_name"
            ],
            "| depth=",
            row[
                "depth"
            ],
            "| recursive=",
            row[
                "recursive_count"
            ],
            "| PRE=",
            row[
                "pre_rrf_returned"
            ],
            "| POST=",
            row[
                "post_rrf_returned"
            ],
            "| preferred=",
            row[
                "preferred"
            ],
        )

    print()
    print(
        "PRE_PREFERRED=",
        pre_better_count,
    )

    print(
        "POST_PREFERRED=",
        post_better_count,
    )

    print(
        "TIE=",
        tie_count,
    )

    print(
        "PRE_ZERO_RESULT_CASES=",
        pre_zero_count,
    )

    print(
        "POST_ZERO_RESULT_CASES=",
        post_zero_count,
    )

    print(
        "OPENAI_API_USED=False"
    )

    print(
        "OUTPUT=",
        OUTPUT_PATH,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )