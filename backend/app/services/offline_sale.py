"""AC-E2E-01 deterministic offline-sale shadow pipeline."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.observability import (
    CorrelationContext,
    bind_context,
    structured_record,
)
from backend.app.models.catalog import SKU, Brand, Product
from backend.app.models.commerce import InventoryLedger, InventorySnapshot
from backend.app.services.ai_mock_consumer import AIMockConsumer
from backend.app.services.ingestion.idempotency import EffectRegistry
from backend.app.services.ingestion.inbox import InboxReceipt, InMemoryInbox
from backend.app.services.inventory_ledger import (
    BusinessIdentityCollision,
    InventoryLedgerRepository,
    InventoryLedgerService,
)
from backend.app.services.inventory_projection import (
    InventoryProjection,
    build_inventory_projection,
)
from contracts.events import EventType


@dataclass
class OfflineSalePipeline:
    starting_inventory: int = 8
    snapshot_provider: str = "DEMO"
    snapshot_reserved: int | None = 0
    snapshot_quality_status: str = "CONFIRMED"
    snapshot_as_of: datetime = field(
        default_factory=lambda: datetime(1970, 1, 1, tzinfo=UTC)
    )
    snapshot_ttl_seconds: int = 300
    snapshot_age_seconds: int = 0
    inbox: InMemoryInbox = field(default_factory=InMemoryInbox)
    effects: EffectRegistry = field(default_factory=EffectRegistry)
    inventory_ledger: InventoryLedgerService = field(
        default_factory=InventoryLedgerService
    )
    inventory_projections: list[InventoryProjection] = field(
        default_factory=list
    )
    db_session_factory: Callable[[], Session] | None = None
    insights: list[dict[str, object]] = field(default_factory=list)
    business_facts: dict[tuple[str, str], tuple[str, int, float]] = field(default_factory=dict)

    ai_consumer: AIMockConsumer = field(default_factory=AIMockConsumer)
    ai_results: list[dict[str, object]] = field(default_factory=list)

    trace: list[str] = field(default_factory=list)
    external_write_count: int = 0

    def _ensure_demo_sku(
        self,
        session: Session,
        *,
        tenant_id: str,
        sku_id: str,
    ) -> None:
        if len(sku_id) > 36:
            raise ValueError("demo sku_id exceeds InventorySnapshot key length")

        existing = session.scalar(
            select(SKU).where(
                SKU.tenant_id == tenant_id,
                SKU.id == sku_id,
            )
        )
        if existing is not None:
            return

        conflicting = session.get(SKU, sku_id)
        if conflicting is not None:
            raise ValueError("DEMO_SKU_ID_TENANT_COLLISION")

        brand_name = f"Demo Synthetic Brand {tenant_id}"
        brand = session.scalar(
            select(Brand).where(
                Brand.tenant_id == tenant_id,
                Brand.canonical_name == brand_name,
            )
        )
        if brand is None:
            brand = Brand(
                tenant_id=tenant_id,
                canonical_name=brand_name,
                aliases=[],
            )
            session.add(brand)
            session.flush()

        product_name = f"Demo Synthetic Product {sku_id}"
        product = session.scalar(
            select(Product).where(
                Product.tenant_id == tenant_id,
                Product.name == product_name,
                Product.brand_id == brand.id,
            )
        )
        if product is None:
            product = Product(
                tenant_id=tenant_id,
                name=product_name,
                brand_id=brand.id,
            )
            session.add(product)
            session.flush()

        session.add(
            SKU(
                id=sku_id,
                tenant_id=tenant_id,
                product_id=product.id,
                canonical_code=sku_id,
                status="ACTIVE",
            )
        )
        session.flush()

    def _ensure_demo_snapshot(
        self,
        session: Session,
        *,
        tenant_id: str,
        sku_id: str,
    ) -> InventorySnapshot:
        self._ensure_demo_sku(
            session,
            tenant_id=tenant_id,
            sku_id=sku_id,
        )
        repository = InventoryLedgerRepository(session)
        existing = repository.latest_snapshot(
            tenant_id=tenant_id,
            sku_id=sku_id,
            provider=self.snapshot_provider,
        )
        if existing is not None:
            return existing
        if self.snapshot_as_of.tzinfo is None or self.snapshot_as_of.utcoffset() is None:
            raise ValueError("snapshot_as_of must include timezone")

        snapshot = InventorySnapshot(
            tenant_id=tenant_id,
            provider=self.snapshot_provider,
            sku_id=sku_id,
            on_hand=self.starting_inventory,
            reserved=(
                0
                if self.snapshot_reserved is None
                else self.snapshot_reserved
            ),
            as_of=self.snapshot_as_of,
        )
        session.add(snapshot)
        session.commit()
        session.refresh(snapshot)
        return snapshot

    def _replace_inventory_projection(
        self,
        projection: InventoryProjection,
    ) -> None:
        for index, current in enumerate(self.inventory_projections):
            if current.tenant_id == projection.tenant_id and current.sku_id == projection.sku_id:
                self.inventory_projections[index] = projection
                return
        self.inventory_projections.append(projection)

    def _refresh_inventory_projection(
        self,
        *,
        tenant_id: str,
        sku_id: str,
    ) -> None:
        ledger_delta = self.inventory_ledger.delta_total(
            tenant_id=tenant_id,
            sku_id=sku_id,
            snapshot_as_of=self.snapshot_as_of,
        )
        evidence = tuple(
            entry.source_event_id
            for entry in self.inventory_ledger.entries
            if entry.tenant_id == tenant_id
            and entry.sku_id == sku_id
            and entry.occurred_at > self.snapshot_as_of
        )
        expected = self.starting_inventory + ledger_delta
        available = (
            None
            if self.snapshot_reserved is None
            else expected - self.snapshot_reserved
        )
        projection = build_inventory_projection(
            tenant_id=tenant_id,
            sku_id=sku_id,
            provider=self.snapshot_provider,
            source_on_hand=self.starting_inventory,
            ledger_delta=ledger_delta,
            reserved=self.snapshot_reserved,
            confirmed_incoming=None,
            quality_status=self.snapshot_quality_status,
            ttl_seconds=self.snapshot_ttl_seconds,
            age_seconds=self.snapshot_age_seconds,
            as_of=self.snapshot_as_of,
            risk_level=(
                "UNKNOWN"
                if available is None
                else "LOW" if available > 2 else "HIGH"
            ),
            evidence=evidence,
        )
        for index, current in enumerate(self.inventory_projections):
            if current.tenant_id == tenant_id and current.sku_id == sku_id:
                self.inventory_projections[index] = projection
                return
        self.inventory_projections.append(projection)

    def _refresh_inventory_projection_from_db(
        self,
        session: Session,
        *,
        tenant_id: str,
        sku_id: str,
        snapshot: InventorySnapshot,
    ) -> None:
        repository = InventoryLedgerRepository(session)
        snapshot_as_of = snapshot.as_of
        if snapshot_as_of.tzinfo is None or snapshot_as_of.utcoffset() is None:
            snapshot_as_of = snapshot_as_of.replace(tzinfo=UTC)
        ledger_delta = repository.delta_total_after_snapshot(
            tenant_id=tenant_id,
            sku_id=sku_id,
            snapshot_as_of=snapshot_as_of,
        )
        evidence = tuple(
            session.scalars(
                select(InventoryLedger.source_event_id)
                .where(
                    InventoryLedger.tenant_id == tenant_id,
                    InventoryLedger.sku_id == sku_id,
                    InventoryLedger.occurred_at > snapshot_as_of,
                )
                .order_by(InventoryLedger.occurred_at, InventoryLedger.id)
            )
        )
        expected = snapshot.on_hand + ledger_delta
        available = (
            None
            if snapshot.reserved is None
            else expected - snapshot.reserved
        )
        projection = build_inventory_projection(
            tenant_id=tenant_id,
            sku_id=sku_id,
            provider=snapshot.provider,
            source_on_hand=snapshot.on_hand,
            ledger_delta=ledger_delta,
            reserved=snapshot.reserved,
            confirmed_incoming=None,
            quality_status=self.snapshot_quality_status,
            ttl_seconds=self.snapshot_ttl_seconds,
            age_seconds=self.snapshot_age_seconds,
            as_of=snapshot_as_of,
            risk_level=(
                "UNKNOWN"
                if available is None
                else "LOW" if available > 2 else "HIGH"
            ),
            evidence=evidence,
        )
        self._replace_inventory_projection(projection)

    def rebuild_inventory_projections(
        self,
        *,
        tenant_id: str | None = None,
    ) -> None:
        """Rebuild the in-memory cache from the persistent Demo source."""

        if self.db_session_factory is None:
            return

        with self.db_session_factory() as session:
            rows = list(
                session.scalars(
                    select(InventorySnapshot)
                    .where(
                        InventorySnapshot.provider == self.snapshot_provider,
                        *(
                            ()
                            if tenant_id is None
                            else (InventorySnapshot.tenant_id == tenant_id,)
                        ),
                    )
                    .order_by(
                        InventorySnapshot.tenant_id,
                        InventorySnapshot.sku_id,
                        InventorySnapshot.as_of.desc(),
                    )
                )
            )
            latest_by_key: dict[tuple[str, str], InventorySnapshot] = {}
            for snapshot in rows:
                key = (snapshot.tenant_id, snapshot.sku_id)
                latest_by_key.setdefault(key, snapshot)

            self.inventory_projections.clear()
            for (snapshot_tenant_id, sku_id), snapshot in latest_by_key.items():
                self._refresh_inventory_projection_from_db(
                    session,
                    tenant_id=snapshot_tenant_id,
                    sku_id=sku_id,
                    snapshot=snapshot,
                )

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
                self.trace.append(structured_record("INQUIRY_AI_DISABLED"))
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
                sku_id = str(event.payload["sku_id"])
                if self.db_session_factory is None:
                    effect_applied = self.effects.apply_business_effect_once(
                        event.tenant_id,
                        "shadow_inventory",
                        business_key_raw,
                    )
                    self.inventory_ledger.append_once(
                        tenant_id=event.tenant_id,
                        sku_id=sku_id,
                        delta=-quantity,
                        reason="OFFLINE_SALE",
                        business_key=business_key_raw,
                        source_event_id=event.event_id,
                        occurred_at=event.occurred_at,
                    )
                    self._refresh_inventory_projection(
                        tenant_id=event.tenant_id,
                        sku_id=sku_id,
                    )
                else:
                    with self.db_session_factory() as session:
                        snapshot = self._ensure_demo_snapshot(
                            session,
                            tenant_id=event.tenant_id,
                            sku_id=sku_id,
                        )
                        repository = InventoryLedgerRepository(session)
                        try:
                            ledger_added = repository.append_once(
                                tenant_id=event.tenant_id,
                                sku_id=sku_id,
                                delta=-quantity,
                                reason="OFFLINE_SALE",
                                business_key=business_key_raw,
                                source_event_id=event.event_id,
                                occurred_at=event.occurred_at,
                            )
                        except BusinessIdentityCollision:
                            self.trace.append(
                                structured_record("business_identity_collision")
                            )
                            return receipt
                        effect_applied = (
                            False
                            if not ledger_added
                            else self.effects.apply_business_effect_once(
                                event.tenant_id,
                                "shadow_inventory",
                                business_key_raw,
                            )
                        )
                        self._refresh_inventory_projection_from_db(
                            session,
                            tenant_id=event.tenant_id,
                            sku_id=sku_id,
                            snapshot=snapshot,
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
