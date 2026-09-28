"""Day 9 예약주문 식별 서비스."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum


class ReservationIdentification(
    StrEnum
):
    CONFIRMED_RESERVATION = (
        "CONFIRMED_RESERVATION"
    )
    UNKNOWN = "UNKNOWN"
    AMBIGUOUS = "AMBIGUOUS"


_PREORDER_MARKERS = (
    "PREORDER",
    "PRE-ORDER",
    "PRE ORDER",
    "예약",
    "예약판매",
)


@dataclass(frozen=True)
class ReservationIdentificationInput:
    order_id: str

    current_category: str | None = None

    # 주문이 발생했을 당시의 category.
    # 현재 category와 구분해야 한다.
    order_category_snapshot: (
        str | None
    ) = None

    reservation_evidence_ids: (
        tuple[str, ...]
    ) = ()

    mapping_candidates: (
        tuple[str, ...]
    ) = ()

    mapping_approved: bool = False
    selected_sku_id: str | None = None

    source_classification: str = (
        "BLOCKED"
    )

    as_of: datetime | None = None


@dataclass(frozen=True)
class ReservationIdentificationResult:
    order_id: str
    status: ReservationIdentification

    selected_sku_id: str | None
    mapping_review_required: bool

    evidence_ids: tuple[str, ...]
    reasons: tuple[str, ...]

    source_classification: str
    as_of: datetime


def _is_preorder_category(
    value: str | None,
) -> bool:
    if not value:
        return False

    normalized = (
        value.strip().upper()
    )

    return any(
        marker in normalized
        for marker in _PREORDER_MARKERS
    )


def identify_reservation(
    item: ReservationIdentificationInput,
) -> ReservationIdentificationResult:
    """Valid-time evidence를 기준으로 예약주문을 식별한다."""

    if not item.order_id:
        raise ValueError(
            "order_id is required"
        )

    as_of = (
        item.as_of
        or datetime.now(UTC)
    )

    reasons: list[str] = []

    # mapping approval 없이 후보가 존재해도
    # 서버가 SKU를 자동 확정하지 않는다.
    if (
        item.mapping_candidates
        and not item.mapping_approved
    ):
        reasons.append(
            "SKU_MAPPING_REVIEW_REQUIRED"
        )

        return (
            ReservationIdentificationResult(
                order_id=item.order_id,
                status=(
                    ReservationIdentification
                    .AMBIGUOUS
                ),
                selected_sku_id=None,
                mapping_review_required=True,
                evidence_ids=(
                    item
                    .reservation_evidence_ids
                ),
                reasons=tuple(reasons),
                source_classification=(
                    item
                    .source_classification
                ),
                as_of=as_of,
            )
        )

    if (
        item.mapping_approved
        and not item.selected_sku_id
    ):
        raise ValueError(
            "approved mapping requires "
            "selected_sku_id"
        )

    if (
        not item.mapping_approved
        and item.selected_sku_id
    ):
        raise ValueError(
            "selected_sku_id cannot be "
            "used without approved mapping"
        )

    valid_category_evidence = (
        _is_preorder_category(
            item.order_category_snapshot
        )
    )

    explicit_evidence = bool(
        item.reservation_evidence_ids
    )

    valid_reservation_evidence = (
        valid_category_evidence
        or explicit_evidence
    )

    if not valid_reservation_evidence:
        if _is_preorder_category(
            item.current_category
        ):
            reasons.append(
                "CURRENT_CATEGORY_ONLY_"
                "NOT_VALID_TIME_EVIDENCE"
            )
        else:
            reasons.append(
                "RESERVATION_EVIDENCE_"
                "MISSING"
            )

        return (
            ReservationIdentificationResult(
                order_id=item.order_id,
                status=(
                    ReservationIdentification
                    .UNKNOWN
                ),
                selected_sku_id=(
                    item.selected_sku_id
                    if item.mapping_approved
                    else None
                ),
                mapping_review_required=(
                    bool(item.mapping_candidates)
                    and not item.mapping_approved
                ),
                evidence_ids=(
                    item
                    .reservation_evidence_ids
                ),
                reasons=tuple(reasons),
                source_classification=(
                    item
                    .source_classification
                ),
                as_of=as_of,
            )
        )

    if not item.mapping_approved:
        reasons.append(
            "SKU_MAPPING_NOT_APPROVED"
        )

        return (
            ReservationIdentificationResult(
                order_id=item.order_id,
                status=(
                    ReservationIdentification
                    .UNKNOWN
                ),
                selected_sku_id=None,
                mapping_review_required=True,
                evidence_ids=(
                    item
                    .reservation_evidence_ids
                ),
                reasons=tuple(reasons),
                source_classification=(
                    item
                    .source_classification
                ),
                as_of=as_of,
            )
        )

    if valid_category_evidence:
        reasons.append(
            "ORDER_TIME_PREORDER_"
            "CATEGORY"
        )

    if explicit_evidence:
        reasons.append(
            "EXPLICIT_RESERVATION_"
            "EVIDENCE"
        )

    return (
        ReservationIdentificationResult(
            order_id=item.order_id,
            status=(
                ReservationIdentification
                .CONFIRMED_RESERVATION
            ),
            selected_sku_id=(
                item.selected_sku_id
            ),
            mapping_review_required=False,
            evidence_ids=(
                item
                .reservation_evidence_ids
            ),
            reasons=tuple(reasons),
            source_classification=(
                item.source_classification
            ),
            as_of=as_of,
        )
    )
