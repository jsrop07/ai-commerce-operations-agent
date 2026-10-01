from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SuitabilityStatus(str, Enum):
    ANSWER = "ANSWER"
    HOLD = "HOLD"


@dataclass(frozen=True)
class SourceEvidence:
    source_type: str
    source_id: str
    freshness: str
    supports_claim: bool


@dataclass(frozen=True)
class SourceSuitabilityResult:
    status: SuitabilityStatus
    reasons: tuple[str, ...]
    provider_call_allowed: bool


def evaluate_source_suitability(
    *,
    required_source_types: tuple[str, ...],
    evidence: tuple[SourceEvidence, ...],
    mapping_ambiguous: bool = False,
    source_conflict: bool = False,
    target_verified: bool = True,
) -> SourceSuitabilityResult:
    reasons: list[str] = []

    if mapping_ambiguous:
        reasons.append("MAPPING_AMBIGUOUS")

    if source_conflict:
        reasons.append("SOURCE_CONFLICT")

    if not target_verified:
        reasons.append("TARGET_UNVERIFIED")

    if not evidence:
        reasons.append("NO_SOURCE")

    actual_source_types = {
        item.source_type
        for item in evidence
    }

    for required in required_source_types:
        if required not in actual_source_types:
            reasons.append(
                f"REQUIRED_SOURCE_MISSING:{required}"
            )

    for item in evidence:
        if item.freshness == "STALE":
            reasons.append(
                f"STALE_EVIDENCE:{item.source_id}"
            )
        elif item.freshness != "FRESH":
            reasons.append(
                f"FRESHNESS_UNVERIFIED:{item.source_id}"
            )

        if not item.supports_claim:
            reasons.append(
                f"CLAIM_NOT_SUPPORTED:{item.source_id}"
            )

    unique_reasons = tuple(dict.fromkeys(reasons))

    if unique_reasons:
        return SourceSuitabilityResult(
            status=SuitabilityStatus.HOLD,
            reasons=unique_reasons,
            provider_call_allowed=False,
        )

    return SourceSuitabilityResult(
        status=SuitabilityStatus.ANSWER,
        reasons=(),
        provider_call_allowed=True,
    )
