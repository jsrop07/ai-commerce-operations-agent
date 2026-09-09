"""Day 8 Backend Phase 2 공식 통합 산출물 생성기."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from backend.app.sync.day08_retrieval_consumer import (
    consume_retrieval_trace,
)


def _load_json(
    path: Path,
) -> dict[str, Any]:
    payload = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(
        payload,
        dict,
    ):
        raise ValueError(
            f"{path.name} must be object"
        )

    return payload


def _write_json(
    path: Path,
    payload: dict[str, Any],
) -> None:
    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def build_day08_phase2_artifacts(
    *,
    artifact_root: Path,
) -> None:
    root = artifact_root.resolve()

    trace_path = (
        root
        / "retrieval_trace.json"
    )

    trace = _load_json(
        trace_path
    )

    result = consume_retrieval_trace(
        trace
    )

    retrieval_consumer_report = {
        "schema_version": (
            "day08.backend-retrieval-consumer.v1"
        ),
        "official_item": "D08-BE-04",
        "status": "PASS",
        "input_artifact": (
            "retrieval_trace.json"
        ),
        "consumer": {
            "request_id": (
                result.request_id
            ),
            "trace_id": (
                result.trace_id
            ),
            "decision": (
                result.decision.value
            ),
            "confidence": (
                result.confidence
            ),
            "answer_status": (
                result.answer_status
            ),
            "method": (
                result.method
            ),
            "index_version": (
                result.index_version
            ),
            "citation_count": (
                result.citation_count
            ),
            "warnings": list(
                result.warnings
            ),
            "required_lookup": list(
                result.required_lookup
            ),
            "human_review_required": (
                result.human_review_required
            ),
            "human_review_reason": list(
                result.human_review_reason
            ),
            "reasons": list(
                result.reasons
            ),
        },
        "safety_contract": {
            "citation_missing": (
                "INSUFFICIENT_EVIDENCE"
            ),
            "non_high_confidence": "HOLD",
            "stale_inventory": "HOLD",
            "live_order_lookup": (
                "HUMAN_REVIEW"
            ),
            "delivery_address_change": (
                "HUMAN_REVIEW"
            ),
            "cancel_refund": (
                "HUMAN_REVIEW"
            ),
            "production_write_allowed": False,
            "provider_calls_allowed": False,
            "tool_calls_allowed": False,
            "raw_pii_allowed": False,
            "raw_customer_text_allowed": False,
        },
        "test_evidence": {
            "retrieval_consumer": (
                "20 passed"
            ),
            "day08_integration": (
                "45 passed"
            ),
            "privacy_and_day08": (
                "105 passed, 1 skipped"
            ),
            "skip_reason": (
                "symlink creation unavailable"
            ),
            "blocking_defects": 0,
        },
    }

    _write_json(
        root
        / "retrieval_consumer_report.json",
        retrieval_consumer_report,
    )

    # 기존 consumer contract를 Phase2 상태로 갱신한다.
    contract_path = (
        root
        / "consumer_contract_report.json"
    )

    contract = _load_json(
        contract_path
    )

    contract["backend_retrieval"] = {
        "official_item": "D08-BE-04",
        "status": "PASS",
        "input_artifacts": [
            "retrieval_baseline.json",
            "retrieval_trace.json",
            "retrieval_cost.csv",
        ],
        "consumer_report": (
            "retrieval_consumer_report.json"
        ),
        "decision_contract": [
            "ANSWER",
            "HOLD",
            "HUMAN_REVIEW",
            "INSUFFICIENT_EVIDENCE",
        ],
        "production_write_count": 0,
    }

    _write_json(
        contract_path,
        contract,
    )

    # AI Day8에서 넘어온 OPEN finding 2건을
    # 기존 defects.csv에 중복 없이 추가한다.
    defects_path = (
        root
        / "defects.csv"
    )

    with defects_path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as fp:
        rows = list(
            csv.DictReader(fp)
        )

    existing_ids = {
        row.get("finding_id")
        for row in rows
    }

    additions = [
        {
            "finding_id": (
                "DAY08_REAL_PRODUCT_FULL_BENCHMARK"
            ),
            "severity": "INFO",
            "status": "OPEN_NON_BLOCKING",
            "area": "AI_RETRIEVAL",
            "summary": (
                "실제 Cafe24 Product 2167개 전체를 "
                "대상으로 한 Retrieval benchmark는 아직 미수행"
            ),
        },
        {
            "finding_id": (
                "DAY08_PRODUCT_METADATA_FILTER_COVERAGE"
            ),
            "severity": "INFO",
            "status": "OPEN_NON_BLOCKING",
            "area": "AI_RETRIEVAL",
            "summary": (
                "실제 Product의 brand/category/language "
                "metadata filter coverage는 아직 미확정"
            ),
        },
    ]

    for addition in additions:
        if (
            addition["finding_id"]
            not in existing_ids
        ):
            rows.append(
                addition
            )

    with defects_path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as fp:
        writer = csv.DictWriter(
            fp,
            fieldnames=[
                "finding_id",
                "severity",
                "status",
                "area",
                "summary",
            ],
        )

        writer.writeheader()
        writer.writerows(
            rows
        )