import pytest

from backend.app.adapters.providers import (
    Cafe24MockProvider,
    EcountMockProvider,
    TossPosMockProvider,
)
from backend.app.adapters.providers.base import UnsupportedCapability
from contracts.providers import CapabilityStatus, ConnectionMode


@pytest.mark.parametrize(
    "provider_type", [Cafe24MockProvider, TossPosMockProvider, EcountMockProvider]
)
def test_mock_provider_contract_only_reads_and_denies_writes(provider_type: type) -> None:
    provider = provider_type()
    capabilities = provider.capabilities()
    assert capabilities.connection_mode == ConnectionMode.CONTRACT_ONLY
    assert capabilities.inventory_write == CapabilityStatus.DISABLED_CORE
    assert provider.read_products().items
    assert provider.read_orders().items
    assert provider.read_inventory().items
    assert provider.read_incoming_stock().items
    with pytest.raises(UnsupportedCapability):
        provider.read_inquiries()
    with pytest.raises(UnsupportedCapability):
        provider.execute_write({"action": "change_inventory"})
