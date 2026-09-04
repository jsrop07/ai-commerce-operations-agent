"""Synthetic contract-only providers; no real endpoint or credential."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from backend.app.adapters.providers.base import (
    CommerceProvider,
    ProviderNonRetryableError,
    ProviderTransientError,
    UnsupportedCapability,
    WriteDisabledMixin,
)
from contracts.events import Provider
from contracts.providers import (
    CapabilityMatrix,
    CapabilityStatus,
    ConnectionMode,
    ProviderReadPage,
)


class MockCommerceProvider(WriteDisabledMixin, CommerceProvider):
    provider: Provider

    def __init__(self, *, failure: str | None = None) -> None:
        self.failure = failure
        self.request_attempts = 0

    def capabilities(self) -> CapabilityMatrix:
        return CapabilityMatrix(
            provider=self.provider,
            connection_mode=ConnectionMode.CONTRACT_ONLY,
            products_read=CapabilityStatus.VERIFY,
            orders_read=CapabilityStatus.VERIFY,
            inventory_read=CapabilityStatus.VERIFY,
            inquiries_read=CapabilityStatus.UNKNOWN,
            incoming_stock_read=CapabilityStatus.VERIFY,
        )

    def verify_health(self) -> dict[str, str]:
        return {"provider": self.provider, "status": "contract_only"}

    def _read(
        self,
        resource: str,
        items: list[dict[str, Any]],
        cursor: str | None = None,
    ) -> ProviderReadPage[dict[str, Any]]:
        self.request_attempts += 1

        if self.failure == "timeout":
            raise TimeoutError(f"{self.provider} timeout")
        if self.failure == "5xx":
            raise ProviderTransientError(f"{self.provider} transient failure")
        if self.failure == "schema":
            raise ProviderNonRetryableError(f"{self.provider} schema mismatch")

        if cursor not in {None, "page-2"}:
            raise ProviderNonRetryableError(
                f"{self.provider} invalid cursor: {cursor}"
            )

        now = datetime.now(UTC)

        if len(items) <= 1:
            page_items = items
            next_cursor = None
            has_more = False
        elif cursor is None:
            page_items = items[:1]
            next_cursor = "page-2"
            has_more = True
        else:
            page_items = items[1:]
            next_cursor = None
            has_more = False

        return ProviderReadPage(
            provider=self.provider,
            resource=resource,
            items=page_items,
            next_cursor=next_cursor,
            watermark=now,
            has_more=has_more,
            request_count=1,
            source_as_of=now,
        )

    def read_products(
        self, cursor: str | None = None
    ) -> ProviderReadPage[dict[str, Any]]:
        return self._read(
            "products",
            [
                {"source_id": f"{self.provider.lower()}-product-001"},
                {"source_id": f"{self.provider.lower()}-product-002"},
            ],
            cursor,
        )

    def read_orders(
        self, cursor: str | None = None
    ) -> ProviderReadPage[dict[str, Any]]:
        return self._read(
            "orders",
            [
                {"source_id": f"{self.provider.lower()}-order-001"},
                {"source_id": f"{self.provider.lower()}-order-002"},
            ],
            cursor,
        )

    def read_inventory(
        self, cursor: str | None = None
    ) -> ProviderReadPage[dict[str, Any]]:
        return self._read(
            "inventory",
            [
                {"sku_id": "sku_demo_001", "on_hand": 8},
                {"sku_id": "sku_demo_002", "on_hand": 3},
            ],
            cursor,
        )

    def read_inquiries(self, cursor: str | None = None) -> ProviderReadPage[dict[str, Any]]:
        if self.capabilities().inquiries_read in {
            CapabilityStatus.UNSUPPORTED,
            CapabilityStatus.UNKNOWN,
        }:
            raise UnsupportedCapability("UNSUPPORTED_CAPABILITY: inquiries not confirmed")
        return self._read(
            "inquiries",
            [
                {"source_id": "inquiry_demo_001"},
                {"source_id": "inquiry_demo_002"},
            ],
            cursor,
        )

    def read_incoming_stock(
        self, cursor: str | None = None
    ) -> ProviderReadPage[dict[str, Any]]:
        return self._read(
            "incoming_stock",
            [
                {"sku_id": "sku_demo_001", "quantity": 3},
                {"sku_id": "sku_demo_002", "quantity": 2},
            ],
            cursor,
        )


class Cafe24MockProvider(MockCommerceProvider):
    provider = Provider.CAFE24


class TossPosMockProvider(MockCommerceProvider):
    provider = Provider.TOSS_POS

    def read_offline_sales(self) -> ProviderReadPage[dict[str, Any]]:
        from backend.app.services.demo import DEMO_SCENARIOS

        event = dict(DEMO_SCENARIOS["offline_sale"])
        return self._read("offline_sales", [event])


class EcountMockProvider(MockCommerceProvider):
    provider = Provider.ECOUNT
