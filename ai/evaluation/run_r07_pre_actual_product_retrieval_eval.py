from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import statistics
import time
from pathlib import Path
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer

from ai.evaluation.run_retrieval_eval import (
    snapshot_to_documents,
)
from ai.retrieval.bm25 import BM25Index
from ai.retrieval.dense import (
    DenseIndex,
    snapshot_to_dense_documents,
)
from ai.retrieval.hybrid import reciprocal_rank_fusion


ROOT = Path(__file__).resolve().parents[2]

EXPERIMENT_DIR = (
    ROOT
    / "artifacts"
    / "experiments"
    / "OPS-RAG-SCALE-01"
)

PRIVATE_DIR = EXPERIMENT_DIR / "private"

PRODUCT_SNAPSHOT = (
    ROOT
    / "artifacts"
    / "experiments"
    / "OPS-R07-PRE"
    / "private"
    / "product"
    / "product_safe_snapshot.jsonl"
)

DEV24_PATH = (
    PRIVATE_DIR
    / "actual_product_dev24.jsonl"
)

RUN_CONFIG_PATH = (
    EXPERIMENT_DIR
    / "r07_pre_run_config.json"
)

PRIVATE_RESULT_PATH = (
    PRIVATE_DIR
    / "r07_pre_retrieval_result.json"
)

SUMMARY_PATH = (
    EXPERIMENT_DIR
    / "r07_pre_summary.json"
)


SNAPSHOT_SHA256 = (
    "6438ad2ca5a21d4d30b1bf5bacbeb186"
    "679df1c16369fbc8eacc9cca3f1a9892"
)

BACKEND_MANIFEST_SHA256 = (
    "4933b41ef73ca05714af08e5544c109e"
    "0502c043457e942f04ff976067539da9"
)

DEV24_SHA256 = (
    "c434e0a6c784861962dc09d5472380e5"
    "d775f4286590b8bc8de564b4552b879a"
)

RECORD_VERSION = (
    "product-file-set-sha256:"
    "fe4737287d33d8ca58fdfd15c0650e35"
    "bfbdbb54db9a83bef7798e8b7b4d6d7c"
)

MODEL_NAME = (
    "sentence-transformers/"
    "paraphrase-multilingual-MiniLM-L12-v2"
)

MODEL_REVISION = (
    "e8f8c211226b894fcb81acc59f3b34ba"
    "3efd5f42"
)

VECTOR_DIMENSION = 384
DEVICE = "cpu"

CANDIDATE_TOP_K = 8
METRIC_TOP_K = 5
RRF_K = 60

SEED = "R07-PRE-E08-20260929"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]


def validate_inputs(
    products: list[dict[str, Any]],
    dev: list[dict[str, Any]],
) -> None:
    if sha256_file(PRODUCT_SNAPSHOT) != SNAPSHOT_SHA256:
        raise RuntimeError(
            "PRODUCT snapshot SHA256 mismatch"
        )

    if sha256_file(DEV24_PATH) != DEV24_SHA256:
        raise RuntimeError(
            "DEV24 SHA256 mismatch"
        )

    if len(products) != 2167:
        raise RuntimeError(
            f"PRODUCT count != 2167: {len(products)}"
        )

    if len(dev) != 24:
        raise RuntimeError(
            f"DEV24 count != 24: {len(dev)}"
        )

    versions = {
        row.get("version")
        for row in products
    }

    if versions != {RECORD_VERSION}:
        raise RuntimeError(
            "unexpected PRODUCT record version"
        )

    quality = {
        row.get("quality_status")
        for row in products
    }

    if quality != {
        "APPROVED_FOR_R07_PRE_PRODUCT_EVAL"
    }:
        raise RuntimeError(
            "PRODUCT quality status mismatch"
        )

    if any(
        row.get("review_status")
        != "HUMAN_REVIEWED"
        for row in dev
    ):
        raise RuntimeError(
            "DEV24 is not fully HUMAN_REVIEWED"
        )


def build_retrieval_snapshot(
    products: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for product in products:
        product_no = str(
            product["product_no"]
        )

        product_name = str(
            product["product_name"]
        ).strip()

        product_code = str(
            product["product_code"]
        ).strip()

        custom_code = str(
            product.get(
                "custom_product_code"
            )
            or ""
        ).strip()

        categories = [
            str(value)
            for value in (
                product.get("category_nos")
                or []
            )
        ]

        text_parts = [
            product_name,
            product_code,
        ]

        if custom_code:
            text_parts.append(custom_code)

        if categories:
            text_parts.append(
                "category_no "
                + " ".join(categories)
            )

        if product.get("is_preorder"):
            text_parts.append(
                "PRE-ORDER preorder 예약 상품"
            )

        text = " | ".join(text_parts)

        rows.append(
            {
                "chunk_id": (
                    f"product:{product_no}:0"
                ),
                "source_id": (
                    f"product:{product_no}"
                ),
                "source_type": "PRODUCT",
                "version": product["version"],
                "text": text,
                "metadata": {
                    "product_no": product_no,
                    "name": product_name,
                    "product_code": (
                        product_code
                    ),
                    "custom_product_code": (
                        custom_code
                    ),
                    "category_nos": (
                        ",".join(categories)
                    ),
                    "is_preorder": str(
                        bool(
                            product.get(
                                "is_preorder"
                            )
                        )
                    ).lower(),
                },
            }
        )

    return rows


def evidence_set(
    case: dict[str, Any],
) -> set[tuple[str, str]]:
    return {
        (
            str(item["source_id"]),
            str(item["version"]),
        )
        for item in case["evidence"]
    }


def result_pairs(
    results: list[Any],
    top_k: int,
) -> list[tuple[str, str]]:
    return [
        (
            str(result.source_id),
            str(result.version),
        )
        for result in results[:top_k]
    ]


def recall_at_5(
    results: list[Any],
    required: set[tuple[str, str]],
) -> float:
    if not required:
        return 0.0

    found = set(
        result_pairs(
            results,
            METRIC_TOP_K,
        )
    )

    return len(
        required & found
    ) / len(required)


def mrr_at_5(
    results: list[Any],
    required: set[tuple[str, str]],
) -> float:
    for rank, pair in enumerate(
        result_pairs(
            results,
            METRIC_TOP_K,
        ),
        start=1,
    ):
        if pair in required:
            return 1.0 / rank

    return 0.0


def full_evidence_at_5(
    results: list[Any],
    required: set[tuple[str, str]],
) -> bool:
    found = set(
        result_pairs(
            results,
            METRIC_TOP_K,
        )
    )

    return required.issubset(found)


def percentile(
    values: list[float],
    p: float,
) -> float | None:
    if not values:
        return None

    ordered = sorted(values)

    if len(ordered) == 1:
        return ordered[0]

    position = (
        len(ordered) - 1
    ) * p

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


def latency_summary(
    values: list[float],
) -> dict[str, Any]:
    if not values:
        return {
            "count": 0,
            "cold_first_ms": None,
            "warm_count": 0,
            "warm_mean_ms": None,
            "warm_p95_ms": None,
        }

    warm = values[1:]

    return {
        "count": len(values),
        "cold_first_ms": values[0],
        "warm_count": len(warm),
        "warm_mean_ms": (
            statistics.mean(warm)
            if warm
            else None
        ),
        "warm_p95_ms": (
            percentile(warm, 0.95)
            if warm
            else None
        ),
    }


def serialize_top5(
    results: list[Any],
) -> list[dict[str, Any]]:
    payload = []

    for result in results[:METRIC_TOP_K]:
        payload.append(
            {
                "rank": int(result.rank),
                "source_id": (
                    str(result.source_id)
                ),
                "version": (
                    str(result.version)
                ),
                "score": float(
                    result.score
                ),
            }
        )

    return payload


def summarize_method(
    rows: list[dict[str, Any]],
    method: str,
) -> dict[str, Any]:
    subset = [
        row
        for row in rows
        if row["method"] == method
        and row["status"] == "SUCCEEDED"
    ]

    answerable = [
        row
        for row in subset
        if row["answerability"]
        == "ANSWERABLE"
    ]

    recall_values = [
        row["recall_at_5"]
        for row in answerable
    ]

    mrr_values = [
        row["mrr_at_5"]
        for row in answerable
    ]

    full_values = [
        row["full_evidence_at_5"]
        for row in answerable
    ]

    zero_results = sum(
        1
        for row in subset
        if row["returned_count"] == 0
    )

    return {
        "attempted": sum(
            1
            for row in rows
            if row["method"] == method
        ),
        "succeeded": len(subset),
        "error": sum(
            1
            for row in rows
            if row["method"] == method
            and row["status"] == "ERROR"
        ),
        "blocked": sum(
            1
            for row in rows
            if row["method"] == method
            and row["status"] == "BLOCKED"
        ),
        "not_run": sum(
            1
            for row in rows
            if row["method"] == method
            and row["status"] == "NOT_RUN"
        ),
        "answerable_denominator": (
            len(answerable)
        ),
        "hold_count": sum(
            1
            for row in subset
            if row["answerability"]
            == "HOLD"
        ),
        "recall_at_5": (
            statistics.mean(
                recall_values
            )
            if recall_values
            else None
        ),
        "mrr_at_5": (
            statistics.mean(
                mrr_values
            )
            if mrr_values
            else None
        ),
        "full_evidence_count": sum(
            bool(value)
            for value in full_values
        ),
        "full_evidence_rate": (
            statistics.mean(
                [
                    1.0
                    if value
                    else 0.0
                    for value in full_values
                ]
            )
            if full_values
            else None
        ),
        "zero_result_count": (
            zero_results
        ),
    }


def main() -> None:
    EXPERIMENT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    PRIVATE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    products = load_jsonl(
        PRODUCT_SNAPSHOT
    )

    dev = load_jsonl(
        DEV24_PATH
    )

    validate_inputs(
        products,
        dev,
    )

    retrieval_snapshot = (
        build_retrieval_snapshot(
            products
        )
    )

    if len(retrieval_snapshot) != 2167:
        raise RuntimeError(
            "retrieval document count mismatch"
        )

    bm25_documents = (
        snapshot_to_documents(
            retrieval_snapshot
        )
    )

    dense_documents = (
        snapshot_to_dense_documents(
            retrieval_snapshot
        )
    )

    # BM25 index build
    started = time.perf_counter()

    bm25 = BM25Index(
        bm25_documents
    )

    bm25_build_ms = (
        time.perf_counter()
        - started
    ) * 1000.0

    # Dense model load
    started = time.perf_counter()

    model = SentenceTransformer(
        MODEL_NAME,
        revision=MODEL_REVISION,
        device=DEVICE,
        local_files_only=True,
    )

    model_load_ms = (
        time.perf_counter()
        - started
    ) * 1000.0

    dimension = int(
        model.get_embedding_dimension()
    )

    if dimension != VECTOR_DIMENSION:
        raise RuntimeError(
            f"vector dimension mismatch: "
            f"{dimension}"
        )

    embedding_calls: list[
        dict[str, Any]
    ] = []

    def embed_texts(
        texts: list[str],
    ) -> np.ndarray:
        started = time.perf_counter()

        vectors = np.asarray(
            model.encode(
                texts,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            ),
            dtype=np.float32,
        )

        elapsed = (
            time.perf_counter()
            - started
        ) * 1000.0

        embedding_calls.append(
            {
                "count": len(texts),
                "elapsed_ms": elapsed,
            }
        )

        return vectors

    # Dense document embedding + index
    started = time.perf_counter()

    dense = DenseIndex(
        dense_documents,
        embed_texts=embed_texts,
    )

    dense_build_total_ms = (
        time.perf_counter()
        - started
    ) * 1000.0

    document_embedding_ms = sum(
        item["elapsed_ms"]
        for item in embedding_calls
    )

    document_embedding_calls = len(
        embedding_calls
    )

    dense_index_only_ms = max(
        0.0,
        dense_build_total_ms
        - document_embedding_ms,
    )

    # 이후 embedding call은 query용
    embedding_calls.clear()

    rows: list[dict[str, Any]] = []

    bm25_latencies: list[float] = []
    dense_latencies: list[float] = []
    rrf_fusion_latencies: list[float] = []
    rrf_e2e_latencies: list[float] = []

    for case in dev:
        query = str(
            case["query"]
        )

        required = evidence_set(
            case
        )

        # BM25
        try:
            started = time.perf_counter()

            bm25_results = bm25.search(
                query,
                top_k=CANDIDATE_TOP_K,
            )

            bm25_ms = (
                time.perf_counter()
                - started
            ) * 1000.0

            bm25_latencies.append(
                bm25_ms
            )

            rows.append(
                {
                    "case_id": (
                        case["case_id"]
                    ),
                    "case_group": (
                        case["case_group"]
                    ),
                    "answerability": (
                        case["answerability"]
                    ),
                    "method": "bm25",
                    "status": "SUCCEEDED",
                    "error": None,
                    "latency_ms": bm25_ms,
                    "returned_count": len(
                        bm25_results
                    ),
                    "recall_at_5": (
                        recall_at_5(
                            bm25_results,
                            required,
                        )
                    ),
                    "mrr_at_5": (
                        mrr_at_5(
                            bm25_results,
                            required,
                        )
                    ),
                    "full_evidence_at_5": (
                        full_evidence_at_5(
                            bm25_results,
                            required,
                        )
                    ),
                    "top5": serialize_top5(
                        bm25_results
                    ),
                }
            )

        except Exception as exc:
            bm25_results = []
            bm25_ms = 0.0

            rows.append(
                {
                    "case_id": (
                        case["case_id"]
                    ),
                    "case_group": (
                        case["case_group"]
                    ),
                    "answerability": (
                        case["answerability"]
                    ),
                    "method": "bm25",
                    "status": "ERROR",
                    "error": (
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    ),
                    "latency_ms": None,
                    "returned_count": 0,
                    "recall_at_5": None,
                    "mrr_at_5": None,
                    "full_evidence_at_5": None,
                    "top5": [],
                }
            )

        # Dense
        try:
            started = time.perf_counter()

            dense_results = dense.search(
                query,
                top_k=CANDIDATE_TOP_K,
            )

            dense_ms = (
                time.perf_counter()
                - started
            ) * 1000.0

            dense_latencies.append(
                dense_ms
            )

            rows.append(
                {
                    "case_id": (
                        case["case_id"]
                    ),
                    "case_group": (
                        case["case_group"]
                    ),
                    "answerability": (
                        case["answerability"]
                    ),
                    "method": "dense",
                    "status": "SUCCEEDED",
                    "error": None,
                    "latency_ms": dense_ms,
                    "returned_count": len(
                        dense_results
                    ),
                    "recall_at_5": (
                        recall_at_5(
                            dense_results,
                            required,
                        )
                    ),
                    "mrr_at_5": (
                        mrr_at_5(
                            dense_results,
                            required,
                        )
                    ),
                    "full_evidence_at_5": (
                        full_evidence_at_5(
                            dense_results,
                            required,
                        )
                    ),
                    "top5": serialize_top5(
                        dense_results
                    ),
                }
            )

        except Exception as exc:
            dense_results = []
            dense_ms = 0.0

            rows.append(
                {
                    "case_id": (
                        case["case_id"]
                    ),
                    "case_group": (
                        case["case_group"]
                    ),
                    "answerability": (
                        case["answerability"]
                    ),
                    "method": "dense",
                    "status": "ERROR",
                    "error": (
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    ),
                    "latency_ms": None,
                    "returned_count": 0,
                    "recall_at_5": None,
                    "mrr_at_5": None,
                    "full_evidence_at_5": None,
                    "top5": [],
                }
            )

        # RRF Hybrid
        if (
            bm25_results
            and dense_results
        ):
            try:
                started = time.perf_counter()

                rrf_results = (
                    reciprocal_rank_fusion(
                        bm25_results,
                        dense_results,
                        candidate_top_k=(
                            CANDIDATE_TOP_K
                        ),
                        rrf_k=RRF_K,
                    )
                )

                fusion_ms = (
                    time.perf_counter()
                    - started
                ) * 1000.0

                e2e_ms = (
                    bm25_ms
                    + dense_ms
                    + fusion_ms
                )

                rrf_fusion_latencies.append(
                    fusion_ms
                )

                rrf_e2e_latencies.append(
                    e2e_ms
                )

                rows.append(
                    {
                        "case_id": (
                            case["case_id"]
                        ),
                        "case_group": (
                            case[
                                "case_group"
                            ]
                        ),
                        "answerability": (
                            case[
                                "answerability"
                            ]
                        ),
                        "method": (
                            "rrf_hybrid"
                        ),
                        "status": (
                            "SUCCEEDED"
                        ),
                        "error": None,
                        "latency_ms": (
                            e2e_ms
                        ),
                        "fusion_latency_ms": (
                            fusion_ms
                        ),
                        "returned_count": (
                            len(rrf_results)
                        ),
                        "recall_at_5": (
                            recall_at_5(
                                rrf_results,
                                required,
                            )
                        ),
                        "mrr_at_5": (
                            mrr_at_5(
                                rrf_results,
                                required,
                            )
                        ),
                        "full_evidence_at_5": (
                            full_evidence_at_5(
                                rrf_results,
                                required,
                            )
                        ),
                        "top5": serialize_top5(
                            rrf_results
                        ),
                    }
                )

            except Exception as exc:
                rows.append(
                    {
                        "case_id": (
                            case["case_id"]
                        ),
                        "case_group": (
                            case[
                                "case_group"
                            ]
                        ),
                        "answerability": (
                            case[
                                "answerability"
                            ]
                        ),
                        "method": (
                            "rrf_hybrid"
                        ),
                        "status": "ERROR",
                        "error": (
                            f"{type(exc).__name__}: "
                            f"{exc}"
                        ),
                        "latency_ms": None,
                        "fusion_latency_ms": None,
                        "returned_count": 0,
                        "recall_at_5": None,
                        "mrr_at_5": None,
                        "full_evidence_at_5": None,
                        "top5": [],
                    }
                )

        else:
            rows.append(
                {
                    "case_id": (
                        case["case_id"]
                    ),
                    "case_group": (
                        case["case_group"]
                    ),
                    "answerability": (
                        case["answerability"]
                    ),
                    "method": (
                        "rrf_hybrid"
                    ),
                    "status": "BLOCKED",
                    "error": (
                        "BM25 or Dense "
                        "prerequisite failed"
                    ),
                    "latency_ms": None,
                    "fusion_latency_ms": None,
                    "returned_count": 0,
                    "recall_at_5": None,
                    "mrr_at_5": None,
                    "full_evidence_at_5": None,
                    "top5": [],
                }
            )

    query_embedding_ms = sum(
        item["elapsed_ms"]
        for item in embedding_calls
    )

    query_embedding_calls = len(
        embedding_calls
    )

    methods = [
        "bm25",
        "dense",
        "rrf_hybrid",
    ]

    summaries = {
        method: summarize_method(
            rows,
            method,
        )
        for method in methods
    }

    latency = {
        "build": {
            "bm25_index_ms": (
                bm25_build_ms
            ),
            "dense_model_load_ms": (
                model_load_ms
            ),
            "dense_document_embedding_ms": (
                document_embedding_ms
            ),
            "dense_document_embedding_calls": (
                document_embedding_calls
            ),
            "dense_index_only_ms": (
                dense_index_only_ms
            ),
            "dense_total_build_ms": (
                dense_build_total_ms
            ),
        },
        "search": {
            "bm25": latency_summary(
                bm25_latencies
            ),
            "dense": latency_summary(
                dense_latencies
            ),
            "rrf_fusion_only": (
                latency_summary(
                    rrf_fusion_latencies
                )
            ),
            "rrf_end_to_end_serial": (
                latency_summary(
                    rrf_e2e_latencies
                )
            ),
            "dense_query_embedding_total_ms": (
                query_embedding_ms
            ),
            "dense_query_embedding_calls": (
                query_embedding_calls
            ),
        },
        "cold_warm_definition": (
            "cold_first_ms is the first "
            "DEV24 execution for each method; "
            "warm metrics use cases 2-24. "
            "No extra warm-up query was added."
        ),
    }

    config = {
        "experiment_id": (
            "OPS-RAG-SCALE-01"
        ),
        "task_id": (
            "R07-PRE-AI-01"
        ),
        "experiment": "E08",
        "scope": "PRODUCT_ONLY",
        "seed": SEED,
        "source_support": {
            "PRODUCT": "SUPPORTED",
            "POLICY": "MISSING",
            "INVENTORY_SNAPSHOT": (
                "BLOCKED"
            ),
            "INCOMING_STOCK": (
                "MISSING"
            ),
            "C02": "BLOCKED",
        },
        "input": {
            "product_records": 2167,
            "retrieval_documents": (
                len(
                    retrieval_snapshot
                )
            ),
            "snapshot_sha256": (
                SNAPSHOT_SHA256
            ),
            "backend_manifest_sha256": (
                BACKEND_MANIFEST_SHA256
            ),
            "record_version": (
                RECORD_VERSION
            ),
            "dev24_count": 24,
            "dev24_sha256": (
                DEV24_SHA256
            ),
            "human_reviewed": True,
            "final12_used": False,
        },
        "embedding": {
            "model": MODEL_NAME,
            "revision": (
                MODEL_REVISION
            ),
            "device": DEVICE,
            "dimension": dimension,
            "normalized": True,
        },
        "retrieval": {
            "methods": methods,
            "candidate_top_k": (
                CANDIDATE_TOP_K
            ),
            "metric_top_k": (
                METRIC_TOP_K
            ),
            "hybrid_method": "RRF",
            "rrf_k": RRF_K,
            "weighted_hybrid_used": (
                False
            ),
            "query_rewrite_used": False,
            "reranker_used": False,
            "compression_used": False,
            "filter": None,
            "as_of": None,
            "scoring_unit": (
                "source_id+version"
            ),
        },
        "document_projection": {
            "one_product_one_document": (
                True
            ),
            "fields_in_text": [
                "product_name",
                "product_code",
                "custom_product_code",
                "category_nos",
                "is_preorder",
            ],
            "external_category_name_text_added": (
                False
            ),
        },
        "hardware": {
            "platform": (
                platform.platform()
            ),
            "processor": (
                platform.processor()
            ),
            "cpu_count": (
                os.cpu_count()
            ),
        },
    }

    detailed_result = {
        "experiment_id": (
            "OPS-RAG-SCALE-01"
        ),
        "execution": {
            "planned_cases": 72,
            "rows_recorded": len(rows),
            "attempted": sum(
                1
                for row in rows
                if row["status"]
                in {
                    "SUCCEEDED",
                    "ERROR",
                }
            ),
            "succeeded": sum(
                row["status"]
                == "SUCCEEDED"
                for row in rows
            ),
            "error": sum(
                row["status"]
                == "ERROR"
                for row in rows
            ),
            "blocked": sum(
                row["status"]
                == "BLOCKED"
                for row in rows
            ),
            "not_run": sum(
                row["status"]
                == "NOT_RUN"
                for row in rows
            ),
        },
        "denominators": {
            "dev24": 24,
            "answerable": sum(
                row["answerability"]
                == "ANSWERABLE"
                for row in dev
            ),
            "hold": sum(
                row["answerability"]
                == "HOLD"
                for row in dev
            ),
        },
        "summaries": summaries,
        "latency": latency,
        "rows": rows,
    }

    public_summary = {
        "experiment_id": (
            "OPS-RAG-SCALE-01"
        ),
        "task_id": (
            "R07-PRE-AI-01"
        ),
        "experiment": "E08",
        "scope": "PRODUCT_ONLY",
        "product_records": 2167,
        "retrieval_documents": (
            len(
                retrieval_snapshot
            )
        ),
        "dev24": {
            "count": 24,
            "answerable": (
                detailed_result[
                    "denominators"
                ]["answerable"]
            ),
            "hold": (
                detailed_result[
                    "denominators"
                ]["hold"]
            ),
            "human_reviewed": True,
            "sha256": DEV24_SHA256,
        },
        "execution": (
            detailed_result[
                "execution"
            ]
        ),
        "methods": summaries,
        "latency": latency,
        "source_support": (
            config["source_support"]
        ),
        "embedding": (
            config["embedding"]
        ),
        "retrieval_config": (
            config["retrieval"]
        ),
        "input_hashes": {
            "snapshot_sha256": (
                SNAPSHOT_SHA256
            ),
            "backend_manifest_sha256": (
                BACKEND_MANIFEST_SHA256
            ),
        },
        "final12_used": False,
        "raw_private_source_used": False,
    }

    RUN_CONFIG_PATH.write_text(
        json.dumps(
            config,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    PRIVATE_RESULT_PATH.write_text(
        json.dumps(
            detailed_result,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    SUMMARY_PATH.write_text(
        json.dumps(
            public_summary,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        "R07_PRE_E08_EXECUTION_COMPLETE"
    )

    print(
        "PRODUCT_RECORDS=",
        len(products),
    )

    print(
        "RETRIEVAL_DOCUMENTS=",
        len(retrieval_snapshot),
    )

    print(
        "DEV24=",
        len(dev),
    )

    print(
        "EXECUTION_ROWS=",
        len(rows),
    )

    print(
        "SUCCEEDED=",
        detailed_result[
            "execution"
        ]["succeeded"],
    )

    print(
        "ERROR=",
        detailed_result[
            "execution"
        ]["error"],
    )

    print(
        "BLOCKED=",
        detailed_result[
            "execution"
        ]["blocked"],
    )

    for method in methods:
        summary = summaries[method]

        print()
        print(
            "METHOD=",
            method,
        )

        print(
            "RECALL@5=",
            summary[
                "recall_at_5"
            ],
        )

        print(
            "MRR@5=",
            summary[
                "mrr_at_5"
            ],
        )

        print(
            "FULL_EVIDENCE=",
            f"{summary['full_evidence_count']}"
            f"/"
            f"{summary['answerable_denominator']}",
        )

        print(
            "ZERO_RESULT=",
            summary[
                "zero_result_count"
            ],
        )

    print()
    print(
        "CONFIG_PATH=",
        RUN_CONFIG_PATH,
    )

    print(
        "PRIVATE_RESULT_PATH=",
        PRIVATE_RESULT_PATH,
    )

    print(
        "SUMMARY_PATH=",
        SUMMARY_PATH,
    )

    print(
        "FINAL12_USED=false"
    )


if __name__ == "__main__":
    main()