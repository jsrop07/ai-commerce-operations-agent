import pytest

from backend.app.adapters.providers.base import (
    ProviderNonRetryableError,
    UnsupportedCapability,
)
from backend.app.adapters.providers.cafe24 import Cafe24Adapter
from backend.app.adapters.providers.capability_guard import (
    CAFE24_ALLOWED_READ_PATHS,
)
from backend.app.adapters.providers.http_transport import ReadOnlyHttpTransport
from contracts.events import Provider
from contracts.providers import (
    CapabilityStatus,
    ConnectionMode,
)


def test_cafe24_capability_record_matches_day5_decision() -> None:
    provider = Cafe24Adapter()

    capability = provider.capabilities()

    assert capability.provider == Provider.CAFE24
    assert capability.connection_mode == ConnectionMode.CONTRACT_ONLY
    assert capability.products_read == CapabilityStatus.SUPPORTED
    assert capability.orders_read == CapabilityStatus.SUPPORTED
    assert capability.inventory_read == CapabilityStatus.VERIFY
    assert capability.inquiries_read == CapabilityStatus.VERIFY
    assert capability.incoming_stock_read == CapabilityStatus.UNKNOWN
    assert capability.inventory_write == CapabilityStatus.DISABLED_CORE
    assert capability.evidence_ref == "docs/provider_capabilities/cafe24.md"


def test_cafe24_health_is_contract_only_before_live_transport() -> None:
    provider = Cafe24Adapter()

    assert provider.verify_health() == {
        "provider": Provider.CAFE24,
        "status": "contract_only",
    }


@pytest.mark.parametrize(
    "method_name",
    [
        "read_products",
        "read_orders",
        "read_inventory",
        "read_inquiries",
        "read_incoming_stock",
    ],
)
def test_cafe24_does_not_call_unapproved_live_transport(
    method_name: str,
) -> None:
    provider = Cafe24Adapter()

    read = getattr(provider, method_name)

    with pytest.raises(UnsupportedCapability):
        read()

def test_cafe24_products_fixture_returns_provider_read_page() -> None:
    captured: dict[str, object] = {}

    def fake_request(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)

        return {
            "products": [
                {
                    "product_no": 101,
                    "product_name": "테스트 보드게임",
                }
            ]
        }

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_product"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
    )

    fixture_mall = "test-mall"
    fixture_value = "synthetic-fixture-value"

    provider = Cafe24Adapter(
        mall_id=fixture_mall,
        access_token=fixture_value,
        transport=transport,
    )

    page = provider.read_products()

    assert page.provider == Provider.CAFE24
    assert page.resource == "products"
    assert page.items == [
        {
            "product_no": 101,
            "product_name": "테스트 보드게임",
        }
    ]
    assert page.next_cursor is None
    assert page.has_more is False
    assert page.request_count == 1
    assert page.schema_version == "provider-read-page.v1"

    assert captured["method"] == "GET"
    assert captured["params"] == {
        "limit": 25,
        "offset": 0,
    }


def test_cafe24_orders_fixture_returns_provider_read_page() -> None:
    def fake_request(**_: object) -> dict[str, object]:
        return {
            "orders": [
                {
                    "order_id": "20260904-000001",
                    "currency": "KRW",
                }
            ]
        }

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_order"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
    )

    fixture_mall = "test-mall"
    fixture_value = "synthetic-fixture-value"

    provider = Cafe24Adapter(
        mall_id=fixture_mall,
        access_token=fixture_value,
        transport=transport,
    )

    page = provider.read_orders()

    assert page.provider == Provider.CAFE24
    assert page.resource == "orders"
    assert len(page.items) == 1
    assert page.items[0]["order_id"] == "20260904-000001"
    assert page.next_cursor is None
    assert page.has_more is False
    assert page.request_count == 1


def test_cafe24_products_uses_offset_cursor() -> None:
    captured: dict[str, object] = {}

    def fake_request(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"products": []}

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_product"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
    )

    fixture_mall = "test-mall"
    fixture_value = "synthetic-fixture-value"

    provider = Cafe24Adapter(
        mall_id=fixture_mall,
        access_token=fixture_value,
        transport=transport,
    )

    provider.read_products(cursor="offset:25")

    assert captured["params"] == {
        "limit": 25,
        "offset": 25,
    }


def test_cafe24_invalid_cursor_does_not_reach_transport() -> None:
    calls = 0

    def fake_request(**_: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"products": []}

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_product"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
    )

    fixture_mall = "test-mall"
    fixture_value = "synthetic-fixture-value"

    provider = Cafe24Adapter(
        mall_id=fixture_mall,
        access_token=fixture_value,
        transport=transport,
    )

    with pytest.raises(ProviderNonRetryableError):
        provider.read_products(cursor="wrong-cursor")

    assert calls == 0
    assert transport.request_count == 0


@pytest.mark.parametrize("cursor", ["offset:-1", "offset:not-a-number", "offset:"])
def test_cafe24_invalid_offset_does_not_reach_transport(cursor: str) -> None:
    calls = 0

    def fake_request(**_: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"products": []}

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_product"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
    )
    fixture_value = "synthetic-fixture-value"
    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=fixture_value,
        transport=transport,
    )

    with pytest.raises(ProviderNonRetryableError):
        provider.read_products(cursor=cursor)

    assert calls == 0
    assert transport.request_count == 0


@pytest.mark.parametrize(
    ("method_name", "response"),
    [
        ("read_products", []),
        ("read_products", {}),
        ("read_products", {"products": ["not-an-object"]}),
        ("read_orders", []),
        ("read_orders", {}),
        ("read_orders", {"orders": ["not-an-object"]}),
    ],
)
def test_cafe24_malformed_fixture_response_is_rejected(
    method_name: str,
    response: object,
) -> None:
    calls = 0

    def fake_request(**_: object) -> object:
        nonlocal calls
        calls += 1
        return response

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_product", "mall.read_order"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
    )
    fixture_value = "synthetic-fixture-value"
    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=fixture_value,
        transport=transport,
    )

    with pytest.raises(ProviderNonRetryableError):
        getattr(provider, method_name)()

    assert calls == 1
    assert transport.request_count == 1


@pytest.mark.parametrize(
    ("method_name", "resource"),
    [("read_products", "products"), ("read_orders", "orders")],
)
def test_cafe24_empty_fixture_response_returns_empty_page(
    method_name: str,
    resource: str,
) -> None:
    def fake_request(**_: object) -> dict[str, object]:
        return {resource: []}

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_product", "mall.read_order"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
    )
    fixture_value = "synthetic-fixture-value"
    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=fixture_value,
        transport=transport,
    )

    page = getattr(provider, method_name)()

    assert page.items == []
    assert page.has_more is False
    assert page.next_cursor is None
    assert page.request_count == 1
