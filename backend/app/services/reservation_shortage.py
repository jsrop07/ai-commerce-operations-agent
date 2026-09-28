"""D09-BE-02 예약 확보·입고·부족수량 계산."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum


class IncomingConfirmation(StrEnum):
    CONFIRMED = "CONFIRMED"
    TENTATIVE = "TENTATIVE"


class IncomingFreshness(StrEnum):
    FRESH = "FRESH"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class IncomingEvidence:
    evidence_id: str
    quantity: int | None
    confirmation_status: str
    quality_status: str
    freshness: str
    source_classification: str
    as_of: datetime | None = None


@dataclass(frozen=True)
class ExcludedIncoming:
    evidence_id: str
    quantity: int | None
    reason: str
    source_classification: str


@dataclass(frozen=True)
class ReservationShortageResult:
    required_qty: int
    secured_qty: int | None

    confirmed_incoming_qty: int | None
    tentative_incoming_qty: int

    shortage: int | None

    calculation_status: str
    excluded_incoming: tuple[ExcludedIncoming, ...]

    evidence_ids: tuple[str, ...]
    as_of: datetime


def calculate_reservation_shortage(
    *,
    required_qty: int,
    secured_qty: int | None,
    incoming: tuple[IncomingEvidence, ...] = (),
    as_of: datetime | None = None,
) -> ReservationShortageResult:
    """확정·신뢰 가능한 입고만 부족수량에서 차감한다."""

    if required_qty <= 0:
        raise ValueError(
            "required_qty must be > 0"
        )

    if secured_qty is not None and secured_qty < 0:
        raise ValueError(
            "secured_qty must be >= 0"
        )

    confirmed_total = 0
    tentative_total = 0

    confirmed_quantity_unknown = False

    excluded: list[ExcludedIncoming] = []
    evidence_ids: list[str] = []

    for item in incoming:
        if item.evidence_id:
            evidence_ids.append(
                item.evidence_id
            )

        # tentative는 확정 입고에서 차감하지 않는다.
        if (
            item.confirmation_status
            == IncomingConfirmation.TENTATIVE
        ):
            if item.quantity is not None:
                tentative_total += item.quantity

            excluded.append(
                ExcludedIncoming(
                    evidence_id=item.evidence_id,
                    quantity=item.quantity,
                    reason="TENTATIVE",
                    source_classification=(
                        item.source_classification
                    ),
                )
            )
            continue

        # 품질 차단 데이터는 사용하지 않는다.
        if item.quality_status != "CONFIRMED":
            excluded.append(
                ExcludedIncoming(
                    evidence_id=item.evidence_id,
                    quantity=item.quantity,
                    reason=(
                        "SOURCE_QUALITY_BLOCKED"
                    ),
                    source_classification=(
                        item.source_classification
                    ),
                )
            )
            continue

        # stale/unknown 입고도 확정 수량에서 제외.
        if (
            item.freshness
            != IncomingFreshness.FRESH
        ):
            excluded.append(
                ExcludedIncoming(
                    evidence_id=item.evidence_id,
                    quantity=item.quantity,
                    reason=(
                        "STALE"
                        if item.freshness
                        == IncomingFreshness.STALE
                        else "FRESHNESS_UNKNOWN"
                    ),
                    source_classification=(
                        item.source_classification
                    ),
                )
            )
            continue

        # 확정·신뢰·fresh인데 quantity가 null이면
        # 0으로 바꾸지 않는다.
        if item.quantity is None:
            confirmed_quantity_unknown = True

            excluded.append(
                ExcludedIncoming(
                    evidence_id=item.evidence_id,
                    quantity=None,
                    reason="QUANTITY_UNKNOWN",
                    source_classification=(
                        item.source_classification
                    ),
                )
            )
            continue

        if item.quantity < 0:
            raise ValueError(
                "incoming quantity must be >= 0"
            )

        confirmed_total += item.quantity

    # 확보수량 자체가 미상인 경우 계산 불가.
    if secured_qty is None:
        confirmed_incoming_qty = (
            None
            if confirmed_quantity_unknown
            else confirmed_total
        )

        shortage = None
        calculation_status = (
            "SECURED_QTY_UNKNOWN"
        )

    # 사용할 수 있어야 할 확정 입고수량이
    # null인 경우에도 임의로 0 처리하지 않는다.
    elif confirmed_quantity_unknown:
        confirmed_incoming_qty = None
        shortage = None
        calculation_status = (
            "CONFIRMED_INCOMING_UNKNOWN"
        )

    else:
        confirmed_incoming_qty = (
            confirmed_total
        )

        shortage = max(
            required_qty
            - secured_qty
            - confirmed_total,
            0,
        )

        calculation_status = "CONFIRMED"

    return ReservationShortageResult(
        required_qty=required_qty,
        secured_qty=secured_qty,
        confirmed_incoming_qty=(
            confirmed_incoming_qty
        ),
        tentative_incoming_qty=(
            tentative_total
        ),
        shortage=shortage,
        calculation_status=(
            calculation_status
        ),
        excluded_incoming=tuple(excluded),
        evidence_ids=tuple(
            dict.fromkeys(evidence_ids)
        ),
        as_of=as_of or datetime.now(UTC),
    )