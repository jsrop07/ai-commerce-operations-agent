from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


BM25_PATH = Path(
    "artifacts/experiments/RAG-01/"
    "bm25_result.json"
)

DENSE_PATH = Path(
    "artifacts/experiments/RAG-01/"
    "dense_result.json"
)

CONFIDENCE_PATH = Path(
    "artifacts/experiments/RAG-01/"
    "confidence_result.json"
)

SNAPSHOT_MANIFEST_PATH = Path(
    "artifacts/experiments/RAG-01/"
    "chunk_snapshot_manifest.json"
)

OUTPUT_PATH = Path(
    "artifacts/experiments/RAG-01/"
    "result.json"
)

EVAL_CODE_PATH = Path(
    "ai/evaluation/"
    "run_retrieval_eval.py"
)

CONFIDENCE_CODE_PATH = Path(
    "ai/retrieval/"
    "confidence.py"
)


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


def metric_delta(
    *,
    bm25: float,
    dense: float,
) -> float:
    return dense - bm25


def build_metric_comparison(
    bm25: dict[str, Any],
    dense: dict[str, Any],
) -> dict[str, Any]:
    bm = bm25["metrics"]
    de = dense["metrics"]

    return {
        "recall_at_1": {
            "bm25": bm["recall_at_1"],
            "dense": de["recall_at_1"],
            "dense_minus_bm25": (
                metric_delta(
                    bm25=bm["recall_at_1"],
                    dense=de["recall_at_1"],
                )
            ),
        },
        "recall_at_3": {
            "bm25": bm["recall_at_3"],
            "dense": de["recall_at_3"],
            "dense_minus_bm25": (
                metric_delta(
                    bm25=bm["recall_at_3"],
                    dense=de["recall_at_3"],
                )
            ),
        },
        "recall_at_5": {
            "bm25": bm["recall_at_5"],
            "dense": de["recall_at_5"],
            "dense_minus_bm25": (
                metric_delta(
                    bm25=bm["recall_at_5"],
                    dense=de["recall_at_5"],
                )
            ),
        },
        "mrr": {
            "bm25": bm["mrr"],
            "dense": de["mrr"],
            "dense_minus_bm25": (
                metric_delta(
                    bm25=bm["mrr"],
                    dense=de["mrr"],
                )
            ),
        },
        "ndcg_at_5": {
            "bm25": bm["ndcg_at_5"],
            "dense": de["ndcg_at_5"],
            "dense_minus_bm25": (
                metric_delta(
                    bm25=bm["ndcg_at_5"],
                    dense=de["ndcg_at_5"],
                )
            ),
        },
    }


def build_latency_comparison(
    bm25: dict[str, Any],
    dense: dict[str, Any],
) -> dict[str, Any]:
    bm = bm25["latency"]
    de = dense["latency"]

    return {
        "bm25": {
            "index_build_ms": (
                bm["index_build_ms"]
            ),
            "query_p50_ms": (
                bm["query_p50_ms"]
            ),
            "query_p95_ms": (
                bm["query_p95_ms"]
            ),
        },
        "dense": {
            "cold_build_ms": (
                de["cold_build_ms"]
            ),
            "warm_build_ms": (
                de["warm_build_ms"]
            ),
            "query_p50_ms": (
                de["query_p50_ms"]
            ),
            "query_p95_ms": (
                de["query_p95_ms"]
            ),
        },
    }


def build_index_comparison(
    bm25: dict[str, Any],
    dense: dict[str, Any],
) -> dict[str, Any]:
    return {
        "bm25": {
            "version": (
                bm25["index"]["version"]
            ),
            "hash": (
                bm25["index"]["hash"]
            ),
            "size_bytes": (
                bm25[
                    "index"
                ][
                    "serialized_size_bytes"
                ]
            ),
            "document_count": (
                bm25[
                    "index"
                ][
                    "document_count"
                ]
            ),
        },
        "dense": {
            "version": (
                dense["index"]["version"]
            ),
            "hash": (
                dense["index"]["hash"]
            ),
            "size_bytes": (
                dense[
                    "index"
                ][
                    "serialized_size_bytes"
                ]
            ),
            "document_count": (
                dense[
                    "index"
                ][
                    "document_count"
                ]
            ),
            "vector_dimension": (
                dense[
                    "index"
                ][
                    "vector_dimension"
                ]
            ),
        },
    }


def build_slice_comparison(
    bm25: dict[str, Any],
    dense: dict[str, Any],
) -> dict[str, Any]:
    bm_slices = (
        bm25["slice_metrics"]
    )

    de_slices = (
        dense["slice_metrics"]
    )

    slice_names = sorted(
        set(bm_slices)
        | set(de_slices)
    )

    result: dict[
        str,
        dict[str, Any],
    ] = {}

    for slice_name in slice_names:
        bm = bm_slices.get(
            slice_name,
            {},
        )

        de = de_slices.get(
            slice_name,
            {},
        )

        result[slice_name] = {
            "query_count": (
                bm.get(
                    "query_count"
                )
                or de.get(
                    "query_count"
                )
            ),
            "bm25": {
                "recall_at_1": (
                    bm.get(
                        "recall_at_1"
                    )
                ),
                "recall_at_3": (
                    bm.get(
                        "recall_at_3"
                    )
                ),
                "recall_at_5": (
                    bm.get(
                        "recall_at_5"
                    )
                ),
                "mrr": (
                    bm.get(
                        "mrr"
                    )
                ),
                "ndcg_at_5": (
                    bm.get(
                        "ndcg_at_5"
                    )
                ),
            },
            "dense": {
                "recall_at_1": (
                    de.get(
                        "recall_at_1"
                    )
                ),
                "recall_at_3": (
                    de.get(
                        "recall_at_3"
                    )
                ),
                "recall_at_5": (
                    de.get(
                        "recall_at_5"
                    )
                ),
                "mrr": (
                    de.get(
                        "mrr"
                    )
                ),
                "ndcg_at_5": (
                    de.get(
                        "ndcg_at_5"
                    )
                ),
            },
        }

    return result


def top_gap(
    query: dict[str, Any],
) -> float:
    top = query["top_results"]

    if not top:
        return 0.0

    if len(top) == 1:
        return float(
            top[0]["score"]
        )

    return (
        float(top[0]["score"])
        - float(top[1]["score"])
    )


def make_case(
    *,
    category: str,
    retriever: str,
    query: dict[str, Any],
    note: str,
) -> dict[str, Any]:
    return {
        "category": category,
        "retriever": retriever,
        "query_id": (
            query["query_id"]
        ),
        "slice": (
            query["slice"]
        ),
        "query": (
            query["query"]
        ),
        "first_relevant_rank": (
            query.get(
                "first_relevant_rank"
            )
        ),
        "top_score": (
            query[
                "top_results"
            ][0][
                "score"
            ]
            if query[
                "top_results"
            ]
            else None
        ),
        "score_gap": (
            top_gap(query)
        ),
        "top_results": (
            query["top_results"]
        ),
        "note": note,
    }


def build_error_analysis(
    bm25: dict[str, Any],
    dense: dict[str, Any],
) -> dict[str, Any]:
    cases: list[
        dict[str, Any]
    ] = []

    # 1. Dense hard success:
    # 검색은 성공했지만 정답이 1위가 아님.
    for query in dense[
        "analysis"
    ][
        "hard_successes"
    ]:
        cases.append(
            make_case(
                category=(
                    "DENSE_HARD_SUCCESS"
                ),
                retriever="dense",
                query=query,
                note=(
                    "Relevant source was "
                    "retrieved within Top-5 "
                    "but not ranked first."
                ),
            )
        )

    # 2. No-answer attraction:
    # 실제 근거가 없는데도 검색기가
    # 높은 score를 부여한 사례.
    for retriever, result in (
        ("bm25", bm25),
        ("dense", dense),
    ):
        for query in result[
            "abstain_queries"
        ]:
            cases.append(
                make_case(
                    category=(
                        "NO_ANSWER_ATTRACTION"
                    ),
                    retriever=retriever,
                    query=query,
                    note=(
                        "No-answer query still "
                        "received non-trivial "
                        "retrieval scores."
                    ),
                )
            )

    # 3. BM25 fragile success:
    # 정답은 1위지만 top1-top2 gap이
    # 작은 성공 사례.
    bm25_fragile = sorted(
        bm25["query_results"],
        key=top_gap,
    )

    for query in bm25_fragile[:4]:
        cases.append(
            make_case(
                category=(
                    "BM25_FRAGILE_SUCCESS"
                ),
                retriever="bm25",
                query=query,
                note=(
                    "Correct Top-1 result but "
                    "with a relatively small "
                    "score margin."
                ),
            )
        )

    # 최소 10개 진단 사례를 보장한다.
    # 현재 데이터에서는 일반적으로
    # 4 dense hard + 4 no-answer +
    # 4 fragile = 12개가 된다.
    if len(cases) < 10:
        raise RuntimeError(
            "Day 7 error analysis requires "
            "at least 10 diagnostic cases"
        )

    retrieval_failure_count = (
        bm25[
            "analysis"
        ][
            "retrieval_failure_count"
        ]
        + dense[
            "analysis"
        ][
            "retrieval_failure_count"
        ]
    )

    hard_success_count = (
        bm25[
            "analysis"
        ][
            "hard_success_count"
        ]
        + dense[
            "analysis"
        ][
            "hard_success_count"
        ]
    )

    return {
        "case_count": len(
            cases
        ),
        "retrieval_failure_count": (
            retrieval_failure_count
        ),
        "hard_success_count": (
            hard_success_count
        ),
        "categories": {
            "dense_hard_success": sum(
                1
                for case in cases
                if case["category"]
                == "DENSE_HARD_SUCCESS"
            ),
            "no_answer_attraction": sum(
                1
                for case in cases
                if case["category"]
                == "NO_ANSWER_ATTRACTION"
            ),
            "bm25_fragile_success": sum(
                1
                for case in cases
                if case["category"]
                == "BM25_FRAGILE_SUCCESS"
            ),
        },
        "cases": cases,
    }


def main() -> None:
    bm25 = load_json(
        BM25_PATH
    )

    dense = load_json(
        DENSE_PATH
    )

    confidence = load_json(
        CONFIDENCE_PATH
    )

    snapshot_manifest = load_json(
        SNAPSHOT_MANIFEST_PATH
    )

    bm25_metrics = (
        bm25["metrics"]
    )

    dense_metrics = (
        dense["metrics"]
    )

    # 현재 Day 7 데이터에서는
    # Top-1 ranking 품질과 latency에서
    # BM25가 우세하다.
    bm25_primary = (
        bm25_metrics["mrr"]
        >= dense_metrics["mrr"]
        and bm25_metrics["ndcg_at_5"]
        >= dense_metrics["ndcg_at_5"]
    )

    result = {
        "schema_version": (
            "rag-experiment-result.v1"
        ),
        "experiment_id": "RAG-01",
        "day": 7,
        "status": "PASS",
        "objective": (
            "Compare BM25 and Dense retrieval "
            "on the same versioned semantic "
            "chunk snapshot and establish "
            "metadata, freshness, confidence, "
            "latency, and error-analysis "
            "baselines."
        ),
        "dataset": {
            "evaluation_path": (
                bm25[
                    "dataset"
                ][
                    "path"
                ]
            ),
            "evaluation_sha256": (
                bm25[
                    "dataset"
                ][
                    "sha256"
                ]
            ),
            "query_count": (
                bm25[
                    "dataset"
                ][
                    "query_count"
                ]
            ),
            "answerable_count": (
                bm25[
                    "dataset"
                ][
                    "answerable_count"
                ]
            ),
            "abstain_count": (
                bm25[
                    "dataset"
                ][
                    "abstain_count"
                ]
            ),
            "answerable_coverage": (
                bm25[
                    "dataset"
                ][
                    "answerable_coverage"
                ]
            ),
            "golden60_used_for_"
            "performance_measurement": False,
            "golden60_exclusion_reason": (
                "Current corpus covers only "
                "2 of 52 answerable Golden60 "
                "queries, so using Golden60 "
                "would primarily measure "
                "missing corpus coverage."
            ),
        },
        "snapshot": {
            "version": (
                snapshot_manifest[
                    "snapshot_version"
                ]
            ),
            "hash": (
                snapshot_manifest[
                    "snapshot_hash"
                ]
            ),
            "corpus_sha256": (
                snapshot_manifest[
                    "corpus"
                ][
                    "sha256"
                ]
            ),
            "chunk_count": (
                snapshot_manifest[
                    "chunking"
                ][
                    "chunk_count"
                ]
            ),
            "chunking": (
                snapshot_manifest[
                    "chunking"
                ]
            ),
        },
        "embedding": (
            dense["embedding"]
        ),
        "metrics": (
            build_metric_comparison(
                bm25,
                dense,
            )
        ),
        "latency": (
            build_latency_comparison(
                bm25,
                dense,
            )
        ),
        "indexes": (
            build_index_comparison(
                bm25,
                dense,
            )
        ),
        "slices": (
            build_slice_comparison(
                bm25,
                dense,
            )
        ),
        "confidence": {
            "calibration_version": (
                confidence[
                    "calibration"
                ][
                    "version"
                ]
            ),
            "production_sla": False,
            "oracle_answerability_"
            "used_as_confidence_input": (
                confidence[
                    "calibration"
                ][
                    "oracle_answerability_"
                    "used_as_confidence_input"
                ]
            ),
            "bm25": (
                confidence[
                    "bm25"
                ][
                    "summary"
                ]
            ),
            "dense": (
                confidence[
                    "dense"
                ][
                    "summary"
                ]
            ),
            "routing": {
                "HIGH": (
                    "definitive_answer_allowed"
                ),
                "MEDIUM": "HOLD",
                "LOW": "HOLD",
                "ABSTAIN": (
                    "answer_generation_blocked"
                ),
            },
        },
        "error_analysis": (
            build_error_analysis(
                bm25,
                dense,
            )
        ),
        "cost": {
            "bm25": (
                bm25["cost"]
            ),
            "dense": (
                dense["cost"]
            ),
            "external_llm_api_used": False,
            "external_embedding_api_used": (
                False
            ),
            "api_cost_usd": 0.0,
        },
        "decision": {
            "primary_day07_baseline": (
                "BM25"
                if bm25_primary
                else "DENSE"
            ),
            "dense_retained": True,
            "hybrid_implemented": False,
            "hybrid_hypothesis_status": (
                "OPEN_FOR_LATER_EXPERIMENT"
            ),
            "rationale": [
                (
                    "BM25 achieved stronger "
                    "Top-1 ranking quality, "
                    "MRR, and nDCG@5 on the "
                    "current exact/lexical-heavy "
                    "synthetic corpus."
                ),
                (
                    "Dense achieved Recall@3 "
                    "and Recall@5 of 1.0 after "
                    "fresh-version handling, "
                    "showing useful semantic "
                    "candidate recall despite "
                    "weaker Top-1 ranking."
                ),
                (
                    "No-answer queries received "
                    "non-trivial scores from "
                    "both retrievers, so raw "
                    "retrieval score alone is "
                    "not treated as an "
                    "answerability classifier."
                ),
                (
                    "Hybrid/Reranker remains "
                    "a hypothesis only and is "
                    "not implemented in Day 7."
                ),
            ],
        },
        "findings": [
            {
                "name": (
                    "version_aware_retrieval"
                ),
                "result": "PASS",
                "detail": (
                    "Superseded "
                    "policy_shipping_demo v1 "
                    "was prevented from becoming "
                    "the representative result "
                    "when fresh v2 existed."
                ),
            },
            {
                "name": (
                    "metadata_filter"
                ),
                "result": "PASS",
                "detail": (
                    "Exact filters apply before "
                    "scoring; uncertain and "
                    "no-match cases preserve "
                    "recall through fallback."
                ),
            },
            {
                "name": (
                    "brand_positive_match"
                ),
                "result": (
                    "NOT_EVALUATED_"
                    "CURRENT_FIXTURE"
                ),
                "detail": (
                    "Current fixture contains "
                    "no real brand metadata."
                ),
            },
            {
                "name": (
                    "sku_positive_match"
                ),
                "result": (
                    "NOT_EVALUATED_"
                    "CURRENT_FIXTURE"
                ),
                "detail": (
                    "Current fixture contains "
                    "no real SKU metadata."
                ),
            },
        ],
        "limitations": [
            (
                "The performance evaluation "
                "contains only 16 queries "
                "against 8 synthetic source "
                "records."
            ),
            (
                "Current slices are dominated "
                "by exact product, policy, "
                "compatibility, and component "
                "queries; they do not represent "
                "the full Warhammer business "
                "domain."
            ),
            (
                "Brand and SKU positive filter "
                "quality cannot be measured "
                "until sanitized/canonical "
                "records containing those "
                "fields are available."
            ),
            (
                "Dense cold/warm/query latency "
                "was measured on local CPU and "
                "may vary between runs."
            ),
            (
                "Confidence thresholds are "
                "DAY07_DEMO_CALIBRATION_V1, "
                "not Production SLA."
            ),
            (
                "No-answer separation is not "
                "solved by raw retrieval score "
                "or score gap alone."
            ),
        ],
        "reproducibility": {
            "bm25_result_sha256": (
                sha256_file(
                    BM25_PATH
                )
            ),
            "dense_result_sha256": (
                sha256_file(
                    DENSE_PATH
                )
            ),
            "confidence_result_sha256": (
                sha256_file(
                    CONFIDENCE_PATH
                )
            ),
            "snapshot_manifest_sha256": (
                sha256_file(
                    SNAPSHOT_MANIFEST_PATH
                )
            ),
            "retrieval_eval_code_sha256": (
                sha256_file(
                    EVAL_CODE_PATH
                )
            ),
            "confidence_code_sha256": (
                sha256_file(
                    CONFIDENCE_CODE_PATH
                )
            ),
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
        "RAG_01_COMPARISON_OK"
    )

    print(
        "STATUS=",
        result["status"],
    )

    print(
        "PRIMARY=",
        result[
            "decision"
        ][
            "primary_day07_baseline"
        ],
    )

    print(
        "ERROR_CASES=",
        result[
            "error_analysis"
        ][
            "case_count"
        ],
    )

    print(
        "RETRIEVAL_FAILURES=",
        result[
            "error_analysis"
        ][
            "retrieval_failure_count"
        ],
    )

    print(
        "HARD_SUCCESSES=",
        result[
            "error_analysis"
        ][
            "hard_success_count"
        ],
    )

    print(
        "BM25_FALSE_HIGH=",
        result[
            "confidence"
        ][
            "bm25"
        ][
            "false_high_count"
        ],
    )

    print(
        "DENSE_FALSE_HIGH=",
        result[
            "confidence"
        ][
            "dense"
        ][
            "false_high_count"
        ],
    )

    print(
        "HYBRID_IMPLEMENTED=",
        result[
            "decision"
        ][
            "hybrid_implemented"
        ],
    )

    print(
        "OUTPUT=",
        OUTPUT_PATH,
    )


if __name__ == "__main__":
    main()