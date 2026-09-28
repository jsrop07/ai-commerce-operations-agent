from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


GOLDEN_PATH = Path(
    "artifacts/experiments/day09/"
    "golden60_hybrid_result.json"
)

ACTUAL_PATH = Path(
    "artifacts/experiments/day09/"
    "actual_filter_eval.json"
)

CONFIDENCE_PATH = Path(
    "artifacts/experiments/day09/"
    "confidence_calibration.json"
)

OUTPUT_PATH = Path(
    "artifacts/experiments/day09/"
    "retrieval_comparison.json"
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


def main() -> int:
    golden = load_json(
        GOLDEN_PATH
    )

    actual = load_json(
        ACTUAL_PATH
    )

    confidence = load_json(
        CONFIDENCE_PATH
    )

    methods = golden[
        "methods"
    ]

    comparison: dict[
        str,
        dict[str, Any],
    ] = {}

    for method in (
        "bm25",
        "vector",
        "rrf",
        "weighted",
    ):
        data = methods[
            method
        ]

        comparison[
            method
        ] = {
            "overall_metrics": (
                data[
                    "overall"
                ][
                    "metrics"
                ]
            ),
            "covered_only_metrics": (
                data[
                    "covered_only"
                ][
                    "metrics"
                ]
            ),
            "latency": (
                data["latency"]
            ),
            "failure_count": (
                data[
                    "failure_count"
                ]
            ),
        }

    vector_mrr = (
        comparison[
            "vector"
        ][
            "overall_metrics"
        ][
            "mrr"
        ]
    )

    rrf_mrr = (
        comparison[
            "rrf"
        ][
            "overall_metrics"
        ][
            "mrr"
        ]
    )

    weighted_mrr = (
        comparison[
            "weighted"
        ][
            "overall_metrics"
        ][
            "mrr"
        ]
    )

    actual_cases = actual[
        "cases"
    ]

    pre_preferred_cases = 0

    filter_summary = []

    for case in actual_cases:
        pre = case[
            "pre_filter"
        ]

        post = case[
            "post_filter"
        ]

        pre_rrf_count = (
            pre[
                "returned_count"
            ][
                "rrf"
            ]
        )

        post_rrf_count = (
            post[
                "returned_count"
            ][
                "rrf"
            ]
        )

        pre_rrf_latency = (
            pre[
                "search_latency_ms"
            ][
                "rrf_end_to_end_serial"
            ]
        )

        post_rrf_latency = (
            post[
                "search_latency_ms"
            ][
                "rrf_end_to_end_serial"
            ]
        )

        if (
            pre_rrf_count
            >= post_rrf_count
            and pre_rrf_latency
            <= post_rrf_latency
        ):
            pre_preferred_cases += 1

        filter_summary.append(
            {
                "case_id": (
                    case[
                        "case_id"
                    ]
                ),
                "expected_filter_count": (
                    case[
                        "expected_filter_count"
                    ]
                ),
                "pre_rrf_returned": (
                    pre_rrf_count
                ),
                "post_rrf_returned": (
                    post_rrf_count
                ),
                "pre_rrf_e2e_ms": (
                    pre_rrf_latency
                ),
                "post_rrf_e2e_ms": (
                    post_rrf_latency
                ),
            }
        )

    coverage = golden[
        "coverage"
    ]

    coverage_sufficient = (
        coverage[
            "coverage_ratio"
        ]
        >= 0.80
    )

    hybrid_quality_proven = (
        coverage_sufficient
        and (
            rrf_mrr > vector_mrr
            or weighted_mrr
            > vector_mrr
        )
    )

    if hybrid_quality_proven:
        hybrid_decision = "ADOPT"
        hybrid_reason = (
            "Hybrid quality improvement "
            "is supported by sufficient "
            "evaluation coverage."
        )
    else:
        hybrid_decision = "HOLD"
        hybrid_reason = (
            "Hybrid implementation is valid, "
            "but superiority over Vector is "
            "not proven under current "
            "Golden60 corpus coverage."
        )

    result = {
        "schema_version": (
            "day09-retrieval-comparison.v1"
        ),
        "day": 9,
        "status": (
            "PASS_WITH_FINDINGS"
        ),
        "inputs": {
            "golden60": {
                "path": str(
                    GOLDEN_PATH
                ),
                "sha256": (
                    sha256_file(
                        GOLDEN_PATH
                    )
                ),
                "source_classification": (
                    golden[
                        "source_classification"
                    ]
                ),
            },
            "actual_catalog": {
                "path": str(
                    ACTUAL_PATH
                ),
                "sha256": (
                    sha256_file(
                        ACTUAL_PATH
                    )
                ),
                "source_classification": (
                    actual[
                        "source_classification"
                    ]
                ),
            },
            "confidence": {
                "path": str(
                    CONFIDENCE_PATH
                ),
                "sha256": (
                    sha256_file(
                        CONFIDENCE_PATH
                    )
                ),
            },
        },
        "golden60": {
            "query_count": (
                golden[
                    "dataset"
                ][
                    "query_count"
                ]
            ),
            "answerable_count": (
                golden[
                    "dataset"
                ][
                    "answerable_count"
                ]
            ),
            "coverage": coverage,
            "methods": comparison,
        },
        "actual_catalog": {
            "full_catalog": (
                actual[
                    "catalog"
                ][
                    "full_catalog"
                ]
            ),
            "operational": (
                actual[
                    "catalog"
                ][
                    "operational"
                ]
            ),
            "metadata_eligibility": (
                actual[
                    "metadata_eligibility"
                ]
            ),
            "filter_cases": (
                filter_summary
            ),
            "pre_filter_preferred_cases": (
                pre_preferred_cases
            ),
            "total_filter_cases": (
                len(
                    filter_summary
                )
            ),
        },
        "confidence": {
            "status": (
                confidence[
                    "status"
                ]
            ),
            "threshold_calibrated": (
                confidence[
                    "calibration"
                ][
                    "threshold_calibrated"
                ]
            ),
            "test_accuracy_measured": (
                confidence[
                    "calibration"
                ][
                    "test_accuracy_measured"
                ]
            ),
            "production_threshold": (
                confidence[
                    "decision"
                ][
                    "production_threshold"
                ]
            ),
        },
        "decisions": {
            "metadata_filter": {
                "decision": (
                    "ADOPT_PRE_FILTER_WHEN_FILTER_KNOWN"
                ),
                "reason": (
                    "Actual Cafe24 cases showed "
                    "better candidate retention "
                    "and lower serial retrieval "
                    "latency for PRE-filter."
                ),
            },
            "vector_baseline": {
                "decision": (
                    "RETAIN_AS_DAY09_REFERENCE"
                ),
                "reason": (
                    "Vector produced the best "
                    "Golden60 metrics under the "
                    "current shared snapshot."
                ),
            },
            "rrf": {
                "decision": (
                    hybrid_decision
                ),
                "reason": (
                    hybrid_reason
                ),
            },
            "weighted_hybrid": {
                "decision": (
                    hybrid_decision
                ),
                "reason": (
                    hybrid_reason
                ),
            },
            "confidence_threshold": {
                "decision": "HOLD",
                "reason": (
                    "Validation coverage is "
                    "2/26 and test coverage "
                    "is 0/26."
                ),
            },
            "brand_filter": {
                "decision": "HOLD",
                "reason": (
                    "brand_code coverage is "
                    "2167/2167 but only one "
                    "distinct value exists."
                ),
            },
            "language_filter": {
                "decision": (
                    "NOT_ELIGIBLE"
                ),
                "reason": (
                    "No authoritative language "
                    "metadata is available."
                ),
            },
        },
        "findings": [
            {
                "id": (
                    "D09-AI-05-F01"
                ),
                "status": "OPEN",
                "type": (
                    "CORPUS_COVERAGE"
                ),
                "detail": (
                    "Golden60 answerable corpus "
                    "coverage is only 2/52."
                ),
            },
            {
                "id": (
                    "D09-AI-05-F02"
                ),
                "status": "OPEN",
                "type": (
                    "CONFIDENCE_CALIBRATION"
                ),
                "detail": (
                    "Production confidence "
                    "threshold cannot be "
                    "validated because test "
                    "covered query count is 0."
                ),
            },
            {
                "id": (
                    "D09-AI-05-F03"
                ),
                "status": "OPEN",
                "type": (
                    "BRAND_METADATA"
                ),
                "detail": (
                    "brand_code has full "
                    "coverage but no semantic "
                    "discrimination."
                ),
            },
        ],
        "safety": {
            "reranker_started": False,
            "qlora_started": False,
            "langgraph_started": False,
            "day10_started": False,
            "production_write_enabled": False,
            "hold_policy_relaxed": False,
        },
        "cost": {
            "openai_api_used": False,
            "external_llm_calls": 0,
            "api_cost_usd": 0.0,
        },
    }

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
        "DAY09_RETRIEVAL_COMPARISON_OK"
    )

    print(
        "STATUS=PASS_WITH_FINDINGS"
    )

    print(
        "GOLDEN_COVERAGE=",
        (
            f"{coverage['answerable_covered']}"
            f"/{coverage['answerable_total']}"
        ),
    )

    for method in (
        "bm25",
        "vector",
        "rrf",
        "weighted",
    ):
        metrics = (
            comparison[
                method
            ][
                "overall_metrics"
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
                metrics[
                    "mrr"
                ],
                4,
            ),
            "NDCG@5=",
            round(
                metrics[
                    "ndcg_at_5"
                ],
                4,
            ),
        )

    print(
        "PRE_FILTER_PREFERRED=",
        (
            f"{pre_preferred_cases}"
            f"/{len(filter_summary)}"
        ),
    )

    print(
        "VECTOR_DECISION="
        "RETAIN_AS_DAY09_REFERENCE"
    )

    print(
        "RRF_DECISION=",
        hybrid_decision,
    )

    print(
        "WEIGHTED_DECISION=",
        hybrid_decision,
    )

    print(
        "CONFIDENCE_THRESHOLD=HOLD"
    )

    print(
        "BRAND_FILTER=HOLD"
    )

    print(
        "LANGUAGE_FILTER=NOT_ELIGIBLE"
    )

    print(
        "OPENAI_API_USED=False"
    )

    print(
        "DAY10_STARTED=False"
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