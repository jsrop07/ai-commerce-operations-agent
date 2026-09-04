import pytest

from backend.app.adapters.providers import (
    Cafe24MockProvider,
    EcountMockProvider,
    TossPosMockProvider,
)
from backend.app.adapters.providers.base import ProviderNonRetryableError


def test_three_mocks_share_provider_read_page_contract() -> None:
    for provider in (Cafe24MockProvider(), TossPosMockProvider(), EcountMockProvider()):
        page = provider.read_inventory()
        assert page.provider == provider.capabilities().provider
        assert page.resource == "inventory"
        assert page.next_cursor == "page-2"
        assert page.has_more is True
        assert page.watermark is not None
        assert page.request_count == 1
        assert page.source_as_of is not None
        assert page.schema_version == "provider-read-page.v1"


def test_provider_read_page_cursor_boundary() -> None:
    provider = Cafe24MockProvider()

    first = provider.read_inventory()

    assert len(first.items) == 1
    assert first.next_cursor == "page-2"
    assert first.has_more is True
    assert first.watermark is not None
    assert first.source_as_of is not None

    second = provider.read_inventory(cursor=first.next_cursor)

    assert len(second.items) == 1
    assert second.next_cursor is None
    assert second.has_more is False
    assert second.watermark is not None
    assert second.source_as_of is not None

    with pytest.raises(ProviderNonRetryableError):
        provider.read_inventory(cursor="unknown-cursor")


@pytest.mark.parametrize(
    "provider_type", [Cafe24MockProvider, TossPosMockProvider, EcountMockProvider]
)
@pytest.mark.parametrize(
    "read_method",
    ["read_products", "read_orders", "read_inventory", "read_incoming_stock"],
)
def test_all_supported_mock_reads_share_cursor_contract(
    provider_type: type, read_method: str
) -> None:
    provider = provider_type()
    read = getattr(provider, read_method)

    first = read()
    second = read(cursor=first.next_cursor)

    assert first.provider == second.provider == provider.capabilities().provider
    assert first.resource == second.resource
    assert first.next_cursor == "page-2"
    assert first.has_more is True
    assert second.next_cursor is None
    assert second.has_more is False
    assert first.request_count == second.request_count == 1
    assert first.watermark is not None and second.watermark is not None
    assert first.source_as_of is not None and second.source_as_of is not None
    assert first.schema_version == second.schema_version == "provider-read-page.v1"

    with pytest.raises(ProviderNonRetryableError):
        read(cursor="unknown-cursor")
