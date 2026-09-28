from __future__ import annotations
import torch
import hashlib
import json
import statistics
import time
from pathlib import Path
from typing import Any

import numpy as np
from sentence_transformers import (
    SentenceTransformer,
)

import ai.evaluation.run_day09_golden_hybrid_eval as d9

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

OUTPUT_PATH = (
    ROOT
    / "artifacts"
    / "experiments"
    / "RAG-03"
    / "result.json"
)

ACTUAL_RERANKER_PATH = (
    ROOT
    / "artifacts"
    / "experiments"
    / "day10"
    / "actual_catalog_reranker_eval.json"
)

TOP_K_VALUES = (
    3,
    5,
    10,
    20,
)

# D10 Reranker 실험 조건
RERANK_CANDIDATE_TOP_K = 30

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
) -> float:
    if not values:
        return 0.0

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

    fraction = (
        position - lower
    )

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
) -> dict[str, float]:
    return {
        "count": len(values),
        "mean_ms": (
            statistics.fmean(values)
            if values
            else 0.0
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


def snapshot_text(
    row: dict[str, Any],
) -> str:
    for key in (
        "content",
        "text",
        "chunk_text",
    ):
        value = row.get(key)

        if value:
            return str(value)

    return ""


def build_source_text_map(
    snapshot: list[
        dict[str, Any]
    ],
) -> dict[str, str]:
    grouped: dict[
        str,
        list[str],
    ] = {}

    for row in snapshot:
        source_id = str(
            row["source_id"]
        )

        text = snapshot_text(
            row
        ).strip()

        if not text:
            continue

        grouped.setdefault(
            source_id,
            [],
        ).append(text)

    return {
        source_id: "\n".join(
            texts
        )
        for source_id, texts
        in grouped.items()
    }


def mrr_at_k(
    ranked_source_ids: list[str],
    grades: dict[str, int],
    k: int,
) -> float:
    for rank, source_id in enumerate(
        ranked_source_ids[:k],
        start=1,
    ):
        if grades.get(
            source_id,
            0,
        ) > 0:
            return 1.0 / rank

    return 0.0


def metrics_at_k(
    *,
    query: dict[str, Any],
    ranked_source_ids: list[str],
    k: int,
) -> dict[str, Any]:
    grades = d9.relevant_grades(
        query
    )

    recall = d9.recall_at_k(
        ranked_source_ids,
        grades,
        k,
    )

    mrr = mrr_at_k(
        ranked_source_ids,
        grades,
        k,
    )

    ndcg = d9.ndcg_at_k(
        ranked_source_ids,
        grades,
        k,
    )

    hit = any(
        grades.get(
            source_id,
            0,
        ) > 0
        for source_id
        in ranked_source_ids[:k]
    )

    return {
        "top_k": k,
        "recall": recall,
        "mrr": mrr,
        "ndcg": ndcg,
        "hit": hit,
        "evidence_miss":
            not hit,
    }


def summarize_rows(
    rows: list[
        dict[str, Any]
    ],
    *,
    top_k: int,
) -> dict[str, Any]:
    selected = [
        row
        for row in rows
        if row["top_k"]
        == top_k
    ]

    if not selected:
        return {
            "query_count": 0,
            "recall": 0.0,
            "mrr": 0.0,
            "ndcg": 0.0,
            "hit_rate": 0.0,
            "evidence_miss_count": 0,
        }

    return {
        "query_count":
            len(selected),
        "recall":
            statistics.fmean(
                row["recall"]
                for row in selected
            ),
        "mrr":
            statistics.fmean(
                row["mrr"]
                for row in selected
            ),
        "ndcg":
            statistics.fmean(
                row["ndcg"]
                for row in selected
            ),
        "hit_rate":
            statistics.fmean(
                1.0
                if row["hit"]
                else 0.0
                for row in selected
            ),
        "evidence_miss_count":
            sum(
                bool(
                    row[
                        "evidence_miss"
                    ]
                )
                for row in selected
            ),
    }


def summarize_by_slice(
    rows: list[
        dict[str, Any]
    ],
    *,
    top_k: int,
) -> dict[str, Any]:
    slices = sorted(
        {
            str(
                row["slice"]
            )
            for row in rows
        }
    )

    output: dict[
        str,
        Any,
    ] = {}

    for slice_name in slices:
        subset = [
            row
            for row in rows
            if (
                row["slice"]
                == slice_name
            )
        ]

        output[
            slice_name
        ] = summarize_rows(
            subset,
            top_k=top_k,
        )

    return output


def main() -> int:
    snapshot = d9.load_jsonl(
        d9.SNAPSHOT_PATH
    )

    manifest = d9.load_json(
        d9.SNAPSHOT_MANIFEST_PATH
    )

    golden = d9.load_jsonl(
        d9.GOLDEN_PATH
    )

    answerable = [
        query
        for query in golden
        if (
            query[
                "expected_answerability"
            ]
            == "ANSWERABLE"
        )
    ]

    snapshot_source_ids = {
        str(row["source_id"])
        for row in snapshot
    }

    covered_query_ids: set[
        str
    ] = set()

    for query in answerable:
        grades = d9.relevant_grades(
            query
        )

        if any(
            (
                source_id
                in snapshot_source_ids
                and grade >= 2
            )
            for source_id, grade
            in grades.items()
        ):
            covered_query_ids.add(
                str(
                    query[
                        "query_id"
                    ]
                )
            )

    source_text_map = (
        build_source_text_map(
            snapshot
        )
    )

    freshness_policy = (
        d9.load_freshness_policy()
    )

    version_catalog = (
        d9.build_version_catalog(
            snapshot
        )
    )

    bm25_documents = (
        d9.snapshot_to_documents(
            snapshot
        )
    )

    dense_documents = (
        d9.snapshot_to_dense_documents(
            snapshot
        )
    )

    bm25_index = BM25Index(
        bm25_documents
    )

    embedding = (
        manifest.get(
            "embedding"
        )
        or {}
    )

    embedding_model = str(
        embedding["model"]
    )

    embedding_revision = str(
        embedding["revision"]
    )

    model = SentenceTransformer(
        embedding_model,
        revision=(
            embedding_revision
        ),
        device="cpu",
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

    dense_index = DenseIndex(
        dense_documents,
        embed_texts=embed_texts,
    )

    print(
        "INDEX_BUILD_OK"
    )

    print(
        "LOADING_RERANKER=",
        MODEL_NAME,
    )

    device = (
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )
    print(
        "DEVICE=",
        device,
    )
    
    scorer = LocalCrossEncoderScorer(
        device=device
    )
    print(
        "RERANKER_LOAD_OK"
    )

    method_rows: dict[
        str,
        list[dict[str, Any]],
    ] = {
        "vector": [],
        "rrf": [],
        "rrf_reranker": [],
    }

    latency: dict[
        str,
        list[float],
    ] = {
        "vector": [],
        "rrf": [],
        "rrf_reranker": [],
    }

    timeout_count = 0
    retry_count = 0
    fallback_count = 0

    answerable_index = 0

    for query in golden:
        if (
            query[
                "expected_answerability"
            ]
            != "ANSWERABLE"
        ):
            continue

        answerable_index += 1

        query_id = str(
            query["query_id"]
        )

        query_text = str(
            query["query"]
        )

        print(
            "QUERY",
            f"{answerable_index}/"
            f"{len(answerable)}",
            query_id,
        )

        bm25_started = (
            time.perf_counter()
        )

        bm25_chunks = (
            bm25_index.search(
                query_text,
                top_k=(
                    bm25_index
                    .document_count
                ),
            )
        )

        bm25_fresh = (
            d9.prefer_fresh_versioned_results(
                bm25_chunks,
                freshness_policy=(
                    freshness_policy
                ),
                version_catalog=(
                    version_catalog
                ),
            )
        )

        bm25_sources = (
            d9.collapse_results_by_source(
                bm25_fresh
            )[
                :RERANK_CANDIDATE_TOP_K
            ]
        )

        bm25_ms = (
            time.perf_counter()
            - bm25_started
        ) * 1000.0

        vector_started = (
            time.perf_counter()
        )

        vector_chunks = (
            dense_index.search(
                query_text,
                top_k=(
                    dense_index
                    .document_count
                ),
            )
        )

        vector_fresh = (
            d9.prefer_fresh_versioned_results(
                vector_chunks,
                freshness_policy=(
                    freshness_policy
                ),
                version_catalog=(
                    version_catalog
                ),
            )
        )

        vector_sources = (
            d9.collapse_results_by_source(
                vector_fresh
            )[
                :RERANK_CANDIDATE_TOP_K
            ]
        )

        vector_ms = (
            time.perf_counter()
            - vector_started
        ) * 1000.0

        rrf_started = (
            time.perf_counter()
        )

        rrf_results = (
            reciprocal_rank_fusion(
                bm25_sources,
                vector_sources,
                candidate_top_k=(
                    RERANK_CANDIDATE_TOP_K
                ),
                rrf_k=d9.RRF_K,
            )
        )

        rrf_ms = (
            time.perf_counter()
            - rrf_started
        ) * 1000.0

        candidates: list[
            RerankCandidate
        ] = []

        for result in rrf_results:
            source_id = str(
                result.source_id
            )

            text = (
                source_text_map.get(
                    source_id,
                    "",
                )
            )

            if not text:
                continue

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
                    text=text,
                    metadata={
                        "source_id":
                            source_id,
                    },
                )
            )

        reranked = (
            rerank_candidates(
                query_text,
                candidates,
                scorer=scorer,
                candidate_top_k=(
                    RERANK_CANDIDATE_TOP_K
                ),
                output_top_k=20,
                timeout_seconds=120.0,
                max_retries=1,
            )
        )

        timeout_count += (
            reranked.trace
            .timeout_count
        )

        retry_count += (
            reranked.trace
            .retry_count
        )

        fallback_count += (
            reranked.trace
            .fallback_count
        )

        rankings = {
            "vector": [
                str(
                    result.source_id
                )
                for result
                in vector_sources
            ],
            "rrf": [
                str(
                    result.source_id
                )
                for result
                in rrf_results
            ],
            "rrf_reranker": [
                str(
                    result.source_id
                )
                for result
                in reranked.results
            ],
        }

        latency[
            "vector"
        ].append(
            vector_ms
        )

        latency[
            "rrf"
        ].append(
            bm25_ms
            + vector_ms
            + rrf_ms
        )

        latency[
            "rrf_reranker"
        ].append(
            bm25_ms
            + vector_ms
            + rrf_ms
            + reranked.trace
            .latency_ms
        )

        for method, ranking in (
            rankings.items()
        ):
            for top_k in (
                TOP_K_VALUES
            ):
                metrics = (
                    metrics_at_k(
                        query=query,
                        ranked_source_ids=(
                            ranking
                        ),
                        k=top_k,
                    )
                )

                method_rows[
                    method
                ].append(
                    {
                        "query_id":
                            query_id,
                        "slice":
                            query["slice"],
                        "split":
                            query["split"],
                        "corpus_covered":
                            (
                                query_id
                                in covered_query_ids
                            ),
                        **metrics,
                    }
                )

    methods: dict[
        str,
        Any,
    ] = {}

    for method, rows in (
        method_rows.items()
    ):
        by_top_k: dict[
            str,
            Any,
        ] = {}

        for top_k in (
            TOP_K_VALUES
        ):
            overall = (
                summarize_rows(
                    rows,
                    top_k=top_k,
                )
            )

            covered_rows = [
                row
                for row in rows
                if row[
                    "corpus_covered"
                ]
            ]

            covered_only = (
                summarize_rows(
                    covered_rows,
                    top_k=top_k,
                )
            )

            by_top_k[
                str(top_k)
            ] = {
                "overall":
                    overall,
                "covered_only":
                    covered_only,
                "by_slice":
                    summarize_by_slice(
                        rows,
                        top_k=top_k,
                    ),
            }

        methods[method] = {
            "top_k":
                by_top_k,
            "latency":
                latency_summary(
                    latency[method]
                ),
        }

    actual_catalog: (
        dict[str, Any]
        | None
    ) = None

    if ACTUAL_RERANKER_PATH.exists():
        actual = json.loads(
            ACTUAL_RERANKER_PATH
            .read_text(
                encoding="utf-8"
            )
        )

        actual_catalog = {
            "source_classification":
                actual.get(
                    "source_classification"
                ),
            "product_count":
                actual.get(
                    "product_count"
                ),
            "summary":
                actual.get(
                    "summary"
                ),
            "query_sets":
                actual.get(
                    "query_sets"
                ),
            "quality_metric_rule": (
                "SANITIZED_REAL catalog "
                "has no general relevance "
                "labels. Do not report "
                "general Recall/MRR/nDCG."
            ),
        }

    coverage_ratio = (
        len(covered_query_ids)
        / len(answerable)
        if answerable
        else 0.0
    )

    status = (
        "PASS_WITH_FINDINGS"
        if coverage_ratio < 1.0
        else "PASS"
    )

    artifact = {
        "schema_version": "1.0",
        "experiment_id":
            "RAG-03",
        "day":
            10,
        "schedule_id":
            "D10-AI-05",
        "status":
            status,
        "top_k_values":
            list(
                TOP_K_VALUES
            ),
        "inputs": {
            "golden_path":
                str(
                    d9.GOLDEN_PATH
                ),
            "golden_sha256":
                sha256_file(
                    d9.GOLDEN_PATH
                ),
            "snapshot_path":
                str(
                    d9.SNAPSHOT_PATH
                ),
            "snapshot_sha256":
                sha256_file(
                    d9.SNAPSHOT_PATH
                ),
            "snapshot_manifest_path":
                str(
                    d9.SNAPSHOT_MANIFEST_PATH
                ),
            "snapshot_manifest_sha256":
                sha256_file(
                    d9.SNAPSHOT_MANIFEST_PATH
                ),
            "embedding_model":
                embedding_model,
            "embedding_revision":
                embedding_revision,
        },
        "coverage": {
            "answerable_total":
                len(answerable),
            "answerable_covered":
                len(
                    covered_query_ids
                ),
            "answerable_uncovered":
                (
                    len(answerable)
                    - len(
                        covered_query_ids
                    )
                ),
            "coverage_ratio":
                coverage_ratio,
            "decision":
                "HOLD"
                if coverage_ratio < 1.0
                else "ASSESSABLE",
        },
        "methods":
            methods,
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
            "candidate_top_k":
                RERANK_CANDIDATE_TOP_K,
            "timeout_count":
                timeout_count,
            "retry_count":
                retry_count,
            "fallback_count":
                fallback_count,
            "external_inference_api_calls":
                0,
        },
        "actual_catalog":
            actual_catalog,
        "token_metric": {
            "status":
                "HOLD",
            "reason": (
                "Final answer-generation "
                "tokenizer/model is not "
                "locked. Character/context "
                "reduction is measured in "
                "D10-AI-04 instead of "
                "fabricating token counts."
            ),
        },
        "decision": {
            "active_top_k":
                None,
            "reranker_active":
                False,
            "confidence_threshold":
                "HOLD",
            "reason": (
                "Golden60 answerable corpus "
                "coverage is insufficient "
                "for production promotion."
            ),
        },
        "limitations": [
            (
                "Only a subset of Golden60 "
                "answerable queries has "
                "relevant evidence in the "
                "current snapshot."
            ),
            (
                "Overall metrics include "
                "queries whose relevant "
                "evidence is absent."
            ),
            (
                "covered_only metrics must "
                "be interpreted separately."
            ),
            (
                "SANITIZED_REAL catalog "
                "operational validation is "
                "not a general relevance "
                "benchmark."
            ),
            (
                "No Top-K or reranker "
                "configuration is promoted "
                "to ACTIVE in Day10."
            ),
        ],
        "safety": {
            "openai_api_calls":
                0,
            "external_llm_api_calls":
                0,
            "production_provider_write":
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
        "DAY10_TOPK_COMPARISON_OK"
    )

    print(
        "ANSWERABLE=",
        len(answerable),
    )

    print(
        "COVERED=",
        len(
            covered_query_ids
        ),
    )

    print(
        "UNCOVERED=",
        len(answerable)
        - len(
            covered_query_ids
        ),
    )

    for method in (
        "vector",
        "rrf",
        "rrf_reranker",
    ):
        print()
        print(
            "METHOD=",
            method,
        )

        for top_k in (
            TOP_K_VALUES
        ):
            summary = (
                methods[
                    method
                ][
                    "top_k"
                ][
                    str(top_k)
                ]
            )

            print(
                "K=",
                top_k,
                "OVERALL=",
                summary[
                    "overall"
                ],
                "COVERED_ONLY=",
                summary[
                    "covered_only"
                ],
            )

    print()
    print(
        "RERANKER_TIMEOUT_COUNT=",
        timeout_count,
    )

    print(
        "RERANKER_FALLBACK_COUNT=",
        fallback_count,
    )

    print(
        "STATUS=",
        status,
    )

    print(
        "ACTIVE_TOP_K=None"
    )

    print(
        "RERANKER_ACTIVE=False"
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