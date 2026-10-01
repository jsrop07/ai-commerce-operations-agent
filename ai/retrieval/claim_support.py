from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class ClaimType(str, Enum):
    RESERVATION_SHIPPING_POLICY = "RESERVATION_SHIPPING_POLICY"
    TENTATIVE_SHORTAGE_POLICY = "TENTATIVE_SHORTAGE_POLICY"
    TENTATIVE_SHIPPING_READINESS = "TENTATIVE_SHIPPING_READINESS"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True)
class ClaimEvidence:
    source_type: str
    source_id: str
    version: str
    excerpt: str


@dataclass(frozen=True)
class ClaimSupportDecision:
    claim_type: ClaimType
    supported: bool
    supported_source_ids: tuple[str, ...]
    missing_requirements: tuple[str, ...]


def classify_claim_type(
    question: str,
) -> ClaimType:
    text = question.strip()

    if not text:
        return ClaimType.UNSUPPORTED

    # GE-D-016 계열:
    # 잠정입고를 근거로 예약상품 출고 준비 완료 여부를 묻는 관계 질문.
    if (
        "잠정입고" in text
        and "예약상품" in text
        and (
            "출고 준비" in text
            or "출고준비" in text
        )
    ):
        return (
            ClaimType
            .TENTATIVE_SHIPPING_READINESS
        )

    # GE-D-007 계열:
    # 잠정입고를 예약 부족수량에서 차감하는지 묻는 정책 질문.
    if (
        "잠정입고" in text
        and (
            "부족수량" in text
            or "부족 수량" in text
        )
        and (
            "차감" in text
            or "빼" in text
        )
    ):
        return (
            ClaimType
            .TENTATIVE_SHORTAGE_POLICY
        )

    # GE-D-005 계열:
    # 예약상품 출고 시점/조건을 묻는 정책 질문.
    if (
        "예약상품" in text
        and "출고" in text
        and (
            "언제" in text
            or "조건" in text
            or "시점" in text
        )
    ):
        return (
            ClaimType
            .RESERVATION_SHIPPING_POLICY
        )

    return ClaimType.UNSUPPORTED


def _normalized(
    text: str,
) -> str:
    return (
        text.replace(" ", "")
        .replace("\n", "")
        .upper()
    )


def _supports_shipping_policy(
    evidence: ClaimEvidence,
) -> bool:
    if evidence.source_type != "POLICY":
        return False

    text = _normalized(
        evidence.excerpt
    )

    return (
        "예약상품" in text
        and "입고" in text
        and "검수" in text
        and "출고" in text
    )


def _supports_tentative_shortage_policy(
    evidence: ClaimEvidence,
) -> bool:
    if evidence.source_type != "POLICY":
        return False

    text = _normalized(
        evidence.excerpt
    )

    return (
        "잠정입고" in text
        and (
            "확정되지" in text
            or "확정입고가아니" in text
            or "TENTATIVE" in text
        )
        and (
            "부족수량" in text
            or "부족수량차감" in text
        )
        and (
            "사용하지않" in text
            or "차감하지않" in text
        )
    )


def _supports_tentative_status(
    evidence: ClaimEvidence,
) -> bool:
    if evidence.source_type not in (
        "INCOMING_STOCK",
        "INCOMING",
    ):
        return False

    text = _normalized(
        evidence.excerpt
    )

    return (
        "TENTATIVE" in text
        or "잠정입고" in text
    ) and (
        "확정입고가아니" in text
        or "아직확정" in text
        or "확정되지" in text
    )


def evaluate_claim_support(
    question: str,
    evidence: Iterable[
        ClaimEvidence
    ],
) -> ClaimSupportDecision:
    claim_type = classify_claim_type(
        question
    )

    items = tuple(evidence)

    if claim_type == ClaimType.UNSUPPORTED:
        return ClaimSupportDecision(
            claim_type=claim_type,
            supported=False,
            supported_source_ids=(),
            missing_requirements=(
                "SUPPORTED_R06_CLAIM_TYPE",
            ),
        )

    supported_ids: list[str] = []
    missing: list[str] = []

    if (
        claim_type
        == ClaimType.RESERVATION_SHIPPING_POLICY
    ):
        matches = [
            item
            for item in items
            if _supports_shipping_policy(
                item
            )
        ]

        if not matches:
            missing.append(
                "RESERVATION_SHIPPING_POLICY"
            )
        else:
            supported_ids.extend(
                item.source_id
                for item in matches
            )

    elif (
        claim_type
        == ClaimType.TENTATIVE_SHORTAGE_POLICY
    ):
        matches = [
            item
            for item in items
            if _supports_tentative_shortage_policy(
                item
            )
        ]

        if not matches:
            missing.append(
                "TENTATIVE_SHORTAGE_POLICY"
            )
        else:
            supported_ids.extend(
                item.source_id
                for item in matches
            )

    elif (
        claim_type
        == ClaimType.TENTATIVE_SHIPPING_READINESS
    ):
        tentative_matches = [
            item
            for item in items
            if _supports_tentative_status(
                item
            )
        ]

        shipping_matches = [
            item
            for item in items
            if _supports_shipping_policy(
                item
            )
        ]

        if not tentative_matches:
            missing.append(
                "TENTATIVE_INCOMING_STATUS"
            )
        else:
            supported_ids.extend(
                item.source_id
                for item in tentative_matches
            )

        if not shipping_matches:
            missing.append(
                "RESERVATION_SHIPPING_POLICY"
            )
        else:
            supported_ids.extend(
                item.source_id
                for item in shipping_matches
            )

    return ClaimSupportDecision(
        claim_type=claim_type,
        supported=not missing,
        supported_source_ids=tuple(
            dict.fromkeys(
                supported_ids
            )
        ),
        missing_requirements=tuple(
            missing
        ),
    )