from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

import numpy as np
from sentence_transformers import (
    SentenceTransformer,
)

from ai.evaluation.run_day09_actual_filter_eval import (
    EMBEDDING_MODEL,
    build_bm25_documents,
    build_dense_documents,
    make_document,
)
from ai.retrieval.bm25 import BM25Index
from ai.retrieval.dense import DenseIndex
from ai.retrieval.hybrid import (
    reciprocal_rank_fusion,
)
from ai.retrieval.reranker import (
    LocalCrossEncoderScorer,
    MODEL_LICENSE,
    MODEL_NAME,
    MODEL_REVISION,
    RerankCandidate,
    rerank_candidates,
)


ROOT = Path(__file__).resolve().parents[2]

HANDOFF_PATH = (
    ROOT
    / "artifacts"
    / "integration"
    / "day09"
    / "ai_catalog_handoff.json"
)

OUTPUT_PATH = (
    ROOT
    / "artifacts"
    / "experiments"
    / "day10"
    / "actual_catalog_reranker_eval.json"
)

RRF_K = 60

# D10-AI-03 공식 실험 조건:
# Hybrid 후보 상위 30개를 rerank한다.
RERANK_CANDIDATE_TOP_K = 30

RERANK_OUTPUT_TOP_K = 10

EXACT_QUERY_COUNT = 8

MODEL_FILE_SHA256 = (
    "d9e3e081faff1eefb84019509b2f5558"
    "fd74c1a05a2c7db22f74174fcedb5286"
)


def sha256_file(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(
                1024 * 1024
            ),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def percentile(
    values: list[float],
    quantile: float,
) -> float | None:
    if not values:
        return None

    ordered = sorted(values)

    if len(ordered) == 1:
        return ordered[0]

    position = (
        len(ordered) - 1
    ) * quantile

    lower = int(position)
    upper = min(
        lower + 1,
        len(ordered) - 1,
    )

    fraction = position - lower

    return (
        ordered[lower]
        + (
            ordered[upper]
            - ordered[lower]
        )
        * fraction
    )


def latency_summary(
    values: list[float],
) -> dict[str, float | None]:
    if not values:
        return {
            "count": 0,
            "p50_ms": None,
            "p95_ms": None,
            "max_ms": None,
        }

    return {
        "count": len(values),
        "p50_ms": percentile(
            values,
            0.50,
        ),
        "p95_ms": percentile(
            values,
            0.95,
        ),
        "max_ms": max(values),
    }


def deterministic_exact_cases(
    products: list[
        dict[str, Any]
    ],
) -> list[dict[str, Any]]:
    """
    실제 SANITIZED_REAL catalog에서
    deterministic하게 exact-name query를 뽑는다.

    Mock query를 만들지 않는다.
    """

    unique: dict[
        str,
        dict[str, Any],
    ] = {}

    for product in products:
        if not product.get(
            "operational"
        ):
            continue

        if (
            product.get(
                "source_classification"
            )
            != "SANITIZED_REAL"
        ):
            continue

        name = str(
            product.get(
                "product_name",
                "",
            )
        ).strip()

        if not name:
            continue

        key = name.casefold()

        if key not in unique:
            unique[key] = product

    def stable_key(
        product: dict[str, Any],
    ) -> str:
        payload = (
            f"{product['product_no']}|"
            f"{product['product_name']}"
        )

        return hashlib.sha256(
            payload.encode(
                "utf-8"
            )
        ).hexdigest()

    ordered = sorted(
        unique.values(),
        key=stable_key,
    )

    return ordered[
        :EXACT_QUERY_COUNT
    ]


def inspection_queries(
    products: list[
        dict[str, Any]
    ],
) -> list[str]:
    """
    실제 catalog에 존재하는 상품군 문자열만 사용한다.

    이 query들은 정답 relevance label이 없으므로
    Recall/MRR/nDCG 계산에 사용하지 않는다.
    """

    candidates = [
        "CHAOS SPACE MARINES",
        "CHAOS KNIGHTS",
        "DEATH GUARD",
        "Obsidian Protocol",
    ]

    names = [
        str(
            product.get(
                "product_name",
                "",
            )
        )
        for product in products
    ]

    output: list[str] = []

    for query in candidates:
        query_key = query.casefold()

        exists = any(
            query_key
            in name.casefold()
            for name in names
        )

        if exists:
            output.append(
                query
            )

    return output


def rank_of(
    source_id: str,
    source_ids: list[str],
) -> int | None:
    try:
        return (
            source_ids.index(
                source_id
            )
            + 1
        )

    except ValueError:
        return None


def main() -> int:
    handoff = json.loads(
        HANDOFF_PATH.read_text(
            encoding="utf-8"
        )
    )

    products = list(
        handoff["products"]
    )

    source_classes = sorted(
        {
            str(
                product.get(
                    "source_classification",
                    ""
                )
            )
            for product in products
        }
    )

    if source_classes != [
        "SANITIZED_REAL"
    ]:
        raise RuntimeError(
            "Unexpected source classification: "
            f"{source_classes}"
        )

    print(
        "PRODUCT_COUNT=",
        len(products),
    )

    print(
        "SOURCE_CLASSIFICATION=",
        source_classes,
    )

    documents = [
        make_document(
            product
        )
        for product in products
    ]

    document_by_source_id = {
        str(
            document["source_id"]
        ): document
        for document in documents
    }

    product_by_source_id = {
        (
            f"product-"
            f"{int(product['product_no'])}"
        ): product
        for product in products
    }

    print(
        "LOADING_EMBEDDING_MODEL=",
        EMBEDDING_MODEL,
    )

    embedding_model = (
        SentenceTransformer(
            EMBEDDING_MODEL
        )
    )

    def embed_texts(
        texts: list[str],
    ) -> np.ndarray:
        return np.asarray(
            embedding_model.encode(
                texts,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            ),
            dtype=np.float32,
        )

    build_started = (
        time.perf_counter()
    )

    bm25_index = BM25Index(
        build_bm25_documents(
            documents
        )
    )

    dense_index = DenseIndex(
        build_dense_documents(
            documents
        ),
        embed_texts=embed_texts,
    )

    build_latency_ms = (
        time.perf_counter()
        - build_started
    ) * 1000.0

    print(
        "INDEX_BUILD_OK"
    )

    print(
        "LOADING_RERANKER=",
        MODEL_NAME,
    )

    scorer = LocalCrossEncoderScorer()

    print(
        "RERANKER_LOAD_OK"
    )

    exact_cases = (
        deterministic_exact_cases(
            products
        )
    )

    broad_queries = (
        inspection_queries(
            products
        )
    )

    cases: list[
        dict[str, Any]
    ] = []

    retrieval_latencies: list[
        float
    ] = []

    rerank_latencies: list[
        float
    ] = []

    timeout_count = 0
    retry_count = 0
    fallback_count = 0

    def run_one(
        *,
        query: str,
        expected_source_id: (
            str | None
        ),
        case_type: str,
    ) -> None:
        nonlocal timeout_count
        nonlocal retry_count
        nonlocal fallback_count

        retrieval_started = (
            time.perf_counter()
        )

        bm25_results = (
            bm25_index.search(
                query,
                top_k=min(
                    RERANK_CANDIDATE_TOP_K,
                    bm25_index.document_count,
                ),
            )
        )

        vector_results = (
            dense_index.search(
                query,
                top_k=min(
                    RERANK_CANDIDATE_TOP_K,
                    dense_index.document_count,
                ),
            )
        )

        hybrid_results = (
            reciprocal_rank_fusion(
                bm25_results,
                vector_results,
                candidate_top_k=(
                    RERANK_CANDIDATE_TOP_K
                ),
                rrf_k=RRF_K,
            )[
                :RERANK_CANDIDATE_TOP_K
            ]
        )

        retrieval_ms = (
            time.perf_counter()
            - retrieval_started
        ) * 1000.0

        retrieval_latencies.append(
            retrieval_ms
        )

        candidates: list[
            RerankCandidate
        ] = []

        for result in hybrid_results:
            source_id = str(
                result.source_id
            )

            document = (
                document_by_source_id[
                    source_id
                ]
            )

            product = (
                product_by_source_id[
                    source_id
                ]
            )

            candidates.append(
                RerankCandidate(
                    original_rank=(
                        result.rank
                    ),
                    source_id=(
                        source_id
                    ),
                    source_type=(
                        result.source_type
                    ),
                    version=(
                        result.version
                    ),
                    text=str(
                        document["text"]
                    ),
                    metadata={
                        "product_name":
                            product.get(
                                "product_name"
                            ),
                        "product_code":
                            product.get(
                                "product_code"
                            ),
                        "evidence_ids":
                            product.get(
                                "evidence_ids",
                                [],
                            ),
                        "as_of":
                            product.get(
                                "as_of"
                            ),
                        "source_classification":
                            product.get(
                                "source_classification"
                            ),
                    },
                )
            )

        reranked = (
            rerank_candidates(
                query,
                candidates,
                scorer=scorer,
                candidate_top_k=(
                    RERANK_CANDIDATE_TOP_K
                ),
                output_top_k=(
                    RERANK_OUTPUT_TOP_K
                ),
                timeout_seconds=120.0,
                max_retries=1,
            )
        )

        rerank_latencies.append(
            reranked.trace.latency_ms
        )

        timeout_count += (
            reranked.trace.timeout_count
        )

        retry_count += (
            reranked.trace.retry_count
        )

        fallback_count += (
            reranked.trace.fallback_count
        )

        before_ids = [
            str(
                result.source_id
            )
            for result
            in hybrid_results
        ]

        after_ids = [
            str(
                result.source_id
            )
            for result
            in reranked.results
        ]

        before_top10 = (
            before_ids[:10]
        )

        after_top10 = (
            after_ids[:10]
        )

        ranking_changed = (
            before_top10
            != after_top10
        )

        evidence_preserved = all(
            bool(
                result.metadata.get(
                    "evidence_ids"
                )
            )
            for result
            in reranked.results
        )

        product_code_preserved = all(
            bool(
                result.metadata.get(
                    "product_code"
                )
            )
            for result
            in reranked.results
        )

        row: dict[str, Any] = {
            "case_type":
                case_type,
            "query":
                query,
            "candidate_count":
                len(
                    hybrid_results
                ),
            "before_top10":
                before_top10,
            "after_top5":
                after_ids[:5],
            "after_top10":
                after_top10,
            "ranking_changed":
                ranking_changed,
            "evidence_id_preserved":
                evidence_preserved,
            "product_code_preserved":
                product_code_preserved,
            "retrieval_latency_ms":
                retrieval_ms,
            "reranker_latency_ms":
                reranked.trace.latency_ms,
            "reranker_status":
                reranked.trace.status,
            "timeout_count":
                reranked.trace.timeout_count,
            "retry_count":
                reranked.trace.retry_count,
            "fallback_count":
                reranked.trace.fallback_count,
        }

        if (
            expected_source_id
            is not None
        ):
            row[
                "expected_source_id"
            ] = expected_source_id

            row[
                "target_rank_before"
            ] = rank_of(
                expected_source_id,
                before_ids,
            )

            row[
                "target_rank_after"
            ] = rank_of(
                expected_source_id,
                after_ids,
            )

        cases.append(
            row
        )

        print(
            "CASE",
            case_type,
            query,
            "STATUS=",
            reranked.trace.status,
        )

    for product in exact_cases:
        source_id = (
            f"product-"
            f"{int(product['product_no'])}"
        )

        run_one(
            query=str(
                product["product_name"]
            ),
            expected_source_id=(
                source_id
            ),
            case_type="EXACT_NAME",
        )

    for query in broad_queries:
        run_one(
            query=query,
            expected_source_id=None,
            case_type=(
                "OPERATIONAL_INSPECTION"
            ),
        )

    exact_rows = [
        row
        for row in cases
        if row["case_type"]
        == "EXACT_NAME"
    ]

    exact_top1_before = sum(
        row.get(
            "target_rank_before"
        )
        == 1
        for row in exact_rows
    )

    exact_top1_after = sum(
        row.get(
            "target_rank_after"
        )
        == 1
        for row in exact_rows
    )

    exact_top5_after = sum(
        (
            row.get(
                "target_rank_after"
            )
            is not None
            and row[
                "target_rank_after"
            ]
            <= 5
        )
        for row in exact_rows
    )

    ranking_changed_count = sum(
        bool(
            row["ranking_changed"]
        )
        for row in cases
    )

    artifact = {
        "experiment_id":
            "D10-AI-03-ACTUAL-RERANKER",
        "source_classification":
            "SANITIZED_REAL",
        "handoff_path":
            str(HANDOFF_PATH),
        "handoff_sha256":
            sha256_file(
                HANDOFF_PATH
            ),
        "product_count":
            len(products),
        "corpus": {
            "document_count":
                len(documents),
            "version":
                "day09-actual-v1",
            "document_text_fields": [
                "product_name",
                "product_code",
                "custom_product_code",
            ],
        },
        "retrieval": {
            "embedding_model":
                EMBEDDING_MODEL,
            "hybrid_method":
                "RRF",
            "rrf_k":
                RRF_K,
            "candidate_top_k":
                RERANK_CANDIDATE_TOP_K,
            "same_day09_document_builder":
                True,
        },
        "reranker": {
            "model":
                MODEL_NAME,
            "revision":
                MODEL_REVISION,
            "model_file_sha256":
                MODEL_FILE_SHA256,
            "license":
                MODEL_LICENSE,
            "execution":
                "LOCAL",
            "output_top_k":
                RERANK_OUTPUT_TOP_K,
            "external_inference_api_calls":
                0,
        },
        "query_sets": {
            "exact_name": {
                "source":
                    "SANITIZED_REAL_PRODUCT_NAME",
                "count":
                    len(exact_rows),
                "ground_truth_scope":
                    "EXACT_PRODUCT_IDENTITY_ONLY",
            },
            "operational_inspection": {
                "source":
                    "ACTUAL_CATALOG_PRODUCT_GROUP_TERMS",
                "count":
                    len(broad_queries),
                "quality_metric_ground_truth":
                    False,
            },
        },
        "summary": {
            "index_build_latency_ms":
                build_latency_ms,
            "retrieval_latency":
                latency_summary(
                    retrieval_latencies
                ),
            "reranker_latency":
                latency_summary(
                    rerank_latencies
                ),
            "ranking_changed_count":
                ranking_changed_count,
            "exact_top1_before":
                exact_top1_before,
            "exact_top1_after":
                exact_top1_after,
            "exact_top5_after":
                exact_top5_after,
            "exact_query_count":
                len(exact_rows),
            "timeout_count":
                timeout_count,
            "retry_count":
                retry_count,
            "fallback_count":
                fallback_count,
        },
        "cases":
            cases,
        "limitations": [
            (
                "SANITIZED_REAL catalog does not "
                "contain general relevance labels."
            ),
            (
                "Recall/MRR/nDCG superiority is "
                "not claimed from this artifact."
            ),
            (
                "Exact-name cases validate only "
                "known product identity retrieval."
            ),
            (
                "Golden60 quality comparison "
                "remains HOLD because backing "
                "evidence coverage is insufficient."
            ),
        ],
        "safety": {
            "production_provider_write":
                0,
            "openai_api_calls":
                0,
            "external_llm_inference_calls":
                0,
        },
    }

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(
            artifact,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print(
        "DAY10_ACTUAL_RERANKER_EVAL_OK"
    )

    print(
        "PRODUCT_COUNT=",
        len(products),
    )

    print(
        "QUERY_COUNT=",
        len(cases),
    )

    print(
        "EXACT_TOP1_BEFORE=",
        f"{exact_top1_before}/"
        f"{len(exact_rows)}",
    )

    print(
        "EXACT_TOP1_AFTER=",
        f"{exact_top1_after}/"
        f"{len(exact_rows)}",
    )

    print(
        "EXACT_TOP5_AFTER=",
        f"{exact_top5_after}/"
        f"{len(exact_rows)}",
    )

    print(
        "RANKING_CHANGED_COUNT=",
        ranking_changed_count,
    )

    print(
        "TIMEOUT_COUNT=",
        timeout_count,
    )

    print(
        "FALLBACK_COUNT=",
        fallback_count,
    )

    print(
        "RERANK_P50_MS=",
        percentile(
            rerank_latencies,
            0.50,
        ),
    )

    print(
        "RERANK_P95_MS=",
        percentile(
            rerank_latencies,
            0.95,
        ),
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