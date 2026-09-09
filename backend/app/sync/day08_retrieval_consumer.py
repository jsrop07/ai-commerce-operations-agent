"""Day 8 AI Retrieval 결과를 Backend에서 안전하게 소비한다."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class RetrievalConsumerDecision(StrEnum):
    ANSWER = "ANSWER"
    HOLD = "HOLD"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


@dataclass(frozen=True)
class RetrievalConsumerResult:
    request_id: str
    trace_id: str
    decision: RetrievalConsumerDecision
    confidence: str
    answer_status: str
    method: str
    index_version: str
    citation_count: int
    warnings: tuple[str, ...]
    required_lookup: tuple[str, ...]
    human_review_required: bool
    human_review_reason: tuple[str, ...]
    reasons: tuple[str, ...]


def _string_list(
    value: Any,
) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()

    return tuple(
        str(item).strip()
        for item in value
        if item is not None
        and str(item).strip()
    )


def _normalized_tokens(
    values: tuple[str, ...],
) -> tuple[str, ...]:
    return tuple(
        value.strip().upper()
        for value in values
    )


def _contains_any(
    values: tuple[str, ...],
    keywords: tuple[str, ...],
) -> bool:
    normalized = _normalized_tokens(
        values
    )

    return any(
        keyword in value
        for value in normalized
        for keyword in keywords
    )


def _citation_is_stale(
    citation: Any,
) -> bool:
    if not isinstance(
        citation,
        dict,
    ):
        return False

    for key, value in citation.items():
        normalized_key = (
            str(key)
            .strip()
            .lower()
        )

        if (
            normalized_key
            in {
                "stale",
                "is_stale",
            }
            and value is True
        ):
            return True

        if normalized_key in {
            "freshness",
            "freshness_status",
            "status",
        }:
            if (
                isinstance(value, str)
                and value.strip().upper()
                == "STALE"
            ):
                return True

        if isinstance(value, dict):
            if _citation_is_stale(
                value
            ):
                return True

        if isinstance(value, list):
            for item in value:
                if _citation_is_stale(
                    item
                ):
                    return True

    return False


def _has_stale_inventory(
    *,
    citations: list[Any],
    warnings: tuple[str, ...],
) -> bool:
    warning_match = _contains_any(
        warnings,
        (
            "STALE_INVENTORY",
            "INVENTORY_STALE",
            "STALE INVENTORY",
        ),
    )

    if warning_match:
        return True

    return any(
        _citation_is_stale(
            citation
        )
        for citation in citations
    )


def _requires_human_review(
    *,
    required_lookup: tuple[str, ...],
    human_review_required: bool,
    human_review_reason: tuple[str, ...],
) -> bool:
    if human_review_required:
        return True

    combined = (
        required_lookup
        + human_review_reason
    )

    return _contains_any(
        combined,
        (
            "LIVE_ORDER",
            "ORDER_LOOKUP",
            "DELIVERY_ADDRESS",
            "ADDRESS_CHANGE",
            "CANCEL",
            "REFUND",
            "취소",
            "환불",
            "배송지",
        ),
    )


def _requires_hold(
    *,
    confidence: str,
    answer_status: str,
    warnings: tuple[str, ...],
    stale_inventory: bool,
) -> bool:
    normalized_confidence = (
        confidence.strip().upper()
    )

    if normalized_confidence in {
        "LOW",
        "ABSTAIN",
        "MEDIUM",
    }:
        return True

    if (
        answer_status.strip().upper()
        == "HOLD"
    ):
        return True

    if stale_inventory:
        return True

    return _contains_any(
        warnings,
        (
            "UNCONFIRMED_RESTOCK",
            "RESTOCK_UNCONFIRMED",
            "UNCONFIRMED_POLICY",
            "POLICY_UNCONFIRMED",
            "MAPPING_CONFLICT",
            "MAPPING CONFLICT",
            "입고일",
            "정책",
            "매핑",
        ),
    )


def consume_retrieval_trace(
    payload: dict[str, Any],
) -> RetrievalConsumerResult:
    if not isinstance(
        payload,
        dict,
    ):
        raise ValueError(
            "retrieval payload must be object"
        )

    request_id = payload.get(
        "request_id"
    )
    trace_id = payload.get(
        "trace_id"
    )

    if not isinstance(
        request_id,
        str,
    ) or not request_id:
        raise ValueError(
            "request_id missing"
        )

    if not isinstance(
        trace_id,
        str,
    ) or not trace_id:
        raise ValueError(
            "trace_id missing"
        )

    retrieval = payload.get(
        "retrieval"
    )

    decision = payload.get(
        "decision"
    )

    safety = payload.get(
        "safety"
    )

    citations = payload.get(
        "citations"
    )

    if not isinstance(
        retrieval,
        dict,
    ):
        raise ValueError(
            "retrieval object missing"
        )

    if not isinstance(
        decision,
        dict,
    ):
        raise ValueError(
            "decision object missing"
        )

    if not isinstance(
        safety,
        dict,
    ):
        raise ValueError(
            "safety object missing"
        )

    if not isinstance(
        citations,
        list,
    ):
        raise ValueError(
            "citations must be list"
        )

    confidence = decision.get(
        "confidence"
    )
    answer_status = decision.get(
        "answer_status"
    )

    method = retrieval.get(
        "method"
    )
    index_version = retrieval.get(
        "index_version"
    )

    for name, value in (
        ("confidence", confidence),
        ("answer_status", answer_status),
        ("method", method),
        ("index_version", index_version),
    ):
        if not isinstance(
            value,
            str,
        ) or not value:
            raise ValueError(
                f"{name} missing"
            )

    required_lookup = _string_list(
        decision.get(
            "required_lookup"
        )
    )

    human_review_reason = _string_list(
        decision.get(
            "human_review_reason"
        )
    )

    human_review_required = (
        decision.get(
            "human_review_required"
        )
    )

    if type(
        human_review_required
    ) is not bool:
        raise ValueError(
            "human_review_required "
            "must be bool"
        )

    # Day8 trace sample에는 warnings가 없지만
    # runtime 계약에서는 optional하게 소비한다.
    warnings = _string_list(
        payload.get(
            "warnings"
        )
    )

    # AI Retrieval 단계는 read-only여야 한다.
    if (
        safety.get(
            "production_write"
        )
        is not False
    ):
        raise ValueError(
            "production write detected"
        )

    if (
        safety.get(
            "provider_calls"
        )
        != 0
    ):
        raise ValueError(
            "provider call detected"
        )

    if (
        safety.get(
            "tool_calls"
        )
        != 0
    ):
        raise ValueError(
            "tool call detected"
        )

    if (
        safety.get(
            "raw_pii_included"
        )
        is not False
    ):
        raise ValueError(
            "raw PII detected"
        )

    if (
        safety.get(
            "raw_customer_text_included"
        )
        is not False
    ):
        raise ValueError(
            "raw customer text detected"
        )

    reasons: list[str] = []

    # 최우선 규칙:
    # 근거가 하나도 없으면 AI confidence와 무관하게
    # 답변하지 않는다.
    if not citations:
        reasons.append(
            "CITATION_MISSING"
        )

        return RetrievalConsumerResult(
            request_id=request_id,
            trace_id=trace_id,
            decision=(
                RetrievalConsumerDecision
                .INSUFFICIENT_EVIDENCE
            ),
            confidence=confidence,
            answer_status=answer_status,
            method=method,
            index_version=index_version,
            citation_count=0,
            warnings=warnings,
            required_lookup=required_lookup,
            human_review_required=(
                human_review_required
            ),
            human_review_reason=(
                human_review_reason
            ),
            reasons=tuple(
                reasons
            ),
        )

    human_review = (
        _requires_human_review(
            required_lookup=(
                required_lookup
            ),
            human_review_required=(
                human_review_required
            ),
            human_review_reason=(
                human_review_reason
            ),
        )
    )

    if human_review:
        reasons.append(
            "HUMAN_REVIEW_GATE"
        )

        return RetrievalConsumerResult(
            request_id=request_id,
            trace_id=trace_id,
            decision=(
                RetrievalConsumerDecision
                .HUMAN_REVIEW
            ),
            confidence=confidence,
            answer_status=answer_status,
            method=method,
            index_version=index_version,
            citation_count=len(
                citations
            ),
            warnings=warnings,
            required_lookup=required_lookup,
            human_review_required=True,
            human_review_reason=(
                human_review_reason
            ),
            reasons=tuple(
                reasons
            ),
        )

    stale_inventory = (
        _has_stale_inventory(
            citations=citations,
            warnings=warnings,
        )
    )

    hold_required = (
        _requires_hold(
            confidence=confidence,
            answer_status=answer_status,
            warnings=warnings,
            stale_inventory=(
                stale_inventory
            ),
        )
    )

    if hold_required:
        if stale_inventory:
            reasons.append(
                "STALE_INVENTORY"
            )

        if (
            confidence.strip().upper()
            in {
                "LOW",
                "ABSTAIN",
                "MEDIUM",
            }
        ):
            reasons.append(
                "CONFIDENCE_NOT_HIGH"
            )

        if (
            answer_status
            .strip()
            .upper()
            == "HOLD"
        ):
            reasons.append(
                "AI_STATUS_HOLD"
            )

        return RetrievalConsumerResult(
            request_id=request_id,
            trace_id=trace_id,
            decision=(
                RetrievalConsumerDecision
                .HOLD
            ),
            confidence=confidence,
            answer_status=answer_status,
            method=method,
            index_version=index_version,
            citation_count=len(
                citations
            ),
            warnings=warnings,
            required_lookup=required_lookup,
            human_review_required=False,
            human_review_reason=(
                human_review_reason
            ),
            reasons=tuple(
                reasons
            ),
        )

    return RetrievalConsumerResult(
        request_id=request_id,
        trace_id=trace_id,
        decision=(
            RetrievalConsumerDecision
            .ANSWER
        ),
        confidence=confidence,
        answer_status=answer_status,
        method=method,
        index_version=index_version,
        citation_count=len(
            citations
        ),
        warnings=warnings,
        required_lookup=required_lookup,
        human_review_required=False,
        human_review_reason=(
            human_review_reason
        ),
        reasons=(
            "EVIDENCE_AND_SAFETY_PASS",
        ),
    )