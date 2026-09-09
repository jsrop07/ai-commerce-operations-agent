import pytest
from datetime import date
from backend.app.adapters.providers.base import (
    ProviderNonRetryableError,
    UnsupportedCapability,
)
from backend.app.adapters.providers.cafe24 import Cafe24Adapter
from backend.app.adapters.providers.capability_guard import (
    CAFE24_ALLOWED_READ_PATH_PATTERNS,
    CAFE24_ALLOWED_READ_PATHS,
    ProviderWriteBlockedError,
    CredentialScopeError,
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

def test_cafe24_orders_accept_explicit_date_window() -> None:
    captured: dict[str, object] = {}

    def fake_request(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"orders": []}

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_order"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
    )

    fixture_value = "synthetic-fixture-value"

    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=fixture_value,
        transport=transport,
    )

    provider.read_orders(
        start_date=date(2026, 3, 8),
        end_date=date(2026, 4, 7),
    )

    assert captured["params"] == {
        "start_date": "2026-03-08",
        "end_date": "2026-04-07",
        "limit": 25,
        "offset": 0,
    }

def test_cafe24_orders_reject_too_wide_date_window() -> None:
    calls = 0

    def fake_request(**_: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"orders": []}

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_order"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
    )

    fixture_value = "synthetic-fixture-value"

    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=fixture_value,
        transport=transport,
    )
    with pytest.raises(
        ProviderNonRetryableError
    ):
        provider.read_orders(
            start_date=date(
                2026,
                3,
                1,
            ),
            end_date=date(
                2026,
                5,
                1,
            ),
        )

    assert calls == 0
    assert transport.request_count == 0

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

def test_cafe24_variant_path_is_allowed() -> None:
    calls = 0

    def fake_request(**_: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"variants": []}

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_product"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
    )

    response = transport.get(
        url=(
            "https://test-mall.cafe24api.com"
            "/api/v2/admin/products/101/variants"
        ),
        required_scopes={"mall.read_product"},
    )

    assert response == {"variants": []}
    assert calls == 1

def test_cafe24_variant_inventory_path_is_allowed() -> None:
    calls = 0

    def fake_request(**_: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"inventories": []}

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_product"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
    )

    response = transport.get(
        url=(
            "https://test-mall.cafe24api.com"
            "/api/v2/admin/products/101/variants/"
            "P000000A000A/inventories"
        ),
        required_scopes={"mall.read_product"},
    )

    assert response == {"inventories": []}
    assert calls == 1

def test_cafe24_unapproved_dynamic_path_is_blocked() -> None:
    calls = 0

    def fake_request(**_: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {}

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_product"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
    )

    with pytest.raises(ProviderWriteBlockedError):
        transport.get(
            url=(
                "https://test-mall.cafe24api.com"
                "/api/v2/admin/products/101/delete"
            ),
            required_scopes={"mall.read_product"},
        )

    assert calls == 0
    assert transport.request_count == 0

def test_cafe24_variants_fixture_returns_provider_read_page() -> None:
    captured: dict[str, object] = {}

    def fake_request(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)

        return {
            "variants": [
                {
                    "variant_code": "P000000A000A",
                    "custom_variant_code": "SKU-001",
                    "display": "T",
                }
            ]
        }

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_product"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
    )

    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=("synthetic-fixture-value"),
        transport=transport,
    )

    page = provider.read_variants(product_no=101)

    assert page.provider == Provider.CAFE24
    assert page.resource == "variants"
    assert page.items == [
        {
            "variant_code": "P000000A000A",
            "custom_variant_code": "SKU-001",
            "display": "T",
            "product_no": 101,
        }
    ]

    assert page.next_cursor is None
    assert page.has_more is False

    assert captured["method"] == "GET"
    assert captured["params"] == {
        "limit": 25,
        "offset": 0,
    }

def test_cafe24_variants_use_offset_cursor() -> None:
    captured: dict[str, object] = {}

    def fake_request(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"variants": []}

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_product"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
    )

    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=("synthetic-fixture-value"),
        transport=transport,
    )

    provider.read_variants(
        product_no=101,
        cursor="offset:25",
    )

    assert captured["params"] == {
        "limit": 25,
        "offset": 25,
    }

@pytest.mark.parametrize("product_no", [0, -1])
def test_cafe24_variants_reject_invalid_product_no(
    product_no: int,
) -> None:
    calls = 0

    def fake_request(**_: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"variants": []}

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_product"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
    )

    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=("synthetic-fixture-value"),
        transport=transport,
    )

    with pytest.raises(ProviderNonRetryableError):
        provider.read_variants(product_no=product_no)

    assert calls == 0
    assert transport.request_count == 0

def test_cafe24_variants_reject_malformed_response() -> None:
    def fake_request(**_: object) -> dict[str, object]:
        return {
            "variants": [
                "not-an-object",
            ]
        }

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_product"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
    )

    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=("synthetic-fixture-value"),
        transport=transport,
    )

    with pytest.raises(ProviderNonRetryableError):
        provider.read_variants(product_no=101)


def test_cafe24_variant_inventory_fixture_returns_provider_read_page() -> None:
    captured: dict[str, object] = {}

    def fake_request(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)

        return {
            "inventory": {
                "variant_code": "P000000A000A",
                "quantity": 7,
                "safety_inventory": 2,
            }
        }

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_product"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
    )

    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=("synthetic-fixture-value"),
        transport=transport,
    )

    page = provider.read_variant_inventory(
        product_no=101,
        variant_code="P000000A000A",
    )

    assert page.provider == Provider.CAFE24
    assert page.resource == "variant_inventories"
    assert page.items == [
        {
            "variant_code": "P000000A000A",
            "quantity": 7,
            "safety_inventory": 2,
            "product_no": 101,
        }
    ]

    assert page.has_more is False
    assert page.next_cursor is None

    assert captured["method"] == "GET"

@pytest.mark.parametrize("product_no", [0, -1])
def test_cafe24_variant_inventory_rejects_invalid_product_no(
    product_no: int,
) -> None:
    calls = 0

    def fake_request(**_: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"inventories": []}

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_product"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
    )

    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=("synthetic-fixture-value"),
        transport=transport,
    )

    with pytest.raises(ProviderNonRetryableError):
        provider.read_variant_inventory(
            product_no=product_no,
            variant_code="P000000A000A",
        )

    assert calls == 0
    assert transport.request_count == 0

@pytest.mark.parametrize("variant_code", ["", "   "])
def test_cafe24_variant_inventory_rejects_empty_variant_code(
    variant_code: str,
) -> None:
    calls = 0

    def fake_request(**_: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"inventories": []}

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_product"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
    )

    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=("synthetic-fixture-value"),
        transport=transport,
    )

    with pytest.raises(ProviderNonRetryableError):
        provider.read_variant_inventory(
            product_no=101,
            variant_code=variant_code,
        )

    assert calls == 0
    assert transport.request_count == 0

def test_cafe24_variant_inventory_rejects_slash_in_variant_code() -> None:
    calls = 0

    def fake_request(**_: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"inventories": []}

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_product"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
    )

    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=("synthetic-fixture-value"),
        transport=transport,
    )

    with pytest.raises(ProviderNonRetryableError):
        provider.read_variant_inventory(
            product_no=101,
            variant_code="../orders",
        )

    assert calls == 0
    assert transport.request_count == 0

def test_cafe24_variant_inventory_rejects_malformed_response() -> None:
    def fake_request(**_: object) -> dict[str, object]:
        return {
            "inventories": [
                "not-an-object",
            ]
        }

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_product"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
    )

    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=("synthetic-fixture-value"),
        transport=transport,
    )

    with pytest.raises(ProviderNonRetryableError):
        provider.read_variant_inventory(
            product_no=101,
            variant_code="P000000A000A",
        )

def test_cafe24_categories_fixture_returns_provider_read_page() -> None:
    captured: dict[str, object] = {}

    def fake_request(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)

        return {
            "categories": [
                {
                    "category_no": 10,
                    "category_name": "Miniatures",
                    "parent_category_no": 1,
                }
            ]
        }

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_category"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
    )

    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=("synthetic-fixture-value"),
        transport=transport,
    )

    page = provider.read_categories()

    assert page.provider == Provider.CAFE24
    assert page.resource == "categories"
    assert page.items == [
        {
            "category_no": 10,
            "category_name": "Miniatures",
            "parent_category_no": 1,
        }
    ]

    assert page.next_cursor is None
    assert page.has_more is False

    assert captured["method"] == "GET"
    assert captured["params"] == {
        "limit": 25,
        "offset": 0,
    }

def test_cafe24_category_detail_fixture_returns_category() -> None:
    captured: dict[str, object] = {}

    def fake_request(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)

        return {
            "category": {
                "category_no": 10,
                "category_name": "Miniatures",
                "parent_category_no": 1,
            }
        }

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_category"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
    )

    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=("synthetic-fixture-value"),
        transport=transport,
    )

    category = provider.read_category(
        category_no=10,
    )

    assert category == {
        "category_no": 10,
        "category_name": "Miniatures",
        "parent_category_no": 1,
    }

    assert captured["method"] == "GET"

@pytest.mark.parametrize("category_no", [0, -1])
def test_cafe24_category_detail_rejects_invalid_category_no(
    category_no: int,
) -> None:
    calls = 0

    def fake_request(**_: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"category": {}}

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_category"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
    )

    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=("synthetic-fixture-value"),
        transport=transport,
    )

    with pytest.raises(ProviderNonRetryableError):
        provider.read_category(
            category_no=category_no,
        )

    assert calls == 0
    assert transport.request_count == 0

def test_cafe24_categories_reject_malformed_response() -> None:
    def fake_request(**_: object) -> dict[str, object]:
        return {
            "categories": [
                "not-an-object",
            ]
        }

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_category"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
    )

    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=("synthetic-fixture-value"),
        transport=transport,
    )

    with pytest.raises(ProviderNonRetryableError):
        provider.read_categories()

def test_cafe24_categories_require_category_scope() -> None:
    calls = 0

    def fake_request(**_: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"categories": []}

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_product"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
    )

    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=("synthetic-fixture-value"),
        transport=transport,
    )

    with pytest.raises(CredentialScopeError):
        provider.read_categories()

    assert calls == 0
    assert transport.request_count == 0

def test_cafe24_order_items_fixture_returns_provider_read_page() -> None:
    captured: dict[str, object] = {}

    def fake_request(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)

        return {
            "items": [
                {
                    "order_item_code": "20260907-000001-01",
                    "product_no": 101,
                    "product_code": "P000000A",
                    "variant_code": "P000000A000A",
                    "custom_variant_code": "SKU-001",
                    "quantity": 2,
                }
            ]
        }

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_order"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
    )

    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=("synthetic-fixture-value"),
        transport=transport,
    )

    page = provider.read_order_items(
        order_id="20260907-000001",
    )

    assert page.provider == Provider.CAFE24
    assert page.resource == "order_items"

    assert page.items == [
        {
            "order_item_code": "20260907-000001-01",
            "product_no": 101,
            "product_code": "P000000A",
            "variant_code": "P000000A000A",
            "custom_variant_code": "SKU-001",
            "quantity": 2,
        }
    ]

    assert page.has_more is False
    assert page.next_cursor is None
    assert captured["method"] == "GET"

@pytest.mark.parametrize("order_id", ["", "   "])
def test_cafe24_order_items_reject_empty_order_id(
    order_id: str,
) -> None:
    calls = 0

    def fake_request(**_: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"items": []}

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_order"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
    )

    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=("synthetic-fixture-value"),
        transport=transport,
    )

    with pytest.raises(ProviderNonRetryableError):
        provider.read_order_items(
            order_id=order_id,
        )

    assert calls == 0
    assert transport.request_count == 0

@pytest.mark.parametrize(
    "order_id",
    [
        "../orders",
        "abc/def",
        "abc?x=1",
    ],
)
def test_cafe24_order_items_reject_invalid_order_id(
    order_id: str,
) -> None:
    calls = 0

    def fake_request(**_: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"items": []}

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_order"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
    )

    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=("synthetic-fixture-value"),
        transport=transport,
    )

    with pytest.raises(ProviderNonRetryableError):
        provider.read_order_items(
            order_id=order_id,
        )

    assert calls == 0
    assert transport.request_count == 0

def test_cafe24_order_items_reject_malformed_response() -> None:
    def fake_request(**_: object) -> dict[str, object]:
        return {
            "items": [
                "not-an-object",
            ]
        }

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_order"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
    )

    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=("synthetic-fixture-value"),
        transport=transport,
    )

    with pytest.raises(ProviderNonRetryableError):
        provider.read_order_items(
            order_id="20260907-000001",
        )

def test_cafe24_order_items_require_order_scope() -> None:
    calls = 0

    def fake_request(**_: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"items": []}

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_product"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
    )

    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=("synthetic-fixture-value"),
        transport=transport,
    )

    with pytest.raises(CredentialScopeError):
        provider.read_order_items(
            order_id="20260907-000001",
        )

    assert calls == 0
    assert transport.request_count == 0

def test_cafe24_refunds_fixture_returns_provider_read_page() -> None:
    captured: dict[str, object] = {}

    def fake_request(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)

        return {
            "refunds": [
                {
                    "refund_code": "R20260907-001",
                    "order_id": "20260907-000001",
                    "refund_amount": "15000.00",
                    "status": "completed",
                }
            ]
        }

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_order"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
    )

    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=("synthetic-fixture-value"),
        transport=transport,
    )

    page = provider.read_refunds()

    assert page.provider == Provider.CAFE24
    assert page.resource == "refunds"

    assert page.items == [
        {
            "refund_code": "R20260907-001",
            "order_id": "20260907-000001",
            "refund_amount": "15000.00",
            "status": "completed",
        }
    ]

    assert page.next_cursor is None
    assert page.has_more is False
    assert captured["method"] == "GET"

    params = captured["params"]

    assert params["limit"] == 25
    assert params["offset"] == 0

def test_cafe24_refunds_accept_explicit_date_window() -> None:
    captured: dict[str, object] = {}

    def fake_request(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"refunds": []}

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_order"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
    )

    fixture_value = "synthetic-fixture-value"

    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=fixture_value,
        transport=transport,
    )

    provider.read_refunds(
        start_date=date(2026, 3, 8),
        end_date=date(2026, 4, 7),
    )

    assert captured["params"] == {
        "start_date": "2026-03-08",
        "end_date": "2026-04-07",
        "limit": 25,
        "offset": 0,
    }


def test_cafe24_refunds_reject_too_wide_date_window() -> None:
    calls = 0

    def fake_request(**_: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"refunds": []}

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_order"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
    )

    fixture_value = "synthetic-fixture-value"

    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=fixture_value,
        transport=transport,
    )

    with pytest.raises(
        ProviderNonRetryableError
    ):
        provider.read_refunds(
            start_date=date(2026, 3, 1),
            end_date=date(2026, 5, 1),
        )

    assert calls == 0
    assert transport.request_count == 0
def test_cafe24_refunds_use_offset_cursor() -> None:
    captured: dict[str, object] = {}

    def fake_request(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"refunds": []}

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_order"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
    )

    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=("synthetic-fixture-value"),
        transport=transport,
    )

    provider.read_refunds(
        cursor="offset:25",
    )

    params = captured["params"]

    assert params["limit"] == 25
    assert params["offset"] == 25

@pytest.mark.parametrize(
    "response",
    [
        [],
        {},
        {"refunds": ["not-an-object"]},
    ],
)
def test_cafe24_refunds_reject_malformed_response(
    response: object,
) -> None:
    def fake_request(**_: object) -> object:
        return response

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_order"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
    )

    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=("synthetic-fixture-value"),
        transport=transport,
    )

    with pytest.raises(ProviderNonRetryableError):
        provider.read_refunds()

def test_cafe24_refunds_require_order_scope() -> None:
    calls = 0

    def fake_request(**_: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"refunds": []}

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_product"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
    )

    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=("synthetic-fixture-value"),
        transport=transport,
    )

    with pytest.raises(CredentialScopeError):
        provider.read_refunds()

    assert calls == 0
    assert transport.request_count == 0

def test_cafe24_refund_write_like_path_is_not_allowed() -> None:
    calls = 0

    def fake_request(**_: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {}

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_order"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
    )

    with pytest.raises(ProviderWriteBlockedError):
        transport.get(
            url=(
                "https://test-mall.cafe24api.com"
                "/api/v2/admin/refunds/123"
            ),
            required_scopes={"mall.read_order"},
        )

    assert calls == 0
    assert transport.request_count == 0

def test_cafe24_boards_fixture_returns_provider_read_page() -> None:
    captured: dict[str, object] = {}

    def fake_request(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)

        return {
            "boards": [
                {
                    "board_no": 6,
                    "board_name": "상품 문의",
                },
                {
                    "board_no": 9,
                    "board_name": "일반 문의",
                },
            ]
        }

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_community"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
    )

    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=("synthetic-fixture-value"),
        transport=transport,
    )

    page = provider.read_boards()

    assert page.provider == Provider.CAFE24
    assert page.resource == "boards"
    assert len(page.items) == 2

    assert page.items[0]["board_no"] == 6
    assert page.items[1]["board_no"] == 9

    assert captured["method"] == "GET"

def test_cafe24_boards_require_community_scope() -> None:
    calls = 0

    def fake_request(**_: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"boards": []}

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_product"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
    )

    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=("synthetic-fixture-value"),
        transport=transport,
    )

    with pytest.raises(CredentialScopeError):
        provider.read_boards()

    assert calls == 0
    assert transport.request_count == 0

@pytest.mark.parametrize(
    "response",
    [
        [],
        {},
        {"boards": ["not-an-object"]},
    ],
)
def test_cafe24_boards_reject_malformed_response(
    response: object,
) -> None:
    def fake_request(**_: object) -> object:
        return response

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_community"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
    )

    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=("synthetic-fixture-value"),
        transport=transport,
    )

    with pytest.raises(ProviderNonRetryableError):
        provider.read_boards()

def test_cafe24_articles_fixture_returns_provider_read_page() -> None:
    captured: dict[str, object] = {}

    def fake_request(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)

        return {
            "articles": [
                {
                    "article_no": 1001,
                    "board_no": 6,
                    "subject": "재입고 문의",
                    "content": "언제 재입고되나요?",
                }
            ]
        }

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_community"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
    )

    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=("synthetic-fixture-value"),
        transport=transport,
    )

    page = provider.read_articles(
        board_no=6,
    )

    assert page.provider == Provider.CAFE24
    assert page.resource == "articles"

    assert len(page.items) == 1
    assert page.items[0]["article_no"] == 1001
    assert page.items[0]["board_no"] == 6

    assert page.next_cursor is None
    assert page.has_more is False

    assert captured["method"] == "GET"
    assert captured["params"] == {
        "limit": 25,
        "offset": 0,
    }

def test_cafe24_articles_use_offset_cursor() -> None:
    captured: dict[str, object] = {}

    def fake_request(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"articles": []}

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_community"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
    )

    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=("synthetic-fixture-value"),
        transport=transport,
    )

    provider.read_articles(
        board_no=6,
        cursor="offset:25",
    )

    assert captured["params"] == {
        "limit": 25,
        "offset": 25,
    }

@pytest.mark.parametrize("board_no", [0, -1])
def test_cafe24_articles_reject_invalid_board_no(
    board_no: int,
) -> None:
    calls = 0

    def fake_request(**_: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"articles": []}

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_community"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
    )

    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=("synthetic-fixture-value"),
        transport=transport,
    )

    with pytest.raises(ProviderNonRetryableError):
        provider.read_articles(
            board_no=board_no,
        )

    assert calls == 0
    assert transport.request_count == 0

def test_cafe24_articles_require_community_scope() -> None:
    calls = 0

    def fake_request(**_: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"articles": []}

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_product"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
    )

    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=("synthetic-fixture-value"),
        transport=transport,
    )

    with pytest.raises(CredentialScopeError):
        provider.read_articles(
            board_no=6,
        )

    assert calls == 0
    assert transport.request_count == 0

@pytest.mark.parametrize(
    "response",
    [
        [],
        {},
        {"articles": ["not-an-object"]},
    ],
)
def test_cafe24_articles_reject_malformed_response(
    response: object,
) -> None:
    def fake_request(**_: object) -> object:
        return response

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_community"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
    )

    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=("synthetic-fixture-value"),
        transport=transport,
    )

    with pytest.raises(ProviderNonRetryableError):
        provider.read_articles(
            board_no=6,
        )

def test_cafe24_article_comments_fixture_returns_provider_read_page() -> None:
    captured: dict[str, object] = {}

    def fake_request(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)

        return {
            "comments": [
                {
                    "comment_no": 5001,
                    "content": "다음 주 입고 예정입니다.",
                    "writer": "operator",
                    "parent_comment_no": None,
                }
            ]
        }

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_community"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
    )

    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=("synthetic-fixture-value"),
        transport=transport,
    )

    page = provider.read_article_comments(
        board_no=6,
        article_no=1001,
    )

    assert page.provider == Provider.CAFE24
    assert page.resource == "article_comments"
    assert len(page.items) == 1
    assert page.items[0]["comment_no"] == 5001

    assert captured["method"] == "GET"
    assert captured["params"] == {
        "limit": 25,
        "offset": 0,
    }

def test_cafe24_article_comments_use_offset_cursor() -> None:
    captured: dict[str, object] = {}

    def fake_request(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"comments": []}

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_community"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
    )

    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=("synthetic-fixture-value"),
        transport=transport,
    )

    provider.read_article_comments(
        board_no=6,
        article_no=1001,
        cursor="offset:25",
    )

    assert captured["params"] == {
        "limit": 25,
        "offset": 25,
    }

@pytest.mark.parametrize(
    ("board_no", "article_no"),
    [
        (0, 1001),
        (-1, 1001),
        (6, 0),
        (6, -1),
    ],
)
def test_cafe24_article_comments_reject_invalid_ids(
    board_no: int,
    article_no: int,
) -> None:
    calls = 0

    def fake_request(**_: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"comments": []}

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_community"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
    )

    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=("synthetic-fixture-value"),
        transport=transport,
    )

    with pytest.raises(ProviderNonRetryableError):
        provider.read_article_comments(
            board_no=board_no,
            article_no=article_no,
        )

    assert calls == 0
    assert transport.request_count == 0

def test_cafe24_article_comments_require_community_scope() -> None:
    calls = 0

    def fake_request(**_: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"comments": []}

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_product"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
    )

    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=("synthetic-fixture-value"),
        transport=transport,
    )

    with pytest.raises(CredentialScopeError):
        provider.read_article_comments(
            board_no=6,
            article_no=1001,
        )

    assert calls == 0
    assert transport.request_count == 0

@pytest.mark.parametrize(
    "response",
    [
        [],
        {},
        {"comments": ["not-an-object"]},
    ],
)
def test_cafe24_article_comments_reject_malformed_response(
    response: object,
) -> None:
    def fake_request(**_: object) -> object:
        return response

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_community"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
    )

    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=("synthetic-fixture-value"),
        transport=transport,
    )

    with pytest.raises(ProviderNonRetryableError):
        provider.read_article_comments(
            board_no=6,
            article_no=1001,
        )

@pytest.mark.parametrize("suffix", [
    "products/1/variants/%2f/inventories", "products/1/variants/%252f/inventories",
    "products/1/variants/../inventories", "products/1/variants/./inventories",
    "products/1/variants/x\\y/inventories", "products?method=DELETE",
    "products#synthetic-secret", "products\n", "products?limit=1&limit=2",
])
def test_bootstrap_read_guard_blocks_url_bypasses(suffix):
    calls = []
    transport = ReadOnlyHttpTransport(
        request_fn=lambda **kw: calls.append(kw),
        granted_scopes={"mall.read_product"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
    )
    with pytest.raises(ProviderWriteBlockedError) as caught:
        transport.get(url="https://synthetic-mall.cafe24api.com/api/v2/admin/" + suffix,
                      required_scopes={"mall.read_product"})
    assert calls == []
    assert "synthetic-secret" not in str(caught.value)


@pytest.mark.parametrize("code", ["%2f", "%252f", "..", "x?y", "x#y", "x\\y", None])
def test_inventory_identifier_fails_before_request(code):
    adapter = Cafe24Adapter()
    with pytest.raises(ProviderNonRetryableError):
        adapter.read_variant_inventory(1, code)


@pytest.mark.parametrize("method,args", [
    ("read_variant_inventory", (1, "SYNTHETIC")), ("read_order_items", ("ORDER-001",)),
])
def test_detail_pages_never_advertise_unusable_offset(method, args):
    def fake_request(**kw):
        url = str(kw.get("url", ""))

        if "/inventories" in url:
            return {
                "inventory": {
                    "variant_code": "SYNTHETIC",
                }
            }

        return {
            "items": [{}] * 25,
        }

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_product", "mall.read_order"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
    )
    adapter = Cafe24Adapter(mall_id="synthetic-mall", access_token=("synthetic-access"), transport=transport)
    page = getattr(adapter, method)(*args)
    if method == "read_variant_inventory":
        assert len(page.items) == 1
    else:
        assert len(page.items) == 25

    assert page.has_more is False
    assert page.next_cursor is None
    assert page.provider == Provider.CAFE24 and page.request_count == 1


@pytest.mark.parametrize("method,args", [
    ("read_variants", (True,)), ("read_category", ("1",)),
    ("read_articles", (1.5,)), ("read_article_comments", (1, False)),
])
def test_integer_identifiers_have_exact_failure_type(method, args):
    with pytest.raises(ProviderNonRetryableError):
        getattr(Cafe24Adapter(), method)(*args)

def test_cafe24_articles_continue_when_response_exceeds_page_size() -> None:
    items = [
        {
            "article_no": index + 1,
            "board_no": 5,
            "subject": (
                f"Synthetic article {index + 1}"
            ),
        }
        for index in range(26)
    ]

    transport = ReadOnlyHttpTransport(
        request_fn=lambda **_: {
            "articles": items
        },
        granted_scopes={
            "mall.read_community"
        },
        allowed_paths=(
            CAFE24_ALLOWED_READ_PATHS
        ),
        allowed_path_patterns=(
            CAFE24_ALLOWED_READ_PATH_PATTERNS
        ),
    )
    fixture_value = "synthetic-fixture-value"
    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=fixture_value,
        transport=transport,
    )

    page = provider.read_articles(
        board_no=5,
    )

    assert len(page.items) == 26
    assert page.has_more is True
    assert page.next_cursor == "offset:25"

def test_cafe24_article_comments_continue_when_response_exceeds_page_size() -> None:
    items = [
        {
            "comment_no": index + 1,
            "content": (
                f"Synthetic comment {index + 1}"
            ),
        }
        for index in range(26)
    ]

    transport = ReadOnlyHttpTransport(
        request_fn=lambda **_: {
            "comments": items
        },
        granted_scopes={
            "mall.read_community"
        },
        allowed_paths=(
            CAFE24_ALLOWED_READ_PATHS
        ),
        allowed_path_patterns=(
            CAFE24_ALLOWED_READ_PATH_PATTERNS
        ),
    )

    fixture_value = "synthetic-fixture-value"

    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=fixture_value,
        transport=transport,
    )

    page = (
        provider.read_article_comments(
            board_no=5,
            article_no=1001,
        )
    )

    assert len(page.items) == 26
    assert page.has_more is True
    assert page.next_cursor == "offset:25"