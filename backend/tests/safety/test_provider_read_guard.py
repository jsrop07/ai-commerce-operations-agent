import pytest

from backend.app.adapters.providers.capability_guard import (
    CAFE24_ALLOWED_READ_PATHS,
    CredentialScopeError,
    ProviderWriteBlockedError,
    validate_provider_read_request,
)
from backend.app.adapters.providers.http_transport import ReadOnlyHttpTransport


def test_cafe24_product_get_is_allowed_with_required_scope() -> None:
    path = validate_provider_read_request(
        method="GET",
        path_or_url="https://example.cafe24api.com/api/v2/admin/products?limit=10",
        granted_scopes={"mall.read_product"},
        required_scopes={"mall.read_product"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
    )

    assert path == "/api/v2/admin/products"


def test_cafe24_order_get_is_allowed_with_required_scope() -> None:
    path = validate_provider_read_request(
        method="GET",
        path_or_url="https://example.cafe24api.com/api/v2/admin/orders?limit=10",
        granted_scopes={"mall.read_order"},
        required_scopes={"mall.read_order"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
    )

    assert path == "/api/v2/admin/orders"


def test_missing_scope_is_blocked_before_transport() -> None:
    calls = 0

    def fake_request(**_: object) -> dict[str, str]:
        nonlocal calls
        calls += 1
        return {"status": "unexpected"}

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_product"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
    )

    with pytest.raises(CredentialScopeError):
        transport.get(
            url="https://example.cafe24api.com/api/v2/admin/orders",
            required_scopes={"mall.read_order"},
        )

    assert calls == 0
    assert transport.request_count == 0


@pytest.mark.parametrize(
    "method",
    ["POST", "PUT", "PATCH", "DELETE"],
)
def test_write_methods_are_blocked_before_transport(method: str) -> None:
    calls = 0

    def fake_request(**_: object) -> dict[str, str]:
        nonlocal calls
        calls += 1
        return {"status": "unexpected"}

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_product"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
    )

    with pytest.raises(ProviderWriteBlockedError):
        transport.request(
            method=method,
            url="https://example.cafe24api.com/api/v2/admin/products",
            required_scopes={"mall.read_product"},
        )

    assert calls == 0
    assert transport.request_count == 0


def test_non_allowlisted_path_is_blocked_before_transport() -> None:
    calls = 0

    def fake_request(**_: object) -> dict[str, str]:
        nonlocal calls
        calls += 1
        return {"status": "unexpected"}

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_product"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
    )

    with pytest.raises(ProviderWriteBlockedError):
        transport.get(
            url="https://example.cafe24api.com/api/v2/admin/products/1",
            required_scopes={"mall.read_product"},
        )

    assert calls == 0
    assert transport.request_count == 0


def test_valid_get_reaches_transport_once() -> None:
    calls = 0

    def fake_request(**kwargs: object) -> dict[str, object]:
        nonlocal calls
        calls += 1

        return {
            "status": 200,
            "method": kwargs["method"],
        }

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_product"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
    )

    response = transport.get(
        url="https://example.cafe24api.com/api/v2/admin/products",
        required_scopes={"mall.read_product"},
    )

    assert response["status"] == 200
    assert response["method"] == "GET"
    assert calls == 1
    assert transport.request_count == 1


@pytest.mark.parametrize("granted_scopes", [None, set()])
def test_unknown_or_empty_scope_is_blocked_before_transport(
    granted_scopes: set[str] | None,
) -> None:
    calls = 0

    def fake_request(**_: object) -> dict[str, str]:
        nonlocal calls
        calls += 1
        return {"status": "unexpected"}

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes=granted_scopes,
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
    )

    with pytest.raises(CredentialScopeError):
        transport.get(
            url="https://example.cafe24api.com/api/v2/admin/products",
            required_scopes={"mall.read_product"},
        )

    assert calls == 0
    assert transport.request_count == 0


def test_guard_failure_does_not_expose_authorization_value() -> None:
    fixture_value = "synthetic-sensitive-fixture-value"
    transport = ReadOnlyHttpTransport(
        request_fn=lambda **_: {"status": "unexpected"},
        granted_scopes=set(),
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
    )

    with pytest.raises(CredentialScopeError) as exc_info:
        transport.get(
            url="https://example.cafe24api.com/api/v2/admin/products",
            required_scopes={"mall.read_product"},
            headers={"Authorization": f"Bearer {fixture_value}"},
        )

    assert fixture_value not in str(exc_info.value)
    assert transport.request_count == 0

@pytest.mark.parametrize(
    "extra_scope",
    ["mall.write_synthetic", "synthetic.unknown_scope"],
)
def test_unexpected_scope_is_blocked_before_transport(extra_scope: str) -> None:
    calls = 0

    def fake_request(**_: object) -> dict[str, str]:
        nonlocal calls
        calls += 1
        return {"status": "unexpected"}

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={
            "mall.read_product",
            "mall.read_order",
            "mall.read_category",
            "mall.read_community",
            extra_scope,
        },
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
    )
    with pytest.raises(CredentialScopeError):
        transport.get(
            url="https://example.cafe24api.com/api/v2/admin/products",
            required_scopes={"mall.read_product"},
        )
    assert calls == 0
    assert transport.request_count == 0


def test_all_four_cafe24_read_scopes_are_allowed() -> None:
    calls = 0

    def fake_request(**_: object) -> dict[str, list[object]]:
        nonlocal calls
        calls += 1
        return {"products": []}

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={
            "mall.read_product", "mall.read_order",
            "mall.read_category", "mall.read_community",
        },
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
    )
    transport.get(
        url="https://example.cafe24api.com/api/v2/admin/products",
        required_scopes={"mall.read_product"},
    )
    assert calls == 1