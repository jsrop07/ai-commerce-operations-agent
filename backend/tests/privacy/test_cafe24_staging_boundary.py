from backend.app.adapters.providers.cafe24 import Cafe24Adapter
from backend.app.adapters.providers.capability_guard import (
    CAFE24_ALLOWED_READ_PATHS,
)
from backend.app.adapters.providers.http_transport import ReadOnlyHttpTransport


def test_cafe24_order_raw_sensitive_fields_do_not_reach_provider_page() -> None:
    fixture_value = "synthetic-fixture-value"

    def fake_request(**_: object) -> dict[str, object]:
        return {
            "orders": [
                {
                    "order_id": "order-demo-001",
                    "buyer_name": "CUSTOMER_VALUE",
                    "phone": "PHONE_VALUE",
                    "email": "EMAIL_VALUE",
                    "product_no": 101,
                    "quantity": 2,
                }
            ]
        }

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_order"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
    )

    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=fixture_value,
        transport=transport,
    )

    page = provider.read_orders()

    assert page.items == [
        {
            "order_id": "order-demo-001",
            "product_no": 101,
            "quantity": 2,
        }
    ]


def test_cafe24_nested_sensitive_fields_do_not_reach_provider_page() -> None:
    fixture_value = "synthetic-fixture-value"

    def fake_request(**_: object) -> dict[str, object]:
        return {
            "orders": [
                {
                    "order_id": "order-demo-002",
                    "receiver": {
                        "receiver_name": "CUSTOMER_VALUE",
                        "address1": "ADDRESS_VALUE",
                    },
                    "items": [
                        {
                            "product_no": 202,
                            "quantity": 1,
                        }
                    ],
                }
            ]
        }

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_order"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
    )

    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=fixture_value,
        transport=transport,
    )

    page = provider.read_orders()

    assert page.items == [
        {
            "order_id": "order-demo-002",
            "receiver": {},
            "items": [
                {
                    "product_no": 202,
                    "quantity": 1,
                }
            ],
        }
    ]


def test_cafe24_raw_and_sanitized_item_counts_match() -> None:
    fixture_value = "synthetic-fixture-value"

    raw_items = [
        {
            "order_id": "order-demo-003",
            "buyer_name": "CUSTOMER_VALUE",
        },
        {
            "order_id": "order-demo-004",
            "buyer_name": "CUSTOMER_VALUE",
        },
    ]

    def fake_request(**_: object) -> dict[str, object]:
        return {"orders": raw_items}

    transport = ReadOnlyHttpTransport(
        request_fn=fake_request,
        granted_scopes={"mall.read_order"},
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
    )

    provider = Cafe24Adapter(
        mall_id="test-mall",
        access_token=fixture_value,
        transport=transport,
    )

    page = provider.read_orders()

    assert len(raw_items) == 2
    assert len(page.items) == 2