"""D09-BE-03 예약→발주→입고→출고 상태 전이."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class ReservationFlowState(StrEnum):
    RESERVATION_CONFIRMED = (
        "RESERVATION_CONFIRMED"
    )
    PURCHASE_ORDER_PENDING = (
        "PURCHASE_ORDER_PENDING"
    )
    PURCHASE_ORDER_CONFIRMED = (
        "PURCHASE_ORDER_CONFIRMED"
    )
    INCOMING_CONFIRMED = (
        "INCOMING_CONFIRMED"
    )
    RECEIVED = "RECEIVED"
    READY_TO_SHIP = "READY_TO_SHIP"
    SHIPPED = "SHIPPED"


class TransitionOutcome(StrEnum):
    ALLOWED = "ALLOWED"
    DENIED = "DENIED"


_ALLOWED_TRANSITIONS = {
    ReservationFlowState.RESERVATION_CONFIRMED: {
        ReservationFlowState.PURCHASE_ORDER_PENDING,
    },
    ReservationFlowState.PURCHASE_ORDER_PENDING: {
        ReservationFlowState.PURCHASE_ORDER_CONFIRMED,
    },
    ReservationFlowState.PURCHASE_ORDER_CONFIRMED: {
        ReservationFlowState.INCOMING_CONFIRMED,
    },
    ReservationFlowState.INCOMING_CONFIRMED: {
        ReservationFlowState.RECEIVED,
    },
    ReservationFlowState.RECEIVED: {
        ReservationFlowState.READY_TO_SHIP,
    },
    ReservationFlowState.READY_TO_SHIP: {
        ReservationFlowState.SHIPPED,
    },
    ReservationFlowState.SHIPPED: set(),
}


@dataclass(frozen=True)
class ReservationTransitionAudit:
    reservation_id: str

    from_state: str
    to_state: str

    actor: str
    evidence_ids: tuple[str, ...]

    occurred_at: datetime
    as_of: datetime

    source_system: str
    source_classification: str

    outcome: str
    reason: str


@dataclass(frozen=True)
class ReservationTransitionResult:
    reservation_id: str

    previous_state: ReservationFlowState
    current_state: ReservationFlowState

    audit: ReservationTransitionAudit


class ReservationTransitionError(
    ValueError
):
    """허용되지 않은 예약 상태 전이."""


@dataclass
class ReservationStateMachine:
    """외부 Write 없이 상태 전이 규칙과 Audit만 관리."""

    audit: list[
        ReservationTransitionAudit
    ] = field(default_factory=list)

    def transition(
        self,
        *,
        reservation_id: str,
        current_state: (
            ReservationFlowState
            | str
        ),
        target_state: (
            ReservationFlowState
            | str
        ),
        actor: str,
        evidence_ids: tuple[str, ...],
        occurred_at: datetime,
        as_of: datetime | None = None,
        source_system: str,
        source_classification: str,
    ) -> ReservationTransitionResult:
        if not reservation_id:
            raise ValueError(
                "reservation_id is required"
            )

        if not actor:
            raise ValueError(
                "actor is required"
            )

        if not evidence_ids:
            raise ValueError(
                "evidence_ids are required"
            )

        current = (
            ReservationFlowState(
                current_state
            )
        )
        target = (
            ReservationFlowState(
                target_state
            )
        )

        effective_as_of = (
            as_of
            or datetime.now(UTC)
        )

        # 현재 실제 연동되지 않은 Source는
        # 실제 완료 근거처럼 사용할 수 없다.
        blocked_reason = (
            self
            ._external_source_block_reason(
                target_state=target,
                source_system=source_system,
                source_classification=(
                    source_classification
                ),
            )
        )

        if blocked_reason is not None:
            audit = self._append_audit(
                reservation_id=(
                    reservation_id
                ),
                current_state=current,
                target_state=target,
                actor=actor,
                evidence_ids=evidence_ids,
                occurred_at=occurred_at,
                as_of=effective_as_of,
                source_system=source_system,
                source_classification=(
                    source_classification
                ),
                outcome=(
                    TransitionOutcome.DENIED
                ),
                reason=blocked_reason,
            )

            raise ReservationTransitionError(
                audit.reason
            )

        allowed_targets = (
            _ALLOWED_TRANSITIONS[
                current
            ]
        )

        if target not in allowed_targets:
            audit = self._append_audit(
                reservation_id=(
                    reservation_id
                ),
                current_state=current,
                target_state=target,
                actor=actor,
                evidence_ids=evidence_ids,
                occurred_at=occurred_at,
                as_of=effective_as_of,
                source_system=source_system,
                source_classification=(
                    source_classification
                ),
                outcome=(
                    TransitionOutcome.DENIED
                ),
                reason=(
                    "INVALID_STATE_TRANSITION"
                ),
            )

            raise ReservationTransitionError(
                audit.reason
            )

        audit = self._append_audit(
            reservation_id=reservation_id,
            current_state=current,
            target_state=target,
            actor=actor,
            evidence_ids=evidence_ids,
            occurred_at=occurred_at,
            as_of=effective_as_of,
            source_system=source_system,
            source_classification=(
                source_classification
            ),
            outcome=(
                TransitionOutcome.ALLOWED
            ),
            reason="STATE_TRANSITION_ALLOWED",
        )

        return ReservationTransitionResult(
            reservation_id=reservation_id,
            previous_state=current,
            current_state=target,
            audit=audit,
        )

    def _append_audit(
        self,
        *,
        reservation_id: str,
        current_state: ReservationFlowState,
        target_state: ReservationFlowState,
        actor: str,
        evidence_ids: tuple[str, ...],
        occurred_at: datetime,
        as_of: datetime,
        source_system: str,
        source_classification: str,
        outcome: TransitionOutcome,
        reason: str,
    ) -> ReservationTransitionAudit:
        audit = ReservationTransitionAudit(
            reservation_id=(
                reservation_id
            ),
            from_state=current_state.value,
            to_state=target_state.value,
            actor=actor,
            evidence_ids=evidence_ids,
            occurred_at=occurred_at,
            as_of=as_of,
            source_system=source_system,
            source_classification=(
                source_classification
            ),
            outcome=outcome.value,
            reason=reason,
        )

        self.audit.append(audit)

        return audit

    @staticmethod
    def _external_source_block_reason(
        *,
        target_state: ReservationFlowState,
        source_system: str,
        source_classification: str,
    ) -> str | None:
        source = source_system.upper()

        # eCount 발주 실제 연동 전.
        if (
            source == "ECOUNT"
            and target_state
            == (
                ReservationFlowState
                .PURCHASE_ORDER_CONFIRMED
            )
            and source_classification
            in {
                "CONTRACT_ONLY",
                "BLOCKED",
            }
        ):
            return (
                "ECOUNT_PURCHASE_ORDER_"
                "NOT_ACTUALLY_INTEGRATED"
            )

        # Gmail 회신 실제 연동 전.
        if (
            source == "GMAIL"
            and target_state
            in {
                ReservationFlowState
                .PURCHASE_ORDER_CONFIRMED,
                ReservationFlowState
                .INCOMING_CONFIRMED,
            }
            and source_classification
            in {
                "CONTRACT_ONLY",
                "BLOCKED",
            }
        ):
            return (
                "GMAIL_REPLY_"
                "NOT_ACTUALLY_INTEGRATED"
            )

        return None