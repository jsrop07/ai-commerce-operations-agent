"""Deterministic synthetic scenarios for the six C1 demo event types."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from zoneinfo import ZoneInfo

from fastapi.encoders import jsonable_encoder

from backend.app.core.config import Environment
from backend.app.services.delay_impact import (
    FreshnessStatus,
    IncomingDateChange,
    IncomingDateEvidence,
    LaunchImpactCandidate,
    ReservationImpactCandidate,
    ScheduledTask,
    SourceClassification,
    SourceQuality,
    calculate_delay_impact,
)
from backend.app.services.reservation_projection import build_reservation_risk_projection
from backend.app.services.reservation_service import (
    ReservationIdentification,
    ReservationIdentificationInput,
    identify_reservation,
)
from backend.app.services.reservation_shortage import (
    IncomingEvidence,
    calculate_reservation_shortage,
)
from backend.app.services.reservation_tasks import register_reservation_risk_projection
from contracts.events import CanonicalCommerceEvent

FIXED_TIME = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
SCHEDULE_C08_SNAPSHOT_ID = "c08-r08-synthetic-v1"


def prepare_synthetic_schedule_c08(app_state, *, tenant_id: str) -> tuple[int, int, str, str]:
    """Register the fixed C08 calculation in memory after an explicit Demo call."""
    settings = app_state.settings
    if settings.environment != Environment.DEMO or tenant_id != settings.tenant_id:
        raise ValueError("SYNTHETIC_SCHEDULE_DEMO_ONLY")

    seoul = ZoneInfo("Asia/Seoul")
    before = datetime(2026, 10, 10, 10, 0, tzinfo=seoul)
    as_of = datetime(2026, 10, 1, 9, 0, tzinfo=seoul)
    impact = calculate_delay_impact(
        change=IncomingDateChange(
            incoming_id="incoming-demo-001",
            before_expected_at=before,
            after_expected_at=before + timedelta(hours=72),
            evidence=IncomingDateEvidence(
                source_id="fixture:incoming-delay-3d",
                source_classification=SourceClassification.FIXTURE,
                as_of=as_of,
                freshness=FreshnessStatus.FRESH,
                quality=SourceQuality.TENTATIVE,
                evidence_ids=("ev-fixture-incoming-001",),
            ),
        ),
        tasks=(
            ScheduledTask("task-inspection", datetime(2026, 10, 10, 18, 0, tzinfo=seoul), True,
                          incoming_id="incoming-demo-001"),
            ScheduledTask("task-product-page", datetime(2026, 10, 11, 18, 0, tzinfo=seoul), True,
                          lag_hours=8, incoming_id="incoming-demo-001"),
            ScheduledTask("task-unrelated", datetime(2026, 10, 12, 18, 0, tzinfo=seoul), False),
            ScheduledTask("task-other-incoming", before, True,
                          incoming_id="incoming-demo-002"),
        ),
        reservations=(ReservationImpactCandidate("reservation-001", "incoming-demo-001"),),
        launch_events=(
            LaunchImpactCandidate("launch-001", datetime(2026, 10, 15, 10, 0, tzinfo=seoul),
                                  True, "incoming-demo-001"),
            LaunchImpactCandidate("launch-other-incoming", before, True,
                                  "incoming-demo-002"),
        ),
    )
    impact_data = jsonable_encoder(impact)
    canonical = json.dumps(
        {"snapshot_id": SCHEDULE_C08_SNAPSHOT_ID, "data_mode": "SYNTHETIC_DEMO",
         "impact": impact_data},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )
    snapshot_sha256 = sha256(canonical.encode("utf-8")).hexdigest()
    projection = {
        **impact_data,
        "tenant_id": tenant_id,
        "data_mode": "SYNTHETIC_DEMO",
        "snapshot_id": SCHEDULE_C08_SNAPSHOT_ID,
        "snapshot_sha256": snapshot_sha256,
    }

    # Reuse the existing Demo preparation lock for atomic in-memory registration.
    with app_state.reservation_demo_prepare_lock:
        matches = [
            item for item in app_state.schedule_delay_impact_projections
            if (item.get("incoming_id") if isinstance(item, dict)
                else getattr(item, "incoming_id", None)) == impact.incoming_id
        ]
        if matches:
            if len(matches) != 1 or matches[0] != projection:
                raise ValueError("SYNTHETIC_SCHEDULE_IDENTITY_CONFLICT")
            return 0, 1, SCHEDULE_C08_SNAPSHOT_ID, snapshot_sha256
        app_state.schedule_delay_impact_projections.append(projection)
        return 1, 1, SCHEDULE_C08_SNAPSHOT_ID, snapshot_sha256


def _event(number: int, event_type: str, payload: dict[str, object]) -> dict[str, object]:
    source = "TOSS_POS" if event_type == "offline_sale.recorded" else "DEMO"
    source_event_id = f"synthetic-{number:02d}"
    schema_version = "1.0"
    return {
        "event_id": f"evt_demo_{number:02d}",
        "event_type": event_type,
        "schema_version": schema_version,
        "idempotency_key": f"{source}:{source_event_id}:{schema_version}",
        "tenant_id": "demo_store",
        "source": source,
        "source_event_id": source_event_id,
        "occurred_at": FIXED_TIME.isoformat().replace("+00:00", "Z"),
        "ingested_at": FIXED_TIME.isoformat().replace("+00:00", "Z"),
        "correlation_id": f"corr_demo_{number:02d}",
        "payload": payload,
    }


DEMO_SCENARIOS: dict[str, dict[str, object]] = {
    "offline_sale": _event(
        2,
        "offline_sale.recorded",
        {
            "sku_id": "sku_demo_001",
            "quantity": 1,
            "amount": {"currency": "KRW", "value": 39000},
            "business_identity_key": "demo-business-sale-001",
        },
    ),
    "reservation_shortage": _event(
        3,
        "reservation.shortage_detected",
        {"sku_id": "sku_demo_002", "reserved": 5, "available": 1, "confirmed_incoming": 2},
    ),
    "incoming_delay": _event(
        6, "incoming.delayed", {"sku_id": "sku_demo_003", "delay_days": 3}
    ),
    "product_inquiry": _event(
        4,
        "inquiry.received",
        {
            "sanitized_text": "기존 문장 그대로",
            "pii_status": "clean",
            "mock_intent": "PRODUCT_INFO",
            "mock_risk": "LOW",
        },
    ),
    "risk_inquiry": _event(
        5,
        "inquiry.received",
        {
            "sanitized_text": "기존 값 유지",
            "pii_status": "clean",
            "mock_intent": "REFUND_CANCEL",
            "mock_risk": "PROHIBITED",
        },
    ),
}
DEMO_SCENARIOS["duplicate_event"] = deepcopy(DEMO_SCENARIOS["offline_sale"])

SCENARIO_EXPECTATIONS: dict[str, dict[str, object]] = {
    "offline_sale": {"inventory_delta": -1},
    "reservation_shortage": {"shortage_quantity": 2},
    "incoming_delay": {"delay_days": 3, "original_schedule_changed": False},
    "product_inquiry": {"answer_is_draft": True, "auto_send": False},
    "risk_inquiry": {"requires_human_review": True, "provider_call_count": 0},
    "duplicate_event": {"processed_effect_count": 1},
}


def scenario(name: str) -> CanonicalCommerceEvent:
    return CanonicalCommerceEvent.model_validate(deepcopy(DEMO_SCENARIOS[name]))


def duplicate_offline_sale_fixture() -> list[CanonicalCommerceEvent]:
    return [scenario("offline_sale"), scenario("duplicate_event")]


@dataclass(frozen=True)
class SyntheticReservationInput:
    """Curated Day9 domain inputs; no real order or customer row is loaded."""

    reservation_id: str
    sku_id: str
    required_qty: int
    secured_qty: int | None
    incoming: tuple[IncomingEvidence, ...]
    aging_hours: int = 0


# Separate C03-style Demo inputs. The C01 event's reserved/available fields
# are not converted into secured_qty or an actual C02 aggregate.
SYNTHETIC_RESERVATION_INPUTS = (
    SyntheticReservationInput(
        reservation_id="demo_reservation_r06_known",
        sku_id="sku_demo_reservation_known",
        required_qty=6,
        secured_qty=2,
        incoming=(
            IncomingEvidence(
                evidence_id="demo_incoming_confirmed_known", quantity=1,
                confirmation_status="CONFIRMED", quality_status="CONFIRMED",
                freshness="FRESH", source_classification="SYNTHETIC_DEMO",
            ),
            IncomingEvidence(
                evidence_id="demo_incoming_tentative_known", quantity=3,
                confirmation_status="TENTATIVE", quality_status="CONFIRMED",
                freshness="FRESH", source_classification="SYNTHETIC_DEMO",
            ),
        ),
    ),
    SyntheticReservationInput(
        reservation_id="demo_reservation_r06_unknown",
        sku_id="sku_demo_reservation_unknown",
        required_qty=4,
        secured_qty=None,
        incoming=(IncomingEvidence(
            evidence_id="demo_incoming_quantity_unknown", quantity=None,
            confirmation_status="CONFIRMED", quality_status="CONFIRMED",
            freshness="FRESH", source_classification="SYNTHETIC_DEMO",
        ),),
    ),
)


def prepare_synthetic_reservations(app_state, *, tenant_id: str) -> tuple[int, int]:
    """Explicit, in-memory Demo caller for the existing Day9 services."""
    settings = app_state.settings
    if settings.environment != Environment.DEMO or tenant_id != settings.tenant_id:
        raise ValueError("SYNTHETIC_RESERVATION_DEMO_ONLY")

    created = 0
    with app_state.reservation_demo_prepare_lock:
        for seed in SYNTHETIC_RESERVATION_INPUTS:
            matches = [item for item in app_state.reservation_risk_projections
                       if item.tenant_id == tenant_id
                       and item.reservation_id == seed.reservation_id]
            if matches:
                if (len(matches) != 1 or matches[0].data_mode != "SYNTHETIC_DEMO"
                        or matches[0].source_classification != "SYNTHETIC_DEMO"):
                    raise ValueError("SYNTHETIC_RESERVATION_IDENTITY_CONFLICT")
                continue

            as_of = datetime.now(UTC)
            identified = identify_reservation(ReservationIdentificationInput(
                order_id=f"synthetic_{seed.reservation_id}",
                order_category_snapshot="PREORDER",
                reservation_evidence_ids=(f"{seed.reservation_id}_category_snapshot",),
                mapping_approved=True, selected_sku_id=seed.sku_id,
                source_classification="SYNTHETIC_DEMO", as_of=as_of,
            ))
            if (identified.status != ReservationIdentification.CONFIRMED_RESERVATION
                    or identified.selected_sku_id != seed.sku_id):
                raise ValueError("SYNTHETIC_RESERVATION_IDENTIFICATION_FAILED")

            shortage = calculate_reservation_shortage(
                required_qty=seed.required_qty, secured_qty=seed.secured_qty,
                incoming=tuple(replace(item, as_of=as_of) for item in seed.incoming),
                as_of=as_of,
            )
            priority, reason = app_state.reservation_task_service._priority_for_aging(
                seed.aging_hours,
            )
            projection = build_reservation_risk_projection(
                reservation_id=seed.reservation_id, tenant_id=tenant_id,
                sku_id=identified.selected_sku_id,
                required_qty=shortage.required_qty,
                secured_qty=shortage.secured_qty,
                confirmed_incoming_qty=shortage.confirmed_incoming_qty,
                tentative_incoming_qty=shortage.tentative_incoming_qty,
                shortage=shortage.shortage,
                affected_order_ids=(), aging_hours=seed.aging_hours,
                priority=priority, priority_reason=reason,
                calculation_status=shortage.calculation_status,
                evidence=tuple(dict.fromkeys(
                    (*identified.evidence_ids, *shortage.evidence_ids),
                )),
                source_classification="SYNTHETIC_DEMO",
                quality_status=("CONFIRMED" if shortage.calculation_status == "CONFIRMED"
                                else "UNKNOWN"),
                as_of=as_of, data_mode="SYNTHETIC_DEMO",
            )
            register_reservation_risk_projection(app_state, projection)
            created += 1

        total = sum(
            item.tenant_id == tenant_id and item.data_mode == "SYNTHETIC_DEMO"
            and item.reservation_id in {
                seed.reservation_id for seed in SYNTHETIC_RESERVATION_INPUTS
            }
            for item in app_state.reservation_risk_projections
        )
    return created, total
