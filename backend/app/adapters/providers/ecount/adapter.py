"""Day 6 eCount contract-only, read-only adapter boundary."""

from __future__ import annotations

from typing import Any

from backend.app.adapters.providers.base import (
    CommerceProvider,
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


class EcountAdapter(WriteDisabledMixin, CommerceProvider):
    """Declare eCount read decisions while blocking untrusted live inventory."""

    provider = Provider.ECOUNT

    def capabilities(self) -> CapabilityMatrix:
        return CapabilityMatrix(
            provider=self.provider,
            connection_mode=ConnectionMode.API_POLL,
            products_read=CapabilityStatus.SUPPORTED,
            orders_read=CapabilityStatus.UNKNOWN,
            inventory_read=CapabilityStatus.VERIFY,
            inquiries_read=CapabilityStatus.UNKNOWN,
            incoming_stock_read=CapabilityStatus.UNKNOWN,
            inventory_write=CapabilityStatus.DISABLED_CORE,
            evidence_ref="docs/provider_capabilities/ecount.md",
        )

    def verify_health(self) -> dict[str, str]:
        return {
            "provider": self.provider.value,
            "status": "contract_only",
            "verification_level": "CONTRACT_ONLY",
            "actual_inventory_source_quality": "SOURCE_QUALITY_BLOCKED",
        }

    @staticmethod
    def _contract_only(resource: str) -> None:
        raise UnsupportedCapability(
            "UNSUPPORTED_CAPABILITY: "
            f"eCount {resource} is CONTRACT_ONLY; live reads are not enabled on Day 6."
        )

    def read_products(self, cursor: str | None = None) -> ProviderReadPage[dict[str, Any]]:
        self._contract_only("items")

    def read_orders(self, cursor: str | None = None) -> ProviderReadPage[dict[str, Any]]:
        raise UnsupportedCapability(
            "UNSUPPORTED_CAPABILITY: eCount sale reads are UNKNOWN/BLOCKED."
        )

    def read_inventory(self, cursor: str | None = None) -> ProviderReadPage[dict[str, Any]]:
        raise UnsupportedCapability(
            "UNSUPPORTED_CAPABILITY: eCount actual inventory is SOURCE_QUALITY_BLOCKED."
        )

    def read_inquiries(self, cursor: str | None = None) -> ProviderReadPage[dict[str, Any]]:
        raise UnsupportedCapability("UNSUPPORTED_CAPABILITY: eCount inquiry reads are UNKNOWN.")

    def read_incoming_stock(self, cursor: str | None = None) -> ProviderReadPage[dict[str, Any]]:
        raise UnsupportedCapability(
            "UNSUPPORTED_CAPABILITY: eCount incoming-stock reads are UNKNOWN/BLOCKED."
        )
