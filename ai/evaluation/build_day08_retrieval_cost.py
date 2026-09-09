from __future__ import annotations

import csv
import json
from pathlib import Path


BM25_PATH = Path(
    "artifacts/experiments/RAG-01/"
    "bm25_result.json"
)

DENSE_PATH = Path(
    "artifacts/experiments/RAG-01/"
    "dense_result.json"
)

OUTPUT_PATH = Path(
    "artifacts/integration/day08/"
    "retrieval_cost.csv"
)


def load_json(
    path: Path,
) -> dict:
    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def main() -> int:
    bm25 = load_json(BM25_PATH)
    dense = load_json(DENSE_PATH)

    bm25_latency = bm25["latency"]
    bm25_cost = bm25["cost"]
    bm25_index = bm25["index"]
    bm25_dataset = bm25["dataset"]

    dense_latency = dense["latency"]
    dense_cost = dense["cost"]
    dense_index = dense["index"]
    dense_dataset = dense["dataset"]
    dense_embedding = dense["embedding"]

    rows = [
        {
            "method": "BM25",
            "source_classification": "FIXTURE",
            "document_count": (
                bm25_index["document_count"]
            ),
            "query_count": (
                bm25_dataset["query_count"]
            ),
            "index_version": (
                bm25_index["version"]
            ),
            "index_build_ms": (
                bm25_latency["index_build_ms"]
            ),
            "cold_build_ms": "",
            "warm_build_ms": "",
            "query_mean_ms": (
                bm25_latency["query_mean_ms"]
            ),
            "query_p50_ms": (
                bm25_latency["query_p50_ms"]
            ),
            "query_p95_ms": (
                bm25_latency["query_p95_ms"]
            ),
            "embedding_api_calls": (
                bm25_cost[
                    "embedding_api_calls"
                ]
            ),
            "llm_api_calls": (
                bm25_cost["llm_api_calls"]
            ),
            "api_cost_usd": (
                bm25_cost["api_cost_usd"]
            ),
            "gpu_used": (
                bm25_cost["gpu_used"]
            ),
            "local_cpu_embedding": False,
            "embedding_model": "",
            "embedding_revision": "",
            "measured_on_cafe24_2167": False,
        },
        {
            "method": "VECTOR",
            "source_classification": "FIXTURE",
            "document_count": (
                dense_index["document_count"]
            ),
            "query_count": (
                dense_dataset["query_count"]
            ),
            "index_version": (
                dense_index["version"]
            ),
            "index_build_ms": "",
            "cold_build_ms": (
                dense_latency["cold_build_ms"]
            ),
            "warm_build_ms": (
                dense_latency["warm_build_ms"]
            ),
            "query_mean_ms": (
                dense_latency["query_mean_ms"]
            ),
            "query_p50_ms": (
                dense_latency["query_p50_ms"]
            ),
            "query_p95_ms": (
                dense_latency["query_p95_ms"]
            ),
            "embedding_api_calls": (
                dense_cost[
                    "embedding_api_calls"
                ]
            ),
            "llm_api_calls": (
                dense_cost["llm_api_calls"]
            ),
            "api_cost_usd": (
                dense_cost["api_cost_usd"]
            ),
            "gpu_used": (
                dense_cost["gpu_used"]
            ),
            "local_cpu_embedding": (
                dense_cost[
                    "local_cpu_embedding"
                ]
            ),
            "embedding_model": (
                dense_embedding["model"]
            ),
            "embedding_revision": (
                dense_embedding["revision"]
            ),
            "measured_on_cafe24_2167": False,
        },
    ]

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_PATH.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=list(
                rows[0].keys()
            ),
        )

        writer.writeheader()
        writer.writerows(rows)

    print("RETRIEVAL_COST_OK")
    print(f"PATH={OUTPUT_PATH}")
    print(
        f"BM25_P50_MS="
        f"{bm25_latency['query_p50_ms']}"
    )
    print(
        f"BM25_P95_MS="
        f"{bm25_latency['query_p95_ms']}"
    )
    print(
        f"VECTOR_P50_MS="
        f"{dense_latency['query_p50_ms']}"
    )
    print(
        f"VECTOR_P95_MS="
        f"{dense_latency['query_p95_ms']}"
    )
    print(
        "BM25_API_COST_USD="
        f"{bm25_cost['api_cost_usd']}"
    )
    print(
        "VECTOR_API_COST_USD="
        f"{dense_cost['api_cost_usd']}"
    )
    print(
        "CAFE24_2167_MEASURED=False"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())