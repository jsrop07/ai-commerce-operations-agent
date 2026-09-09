"""Day 8 Retrieval Consumer Integration 테스트."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.sync.day08_retrieval_consumer import (
    RetrievalConsumerDecision,
    consume_retrieval_trace,
)


ROOT = Path(__file__).resolve().parents[2]

TRACE_PATH = (
    ROOT.parent
    / "artifacts"
    / "integration"
    / "day08"
    / "retrieval_trace.json"
)


def _base_payload() -> dict:
    return {
        "schema_version": "test.v1",
        "request_id": "req-test",
        "trace_id": "trace-test",
        "query": {
            "hash": "abc",
            "sanitized": "상품 문의",
            "rewrite_applied": False,
            "rewritten": None,
        },
        "retrieval": {
            "method": "BM25",
            "top_k": 2,
            "filters": [],
            "candidates_before_rerank": [],
            "index_version": "test-index-v1",
        },
        "citations": [
            {
                "evidence_id": "ev-1",
                "freshness": "FRESH",
            }
        ],
        "decision": {
            "confidence": "HIGH",
            "answer_status": "ANSWER",
            "required_lookup": [],
            "human_review_required": False,
            "human_review_reason": [],
        },
        "safety": {
            "raw_pii_included": False,
            "raw_customer_text_included": False,
            "production_write": False,
            "provider_calls": 0,
            "tool_calls": 0,
        },
    }


def test_real_day08_trace_is_consumable() -> None:
    payload = json.loads(
        TRACE_PATH.read_text(
            encoding="utf-8"
        )
    )

    result = consume_retrieval_trace(
        payload
    )

    assert result.request_id
    assert result.trace_id
    assert result.method == "BM25"
    assert result.index_version

    # 현재 AI Day8 trace는 MEDIUM + HOLD다.
    assert result.confidence == "MEDIUM"
    assert (
        result.decision
        == RetrievalConsumerDecision.HOLD
    )


def test_missing_citation_is_insufficient_evidence() -> None:
    payload = _base_payload()
    payload["citations"] = []

    result = consume_retrieval_trace(
        payload
    )

    assert (
        result.decision
        == RetrievalConsumerDecision
        .INSUFFICIENT_EVIDENCE
    )

    assert (
        "CITATION_MISSING"
        in result.reasons
    )


@pytest.mark.parametrize(
    "confidence",
    [
        "LOW",
        "ABSTAIN",
        "MEDIUM",
    ],
)
def test_non_high_confidence_is_hold(
    confidence: str,
) -> None:
    payload = _base_payload()

    payload["decision"][
        "confidence"
    ] = confidence

    result = consume_retrieval_trace(
        payload
    )

    assert (
        result.decision
        == RetrievalConsumerDecision.HOLD
    )


def test_stale_inventory_is_hold() -> None:
    payload = _base_payload()

    payload["citations"][0][
        "freshness"
    ] = "STALE"

    result = consume_retrieval_trace(
        payload
    )

    assert (
        result.decision
        == RetrievalConsumerDecision.HOLD
    )

    assert (
        "STALE_INVENTORY"
        in result.reasons
    )


def test_live_order_lookup_is_human_review() -> None:
    payload = _base_payload()

    payload["decision"][
        "required_lookup"
    ] = [
        "LIVE_ORDER_LOOKUP"
    ]

    result = consume_retrieval_trace(
        payload
    )

    assert (
        result.decision
        == RetrievalConsumerDecision
        .HUMAN_REVIEW
    )


def test_delivery_address_change_is_human_review() -> None:
    payload = _base_payload()

    payload["decision"][
        "human_review_reason"
    ] = [
        "DELIVERY_ADDRESS_CHANGE"
    ]

    result = consume_retrieval_trace(
        payload
    )

    assert (
        result.decision
        == RetrievalConsumerDecision
        .HUMAN_REVIEW
    )


@pytest.mark.parametrize(
    "reason",
    [
        "CANCEL_REQUEST",
        "REFUND_REQUEST",
    ],
)
def test_cancel_or_refund_is_human_review(
    reason: str,
) -> None:
    payload = _base_payload()

    payload["decision"][
        "human_review_reason"
    ] = [
        reason
    ]

    result = consume_retrieval_trace(
        payload
    )

    assert (
        result.decision
        == RetrievalConsumerDecision
        .HUMAN_REVIEW
    )


def test_explicit_human_review_flag_wins() -> None:
    payload = _base_payload()

    payload["decision"][
        "human_review_required"
    ] = True

    result = consume_retrieval_trace(
        payload
    )

    assert (
        result.decision
        == RetrievalConsumerDecision
        .HUMAN_REVIEW
    )


@pytest.mark.parametrize(
    "warning",
    [
        "UNCONFIRMED_RESTOCK_DATE",
        "UNCONFIRMED_POLICY",
        "MAPPING_CONFLICT",
    ],
)
def test_uncertain_warning_is_hold(
    warning: str,
) -> None:
    payload = _base_payload()

    payload["warnings"] = [
        warning
    ]

    result = consume_retrieval_trace(
        payload
    )

    assert (
        result.decision
        == RetrievalConsumerDecision.HOLD
    )


def test_safe_high_confidence_with_evidence_can_answer() -> None:
    payload = _base_payload()

    result = consume_retrieval_trace(
        payload
    )

    assert (
        result.decision
        == RetrievalConsumerDecision.ANSWER
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        (
            "production_write",
            True,
        ),
        (
            "provider_calls",
            1,
        ),
        (
            "tool_calls",
            1,
        ),
        (
            "raw_pii_included",
            True,
        ),
        (
            "raw_customer_text_included",
            True,
        ),
    ],
)
def test_safety_violation_is_rejected(
    field: str,
    value: object,
) -> None:
    payload = _base_payload()

    payload["safety"][
        field
    ] = value

    with pytest.raises(
        ValueError
    ):
        consume_retrieval_trace(
            payload
        )