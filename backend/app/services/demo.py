"""Deterministic synthetic scenarios for the six C1 demo event types."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime

from contracts.events import CanonicalCommerceEvent

FIXED_TIME = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)


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
        {"sku_id": "sku_demo_001", "quantity": 1, "amount": {"currency": "KRW", "value": 39000}},
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
