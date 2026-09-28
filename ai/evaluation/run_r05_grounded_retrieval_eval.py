from __future__ import annotations

import json
import statistics
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer

from ai.evaluation.run_day09_golden_hybrid_eval import snapshot_to_documents, snapshot_to_dense_documents
from ai.evaluation.run_retrieval_eval import collapse_results_by_source, prefer_fresh_versioned_results
from ai.retrieval.bm25 import BM25Index
from ai.retrieval.dense import DenseIndex
from ai.retrieval.freshness import load_freshness_policy, build_version_catalog
from ai.retrieval.hybrid import reciprocal_rank_fusion

SNAPSHOT_PATH = Path(r"artifacts/experiments/OPS-RAG-01/r05_grounded_snapshot_v2.jsonl")
SNAPSHOT_MANIFEST_PATH = Path(r"artifacts/experiments/OPS-RAG-01/r05_grounded_snapshot_manifest_v2.json")
DEV_PATH = Path(r"ai/evaluation/datasets/grounded_eval_dev.jsonl")
CONFIG_PATH = Path(r"artifacts/experiments/OPS-RAG-01/r05_run_config.json")
OUTPUT_PATH = Path(r"artifacts/experiments/OPS-RAG-01/r05_retrieval_result.json")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def recall_at_5(results: list[Any], required: set[tuple[str, str]]) -> float:
    found = {(str(x.source_id), str(x.version)) for x in results[:5]}
    return len(found & required) / len(required) if required else 0.0


def reciprocal_rank_at_5(results: list[Any], required: set[tuple[str, str]]) -> float:
    for rank, x in enumerate(results[:5], start=1):
        if (str(x.source_id), str(x.version)) in required:
            return 1.0 / rank
    return 0.0


def serialize(results: list[Any]) -> list[dict[str, Any]]:
    return [{"rank": i, "source_id": str(x.source_id), "version": str(x.version), "chunk_id": str(x.chunk_id), "score": float(x.score)} for i, x in enumerate(results[:5], start=1)]


def p95(values: list[float]) -> float:
    if not values:
        return 0.0
    vals = sorted(values)
    idx = max(0, min(len(vals) - 1, int(np.ceil(0.95 * len(vals))) - 1))
    return vals[idx]


def main() -> None:
    snapshot = load_jsonl(SNAPSHOT_PATH)
    dev = load_jsonl(DEV_PATH)
    manifest = json.loads(SNAPSHOT_MANIFEST_PATH.read_text(encoding="utf-8"))
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    evaluation_as_of = datetime.fromisoformat(config["freshness"]["evaluation_as_of"].replace("Z", "+00:00"))
    freshness_policy = load_freshness_policy()
    version_catalog = build_version_catalog(snapshot)
    bm25_docs = snapshot_to_documents(snapshot)
    dense_docs = snapshot_to_dense_documents(snapshot)

    t0 = time.perf_counter()
    bm25 = BM25Index(bm25_docs)
    bm25_build_ms = (time.perf_counter() - t0) * 1000.0

    emb = manifest["embedding"]
    t0 = time.perf_counter()
    model = SentenceTransformer(emb["model"], revision=emb["revision"], device="cpu")
    def embed_texts(texts: list[str]) -> np.ndarray:
        return np.asarray(model.encode(texts, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False), dtype=np.float32)
    dense = DenseIndex(dense_docs, embed_texts=embed_texts)
    dense_build_ms = (time.perf_counter() - t0) * 1000.0

    candidate_top_k = int(config["retrieval"]["candidate_top_k"])
    rrf_k = int(config["retrieval"]["rrf_k"])
    rows = []
    latencies = {"bm25": [], "dense": [], "rrf_hybrid": []}

    for case in dev:
        q = str(case["query"])

        started = time.perf_counter()
        b = bm25.search(q, top_k=bm25.document_count)
        b = prefer_fresh_versioned_results(b, freshness_policy=freshness_policy, version_catalog=version_catalog, now=evaluation_as_of)
        b = collapse_results_by_source(b)[:candidate_top_k]
        b_ms = (time.perf_counter() - started) * 1000.0

        started = time.perf_counter()
        d = dense.search(q, top_k=dense.document_count)
        d = prefer_fresh_versioned_results(d, freshness_policy=freshness_policy, version_catalog=version_catalog, now=evaluation_as_of)
        d = collapse_results_by_source(d)[:candidate_top_k]
        d_ms = (time.perf_counter() - started) * 1000.0

        started = time.perf_counter()
        h = reciprocal_rank_fusion(b, d, candidate_top_k=candidate_top_k, rrf_k=rrf_k)
        fusion_ms = (time.perf_counter() - started) * 1000.0
        h_ms = b_ms + d_ms + fusion_ms

        latencies["bm25"].append(b_ms)
        latencies["dense"].append(d_ms)
        latencies["rrf_hybrid"].append(h_ms)

        required = {(str(e["source_id"]), str(e["version"])) for e in case.get("evidence", [])}
        answerable = case["answerability"] == "ANSWERABLE"
        method_results = {"bm25": b, "dense": d, "rrf_hybrid": h}
        method_latencies = {"bm25": b_ms, "dense": d_ms, "rrf_hybrid": h_ms}

        for method, result in method_results.items():
            rows.append({"case_id": case["case_id"], "category": case["category"], "answerability": case["answerability"], "hold_reason": case.get("hold_reason"), "method": method, "executed": True, "latency_ms": method_latencies[method], "error": None, "required_evidence": sorted([{"source_id": s, "version": v} for s, v in required], key=lambda x: (x["source_id"], x["version"])), "recall_at_5": recall_at_5(result, required) if answerable else None, "mrr_at_5": reciprocal_rank_at_5(result, required) if answerable else None, "top5": serialize(result)})

    answerable_rows = [x for x in rows if x["answerability"] == "ANSWERABLE"]
    summaries = {}
    for method in ("bm25", "dense", "rrf_hybrid"):
        rs = [x for x in answerable_rows if x["method"] == method]
        recalls = [float(x["recall_at_5"]) for x in rs]
        mrrs = [float(x["mrr_at_5"]) for x in rs]
        full = sum(1 for x in rs if x["recall_at_5"] == 1.0)
        lv = latencies[method]
        summaries[method] = {"answerable_cases": len(rs), "mean_recall_at_5": statistics.fmean(recalls), "mean_mrr_at_5": statistics.fmean(mrrs), "full_evidence_cases": full, "mean_latency_ms": statistics.fmean(lv), "p95_latency_ms": p95(lv)}

    result = {"experiment_id": "OPS-RAG-01-R05", "dev_selection": config.get("dev_selection"), "execution_count": len(rows), "query_count": len(dev), "answerable_query_count": sum(1 for x in dev if x["answerability"] == "ANSWERABLE"), "hold_query_count": sum(1 for x in dev if x["answerability"] == "HOLD"), "hold_behavior_evaluated": False, "evaluation_as_of": config["freshness"]["evaluation_as_of"], "build_latency_ms": {"bm25": bm25_build_ms, "dense_with_embeddings": dense_build_ms}, "summaries": summaries, "rows": rows}
    OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print("R05_RETRIEVAL_EVAL_OK")
    print("QUERY_COUNT=", len(dev))
    print("EXECUTION_COUNT=", len(rows))
    print("ANSWERABLE=", result["answerable_query_count"])
    print("HOLD=", result["hold_query_count"])
    for method, summary in summaries.items():
        print(method.upper(), "RECALL@5=", round(summary["mean_recall_at_5"], 4), "MRR@5=", round(summary["mean_mrr_at_5"], 4), "FULL=", summary["full_evidence_cases"], "MEAN_MS=", round(summary["mean_latency_ms"], 3), "P95_MS=", round(summary["p95_latency_ms"], 3))
    print("OUTPUT=", OUTPUT_PATH)


if __name__ == "__main__":
    main()
