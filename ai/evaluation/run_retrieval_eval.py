from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import time
import numpy as np
from sentence_transformers import SentenceTransformer

from ai.retrieval.dense import (
    DenseIndex,
    snapshot_to_dense_documents,
)

from pathlib import Path
from typing import Any, Iterable

from ai.retrieval.bm25 import (
    BM25Config,
    BM25Document,
    BM25Index,
)

from ai.retrieval.freshness import (
    FreshnessState,
    build_version_catalog,
    evaluate_freshness,
    load_freshness_policy,
)

DEFAULT_SNAPSHOT_PATH = Path(
    "artifacts/experiments/RAG-01/"
    "chunk_snapshot.jsonl"
)

DEFAULT_MANIFEST_PATH = Path(
    "artifacts/experiments/RAG-01/"
    "chunk_snapshot_manifest.json"
)

DEFAULT_EVAL_PATH = Path(
    "ai/evaluation/datasets/"
    "chunking_eval.jsonl"
)

DEFAULT_OUTPUT_PATH = Path(
    "artifacts/experiments/RAG-01/"
    "bm25_result.json"
)

BM25_INDEX_VERSION = "bm25-day07-v1"

DENSE_INDEX_VERSION = "dense-day07-v1"

DENSE_DEVICE = "cpu"

def load_jsonl(
    path: Path,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for line in path.read_text(
        encoding="utf-8"
    ).splitlines():
        if not line.strip():
            continue

        rows.append(json.loads(line))

    return rows


def load_json(
    path: Path,
) -> dict[str, Any]:
    return json.loads(
        path.read_text(encoding="utf-8")
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
    serialized = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()


def percentile(
    values: Iterable[float],
    probability: float,
) -> float:
    ordered = sorted(values)

    if not ordered:
        return 0.0

    if len(ordered) == 1:
        return ordered[0]

    position = (
        len(ordered) - 1
    ) * probability

    lower = math.floor(position)
    upper = math.ceil(position)

    if lower == upper:
        return ordered[lower]

    fraction = position - lower

    return (
        ordered[lower]
        + (
            ordered[upper]
            - ordered[lower]
        )
        * fraction
    )


def snapshot_to_documents(
    rows: list[dict[str, Any]],
) -> list[BM25Document]:
    documents: list[BM25Document] = []

    for row in rows:
        metadata = row.get("metadata") or {}

        if not isinstance(
            metadata,
            dict,
        ):
            raise ValueError(
                "snapshot metadata must be "
                f"an object: {row.get('chunk_id')}"
            )

        documents.append(
            BM25Document(
                chunk_id=str(
                    row["chunk_id"]
                ),
                source_id=str(
                    row["source_id"]
                ),
                source_type=str(
                    row["source_type"]
                ),
                version=str(
                    row["version"]
                ),
                text=str(
                    row["text"]
                ),
                metadata={
                    str(key): str(value)
                    for key, value
                    in metadata.items()
                },
            )
        )

    return documents


def relevant_grades(
    query: dict[str, Any],
) -> dict[str, int]:
    grades: dict[str, int] = {}

    for item in query.get(
        "relevant",
        [],
    ):
        source_id = str(
            item["source_id"]
        )

        grade = int(
            item.get("grade", 0)
        )

        grades[source_id] = max(
            grades.get(source_id, 0),
            grade,
        )

    return grades


def collapse_results_by_source(
    results: list[Any],
) -> list[Any]:
    collapsed: list[Any] = []
    seen: set[str] = set()

    for result in results:
        if result.source_id in seen:
            continue

        seen.add(result.source_id)
        collapsed.append(result)

    return collapsed

def prefer_fresh_versioned_results(
    results: list[Any],
    *,
    freshness_policy: dict[str, Any],
    version_catalog: dict[
        str,
        list[str],
    ],
) -> list[Any]:
    """
    VERSIONED source에 최신 valid version이 있으면
    superseded version을 대표 검색 결과로 사용하지 않는다.

    TTL / 정책 미정의 / 판정 불가능 source는
    이 함수에서 임의로 제거하지 않는다.
    """

    states_by_result_id: dict[
        int,
        FreshnessState,
    ] = {}

    source_has_fresh: set[str] = set()

    for result in results:
        freshness = evaluate_freshness(
            source_type=(
                result.source_type
            ),
            source_id=(
                result.source_id
            ),
            version=(
                result.version
            ),
            metadata=(
                result.metadata
            ),
            policy=(
                freshness_policy
            ),
            version_catalog=(
                version_catalog
            ),
        )

        states_by_result_id[
            id(result)
        ] = freshness.state

        if (
            freshness.state
            == FreshnessState.FRESH
        ):
            source_has_fresh.add(
                result.source_id
            )

    filtered: list[Any] = []

    for result in results:
        source_policy = (
            freshness_policy
            .get(
                "sources",
                {},
            )
            .get(
                result.source_type,
                {},
            )
        )

        mode = source_policy.get(
            "freshness_mode"
        )

        # VERSIONED source이고
        # 동일 source에 FRESH version이 실제 존재하면
        # STALE version은 검색 대표 후보에서 제외한다.
        if (
            mode == "VERSIONED"
            and result.source_id
            in source_has_fresh
            and states_by_result_id[
                id(result)
            ]
            != FreshnessState.FRESH
        ):
            continue

        filtered.append(
            result
        )

    return filtered

def first_relevant_rank(
    ranked_source_ids: list[str],
    grades: dict[str, int],
) -> int | None:
    for rank, source_id in enumerate(
        ranked_source_ids,
        start=1,
    ):
        if grades.get(source_id, 0) >= 2:
            return rank

    return None


def recall_at_k(
    ranked_source_ids: list[str],
    grades: dict[str, int],
    k: int,
) -> float:
    relevant = {
        source_id
        for source_id, grade
        in grades.items()
        if grade >= 2
    }

    if not relevant:
        return 0.0

    retrieved = set(
        ranked_source_ids[:k]
    )

    return len(
        relevant & retrieved
    ) / len(relevant)


def reciprocal_rank(
    ranked_source_ids: list[str],
    grades: dict[str, int],
) -> float:
    rank = first_relevant_rank(
        ranked_source_ids,
        grades,
    )

    if rank is None:
        return 0.0

    return 1.0 / rank


def dcg_at_k(
    ranked_source_ids: list[str],
    grades: dict[str, int],
    k: int,
) -> float:
    score = 0.0

    for index, source_id in enumerate(
        ranked_source_ids[:k],
        start=1,
    ):
        grade = grades.get(
            source_id,
            0,
        )

        if grade <= 0:
            continue

        gain = (2**grade) - 1

        score += (
            gain
            / math.log2(
                index + 1
            )
        )

    return score


def ndcg_at_k(
    ranked_source_ids: list[str],
    grades: dict[str, int],
    k: int,
) -> float:
    actual = dcg_at_k(
        ranked_source_ids,
        grades,
        k,
    )

    ideal_grades = sorted(
        grades.values(),
        reverse=True,
    )

    ideal = 0.0

    for index, grade in enumerate(
        ideal_grades[:k],
        start=1,
    ):
        if grade <= 0:
            continue

        ideal += (
            ((2**grade) - 1)
            / math.log2(
                index + 1
            )
        )

    if ideal <= 0:
        return 0.0

    return actual / ideal


def average(
    values: list[float],
) -> float:
    if not values:
        return 0.0

    return statistics.fmean(values)


def evaluate_bm25(
    *,
    snapshot_path: Path,
    manifest_path: Path,
    evaluation_path: Path,
    top_k: int,
) -> dict[str, Any]:
    snapshot = load_jsonl(
        snapshot_path
    )

    manifest = load_json(
        manifest_path
    )

    queries = load_jsonl(
        evaluation_path
    )

    freshness_policy = (
        load_freshness_policy()
    )

    version_catalog = (
        build_version_catalog(
            snapshot
        )
    )

    documents = snapshot_to_documents(
        snapshot
    )

    config = BM25Config()

    build_started = (
        time.perf_counter()
    )

    index = BM25Index(
        documents,
        config=config,
    )

    build_ms = (
        time.perf_counter()
        - build_started
    ) * 1000.0

    query_latencies: list[
        float
    ] = []

    answerable_results: list[
        dict[str, Any]
    ] = []

    abstain_results: list[
        dict[str, Any]
    ] = []

    for query in queries:
        query_started = (
            time.perf_counter()
        )

        # Chunk duplicate 때문에 source ranking이
        # 잘리지 않도록 전체 chunk를 먼저 검색한다.
        chunk_results = index.search(
            str(query["query"]),
            top_k=index.document_count,
        )

        fresh_results = (
            prefer_fresh_versioned_results(
                chunk_results,
                freshness_policy=(
                    freshness_policy
                ),
                version_catalog=(
                    version_catalog
                ),
            )
        )

        source_results = (
            collapse_results_by_source(
                fresh_results
            )
        )

        query_ms = (
            time.perf_counter()
            - query_started
        ) * 1000.0

        query_latencies.append(
            query_ms
        )

        top_results = (
            source_results[:top_k]
        )

        ranked_source_ids = [
            result.source_id
            for result in source_results
        ]

        serialized_top = [
            {
                "rank": rank,
                "source_id": (
                    result.source_id
                ),
                "version": (
                    result.version
                ),
                "chunk_id": (
                    result.chunk_id
                ),
                "score": (
                    result.score
                ),
            }
            for rank, result
            in enumerate(
                top_results,
                start=1,
            )
        ]

        if (
            query.get(
                "expected_answerability"
            )
            == "ANSWERABLE"
        ):
            grades = relevant_grades(
                query
            )

            result = {
                "query_id": (
                    query["query_id"]
                ),
                "query": (
                    query["query"]
                ),
                "slice": (
                    query["slice"]
                ),
                "first_relevant_rank": (
                    first_relevant_rank(
                        ranked_source_ids,
                        grades,
                    )
                ),
                "recall_at_1": (
                    recall_at_k(
                        ranked_source_ids,
                        grades,
                        1,
                    )
                ),
                "recall_at_3": (
                    recall_at_k(
                        ranked_source_ids,
                        grades,
                        3,
                    )
                ),
                "recall_at_5": (
                    recall_at_k(
                        ranked_source_ids,
                        grades,
                        5,
                    )
                ),
                "mrr": (
                    reciprocal_rank(
                        ranked_source_ids,
                        grades,
                    )
                ),
                "ndcg_at_5": (
                    ndcg_at_k(
                        ranked_source_ids,
                        grades,
                        5,
                    )
                ),
                "top_results": (
                    serialized_top
                ),
                "latency_ms": (
                    query_ms
                ),
            }

            answerable_results.append(
                result
            )

        else:
            abstain_results.append(
                {
                    "query_id": (
                        query["query_id"]
                    ),
                    "query": (
                        query["query"]
                    ),
                    "slice": (
                        query["slice"]
                    ),
                    "top_results": (
                        serialized_top
                    ),
                    "latency_ms": (
                        query_ms
                    ),
                }
            )

    slices = sorted(
        {
            result["slice"]
            for result
            in answerable_results
        }
    )

    slice_metrics: dict[
        str,
        dict[str, Any],
    ] = {}

    for slice_name in slices:
        subset = [
            result
            for result
            in answerable_results
            if result["slice"]
            == slice_name
        ]

        slice_metrics[
            slice_name
        ] = {
            "query_count": len(
                subset
            ),
            "recall_at_1": average(
                [
                    item["recall_at_1"]
                    for item in subset
                ]
            ),
            "recall_at_3": average(
                [
                    item["recall_at_3"]
                    for item in subset
                ]
            ),
            "recall_at_5": average(
                [
                    item["recall_at_5"]
                    for item in subset
                ]
            ),
            "mrr": average(
                [
                    item["mrr"]
                    for item in subset
                ]
            ),
            "ndcg_at_5": average(
                [
                    item["ndcg_at_5"]
                    for item in subset
                ]
            ),
        }

    index_payload = {
        "config": {
            "k1": config.k1,
            "b": config.b,
            "field_weights": dict(
                config.field_weights
            ),
        },
        "documents": [
            {
                "chunk_id": (
                    document.chunk_id
                ),
                "source_id": (
                    document.source_id
                ),
                "version": (
                    document.version
                ),
                "text": (
                    document.text
                ),
                "metadata": dict(
                    document.metadata
                ),
            }
            for document in documents
        ],
    }

    serialized_index = json.dumps(
        index_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    config_payload = {
        "index_version": (
            BM25_INDEX_VERSION
        ),
        "snapshot_hash": (
            manifest[
                "snapshot_hash"
            ]
        ),
        "k1": config.k1,
        "b": config.b,
        "field_weights": dict(
            config.field_weights
        ),
        "bm25_code_sha256": (
            sha256_file(
                Path(
                    "ai/retrieval/bm25.py"
                )
            )
        ),
    }

    index_hash = sha256_json(
        config_payload
    )

    failures = [
        result
        for result
        in answerable_results
        if result[
            "first_relevant_rank"
        ]
        is None
        or result[
            "first_relevant_rank"
        ] > 5
    ]

    hard_successes = [
        result
        for result
        in answerable_results
        if result[
            "first_relevant_rank"
        ]
        is not None
        and result[
            "first_relevant_rank"
        ] > 1
        and result[
            "first_relevant_rank"
        ] <= 5
    ]

    return {
        "schema_version": (
            "retrieval-eval-result.v1"
        ),
        "retriever": "bm25",
        "index": {
            "version": (
                BM25_INDEX_VERSION
            ),
            "hash": (
                index_hash
            ),
            "serialized_size_bytes": (
                len(serialized_index)
            ),
            "document_count": (
                index.document_count
            ),
            "config": {
                "k1": (
                    config.k1
                ),
                "b": (
                    config.b
                ),
                "field_weights": dict(
                    config.field_weights
                ),
            },
            "code_sha256": (
                sha256_file(
                    Path(
                        "ai/retrieval/bm25.py"
                    )
                )
            ),
        },
        "snapshot": {
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
            "chunking": (
                manifest[
                    "chunking"
                ]
            ),
        },
        "dataset": {
            "path": str(
                evaluation_path
            ),
            "sha256": (
                sha256_file(
                    evaluation_path
                )
            ),
            "query_count": len(
                queries
            ),
            "answerable_count": len(
                answerable_results
            ),
            "abstain_count": len(
                abstain_results
            ),
            "answerable_coverage": (
                manifest[
                    "evaluation"
                ][
                    "answerable_coverage"
                ]
            ),
        },
        "metrics": {
            "recall_at_1": average(
                [
                    item["recall_at_1"]
                    for item
                    in answerable_results
                ]
            ),
            "recall_at_3": average(
                [
                    item["recall_at_3"]
                    for item
                    in answerable_results
                ]
            ),
            "recall_at_5": average(
                [
                    item["recall_at_5"]
                    for item
                    in answerable_results
                ]
            ),
            "mrr": average(
                [
                    item["mrr"]
                    for item
                    in answerable_results
                ]
            ),
            "ndcg_at_5": average(
                [
                    item["ndcg_at_5"]
                    for item
                    in answerable_results
                ]
            ),
        },
        "latency": {
            "index_build_ms": (
                build_ms
            ),
            "query_p50_ms": (
                percentile(
                    query_latencies,
                    0.50,
                )
            ),
            "query_p95_ms": (
                percentile(
                    query_latencies,
                    0.95,
                )
            ),
            "query_mean_ms": (
                average(
                    query_latencies
                )
            ),
        },
        "slice_metrics": (
            slice_metrics
        ),
        "analysis": {
            "retrieval_failure_count": (
                len(failures)
            ),
            "hard_success_count": (
                len(hard_successes)
            ),
            "retrieval_failures": (
                failures
            ),
            "hard_successes": (
                hard_successes
            ),
        },
        "query_results": (
            answerable_results
        ),
        "abstain_queries": (
            abstain_results
        ),
        "cost": {
            "llm_api_calls": 0,
            "embedding_api_calls": 0,
            "api_cost_usd": 0.0,
            "gpu_used": False,
        },
        "limitations": [
            (
                "Day 7 BM25 baseline uses "
                "the 16-query versioned "
                "chunking evaluation set."
            ),
            (
                "Golden60 is not used for "
                "performance measurement "
                "because the current corpus "
                "covers only 2 of 52 "
                "answerable queries."
            ),
            (
                "brand and sku field weights "
                "are configured but inactive "
                "because the current fixture "
                "does not contain those fields."
            ),
            (
                "ABSTAIN behavior is not "
                "decided by BM25 ranking alone; "
                "confidence routing is D07-AI-04."
            ),
        ],
    }

def evaluate_dense(
    *,
    snapshot_path: Path,
    manifest_path: Path,
    evaluation_path: Path,
    top_k: int,
) -> dict[str, Any]:
    """
    Day 7 Dense baseline 평가.

    cold build:
        model load + document embedding + index build

    warm build:
        이미 load된 model 재사용
        + document embedding + index build

    query latency:
        완성된 warm index에서 query embedding
        + cosine ranking 시간
    """

    snapshot = load_jsonl(
        snapshot_path
    )

    manifest = load_json(
        manifest_path
    )

    queries = load_jsonl(
        evaluation_path
    )

    freshness_policy = (
        load_freshness_policy()
    )

    version_catalog = (
        build_version_catalog(
            snapshot
        )
    )

    documents = (
        snapshot_to_dense_documents(
            snapshot
        )
    )

    embedding_config = manifest.get(
        "embedding"
    ) or {}

    model_name = embedding_config.get(
        "model"
    )

    model_revision = embedding_config.get(
        "revision"
    )

    if not model_name:
        raise ValueError(
            "snapshot manifest is missing "
            "embedding.model"
        )

    if not model_revision:
        raise ValueError(
            "snapshot manifest is missing "
            "embedding.revision"
        )

    # ---------------------------------
    # Cold Build
    # model load를 포함한다.
    # ---------------------------------

    cold_started = (
        time.perf_counter()
    )

    model = SentenceTransformer(
        model_name,
        revision=model_revision,
        device=DENSE_DEVICE,
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

    cold_index = DenseIndex(
        documents,
        embed_texts=embed_texts,
    )

    cold_build_ms = (
        time.perf_counter()
        - cold_started
    ) * 1000.0

    # cold index가 정상 생성됐는지 확인 후
    # warm 측정을 별도로 수행한다.
    if cold_index.document_count != len(
        documents
    ):
        raise RuntimeError(
            "cold dense index document "
            "count mismatch"
        )

    # ---------------------------------
    # Warm Build
    # model은 이미 memory에 load되어 있다.
    # ---------------------------------

    warm_started = (
        time.perf_counter()
    )

    index = DenseIndex(
        documents,
        embed_texts=embed_texts,
    )

    warm_build_ms = (
        time.perf_counter()
        - warm_started
    ) * 1000.0

    vector_dimension = (
        index.vector_dimension
    )

    embeddings = (
        index.embeddings
    )

    if embeddings.shape != (
        len(documents),
        vector_dimension,
    ):
        raise RuntimeError(
            "dense embedding matrix shape "
            "is invalid"
        )

    # normalize_embeddings=True가 실제로
    # 적용됐는지 검증한다.
    norms = np.linalg.norm(
        embeddings,
        axis=1,
    )

    if not np.allclose(
        norms,
        1.0,
        atol=1e-4,
    ):
        raise RuntimeError(
            "document embeddings are "
            "not normalized"
        )

    query_latencies: list[
        float
    ] = []

    answerable_results: list[
        dict[str, Any]
    ] = []

    abstain_results: list[
        dict[str, Any]
    ] = []

    for query in queries:
        query_started = (
            time.perf_counter()
        )

        # source-level collapse 전에 모든
        # chunk를 검색한다.
        chunk_results = index.search(
            str(query["query"]),
            top_k=index.document_count,
        )

        fresh_results = (
            prefer_fresh_versioned_results(
                chunk_results,
                freshness_policy=(
                    freshness_policy
                ),
                version_catalog=(
                    version_catalog
                ),
            )
        )

        source_results = (
            collapse_results_by_source(
                fresh_results
            )
        )

        query_ms = (
            time.perf_counter()
            - query_started
        ) * 1000.0

        query_latencies.append(
            query_ms
        )

        top_results = (
            source_results[:top_k]
        )

        ranked_source_ids = [
            result.source_id
            for result
            in source_results
        ]

        serialized_top = [
            {
                "rank": rank,
                "source_id": (
                    result.source_id
                ),
                "version": (
                    result.version
                ),
                "chunk_id": (
                    result.chunk_id
                ),
                "score": (
                    result.score
                ),
            }
            for rank, result
            in enumerate(
                top_results,
                start=1,
            )
        ]

        if (
            query.get(
                "expected_answerability"
            )
            == "ANSWERABLE"
        ):
            grades = relevant_grades(
                query
            )

            answerable_results.append(
                {
                    "query_id": (
                        query["query_id"]
                    ),
                    "query": (
                        query["query"]
                    ),
                    "slice": (
                        query["slice"]
                    ),
                    "first_relevant_rank": (
                        first_relevant_rank(
                            ranked_source_ids,
                            grades,
                        )
                    ),
                    "recall_at_1": (
                        recall_at_k(
                            ranked_source_ids,
                            grades,
                            1,
                        )
                    ),
                    "recall_at_3": (
                        recall_at_k(
                            ranked_source_ids,
                            grades,
                            3,
                        )
                    ),
                    "recall_at_5": (
                        recall_at_k(
                            ranked_source_ids,
                            grades,
                            5,
                        )
                    ),
                    "mrr": (
                        reciprocal_rank(
                            ranked_source_ids,
                            grades,
                        )
                    ),
                    "ndcg_at_5": (
                        ndcg_at_k(
                            ranked_source_ids,
                            grades,
                            5,
                        )
                    ),
                    "top_results": (
                        serialized_top
                    ),
                    "latency_ms": (
                        query_ms
                    ),
                }
            )

        else:
            abstain_results.append(
                {
                    "query_id": (
                        query["query_id"]
                    ),
                    "query": (
                        query["query"]
                    ),
                    "slice": (
                        query["slice"]
                    ),
                    "top_results": (
                        serialized_top
                    ),
                    "latency_ms": (
                        query_ms
                    ),
                }
            )

    slices = sorted(
        {
            result["slice"]
            for result
            in answerable_results
        }
    )

    slice_metrics: dict[
        str,
        dict[str, Any],
    ] = {}

    for slice_name in slices:
        subset = [
            result
            for result
            in answerable_results
            if result["slice"]
            == slice_name
        ]

        slice_metrics[
            slice_name
        ] = {
            "query_count": len(
                subset
            ),
            "recall_at_1": average(
                [
                    item["recall_at_1"]
                    for item in subset
                ]
            ),
            "recall_at_3": average(
                [
                    item["recall_at_3"]
                    for item in subset
                ]
            ),
            "recall_at_5": average(
                [
                    item["recall_at_5"]
                    for item in subset
                ]
            ),
            "mrr": average(
                [
                    item["mrr"]
                    for item in subset
                ]
            ),
            "ndcg_at_5": average(
                [
                    item["ndcg_at_5"]
                    for item in subset
                ]
            ),
        }

    failures = [
        result
        for result
        in answerable_results
        if result[
            "first_relevant_rank"
        ]
        is None
        or result[
            "first_relevant_rank"
        ] > 5
    ]

    hard_successes = [
        result
        for result
        in answerable_results
        if result[
            "first_relevant_rank"
        ]
        is not None
        and result[
            "first_relevant_rank"
        ] > 1
        and result[
            "first_relevant_rank"
        ] <= 5
    ]

    # Vector matrix 자체의 byte 크기와
    # source/chunk metadata 크기를 합쳐
    # 비교 가능한 index size 근사값을 만든다.
    metadata_payload = [
        {
            "chunk_id": (
                document.chunk_id
            ),
            "source_id": (
                document.source_id
            ),
            "source_type": (
                document.source_type
            ),
            "version": (
                document.version
            ),
            "metadata": dict(
                document.metadata
            ),
        }
        for document in documents
    ]

    metadata_bytes = len(
        json.dumps(
            metadata_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )

    vector_bytes = int(
        embeddings.nbytes
    )

    index_size_bytes = (
        vector_bytes
        + metadata_bytes
    )

    config_payload = {
        "index_version": (
            DENSE_INDEX_VERSION
        ),
        "snapshot_hash": (
            manifest[
                "snapshot_hash"
            ]
        ),
        "model": model_name,
        "revision": (
            model_revision
        ),
        "vector_dimension": (
            vector_dimension
        ),
        "normalized": True,
        "device": (
            DENSE_DEVICE
        ),
        "dense_code_sha256": (
            sha256_file(
                Path(
                    "ai/retrieval/dense.py"
                )
            )
        ),
    }

    index_hash = sha256_json(
        config_payload
    )

    return {
        "schema_version": (
            "retrieval-eval-result.v1"
        ),
        "retriever": "dense",
        "index": {
            "version": (
                DENSE_INDEX_VERSION
            ),
            "hash": (
                index_hash
            ),
            "document_count": (
                index.document_count
            ),
            "vector_dimension": (
                vector_dimension
            ),
            "vector_bytes": (
                vector_bytes
            ),
            "metadata_bytes": (
                metadata_bytes
            ),
            "serialized_size_bytes": (
                index_size_bytes
            ),
            "code_sha256": (
                sha256_file(
                    Path(
                        "ai/retrieval/dense.py"
                    )
                )
            ),
        },
        "embedding": {
            "model": (
                model_name
            ),
            "revision": (
                model_revision
            ),
            "normalized": True,
            "device": (
                DENSE_DEVICE
            ),
        },
        "snapshot": {
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
            "chunking": (
                manifest[
                    "chunking"
                ]
            ),
        },
        "dataset": {
            "path": str(
                evaluation_path
            ),
            "sha256": (
                sha256_file(
                    evaluation_path
                )
            ),
            "query_count": len(
                queries
            ),
            "answerable_count": len(
                answerable_results
            ),
            "abstain_count": len(
                abstain_results
            ),
            "answerable_coverage": (
                manifest[
                    "evaluation"
                ][
                    "answerable_coverage"
                ]
            ),
        },
        "metrics": {
            "recall_at_1": average(
                [
                    item["recall_at_1"]
                    for item
                    in answerable_results
                ]
            ),
            "recall_at_3": average(
                [
                    item["recall_at_3"]
                    for item
                    in answerable_results
                ]
            ),
            "recall_at_5": average(
                [
                    item["recall_at_5"]
                    for item
                    in answerable_results
                ]
            ),
            "mrr": average(
                [
                    item["mrr"]
                    for item
                    in answerable_results
                ]
            ),
            "ndcg_at_5": average(
                [
                    item["ndcg_at_5"]
                    for item
                    in answerable_results
                ]
            ),
        },
        "latency": {
            "cold_build_ms": (
                cold_build_ms
            ),
            "warm_build_ms": (
                warm_build_ms
            ),
            "query_mean_ms": (
                average(
                    query_latencies
                )
            ),
            "query_p50_ms": (
                percentile(
                    query_latencies,
                    0.50,
                )
            ),
            "query_p95_ms": (
                percentile(
                    query_latencies,
                    0.95,
                )
            ),
        },
        "slice_metrics": (
            slice_metrics
        ),
        "analysis": {
            "retrieval_failure_count": (
                len(failures)
            ),
            "hard_success_count": (
                len(hard_successes)
            ),
            "retrieval_failures": (
                failures
            ),
            "hard_successes": (
                hard_successes
            ),
        },
        "query_results": (
            answerable_results
        ),
        "abstain_queries": (
            abstain_results
        ),
        "cost": {
            "llm_api_calls": 0,
            "embedding_api_calls": 0,
            "api_cost_usd": 0.0,
            "gpu_used": False,
            "local_cpu_embedding": True,
        },
        "limitations": [
            (
                "Dense uses the same "
                "31-chunk semantic snapshot "
                "as BM25."
            ),
            (
                "Golden60 is not used because "
                "the current corpus covers "
                "only 2 of 52 answerable "
                "Golden queries."
            ),
            (
                "Cold build includes model "
                "loading and document embedding."
            ),
            (
                "Warm build reuses the already "
                "loaded embedding model."
            ),
            (
                "ABSTAIN routing is evaluated "
                "in D07-AI-04 confidence."
            ),
        ],
    }

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run Day 7 retrieval evaluation."
        )
    )

    parser.add_argument(
        "--retriever",
        choices=[
            "bm25",
            "dense",
        ],
        default="bm25",
    )

    parser.add_argument(
        "--snapshot",
        type=Path,
        default=DEFAULT_SNAPSHOT_PATH,
    )

    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
    )

    parser.add_argument(
        "--evaluation",
        type=Path,
        default=DEFAULT_EVAL_PATH,
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.top_k <= 0:
        raise ValueError(
            "top-k must be greater than 0"
        )

    if args.retriever == "bm25":
        result = evaluate_bm25(
            snapshot_path=args.snapshot,
            manifest_path=args.manifest,
            evaluation_path=args.evaluation,
            top_k=args.top_k,
        )

    elif args.retriever == "dense":
        result = evaluate_dense(
            snapshot_path=args.snapshot,
            manifest_path=args.manifest,
            evaluation_path=args.evaluation,
            top_k=args.top_k,
        )

    else:
        raise ValueError(
            f"unsupported retriever: "
            f"{args.retriever}"
        )

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    args.output.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    metrics = result["metrics"]
    latency = result["latency"]

    print("RETRIEVAL_EVAL_OK")

    print(
        "RETRIEVER=",
        result["retriever"],
    )

    print(
        "INDEX_VERSION=",
        result["index"]["version"],
    )

    print(
        "INDEX_HASH=",
        result["index"]["hash"],
    )

    print(
        "INDEX_SIZE_BYTES=",
        result[
            "index"
        ][
            "serialized_size_bytes"
        ],
    )

    if result["retriever"] == "dense":
        print(
            "VECTOR_DIMENSION=",
            result[
                "index"
            ][
                "vector_dimension"
            ],
        )

        print(
            "MODEL=",
            result[
                "embedding"
            ][
                "model"
            ],
        )

        print(
            "MODEL_REVISION=",
            result[
                "embedding"
            ][
                "revision"
            ],
        )

    print(
        "RECALL@1=",
        round(
            metrics["recall_at_1"],
            4,
        ),
    )

    print(
        "RECALL@3=",
        round(
            metrics["recall_at_3"],
            4,
        ),
    )

    print(
        "RECALL@5=",
        round(
            metrics["recall_at_5"],
            4,
        ),
    )

    print(
        "MRR=",
        round(
            metrics["mrr"],
            4,
        ),
    )

    print(
        "NDCG@5=",
        round(
            metrics["ndcg_at_5"],
            4,
        ),
    )

    if result["retriever"] == "bm25":
        print(
            "BUILD_MS=",
            round(
                latency[
                    "index_build_ms"
                ],
                4,
            ),
        )

    else:
        print(
            "COLD_BUILD_MS=",
            round(
                latency[
                    "cold_build_ms"
                ],
                4,
            ),
        )

        print(
            "WARM_BUILD_MS=",
            round(
                latency[
                    "warm_build_ms"
                ],
                4,
            ),
        )

    print(
        "QUERY_P50_MS=",
        round(
            latency["query_p50_ms"],
            4,
        ),
    )

    print(
        "QUERY_P95_MS=",
        round(
            latency["query_p95_ms"],
            4,
        ),
    )
    print(
        "FAILURE_COUNT=",
        result[
            "analysis"
        ][
            "retrieval_failure_count"
        ],
    )
    print(
        "HARD_SUCCESS_COUNT=",
        result[
            "analysis"
        ][
            "hard_success_count"
        ],
    )
    print(
        "OUTPUT=",
        args.output,
    )


if __name__ == "__main__":
    main()