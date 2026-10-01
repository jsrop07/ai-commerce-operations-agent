from __future__ import annotations

import json
import statistics
import time
from pathlib import Path
from typing import Any

import tiktoken

from ai.retrieval.context_compression import compress_context

TASK_ID = "R07-AI-01"
EXPERIMENT_ID = "OPS-RAG-02-COMPRESSION"
TOKENIZER_NAME = "cl100k_base"

OUTPUT_DIR = Path("artifacts/experiments/OPS-RAG-02")
PRIVATE_DIR = OUTPUT_DIR / "private"
CONFIG_PATH = OUTPUT_DIR / "r07_context_compression_config.json"
SUMMARY_PATH = OUTPUT_DIR / "r07_context_compression_summary.json"
RESULT_PATH = PRIVATE_DIR / "r07_context_compression_result.json"


def _policy_item(
    *,
    source_id: str,
    title: str,
    excerpt: str,
    field_or_path: str,
    policy_exception: str | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "source_id": source_id,
        "title": title,
        "record_id": source_id,
        "source_type": "POLICY",
        "as_of": "2026-09-01T00:00:00Z",
        "field_or_path": field_or_path,
        "excerpt": excerpt,
        "version": "v1",
        "evidence_id": f"synthetic:{source_id}",
        # 검색/디버깅용 불필요 필드: compression 대상
        "rank": 1,
        "score": 0.93,
        "bm25_rank": 2,
        "vector_rank": 1,
        "bm25_score": 8.14,
        "vector_score": 0.87,
        "bm25_normalized": 0.91,
        "vector_normalized": 0.89,
        "fusion_method": "RRF",
        "rerank_score": 0.97,
        "matched_query_indexes": [0, 1],
        "matched_queries": ["synthetic query", "alternate synthetic query"],
        "combine_reason": "synthetic R07 compression evaluation",
        "debug": {
            "trace": "LOCAL_EVAL_ONLY",
            "note": "SYNTHETIC_POLICY_FIXTURE",
        },
        "ui_state": {
            "expanded": True,
            "selected": False,
        },
    }
    if policy_exception is not None:
        item["policy_exception"] = policy_exception
    return item


def _incoming_item() -> dict[str, Any]:
    return {
        "source_id": "incoming_stock_demo_tentative_001",
        "title": "Tentative Incoming Stock",
        "record_id": "incoming_stock_demo_tentative_001",
        "source_type": "INCOMING_STOCK",
        "as_of": "2026-09-01T00:00:00Z",
        "field_or_path": "incoming.status",
        "excerpt": "상태는 TENTATIVE이며 아직 확정입고가 아닙니다.",
        "version": "v1",
        "evidence_id": "synthetic:incoming_stock_demo_tentative_001",
        "rank": 1,
        "score": 0.88,
        "bm25_rank": 1,
        "vector_rank": 2,
        "bm25_score": 7.9,
        "vector_score": 0.82,
        "fusion_method": "RRF",
        "rerank_score": 0.94,
        "matched_queries": ["synthetic shipping readiness"],
        "debug": {
            "trace": "LOCAL_EVAL_ONLY",
            "note": "SYNTHETIC_INCOMING_FIXTURE",
        },
        "ui_state": {
            "expanded": False,
        },
    }


def build_cases() -> list[dict[str, Any]]:
    return [
        {
            "case_id": "R07-COMP-001",
            "claim_type": "RESERVATION_SHIPPING_POLICY",
            "query": "예약상품은 언제 출고해?",
            "items": [
                _policy_item(
                    source_id="policy_shipping_demo",
                    title="Reservation Shipping Policy",
                    field_or_path="reservation.shipping",
                    excerpt=(
                        "예약상품은 상품 입고와 검수 완료 후 "
                        "순차적으로 출고합니다."
                    ),
                )
            ],
        },
        {
            "case_id": "R07-COMP-002",
            "claim_type": "TENTATIVE_SHORTAGE_POLICY",
            "query": (
                "잠정입고가 3개 있는데 왜 예약 부족수량에서 안 빼?"
            ),
            "items": [
                _policy_item(
                    source_id="policy_reservation_shortage_demo",
                    title="Tentative Shortage Policy",
                    field_or_path="reservation.shortage",
                    excerpt=(
                        "잠정입고 수량은 아직 확정되지 않았으므로 "
                        "예약 부족수량 차감에 사용하지 않습니다."
                    ),
                )
            ],
        },
        {
            "case_id": "R07-COMP-003",
            "claim_type": "TENTATIVE_SHIPPING_READINESS",
            "query": (
                "잠정입고 상태인 물량을 근거로 예약상품 출고 준비가 "
                "끝났다고 봐도 돼?"
            ),
            "items": [
                _incoming_item(),
                _policy_item(
                    source_id="policy_shipping_demo",
                    title="Reservation Shipping Policy",
                    field_or_path="reservation.shipping",
                    excerpt=(
                        "예약상품은 상품 입고와 검수 완료 후 "
                        "순차적으로 출고합니다."
                    ),
                ),
            ],
        },
    ]


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def token_count(encoding: Any, value: Any) -> int:
    return len(encoding.encode(canonical_json(value)))


def required_evidence_signature(item: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "source_id",
        "title",
        "record_id",
        "source_type",
        "field_or_path",
        "excerpt",
        "as_of",
        "version",
        "evidence_id",
        "evidence_ids",
        "policy_exception",
        "policy_exceptions",
    )
    return {
        key: item.get(key)
        for key in fields
        if key in item
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PRIVATE_DIR.mkdir(parents=True, exist_ok=True)

    encoding = tiktoken.get_encoding(TOKENIZER_NAME)
    cases = build_cases()

    rows: list[dict[str, Any]] = []
    compression_latencies: list[float] = []

    total_before_tokens = 0
    total_after_tokens = 0
    total_before_chars = 0
    total_after_chars = 0
    total_evidence_loss = 0
    total_fallback = 0
    total_duplicates = 0
    preserved_case_count = 0

    for case in cases:
        original_items = [
            dict(item)
            for item in case["items"]
        ]

        before_tokens = token_count(
            encoding,
            original_items,
        )

        started = time.perf_counter()
        outcome = compress_context(original_items)
        compression_ms = (
            time.perf_counter() - started
        ) * 1000.0

        compressed_items = [
            dict(item.compressed)
            for item in outcome.items
        ]

        after_tokens = token_count(
            encoding,
            compressed_items,
        )

        before_signatures = [
            required_evidence_signature(item)
            for item in original_items
        ]
        after_signatures = [
            required_evidence_signature(item)
            for item in compressed_items
        ]

        evidence_preserved = (
            before_signatures
            == after_signatures
        )

        citation_preserved = (
            outcome.trace.citation_answerable_after
            == outcome.trace.citation_answerable_before
        )

        token_reduction_ratio = (
            0.0
            if before_tokens <= 0
            else 1.0 - (
                after_tokens / before_tokens
            )
        )

        if (
            evidence_preserved
            and citation_preserved
            and outcome.trace.evidence_loss_count == 0
        ):
            preserved_case_count += 1

        total_before_tokens += before_tokens
        total_after_tokens += after_tokens
        total_before_chars += outcome.trace.before_char_count
        total_after_chars += outcome.trace.after_char_count
        total_evidence_loss += outcome.trace.evidence_loss_count
        total_fallback += outcome.trace.fallback_count
        total_duplicates += outcome.trace.duplicate_count
        compression_latencies.append(compression_ms)

        rows.append(
            {
                "case_id": case["case_id"],
                "claim_type": case["claim_type"],
                "source_classification": "LOCAL_EVAL_SYNTHETIC",
                "query": case["query"],
                "input_count": outcome.trace.input_count,
                "output_count": outcome.trace.output_count,
                "before_tokens": before_tokens,
                "after_tokens": after_tokens,
                "token_reduction_ratio": token_reduction_ratio,
                "before_char_count": outcome.trace.before_char_count,
                "after_char_count": outcome.trace.after_char_count,
                "char_reduction_ratio": outcome.trace.reduction_ratio,
                "duplicate_count": outcome.trace.duplicate_count,
                "evidence_loss_count": outcome.trace.evidence_loss_count,
                "fallback_count": outcome.trace.fallback_count,
                "citation_answerable_before": (
                    outcome.trace.citation_answerable_before
                ),
                "citation_answerable_after": (
                    outcome.trace.citation_answerable_after
                ),
                "evidence_preserved": evidence_preserved,
                "citation_preserved": citation_preserved,
                "compression_latency_ms": compression_ms,
                "before_evidence": before_signatures,
                "after_evidence": after_signatures,
            }
        )

    total_token_reduction_ratio = (
        0.0
        if total_before_tokens <= 0
        else 1.0 - (
            total_after_tokens
            / total_before_tokens
        )
    )

    config = {
        "task_id": TASK_ID,
        "experiment_id": EXPERIMENT_ID,
        "scope": "SYNTHETIC_POLICY_COMPRESSION_ONLY",
        "source_classification": "LOCAL_EVAL_SYNTHETIC",
        "actual_policy_used": False,
        "final12_used": False,
        "retrieval_run_used": False,
        "reranker_run_used": False,
        "compression_function": "ai.retrieval.context_compression.compress_context",
        "tokenizer": {
            "library": "tiktoken",
            "name": TOKENIZER_NAME,
        },
        "case_count": len(cases),
        "claim_types": [
            case["claim_type"]
            for case in cases
        ],
        "notes": [
            "Synthetic fixtures only; not actual company policy.",
            "Token counts use canonical compact JSON serialization.",
            "Existing compression implementation is not modified.",
            "This experiment is separate from PRODUCT reranker evaluation.",
        ],
    }

    result = {
        "config": config,
        "rows": rows,
    }

    summary = {
        "task_id": TASK_ID,
        "experiment_id": EXPERIMENT_ID,
        "source_classification": "LOCAL_EVAL_SYNTHETIC",
        "case_count": len(rows),
        "preserved_case_count": preserved_case_count,
        "total_before_tokens": total_before_tokens,
        "total_after_tokens": total_after_tokens,
        "token_reduction_ratio": total_token_reduction_ratio,
        "total_before_chars": total_before_chars,
        "total_after_chars": total_after_chars,
        "evidence_loss_count": total_evidence_loss,
        "fallback_count": total_fallback,
        "duplicate_count": total_duplicates,
        "citation_preserved_all": all(
            row["citation_preserved"]
            for row in rows
        ),
        "evidence_preserved_all": all(
            row["evidence_preserved"]
            for row in rows
        ),
        "compression_latency_ms": {
            "mean": statistics.mean(
                compression_latencies
            ),
            "min": min(compression_latencies),
            "max": max(compression_latencies),
        },
        "per_case": [
            {
                "case_id": row["case_id"],
                "claim_type": row["claim_type"],
                "before_tokens": row["before_tokens"],
                "after_tokens": row["after_tokens"],
                "token_reduction_ratio": row[
                    "token_reduction_ratio"
                ],
                "evidence_preserved": row[
                    "evidence_preserved"
                ],
                "citation_preserved": row[
                    "citation_preserved"
                ],
                "fallback_count": row[
                    "fallback_count"
                ],
                "compression_latency_ms": row[
                    "compression_latency_ms"
                ],
            }
            for row in rows
        ],
    }

    CONFIG_PATH.write_text(
        json.dumps(
            config,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    RESULT_PATH.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    SUMMARY_PATH.write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("R07_CONTEXT_COMPRESSION_EVAL_OK")
    print("CONFIG=", CONFIG_PATH.resolve())
    print("RESULT=", RESULT_PATH.resolve())
    print("SUMMARY=", SUMMARY_PATH.resolve())
    print("CASE_COUNT=", len(rows))
    print("BEFORE_TOKENS=", total_before_tokens)
    print("AFTER_TOKENS=", total_after_tokens)
    print(
        "TOKEN_REDUCTION_RATIO=",
        round(total_token_reduction_ratio, 6),
    )
    print(
        "EVIDENCE_PRESERVED_ALL=",
        summary["evidence_preserved_all"],
    )
    print(
        "CITATION_PRESERVED_ALL=",
        summary["citation_preserved_all"],
    )
    print(
        "EVIDENCE_LOSS_COUNT=",
        total_evidence_loss,
    )
    print("FALLBACK_COUNT=", total_fallback)
    print(
        "COMPRESSION_MEAN_MS=",
        round(
            summary["compression_latency_ms"]["mean"],
            6,
        ),
    )
    for row in summary["per_case"]:
        print(
            row["case_id"],
            row["claim_type"],
            "before_tokens=",
            row["before_tokens"],
            "after_tokens=",
            row["after_tokens"],
            "reduction=",
            round(
                row["token_reduction_ratio"],
                6,
            ),
            "evidence_preserved=",
            row["evidence_preserved"],
            "citation_preserved=",
            row["citation_preserved"],
            "fallback=",
            row["fallback_count"],
        )


if __name__ == "__main__":
    main()
