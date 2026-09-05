import pytest

from backend.app.adapters.providers.base import UnsupportedCapability
from backend.app.adapters.providers.ecount import EcountAdapter
from contracts.providers import CapabilityStatus, ConnectionMode


def test_ecount_adapter_declares_contract_and_source_quality_separately() -> None:
    adapter = EcountAdapter()
    health = adapter.verify_health()

    assert adapter.capabilities().connection_mode == ConnectionMode.API_POLL
    assert adapter.capabilities().inventory_read == CapabilityStatus.VERIFY
    assert health["verification_level"] == "CONTRACT_ONLY"
    assert health["actual_inventory_source_quality"] == "SOURCE_QUALITY_BLOCKED"


@pytest.mark.parametrize(
    ("method_name", "boundary"),
    [
        ("read_products", "CONTRACT_ONLY"),
        ("read_orders", "UNKNOWN/BLOCKED"),
        ("read_inventory", "SOURCE_QUALITY_BLOCKED"),
        ("read_inquiries", "UNKNOWN"),
        ("read_incoming_stock", "UNKNOWN/BLOCKED"),
    ],
)
def test_ecount_adapter_blocks_live_and_unselected_paths(method_name: str, boundary: str) -> None:
    with pytest.raises(UnsupportedCapability, match=boundary):
        getattr(EcountAdapter(), method_name)()


def test_ecount_adapter_denies_provider_writes() -> None:
    with pytest.raises(UnsupportedCapability, match="writes are disabled"):
        EcountAdapter().execute_write({"action": "change_inventory"})
