"""Day 6 Toss POS contract-only, read-only adapter boundary."""

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


class TossPosAdapter(WriteDisabledMixin, CommerceProvider):
    """Declare the selected Toss read mode without enabling a live transport."""

    provider = Provider.TOSS_POS

    def capabilities(self) -> CapabilityMatrix:
        return CapabilityMatrix(
            provider=self.provider,
            connection_mode=ConnectionMode.API_POLL,
            products_read=CapabilityStatus.SUPPORTED,
            orders_read=CapabilityStatus.SUPPORTED,
            inventory_read=CapabilityStatus.UNSUPPORTED,
            inquiries_read=CapabilityStatus.UNKNOWN,
            incoming_stock_read=CapabilityStatus.UNKNOWN,
            inventory_write=CapabilityStatus.DISABLED_CORE,
            evidence_ref="docs/provider_capabilities/toss_pos.md",
        )

    def verify_health(self) -> dict[str, str]:
        return {
            "provider": self.provider.value,
            "status": "contract_only",
            "verification_level": "CONTRACT_ONLY",
        }

    @staticmethod
    def _contract_only(resource: str) -> None:
        raise UnsupportedCapability(
            "UNSUPPORTED_CAPABILITY: "
            f"Toss POS {resource} is CONTRACT_ONLY; live reads are not enabled on Day 6."
        )

    def read_products(self, cursor: str | None = None) -> ProviderReadPage[dict[str, Any]]:
        self._contract_only("catalog")

    def read_orders(self, cursor: str | None = None) -> ProviderReadPage[dict[str, Any]]:
        self._contract_only("orders")

    def read_inventory(self, cursor: str | None = None) -> ProviderReadPage[dict[str, Any]]:
        raise UnsupportedCapability(
            "UNSUPPORTED_CAPABILITY: Toss POS inventory reads are unsupported."
        )

    def read_inquiries(self, cursor: str | None = None) -> ProviderReadPage[dict[str, Any]]:
        raise UnsupportedCapability("UNSUPPORTED_CAPABILITY: Toss POS inquiry reads are UNKNOWN.")

    def read_incoming_stock(self, cursor: str | None = None) -> ProviderReadPage[dict[str, Any]]:
        raise UnsupportedCapability(
            "UNSUPPORTED_CAPABILITY: Toss POS incoming-stock reads are UNKNOWN."
        )
