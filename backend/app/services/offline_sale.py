"""AC-E2E-01 deterministic offline-sale shadow pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.app.core.observability import (
    CorrelationContext,
    bind_context,
    structured_record,
)
from backend.app.services.ai_mock_consumer import AIMockConsumer
from backend.app.services.ingestion.idempotency import EffectRegistry
from backend.app.services.ingestion.inbox import InboxReceipt, InMemoryInbox
from contracts.events import EventType


@dataclass
class OfflineSalePipeline:
    starting_inventory: int = 8
    inbox: InMemoryInbox = field(default_factory=InMemoryInbox)
    effects: EffectRegistry = field(default_factory=EffectRegistry)
    insights: list[dict[str, object]] = field(default_factory=list)
    business_facts: dict[tuple[str, str], tuple[str, int, float]] = field(default_factory=dict)

    ai_consumer: AIMockConsumer = field(default_factory=AIMockConsumer)
    ai_results: list[dict[str, object]] = field(default_factory=list)

    trace: list[str] = field(default_factory=list)
    external_write_count: int = 0

    def process(
        self,
        raw: dict[str, object],
        environment: str = "DEMO",
        request_id: str | None = None,
        trace_id: str | None = None,
    ) -> InboxReceipt:
        event, receipt = self.inbox.ingest(raw)
        if event is None:
            return receipt
        with bind_context(
            CorrelationContext(
                request_id=request_id or f"req_{event.event_id}",
                trace_id=trace_id or f"tr_{event.event_id}",
                correlation_id=event.correlation_id,
                tenant_id=event.tenant_id,
                environment=environment,
                event_id=event.event_id,
            )
        ):
            self.trace.append(structured_record("event_received", inbox_status=receipt.status))
            if event.event_type == EventType.INQUIRY_RECEIVED:
                consumer = "mock_ai_inquiry"
                if self.effects.was_applied(event.tenant_id, consumer, event.idempotency_key):
                    self.trace.append(structured_record("mock_ai_inquiry_replayed"))
                    return receipt

                ai_result = self.ai_consumer.classify_inquiry(
                    request_id=request_id or f"req_{event.event_id}",
                    trace_id=trace_id or f"tr_{event.event_id}",
                    intent=str(event.payload["mock_intent"]),
                    risk=str(event.payload["mock_risk"]),
                    evidence_ids=[event.event_id],
                )

                if not self.effects.apply_once(event.tenant_id, consumer, event.idempotency_key):
                    self.trace.append(structured_record("mock_ai_inquiry_replayed"))
                    return receipt

                self.ai_results.append(ai_result)

                self.trace.append(
                    structured_record(
                        "mock_ai_inquiry_route",
                        route=ai_result["route"],
                    )
                )

                return receipt
            if event.event_type != EventType.OFFLINE_SALE_RECORDED:
                return receipt
            business_key_raw = event.payload.get("business_identity_key")
            quantity = int(event.payload["quantity"])

            if isinstance(business_key_raw, str) and business_key_raw:
                fact_key = (event.tenant_id, business_key_raw)
                fact = (str(event.payload.get("sku_id")), quantity, event.occurred_at.timestamp())
                previous_fact = self.business_facts.get(fact_key)
                if previous_fact is not None and previous_fact != fact:
                    self.trace.append(structured_record("business_identity_collision"))
                    return receipt
                self.business_facts[fact_key] = fact
                effect_applied = self.effects.apply_business_effect_once(
                    event.tenant_id,
                    "shadow_inventory",
                    business_key_raw,
                )
            else:
                # Legacy source-only identity remains available for Demo fixtures only.
                if environment != "DEMO":
                    self.trace.append(structured_record("business_identity_required"))
                    return receipt
                effect_applied = self.effects.apply_once(
                    event.tenant_id,
                    "shadow_inventory",
                    event.idempotency_key,
                )

            if not effect_applied:
                self.trace.append(structured_record("effect_replayed"))
                return receipt
            quantity = int(event.payload["quantity"])
            expected = self.starting_inventory - quantity
            insight = {
                "insight_id": f"ins_{event.event_id}",
                "type": "INVENTORY_RISK",
                "severity": "LOW" if expected > 2 else "HIGH",
                "confidence": 1.0,
                "summary": "오프라인 판매가 예상 재고에 반영되었습니다.",
                "calculation": {
                    "starting_inventory": self.starting_inventory,
                    "sold": quantity,
                    "expected_inventory": expected,
                },
                "evidence_ids": [event.event_id],
                "correlation_id": event.correlation_id,
                "model_run_id": None,
                "rule_version": "shadow-inventory-v1",
            }
            self.insights.append(insight)
            self.trace.append(structured_record("shadow_inventory_effect", expected=expected))
            return receipt
