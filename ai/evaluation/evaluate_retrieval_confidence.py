from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from ai.retrieval.confidence import (
    ConfidenceLevel,
    DAY07_THRESHOLDS,
    evaluate_confidence,
)
from ai.retrieval.freshness import (
    build_version_catalog,
    evaluate_freshness,
    load_freshness_policy,
)


DEFAULT_SNAPSHOT = Path(
    "artifacts/experiments/RAG-01/"
    "chunk_snapshot.jsonl"
)

DEFAULT_EVAL = Path(
    "ai/evaluation/datasets/"
    "chunking_eval.jsonl"
)

DEFAULT_BM25 = Path(
    "artifacts/experiments/RAG-01/"
    "bm25_result.json"
)

DEFAULT_DENSE = Path(
    "artifacts/experiments/RAG-01/"
    "dense_result.json"
)

DEFAULT_OUTPUT = Path(
    "artifacts/experiments/RAG-01/"
    "confidence_result.json"
)


def load_json(
    path: Path,
) -> dict[str, Any]:
    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def load_jsonl(
    path: Path,
) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]


def index_snapshot_by_chunk(
    rows: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    result: dict[
        str,
        dict[str, Any],
    ] = {}

    for row in rows:
        chunk_id = str(
            row["chunk_id"]
        )

        if chunk_id in result:
            raise ValueError(
                "duplicate chunk_id in snapshot: "
                f"{chunk_id}"
            )

        result[chunk_id] = row

    return result


def evaluate_one_retriever(
    *,
    retriever: str,
    retrieval_result: dict[str, Any],
    evaluation_rows: list[dict[str, Any]],
    snapshot_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    policy = (
        load_freshness_policy()
    )

    version_catalog = (
        build_version_catalog(
            snapshot_rows
        )
    )

    snapshot_by_chunk = (
        index_snapshot_by_chunk(
            snapshot_rows
        )
    )

    eval_by_query_id = {
        str(row["query_id"]): row
        for row in evaluation_rows
    }

    all_queries = (
        retrieval_result[
            "query_results"
        ]
        + retrieval_result[
            "abstain_queries"
        ]
    )

    evaluated: list[
        dict[str, Any]
    ] = []

    for query_result in all_queries:
        query_id = str(
            query_result["query_id"]
        )

        expected = eval_by_query_id[
            query_id
        ][
            "expected_answerability"
        ]

        top_results = (
            query_result[
                "top_results"
            ]
        )

        scores: list[float] = []

        freshness_states = []

        freshness_details: list[
            dict[str, Any]
        ] = []

        for result in top_results:
            scores.append(
                float(
                    result["score"]
                )
            )

            snapshot_row = (
                snapshot_by_chunk[
                    result["chunk_id"]
                ]
            )

            freshness = (
                evaluate_freshness(
                    source_type=str(
                        snapshot_row[
                            "source_type"
                        ]
                    ),
                    source_id=str(
                        snapshot_row[
                            "source_id"
                        ]
                    ),
                    version=str(
                        snapshot_row[
                            "version"
                        ]
                    ),
                    metadata=(
                        snapshot_row.get(
                            "metadata"
                        )
                        or {}
                    ),
                    policy=policy,
                    version_catalog=(
                        version_catalog
                    ),
                )
            )

            freshness_states.append(
                freshness.state
            )

            freshness_details.append(
                {
                    "source_id": (
                        snapshot_row[
                            "source_id"
                        ]
                    ),
                    "version": (
                        snapshot_row[
                            "version"
                        ]
                    ),
                    "state": (
                        freshness.state.value
                    ),
                    "reason": (
                        freshness.reason
                    ),
                }
            )

        # 중요:
        # expected_answerability를 confidence 입력으로
        # 넣지 않는다.
        #
        # 즉 ABSTAIN 정답 라벨을 runtime에 몰래 사용해
        # 결과를 만드는 것이 아니다.
        confidence = evaluate_confidence(
            retriever=retriever,
            scores=scores,
            freshness_states=(
                freshness_states
            ),
            no_relevant_evidence=False,
        )

        false_high = (
            expected == "ABSTAIN"
            and confidence.level
            == ConfidenceLevel.HIGH
        )

        false_answer_allowed = (
            expected == "ABSTAIN"
            and confidence.answer_allowed
        )

        evaluated.append(
            {
                "query_id": query_id,
                "query": (
                    query_result["query"]
                ),
                "slice": (
                    query_result["slice"]
                ),
                "expected_answerability": (
                    expected
                ),
                "confidence": (
                    confidence.level.value
                ),
                "answer_allowed": (
                    confidence.answer_allowed
                ),
                "top_score": (
                    confidence.top_score
                ),
                "score_gap": (
                    confidence.score_gap
                ),
                "result_count": (
                    confidence.result_count
                ),
                "effective_result_count": (
                    confidence
                    .effective_result_count
                ),
                "freshness_state": (
                    confidence
                    .freshness_state
                    .value
                ),
                "reasons": list(
                    confidence.reasons
                ),
                "false_high": (
                    false_high
                ),
                "false_answer_allowed": (
                    false_answer_allowed
                ),
                "freshness_details": (
                    freshness_details
                ),
            }
        )

    confidence_counts = Counter(
        row["confidence"]
        for row in evaluated
    )

    answerable_rows = [
        row
        for row in evaluated
        if (
            row[
                "expected_answerability"
            ]
            == "ANSWERABLE"
        )
    ]

    abstain_rows = [
        row
        for row in evaluated
        if (
            row[
                "expected_answerability"
            ]
            == "ABSTAIN"
        )
    ]

    false_high_rows = [
        row
        for row in abstain_rows
        if row["false_high"]
    ]

    false_answer_allowed_rows = [
        row
        for row in abstain_rows
        if row[
            "false_answer_allowed"
        ]
    ]

    high_answerable = [
        row
        for row in answerable_rows
        if row["confidence"] == "HIGH"
    ]

    return {
        "retriever": retriever,
        "thresholds": {
            "calibration_version": (
                "DAY07_DEMO_CALIBRATION_V1"
            ),
            "production_sla": False,
            "evidence_score_floor": (
                DAY07_THRESHOLDS[
                    retriever
                ].evidence_score_floor
            ),
            "medium_score": (
                DAY07_THRESHOLDS[
                    retriever
                ].medium_score
            ),
            "high_score": (
                DAY07_THRESHOLDS[
                    retriever
                ].high_score
            ),
            "high_gap": (
                DAY07_THRESHOLDS[
                    retriever
                ].high_gap
            ),
        },
        "summary": {
            "query_count": len(
                evaluated
            ),
            "answerable_count": len(
                answerable_rows
            ),
            "abstain_count": len(
                abstain_rows
            ),
            "confidence_counts": dict(
                sorted(
                    confidence_counts.items()
                )
            ),
            "false_high_count": len(
                false_high_rows
            ),
            "false_answer_allowed_count": (
                len(
                    false_answer_allowed_rows
                )
            ),
            "high_answerable_count": len(
                high_answerable
            ),
        },
        "false_high_queries": (
            false_high_rows
        ),
        "false_answer_allowed_queries": (
            false_answer_allowed_rows
        ),
        "queries": evaluated,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate Day 7 retrieval "
            "confidence calibration."
        )
    )

    parser.add_argument(
        "--snapshot",
        type=Path,
        default=DEFAULT_SNAPSHOT,
    )

    parser.add_argument(
        "--evaluation",
        type=Path,
        default=DEFAULT_EVAL,
    )

    parser.add_argument(
        "--bm25",
        type=Path,
        default=DEFAULT_BM25,
    )

    parser.add_argument(
        "--dense",
        type=Path,
        default=DEFAULT_DENSE,
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
    )

    args = parser.parse_args()

    snapshot_rows = load_jsonl(
        args.snapshot
    )

    evaluation_rows = load_jsonl(
        args.evaluation
    )

    bm25_result = load_json(
        args.bm25
    )

    dense_result = load_json(
        args.dense
    )

    result = {
        "schema_version": (
            "retrieval-confidence-eval.v1"
        ),
        "calibration": {
            "version": (
                "DAY07_DEMO_CALIBRATION_V1"
            ),
            "production_sla": False,
            "oracle_answerability_used_"
            "as_confidence_input": False,
            "known_answerability_used_"
            "only_for_evaluation": True,
        },
        "bm25": evaluate_one_retriever(
            retriever="bm25",
            retrieval_result=(
                bm25_result
            ),
            evaluation_rows=(
                evaluation_rows
            ),
            snapshot_rows=(
                snapshot_rows
            ),
        ),
        "dense": evaluate_one_retriever(
            retriever="dense",
            retrieval_result=(
                dense_result
            ),
            evaluation_rows=(
                evaluation_rows
            ),
            snapshot_rows=(
                snapshot_rows
            ),
        ),
        "limitations": [
            (
                "Retrieval score and score gap "
                "do not independently determine "
                "answerability."
            ),
            (
                "No-answer queries produced "
                "non-trivial BM25 and Dense "
                "scores during calibration."
            ),
            (
                "Thresholds are Day 7 demo "
                "calibration values, not "
                "Production SLA."
            ),
            (
                "A future verifier, reranker, "
                "or Hybrid retrieval experiment "
                "may improve no-answer routing."
            ),
        ],
    }

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

    print(
        "CONFIDENCE_EVAL_OK"
    )

    for retriever in (
        "bm25",
        "dense",
    ):
        summary = result[
            retriever
        ][
            "summary"
        ]

        print(
            retriever.upper(),
            "COUNTS=",
            summary[
                "confidence_counts"
            ],
        )

        print(
            retriever.upper(),
            "FALSE_HIGH=",
            summary[
                "false_high_count"
            ],
        )

        print(
            retriever.upper(),
            "FALSE_ANSWER_ALLOWED=",
            summary[
                "false_answer_allowed_count"
            ],
        )

    print(
        "OUTPUT=",
        args.output,
    )


if __name__ == "__main__":
    main()