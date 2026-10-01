from __future__ import annotations

import hashlib
import json
import platform
import time
from pathlib import Path
from statistics import mean
from typing import Any

import torch

import ai.evaluation.run_r07_pre_actual_product_retrieval_eval as pre
from ai.retrieval.reranker import (
    LocalCrossEncoderScorer,
    MODEL_LICENSE,
    MODEL_NAME,
    MODEL_REVISION,
    RerankCandidate,
    rerank_candidates,
)

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "artifacts" / "experiments" / "OPS-RAG-02"
CONFIG_PATH = OUTPUT_DIR / "r07_reranker_config.json"
RESULT_PATH = OUTPUT_DIR / "private" / "r07_reranker_result.json"
SUMMARY_PATH = OUTPUT_DIR / "r07_reranker_summary.json"

CANDIDATE_TOP_K = 8
OUTPUT_TOP_K = 5
TIMEOUT_SECONDS = 120.0
MAX_RETRIES = 1
EXPERIMENT_ID = "OPS-RAG-02"
TASK_ID = "R07-AI-01"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def pct(values: list[float], p: float) -> float | None:
    if not values:
        return None
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * p
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    frac = pos - lo
    return xs[lo] + (xs[hi] - xs[lo]) * frac


def latency_summary(values: list[float]) -> dict[str, float | int | None]:
    return {
        "count": len(values),
        "mean_ms": mean(values) if values else None,
        "p95_ms": pct(values, 0.95),
        "min_ms": min(values) if values else None,
        "max_ms": max(values) if values else None,
    }


def metric_direction(before: float, after: float) -> str:
    if after > before:
        return "IMPROVED"
    if after < before:
        return "REGRESSED"
    return "UNCHANGED"


def bool_direction(before: bool, after: bool) -> str:
    if (not before) and after:
        return "IMPROVED"
    if before and (not after):
        return "REGRESSED"
    return "UNCHANGED"


def safe_rerank_result_pairs(results: list[Any], top_k: int) -> list[tuple[str, str]]:
    return [
        (str(r.source_id), str(r.version))
        for r in results[:top_k]
    ]


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)

    products = pre.load_jsonl(pre.PRODUCT_SNAPSHOT)
    dev = pre.load_jsonl(pre.DEV24_PATH)
    pre.validate_inputs(products, dev)

    retrieval_snapshot = pre.build_retrieval_snapshot(products)
    if len(retrieval_snapshot) != 2167:
        raise RuntimeError(
            f"retrieval document count mismatch: {len(retrieval_snapshot)}"
        )

    docs = {
        (str(d["source_id"]), str(d["version"])): d
        for d in retrieval_snapshot
    }

    bm25_started = time.perf_counter()
    bm25 = pre.BM25Index(pre.snapshot_to_documents(retrieval_snapshot))
    bm25_build_ms = (time.perf_counter() - bm25_started) * 1000.0

    model_started = time.perf_counter()
    scorer = LocalCrossEncoderScorer(device="cpu")
    model_load_ms = (time.perf_counter() - model_started) * 1000.0

    rows: list[dict[str, Any]] = []
    search_latencies: list[float] = []
    rerank_latencies: list[float] = []
    e2e_latencies: list[float] = []

    timeout_count = 0
    retry_count = 0
    fallback_count = 0

    before_recall_values: list[float] = []
    after_recall_values: list[float] = []
    before_mrr_values: list[float] = []
    after_mrr_values: list[float] = []
    before_full_count = 0
    after_full_count = 0

    recall_changes = {"IMPROVED": 0, "REGRESSED": 0, "UNCHANGED": 0}
    mrr_changes = {"IMPROVED": 0, "REGRESSED": 0, "UNCHANGED": 0}
    full_changes = {"IMPROVED": 0, "REGRESSED": 0, "UNCHANGED": 0}

    candidate_miss_cases: list[str] = []

    for case in dev:
        case_id = str(case["case_id"])
        query = str(case["query"])
        required = pre.evidence_set(case)

        search_started = time.perf_counter()
        bm25_results = bm25.search(query, top_k=CANDIDATE_TOP_K)
        search_ms = (time.perf_counter() - search_started) * 1000.0
        search_latencies.append(search_ms)

        candidate_pairs = set(pre.result_pairs(bm25_results, CANDIDATE_TOP_K))
        full_gold_in_top8 = required.issubset(candidate_pairs)
        matched_top8 = len(required & candidate_pairs)
        if not full_gold_in_top8:
            candidate_miss_cases.append(case_id)

        candidates: list[RerankCandidate] = []
        for result in bm25_results:
            key = (str(result.source_id), str(result.version))
            document = docs[key]
            candidates.append(
                RerankCandidate(
                    original_rank=int(result.rank),
                    source_id=str(result.source_id),
                    source_type=str(result.source_type),
                    version=str(result.version),
                    text=str(document["text"]),
                    metadata=dict(document.get("metadata", {})),
                )
            )

        e2e_started = time.perf_counter()
        reranked = rerank_candidates(
            query,
            candidates,
            scorer=scorer,
            candidate_top_k=CANDIDATE_TOP_K,
            output_top_k=OUTPUT_TOP_K,
            timeout_seconds=TIMEOUT_SECONDS,
            max_retries=MAX_RETRIES,
        )
        e2e_ms = search_ms + reranked.trace.latency_ms
        _ = (time.perf_counter() - e2e_started) * 1000.0

        rerank_latencies.append(reranked.trace.latency_ms)
        e2e_latencies.append(e2e_ms)
        timeout_count += reranked.trace.timeout_count
        retry_count += reranked.trace.retry_count
        fallback_count += reranked.trace.fallback_count

        reranked_results = list(reranked.results)

        before_recall = pre.recall_at_5(bm25_results, required)
        after_recall = pre.recall_at_5(reranked_results, required)
        before_mrr = pre.mrr_at_5(bm25_results, required)
        after_mrr = pre.mrr_at_5(reranked_results, required)
        before_full = pre.full_evidence_at_5(bm25_results, required)
        after_full = pre.full_evidence_at_5(reranked_results, required)

        before_recall_values.append(before_recall)
        after_recall_values.append(after_recall)
        before_mrr_values.append(before_mrr)
        after_mrr_values.append(after_mrr)
        before_full_count += int(before_full)
        after_full_count += int(after_full)

        recall_dir = metric_direction(before_recall, after_recall)
        mrr_dir = metric_direction(before_mrr, after_mrr)
        full_dir = bool_direction(before_full, after_full)
        recall_changes[recall_dir] += 1
        mrr_changes[mrr_dir] += 1
        full_changes[full_dir] += 1

        rows.append(
            {
                "case_id": case_id,
                "case_group": case.get("case_group"),
                "answerability": case.get("answerability"),
                "required_count": len(required),
                "candidate_count": len(candidates),
                "matched_top8": matched_top8,
                "full_gold_in_top8": full_gold_in_top8,
                "before": {
                    "recall_at_5": before_recall,
                    "mrr_at_5": before_mrr,
                    "full_evidence_at_5": before_full,
                    "top5": [
                        {
                            "rank": int(r.rank),
                            "score": float(r.score),
                            "source_id": str(r.source_id),
                            "version": str(r.version),
                        }
                        for r in bm25_results[:OUTPUT_TOP_K]
                    ],
                },
                "after": {
                    "recall_at_5": after_recall,
                    "mrr_at_5": after_mrr,
                    "full_evidence_at_5": after_full,
                    "top5": [
                        {
                            "rank": int(r.rank),
                            "original_rank": int(r.original_rank),
                            "rerank_score": (
                                None
                                if r.rerank_score is None
                                else float(r.rerank_score)
                            ),
                            "source_id": str(r.source_id),
                            "version": str(r.version),
                            "fallback": bool(r.fallback),
                        }
                        for r in reranked_results[:OUTPUT_TOP_K]
                    ],
                },
                "change": {
                    "recall_at_5": recall_dir,
                    "mrr_at_5": mrr_dir,
                    "full_evidence_at_5": full_dir,
                },
                "latency_ms": {
                    "bm25_search": search_ms,
                    "reranker": reranked.trace.latency_ms,
                    "e2e_search_plus_rerank": e2e_ms,
                },
                "reranker_trace": {
                    "status": reranked.trace.status,
                    "timeout_count": reranked.trace.timeout_count,
                    "retry_count": reranked.trace.retry_count,
                    "fallback_count": reranked.trace.fallback_count,
                },
            }
        )

    before = {
        "recall_at_5": mean(before_recall_values),
        "mrr_at_5": mean(before_mrr_values),
        "full_evidence_count": before_full_count,
        "full_evidence_rate": before_full_count / len(dev),
    }
    after = {
        "recall_at_5": mean(after_recall_values),
        "mrr_at_5": mean(after_mrr_values),
        "full_evidence_count": after_full_count,
        "full_evidence_rate": after_full_count / len(dev),
    }

    result = {
        "task_id": TASK_ID,
        "experiment_id": EXPERIMENT_ID,
        "scope": "PRODUCT_ONLY",
        "execution": {
            "case_count": len(dev),
            "product_records": len(products),
            "retrieval_documents": len(retrieval_snapshot),
        },
        "rows": rows,
        "summary": {
            "before": before,
            "after": after,
            "delta": {
                "recall_at_5": after["recall_at_5"] - before["recall_at_5"],
                "mrr_at_5": after["mrr_at_5"] - before["mrr_at_5"],
                "full_evidence_count": (
                    after["full_evidence_count"] - before["full_evidence_count"]
                ),
            },
            "per_metric_change_counts": {
                "recall_at_5": recall_changes,
                "mrr_at_5": mrr_changes,
                "full_evidence_at_5": full_changes,
            },
            "candidate_miss": {
                "count": len(candidate_miss_cases),
                "case_ids": candidate_miss_cases,
            },
            "latency": {
                "bm25_build_ms": bm25_build_ms,
                "reranker_model_load_ms": model_load_ms,
                "bm25_search": latency_summary(search_latencies),
                "reranker": latency_summary(rerank_latencies),
                "e2e_search_plus_rerank": latency_summary(e2e_latencies),
            },
            "reranker_events": {
                "timeout_count": timeout_count,
                "retry_count": retry_count,
                "fallback_count": fallback_count,
            },
        },
    }

    config = {
        "task_id": TASK_ID,
        "experiment_id": EXPERIMENT_ID,
        "scope": "PRODUCT_ONLY",
        "input": {
            "product_snapshot": str(pre.PRODUCT_SNAPSHOT),
            "product_snapshot_sha256": sha256_file(pre.PRODUCT_SNAPSHOT),
            "dev24": str(pre.DEV24_PATH),
            "dev24_sha256": sha256_file(pre.DEV24_PATH),
            "product_records": len(products),
            "retrieval_documents": len(retrieval_snapshot),
            "final12_used": False,
        },
        "retrieval": {
            "baseline": "bm25",
            "candidate_top_k": CANDIDATE_TOP_K,
            "metric_top_k": OUTPUT_TOP_K,
            "filter": None,
            "as_of": None,
            "same_candidate_set_before_after": True,
        },
        "reranker": {
            "model": MODEL_NAME,
            "revision": MODEL_REVISION,
            "license": MODEL_LICENSE,
            "execution": "LOCAL",
            "device": "cpu",
            "candidate_top_k": CANDIDATE_TOP_K,
            "output_top_k": OUTPUT_TOP_K,
            "timeout_seconds": TIMEOUT_SECONDS,
            "max_retries": MAX_RETRIES,
        },
        "runtime": {
            "python_platform": platform.platform(),
            "torch_version": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
        },
    }

    summary = {
        "task_id": TASK_ID,
        "experiment_id": EXPERIMENT_ID,
        "input_hashes": {
            "product_snapshot_sha256": config["input"]["product_snapshot_sha256"],
            "dev24_sha256": config["input"]["dev24_sha256"],
        },
        "before": before,
        "after": after,
        "delta": result["summary"]["delta"],
        "per_metric_change_counts": result["summary"]["per_metric_change_counts"],
        "candidate_miss": result["summary"]["candidate_miss"],
        "latency": result["summary"]["latency"],
        "reranker_events": result["summary"]["reranker_events"],
        "model": config["reranker"],
        "final12_used": False,
    }

    CONFIG_PATH.write_text(
        json.dumps(config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    RESULT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("R07_RERANKER_EVAL_OK")
    print("CONFIG=", CONFIG_PATH)
    print("RESULT=", RESULT_PATH)
    print("SUMMARY=", SUMMARY_PATH)
    print("BEFORE_RECALL_AT_5=", round(before["recall_at_5"], 6))
    print("AFTER_RECALL_AT_5=", round(after["recall_at_5"], 6))
    print("BEFORE_MRR_AT_5=", round(before["mrr_at_5"], 6))
    print("AFTER_MRR_AT_5=", round(after["mrr_at_5"], 6))
    print("BEFORE_FULL=", f"{before_full_count}/{len(dev)}")
    print("AFTER_FULL=", f"{after_full_count}/{len(dev)}")
    print("CANDIDATE_MISS=", len(candidate_miss_cases))
    print("RECALL_CHANGE_COUNTS=", recall_changes)
    print("MRR_CHANGE_COUNTS=", mrr_changes)
    print("FULL_CHANGE_COUNTS=", full_changes)
    print("RERANK_MEAN_MS=", round(mean(rerank_latencies), 3))
    print("E2E_MEAN_MS=", round(mean(e2e_latencies), 3))
    print("TIMEOUT_COUNT=", timeout_count)
    print("RETRY_COUNT=", retry_count)
    print("FALLBACK_COUNT=", fallback_count)


if __name__ == "__main__":
    main()
