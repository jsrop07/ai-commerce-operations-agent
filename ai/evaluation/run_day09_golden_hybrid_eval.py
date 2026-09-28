from __future__ import annotations

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

from ai.evaluation.run_retrieval_eval import (
    average,
    build_version_catalog,
    collapse_results_by_source,
    first_relevant_rank,
    load_freshness_policy,
    ndcg_at_k,
    percentile,
    prefer_fresh_versioned_results,
    recall_at_k,
    reciprocal_rank,
    relevant_grades,
    snapshot_to_documents,
)
from ai.retrieval.bm25 import BM25Index
from ai.retrieval.dense import (
    DenseIndex,
    snapshot_to_dense_documents,
)
from ai.retrieval.hybrid import (
    reciprocal_rank_fusion,
    weighted_hybrid,
)


SNAPSHOT_PATH = Path(
    "artifacts/experiments/RAG-01/"
    "chunk_snapshot.jsonl"
)

SNAPSHOT_MANIFEST_PATH = Path(
    "artifacts/experiments/RAG-01/"
    "chunk_snapshot_manifest.json"
)

GOLDEN_PATH = Path(
    "ai/evaluation/datasets/"
    "golden_retrieval.jsonl"
)

OUTPUT_PATH = Path(
    "artifacts/experiments/day09/"
    "golden60_hybrid_result.json"
)

SOURCE_CLASSIFICATION = "FIXTURE"

CANDIDATE_TOP_K = 20
METRIC_TOP_K = 5

RRF_K = 60

BM25_WEIGHT = 0.5
VECTOR_WEIGHT = 0.5

BM25_INDEX_VERSION = (
    "bm25-day09-golden-v1"
)

VECTOR_INDEX_VERSION = (
    "dense-day09-golden-v1"
)

RRF_INDEX_VERSION = (
    "rrf-day09-golden-v1"
)

WEIGHTED_INDEX_VERSION = (
    "weighted-day09-golden-v1"
)


def load_jsonl(
    path: Path,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for line in path.read_text(
        encoding="utf-8"
    ).splitlines():
        if not line.strip():
            continue

        rows.append(
            json.loads(line)
        )

    return rows


def load_json(
    path: Path,
) -> dict[str, Any]:
    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def sha256_file(
    path: Path,
) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def sha256_json(
    value: Any,
) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(
        payload
    ).hexdigest()


def evaluate_ranking(
    *,
    query: dict[str, Any],
    ranked_source_ids: list[str],
) -> dict[str, Any]:
    grades = relevant_grades(
        query
    )

    return {
        "first_relevant_rank": (
            first_relevant_rank(
                ranked_source_ids,
                grades,
            )
        ),
        "recall_at_1": recall_at_k(
            ranked_source_ids,
            grades,
            1,
        ),
        "recall_at_3": recall_at_k(
            ranked_source_ids,
            grades,
            3,
        ),
        "recall_at_5": recall_at_k(
            ranked_source_ids,
            grades,
            5,
        ),
        "mrr": reciprocal_rank(
            ranked_source_ids,
            grades,
        ),
        "ndcg_at_5": ndcg_at_k(
            ranked_source_ids,
            grades,
            5,
        ),
    }


def summarize_metrics(
    rows: list[dict[str, Any]],
) -> dict[str, float]:
    if not rows:
        return {
            "recall_at_1": 0.0,
            "recall_at_3": 0.0,
            "recall_at_5": 0.0,
            "mrr": 0.0,
            "ndcg_at_5": 0.0,
        }

    return {
        "recall_at_1": average(
            [
                row["recall_at_1"]
                for row in rows
            ]
        ),
        "recall_at_3": average(
            [
                row["recall_at_3"]
                for row in rows
            ]
        ),
        "recall_at_5": average(
            [
                row["recall_at_5"]
                for row in rows
            ]
        ),
        "mrr": average(
            [
                row["mrr"]
                for row in rows
            ]
        ),
        "ndcg_at_5": average(
            [
                row["ndcg_at_5"]
                for row in rows
            ]
        ),
    }


def latency_summary(
    values: list[float],
) -> dict[str, float]:
    return {
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


def serialize_results(
    results: list[Any],
    *,
    top_k: int,
) -> list[dict[str, Any]]:
    return [
        {
            "rank": rank,
            "source_id": (
                result.source_id
            ),
            "chunk_id": (
                result.chunk_id
            ),
            "version": (
                result.version
            ),
            "score": float(
                result.score
            ),
        }
        for rank, result
        in enumerate(
            results[:top_k],
            start=1,
        )
    ]


def split_summary(
    rows: list[dict[str, Any]],
    split: str,
) -> dict[str, Any]:
    subset = [
        row
        for row in rows
        if row["split"] == split
    ]

    return {
        "query_count": len(
            subset
        ),
        "metrics": summarize_metrics(
            subset
        ),
    }


def main() -> int:
    snapshot = load_jsonl(
        SNAPSHOT_PATH
    )

    manifest = load_json(
        SNAPSHOT_MANIFEST_PATH
    )

    golden = load_jsonl(
        GOLDEN_PATH
    )

    answerable = [
        query
        for query in golden
        if query[
            "expected_answerability"
        ]
        == "ANSWERABLE"
    ]

    abstain = [
        query
        for query in golden
        if query[
            "expected_answerability"
        ]
        == "ABSTAIN"
    ]

    snapshot_source_ids = {
        str(row["source_id"])
        for row in snapshot
    }

    covered_query_ids: set[str] = set()

    for query in answerable:
        grades = relevant_grades(
            query
        )

        if any(
            source_id
            in snapshot_source_ids
            and grade >= 2
            for source_id, grade
            in grades.items()
        ):
            covered_query_ids.add(
                str(query["query_id"])
            )

    freshness_policy = (
        load_freshness_policy()
    )

    version_catalog = (
        build_version_catalog(
            snapshot
        )
    )

    bm25_documents = (
        snapshot_to_documents(
            snapshot
        )
    )

    dense_documents = (
        snapshot_to_dense_documents(
            snapshot
        )
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

    embedding = manifest.get(
        "embedding"
    ) or {}

    model_name = embedding.get(
        "model"
    )

    model_revision = embedding.get(
        "revision"
    )

    if not model_name:
        raise ValueError(
            "embedding.model missing"
        )

    if not model_revision:
        raise ValueError(
            "embedding.revision missing"
        )

    dense_build_started = (
        time.perf_counter()
    )

    model = SentenceTransformer(
        model_name,
        revision=model_revision,
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

    dense_build_ms = (
        time.perf_counter()
        - dense_build_started
    ) * 1000.0

    bm25_latencies: list[float] = []
    vector_latencies: list[float] = []

    rrf_fusion_latencies: list[
        float
    ] = []

    weighted_fusion_latencies: list[
        float
    ] = []

    rrf_end_to_end_latencies: list[
        float
    ] = []

    weighted_end_to_end_latencies: list[
        float
    ] = []

    method_rows: dict[
        str,
        list[dict[str, Any]],
    ] = {
        "bm25": [],
        "vector": [],
        "rrf": [],
        "weighted": [],
    }

    abstain_rows: list[
        dict[str, Any]
    ] = []

    for query in golden:
        query_text = str(
            query["query"]
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
            prefer_fresh_versioned_results(
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
            collapse_results_by_source(
                bm25_fresh
            )[
                :CANDIDATE_TOP_K
            ]
        )

        bm25_ms = (
            time.perf_counter()
            - bm25_started
        ) * 1000.0

        bm25_latencies.append(
            bm25_ms
        )

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
            prefer_fresh_versioned_results(
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
            collapse_results_by_source(
                vector_fresh
            )[
                :CANDIDATE_TOP_K
            ]
        )

        vector_ms = (
            time.perf_counter()
            - vector_started
        ) * 1000.0

        vector_latencies.append(
            vector_ms
        )

        rrf_started = (
            time.perf_counter()
        )

        rrf_results = (
            reciprocal_rank_fusion(
                bm25_sources,
                vector_sources,
                candidate_top_k=(
                    CANDIDATE_TOP_K
                ),
                rrf_k=RRF_K,
            )
        )

        rrf_fusion_ms = (
            time.perf_counter()
            - rrf_started
        ) * 1000.0

        rrf_fusion_latencies.append(
            rrf_fusion_ms
        )

        rrf_end_to_end_latencies.append(
            bm25_ms
            + vector_ms
            + rrf_fusion_ms
        )

        weighted_started = (
            time.perf_counter()
        )

        weighted_results = (
            weighted_hybrid(
                bm25_sources,
                vector_sources,
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

        weighted_fusion_ms = (
            time.perf_counter()
            - weighted_started
        ) * 1000.0

        weighted_fusion_latencies.append(
            weighted_fusion_ms
        )

        weighted_end_to_end_latencies.append(
            bm25_ms
            + vector_ms
            + weighted_fusion_ms
        )

        if (
            query[
                "expected_answerability"
            ]
            == "ABSTAIN"
        ):
            abstain_rows.append(
                {
                    "query_id": (
                        query["query_id"]
                    ),
                    "slice": (
                        query["slice"]
                    ),
                    "bm25_top": (
                        serialize_results(
                            bm25_sources,
                            top_k=5,
                        )
                    ),
                    "vector_top": (
                        serialize_results(
                            vector_sources,
                            top_k=5,
                        )
                    ),
                    "rrf_top": (
                        serialize_results(
                            rrf_results,
                            top_k=5,
                        )
                    ),
                    "weighted_top": (
                        serialize_results(
                            weighted_results,
                            top_k=5,
                        )
                    ),
                }
            )

            continue

        rankings = {
            "bm25": bm25_sources,
            "vector": vector_sources,
            "rrf": rrf_results,
            "weighted": (
                weighted_results
            ),
        }

        for method, results in (
            rankings.items()
        ):
            ranked_source_ids = [
                str(result.source_id)
                for result in results
            ]

            metrics = evaluate_ranking(
                query=query,
                ranked_source_ids=(
                    ranked_source_ids
                ),
            )

            method_rows[
                method
            ].append(
                {
                    "query_id": (
                        query["query_id"]
                    ),
                    "slice": (
                        query["slice"]
                    ),
                    "split": (
                        query["split"]
                    ),
                    "corpus_covered": (
                        str(
                            query[
                                "query_id"
                            ]
                        )
                        in covered_query_ids
                    ),
                    **metrics,
                    "top_results": (
                        serialize_results(
                            list(results),
                            top_k=5,
                        )
                    ),
                }
            )

    methods: dict[
        str,
        dict[str, Any],
    ] = {}

    latency_map = {
        "bm25": latency_summary(
            bm25_latencies
        ),
        "vector": latency_summary(
            vector_latencies
        ),
        "rrf": {
            "fusion_only": (
                latency_summary(
                    rrf_fusion_latencies
                )
            ),
            "end_to_end_serial": (
                latency_summary(
                    rrf_end_to_end_latencies
                )
            ),
        },
        "weighted": {
            "fusion_only": (
                latency_summary(
                    weighted_fusion_latencies
                )
            ),
            "end_to_end_serial": (
                latency_summary(
                    weighted_end_to_end_latencies
                )
            ),
        },
    }

    for method, rows in (
        method_rows.items()
    ):
        covered_rows = [
            row
            for row in rows
            if row[
                "corpus_covered"
            ]
        ]

        failures = [
            {
                "query_id": (
                    row["query_id"]
                ),
                "slice": (
                    row["slice"]
                ),
                "split": (
                    row["split"]
                ),
                "corpus_covered": (
                    row[
                        "corpus_covered"
                    ]
                ),
                "first_relevant_rank": (
                    row[
                        "first_relevant_rank"
                    ]
                ),
                "top_results": (
                    row["top_results"]
                ),
            }
            for row in rows
            if (
                row[
                    "first_relevant_rank"
                ]
                is None
                or row[
                    "first_relevant_rank"
                ]
                > METRIC_TOP_K
            )
        ]

        methods[method] = {
            "overall": {
                "query_count": len(
                    rows
                ),
                "metrics": (
                    summarize_metrics(
                        rows
                    )
                ),
            },
            "covered_only": {
                "query_count": len(
                    covered_rows
                ),
                "metrics": (
                    summarize_metrics(
                        covered_rows
                    )
                ),
            },
            "validation_split": (
                split_summary(
                    rows,
                    "validation",
                )
            ),
            "test_split": (
                split_summary(
                    rows,
                    "test",
                )
            ),
            "failure_count": len(
                failures
            ),
            "failures": failures,
            "latency": (
                latency_map[
                    method
                ]
            ),
        }

    index_config = {
        "snapshot_hash": (
            manifest["snapshot_hash"]
        ),
        "candidate_top_k": (
            CANDIDATE_TOP_K
        ),
        "metric_top_k": (
            METRIC_TOP_K
        ),
        "rrf_k": RRF_K,
        "bm25_weight": (
            BM25_WEIGHT
        ),
        "vector_weight": (
            VECTOR_WEIGHT
        ),
        "embedding_model": (
            model_name
        ),
        "embedding_revision": (
            model_revision
        ),
    }

    result = {
        "schema_version": (
            "day09-golden-hybrid-eval.v1"
        ),
        "day": 9,
        "source_classification": (
            SOURCE_CLASSIFICATION
        ),
        "dataset": {
            "path": str(
                GOLDEN_PATH
            ),
            "raw_sha256": (
                sha256_file(
                    GOLDEN_PATH
                )
            ),
            "query_count": len(
                golden
            ),
            "answerable_count": len(
                answerable
            ),
            "abstain_count": len(
                abstain
            ),
        },
        "snapshot": {
            "path": str(
                SNAPSHOT_PATH
            ),
            "version": (
                manifest[
                    "snapshot_version"
                ]
            ),
            "hash": (
                manifest[
                    "snapshot_hash"
                ]
            ),
            "chunk_count": len(
                snapshot
            ),
            "unique_source_count": len(
                snapshot_source_ids
            ),
            "corpus": (
                manifest["corpus"]
            ),
        },
        "coverage": {
            "answerable_total": len(
                answerable
            ),
            "answerable_covered": len(
                covered_query_ids
            ),
            "answerable_not_covered": (
                len(answerable)
                - len(
                    covered_query_ids
                )
            ),
            "coverage_ratio": (
                len(covered_query_ids)
                / len(answerable)
                if answerable
                else 0.0
            ),
            "interpretation": (
                "Overall Golden60 metrics "
                "include queries whose relevant "
                "source is absent from the current "
                "snapshot. covered_only metrics "
                "must be reported separately."
            ),
        },
        "candidate_policy": {
            "same_candidate_top_k": True,
            "candidate_top_k": (
                CANDIDATE_TOP_K
            ),
            "metric_top_k": (
                METRIC_TOP_K
            ),
        },
        "fusion": {
            "rrf": {
                "k": RRF_K,
                "version": (
                    RRF_INDEX_VERSION
                ),
            },
            "weighted": {
                "bm25_weight": (
                    BM25_WEIGHT
                ),
                "vector_weight": (
                    VECTOR_WEIGHT
                ),
                "normalization": (
                    "MIN_MAX_PER_QUERY"
                ),
                "version": (
                    WEIGHTED_INDEX_VERSION
                ),
            },
        },
        "indexes": {
            "bm25": {
                "version": (
                    BM25_INDEX_VERSION
                ),
                "hash": sha256_json(
                    {
                        **index_config,
                        "method": "bm25",
                    }
                ),
                "build_ms": (
                    bm25_build_ms
                ),
            },
            "vector": {
                "version": (
                    VECTOR_INDEX_VERSION
                ),
                "hash": sha256_json(
                    {
                        **index_config,
                        "method": "vector",
                    }
                ),
                "build_ms": (
                    dense_build_ms
                ),
                "embedding": {
                    "model": (
                        model_name
                    ),
                    "revision": (
                        model_revision
                    ),
                    "device": "cpu",
                },
            },
            "rrf": {
                "version": (
                    RRF_INDEX_VERSION
                ),
                "hash": sha256_json(
                    {
                        **index_config,
                        "method": "rrf",
                    }
                ),
            },
            "weighted": {
                "version": (
                    WEIGHTED_INDEX_VERSION
                ),
                "hash": sha256_json(
                    {
                        **index_config,
                        "method": (
                            "weighted"
                        ),
                    }
                ),
            },
        },
        "methods": methods,
        "abstain_queries": (
            abstain_rows
        ),
        "cost": {
            "external_llm_calls": 0,
            "external_embedding_api_calls": 0,
            "api_cost_usd": 0.0,
            "local_cpu_embedding": True,
        },
        "limitations": [
            (
                "Current snapshot contains "
                "relevant evidence for only "
                f"{len(covered_query_ids)} of "
                f"{len(answerable)} answerable "
                "Golden60 queries."
            ),
            (
                "Absolute Golden60 metrics are "
                "therefore strongly limited by "
                "corpus coverage."
            ),
            (
                "Weighted Hybrid uses fixed "
                "0.5/0.5 weights in D09-AI-02. "
                "No test-set tuning is performed."
            ),
            (
                "No reranker is used."
            ),
        ],
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
        "DAY09_GOLDEN_HYBRID_EVAL_OK"
    )

    print(
        "SOURCE_CLASSIFICATION=",
        SOURCE_CLASSIFICATION,
    )

    print(
        "GOLDEN_TOTAL=",
        len(golden),
    )

    print(
        "ANSWERABLE=",
        len(answerable),
    )

    print(
        "COVERED=",
        len(covered_query_ids),
    )

    print(
        "COVERAGE_RATIO=",
        round(
            result[
                "coverage"
            ][
                "coverage_ratio"
            ],
            4,
        ),
    )

    for method in (
        "bm25",
        "vector",
        "rrf",
        "weighted",
    ):
        metrics = (
            result[
                "methods"
            ][
                method
            ][
                "overall"
            ][
                "metrics"
            ]
        )

        covered_metrics = (
            result[
                "methods"
            ][
                method
            ][
                "covered_only"
            ][
                "metrics"
            ]
        )

        print(
            method.upper(),
            "RECALL@5=",
            round(
                metrics[
                    "recall_at_5"
                ],
                4,
            ),
            "MRR=",
            round(
                metrics["mrr"],
                4,
            ),
            "NDCG@5=",
            round(
                metrics[
                    "ndcg_at_5"
                ],
                4,
            ),
            "COVERED_MRR=",
            round(
                covered_metrics[
                    "mrr"
                ],
                4,
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