from __future__ import annotations

import hashlib
import json
import statistics
import time
from pathlib import Path
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer

from ai.retrieval.bm25 import BM25Index
from ai.retrieval.catalog_filter import (
    CatalogFilter,
    build_descendant_map,
    filter_products,
    product_matches,
)
from ai.retrieval.dense import DenseIndex
from ai.retrieval.hybrid import (
    reciprocal_rank_fusion,
    weighted_hybrid,
)


HANDOFF_PATH = Path(
    "artifacts/integration/day09/"
    "ai_catalog_handoff.json"
)

OUTPUT_PATH = Path(
    "artifacts/experiments/day09/"
    "actual_filter_eval.json"
)

SOURCE_CLASSIFICATION = "SANITIZED_REAL"

CANDIDATE_TOP_K = 20

EMBEDDING_MODEL = (
    "sentence-transformers/"
    "paraphrase-multilingual-MiniLM-L12-v2"
)

BM25_WEIGHT = 0.5
VECTOR_WEIGHT = 0.5
RRF_K = 60


def load_handoff() -> dict[str, Any]:
    return json.loads(
        HANDOFF_PATH.read_text(
            encoding="utf-8"
        )
    )


def sha256_file(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def percentile(
    values: list[float],
    q: float,
) -> float:
    if not values:
        return 0.0

    ordered = sorted(values)

    if len(ordered) == 1:
        return ordered[0]

    pos = (
        len(ordered) - 1
    ) * q

    low = int(pos)
    high = min(
        low + 1,
        len(ordered) - 1,
    )

    weight = pos - low

    return (
        ordered[low]
        * (1.0 - weight)
        + ordered[high]
        * weight
    )


def latency_summary(
    values: list[float],
) -> dict[str, float]:
    if not values:
        return {
            "mean_ms": 0.0,
            "p50_ms": 0.0,
            "p95_ms": 0.0,
        }

    return {
        "mean_ms": statistics.fmean(
            values
        ),
        "p50_ms": percentile(
            values,
            0.50,
        ),
        "p95_ms": percentile(
            values,
            0.95,
        ),
    }


def make_document(
    product: dict[str, Any],
) -> dict[str, Any]:
    """
    SANITIZED_REAL Product를
    retrieval document 형태로 변환한다.
    """

    product_no = int(
        product["product_no"]
    )

    text_parts = [
        str(
            product.get(
                "product_name",
                "",
            )
        ).strip(),
        str(
            product.get(
                "product_code",
                "",
            )
        ).strip(),
        str(
            product.get(
                "custom_product_code",
                "",
            )
        ).strip(),
    ]

    text = " ".join(
        part
        for part in text_parts
        if part
    )

    return {
        "chunk_id": (
            f"product-{product_no}"
        ),
        "source_id": (
            f"product-{product_no}"
        ),
        "source_type": "PRODUCT",
        "version": "day09-actual-v1",
        "text": text,
        "metadata": {
            "product_no": str(
                product_no
            ),
            "product_code": str(
                product.get(
                    "product_code",
                    "",
                )
            ),
            "custom_product_code": str(
                product.get(
                    "custom_product_code",
                    "",
                )
            ),
            "brand_code": str(
                product.get(
                    "brand_code",
                    "",
                )
            ),
            "operational": str(
                bool(
                    product.get(
                        "operational"
                    )
                )
            ),
            "sold_out": str(
                product.get(
                    "sold_out",
                    "",
                )
            ),
            "category_status": str(
                product.get(
                    "category_status",
                    "",
                )
            ),
            "category_nos": ",".join(
                str(value)
                for value in product.get(
                    "category_nos",
                    [],
                )
            ),
        },
    }


def build_bm25_documents(
    documents: list[
        dict[str, Any]
    ],
) -> list[Any]:
    from ai.retrieval.bm25 import (
        BM25Document,
    )

    return [
        BM25Document(
            chunk_id=document[
                "chunk_id"
            ],
            source_id=document[
                "source_id"
            ],
            source_type=document[
                "source_type"
            ],
            version=document[
                "version"
            ],
            text=document[
                "text"
            ],
            metadata=document[
                "metadata"
            ],
        )
        for document in documents
    ]


def build_dense_documents(
    documents: list[
        dict[str, Any]
    ],
) -> list[Any]:
    from ai.retrieval.dense import (
        DenseDocument,
    )

    return [
        DenseDocument(
            chunk_id=document[
                "chunk_id"
            ],
            source_id=document[
                "source_id"
            ],
            source_type=document[
                "source_type"
            ],
            version=document[
                "version"
            ],
            text=document[
                "text"
            ],
            metadata=document[
                "metadata"
            ],
        )
        for document in documents
    ]


def result_matches_filter(
    result: Any,
    *,
    product_by_source_id: dict[
        str,
        dict[str, Any]
    ],
    filter_: CatalogFilter,
    descendant_map: dict[
        int,
        set[int],
    ],
) -> bool:
    product = product_by_source_id.get(
        str(result.source_id)
    )

    if product is None:
        return False

    return product_matches(
        product,
        filter_=filter_,
        descendant_map=descendant_map,
    )


def run_search_suite(
    *,
    query: str,
    products: list[
        dict[str, Any]
    ],
    all_products: list[
        dict[str, Any]
    ],
    filter_: CatalogFilter,
    descendant_map: dict[
        int,
        set[int],
    ],
    model: SentenceTransformer,
    mode: str,
) -> dict[str, Any]:
    documents = [
        make_document(product)
        for product in products
    ]

    bm25_documents = (
        build_bm25_documents(
            documents
        )
    )

    dense_documents = (
        build_dense_documents(
            documents
        )
    )

    def embed_texts(
        texts: list[str],
    ) -> np.ndarray:
        return np.asarray(
            model.encode(
                texts,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            ),
            dtype=np.float32,
        )

    bm25_build_started = (
        time.perf_counter()
    )

    bm25_index = BM25Index(
        bm25_documents
    )

    bm25_build_ms = (
        time.perf_counter()
        - bm25_build_started
    ) * 1000.0

    dense_build_started = (
        time.perf_counter()
    )

    dense_index = DenseIndex(
        dense_documents,
        embed_texts=embed_texts,
    )

    dense_build_ms = (
        time.perf_counter()
        - dense_build_started
    ) * 1000.0

    product_by_source_id = {
        f"product-{int(product['product_no'])}":
        product
        for product in all_products
    }

    bm25_started = (
        time.perf_counter()
    )

    bm25_results = bm25_index.search(
        query,
        top_k=min(
            CANDIDATE_TOP_K,
            bm25_index.document_count,
        ),
    )

    bm25_ms = (
        time.perf_counter()
        - bm25_started
    ) * 1000.0

    vector_started = (
        time.perf_counter()
    )

    vector_results = (
        dense_index.search(
            query,
            top_k=min(
                CANDIDATE_TOP_K,
                dense_index.document_count,
            ),
        )
    )

    vector_ms = (
        time.perf_counter()
        - vector_started
    ) * 1000.0

    if mode == "POST":
        bm25_results = [
            result
            for result
            in bm25_results
            if result_matches_filter(
                result,
                product_by_source_id=(
                    product_by_source_id
                ),
                filter_=filter_,
                descendant_map=(
                    descendant_map
                ),
            )
        ]

        vector_results = [
            result
            for result
            in vector_results
            if result_matches_filter(
                result,
                product_by_source_id=(
                    product_by_source_id
                ),
                filter_=filter_,
                descendant_map=(
                    descendant_map
                ),
            )
        ]

    rrf_started = (
        time.perf_counter()
    )

    rrf_results = (
        reciprocal_rank_fusion(
            bm25_results,
            vector_results,
            candidate_top_k=(
                CANDIDATE_TOP_K
            ),
            rrf_k=RRF_K,
        )
    )

    rrf_ms = (
        time.perf_counter()
        - rrf_started
    ) * 1000.0

    weighted_started = (
        time.perf_counter()
    )

    weighted_results = (
        weighted_hybrid(
            bm25_results,
            vector_results,
            candidate_top_k=(
                CANDIDATE_TOP_K
            ),
            bm25_weight=(
                BM25_WEIGHT
            ),
            vector_weight=(
                VECTOR_WEIGHT
            ),
        )
    )

    weighted_ms = (
        time.perf_counter()
        - weighted_started
    ) * 1000.0

    return {
        "mode": mode,
        "index_document_count": len(
            documents
        ),
        "build_latency_ms": {
            "bm25": bm25_build_ms,
            "vector": dense_build_ms,
        },
        "search_latency_ms": {
            "bm25": bm25_ms,
            "vector": vector_ms,
            "rrf_fusion": rrf_ms,
            "weighted_fusion": (
                weighted_ms
            ),
            "rrf_end_to_end_serial": (
                bm25_ms
                + vector_ms
                + rrf_ms
            ),
            "weighted_end_to_end_serial": (
                bm25_ms
                + vector_ms
                + weighted_ms
            ),
        },
        "returned_count": {
            "bm25": len(
                bm25_results
            ),
            "vector": len(
                vector_results
            ),
            "rrf": len(
                rrf_results
            ),
            "weighted": len(
                weighted_results
            ),
        },
        "top_source_ids": {
            "bm25": [
                result.source_id
                for result
                in bm25_results[:5]
            ],
            "vector": [
                result.source_id
                for result
                in vector_results[:5]
            ],
            "rrf": [
                result.source_id
                for result
                in rrf_results[:5]
            ],
            "weighted": [
                result.source_id
                for result
                in weighted_results[:5]
            ],
        },
    }


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

    model = SentenceTransformer(
        EMBEDDING_MODEL,
        device="cpu",
    )

    cases = [
        {
            "id": "PREORDER",
            "query": "PRE-ORDER",
            "filter": CatalogFilter(
                category_no=56,
                recursive_category=False,
            ),
            "expected_count": 48,
        },
        {
            "id": (
                "PREORDER_OPERATIONAL"
            ),
            "query": "PRE-ORDER",
            "filter": CatalogFilter(
                category_no=56,
                recursive_category=False,
                operational=True,
            ),
            "expected_count": 46,
        },
        {
            "id": (
                "GAMES_WORKSHOP_RECURSIVE"
            ),
            "query": (
                "Games Workshop"
            ),
            "filter": CatalogFilter(
                category_no=46,
                recursive_category=True,
            ),
            "expected_count": 570,
        },
        {
            "id": (
                "WARHAMMER_40K_RECURSIVE"
            ),
            "query": "Warhammer 40K",
            "filter": CatalogFilter(
                category_no=57,
                recursive_category=True,
            ),
            "expected_count": 669,
        },
        {
            "id": (
                "PAINT_RECURSIVE"
            ),
            "query": "Paint",
            "filter": CatalogFilter(
                category_no=67,
                recursive_category=True,
            ),
            "expected_count": 364,
        },
    ]

    results = []

    for case in cases:
        filtered_products = (
            filter_products(
                products,
                filter_=case[
                    "filter"
                ],
                descendant_map=(
                    descendant_map
                ),
            )
        )

        if (
            len(filtered_products)
            != case["expected_count"]
        ):
            raise AssertionError(
                (
                    f"{case['id']} "
                    f"expected="
                    f"{case['expected_count']} "
                    f"actual="
                    f"{len(filtered_products)}"
                )
            )

        pre_result = (
            run_search_suite(
                query=case[
                    "query"
                ],
                products=(
                    filtered_products
                ),
                all_products=products,
                filter_=case[
                    "filter"
                ],
                descendant_map=(
                    descendant_map
                ),
                model=model,
                mode="PRE",
            )
        )

        post_result = (
            run_search_suite(
                query=case[
                    "query"
                ],
                products=products,
                all_products=products,
                filter_=case[
                    "filter"
                ],
                descendant_map=(
                    descendant_map
                ),
                model=model,
                mode="POST",
            )
        )

        results.append(
            {
                "case_id": case[
                    "id"
                ],
                "query": case[
                    "query"
                ],
                "expected_filter_count": (
                    case[
                        "expected_count"
                    ]
                ),
                "pre_filter": (
                    pre_result
                ),
                "post_filter": (
                    post_result
                ),
            }
        )

    result = {
        "schema_version": (
            "day09-actual-filter-eval.v1"
        ),
        "day": 9,
        "source_classification": (
            SOURCE_CLASSIFICATION
        ),
        "input": {
            "path": str(
                HANDOFF_PATH
            ),
            "declared_artifact_hash": (
                handoff[
                    "artifact_hash"
                ]
            ),
            "raw_file_sha256": (
                sha256_file(
                    HANDOFF_PATH
                )
            ),
            "artifact_version": (
                handoff[
                    "artifact_version"
                ]
            ),
            "product_snapshot_as_of": (
                handoff[
                    "product_snapshot_as_of"
                ]
            ),
            "category_snapshot_as_of": (
                handoff[
                    "category_snapshot_as_of"
                ]
            ),
            "relation_snapshot_as_of": (
                handoff[
                    "relation_snapshot_as_of"
                ]
            ),
        },
        "catalog": {
            "full_catalog": len(
                products
            ),
            "operational": (
                handoff[
                    "operational_product_count"
                ]
            ),
            "category_count": (
                handoff[
                    "category_count"
                ]
            ),
        },
        "embedding": {
            "model": EMBEDDING_MODEL,
            "device": "cpu",
            "external_api": False,
        },
        "candidate_top_k": (
            CANDIDATE_TOP_K
        ),
        "cases": results,
        "metadata_eligibility": {
            "category": "ELIGIBLE",
            "operational": (
                "ELIGIBLE"
            ),
            "sold_out": "ELIGIBLE",
            "brand": "HOLD",
            "language": (
                "NOT_ELIGIBLE"
            ),
        },
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
            result,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        "DAY09_ACTUAL_FILTER_EVAL_OK"
    )

    print(
        "SOURCE_CLASSIFICATION=",
        SOURCE_CLASSIFICATION,
    )

    print(
        "FULL_CATALOG=",
        len(products),
    )

    for case in results:
        pre = case[
            "pre_filter"
        ]

        post = case[
            "post_filter"
        ]

        print()
        print(
            "CASE=",
            case["case_id"],
        )

        print(
            "EXPECTED_FILTER_COUNT=",
            case[
                "expected_filter_count"
            ],
        )

        print(
            "PRE_INDEX_DOCS=",
            pre[
                "index_document_count"
            ],
        )

        print(
            "POST_INDEX_DOCS=",
            post[
                "index_document_count"
            ],
        )

        print(
            "PRE_RETURNED=",
            pre[
                "returned_count"
            ],
        )

        print(
            "POST_RETURNED=",
            post[
                "returned_count"
            ],
        )

        print(
            "PRE_LATENCY=",
            pre[
                "search_latency_ms"
            ],
        )

        print(
            "POST_LATENCY=",
            post[
                "search_latency_ms"
            ],
        )

    print()
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