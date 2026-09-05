import pytest

from backend.app.adapters.providers.base import UnsupportedCapability
from backend.app.adapters.providers.toss_pos import TossPosAdapter
from contracts.providers import CapabilityStatus, ConnectionMode


def test_toss_adapter_declares_api_poll_but_contract_only_verification() -> None:
    adapter = TossPosAdapter()

    assert adapter.capabilities().connection_mode == ConnectionMode.API_POLL
    assert adapter.capabilities().orders_read == CapabilityStatus.SUPPORTED
    assert adapter.verify_health()["verification_level"] == "CONTRACT_ONLY"


@pytest.mark.parametrize(
    ("method_name", "boundary"),
    [
        ("read_products", "CONTRACT_ONLY"),
        ("read_orders", "CONTRACT_ONLY"),
        ("read_inventory", "unsupported"),
        ("read_inquiries", "UNKNOWN"),
        ("read_incoming_stock", "UNKNOWN"),
    ],
)
def test_toss_adapter_never_confuses_fixture_with_live_read(
    method_name: str, boundary: str
) -> None:
    with pytest.raises(UnsupportedCapability, match=boundary):
        getattr(TossPosAdapter(), method_name)()


def test_toss_adapter_denies_provider_writes() -> None:
    with pytest.raises(UnsupportedCapability, match="writes are disabled"):
        TossPosAdapter().execute_write({"action": "cancel"})
