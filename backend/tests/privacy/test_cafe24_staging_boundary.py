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

def test_community_sanitized_schema_drops_structured_pii_and_full_url() -> None:
    from backend.app.worker.privacy.staging import sanitize_community_record

    synthetic_url = "https://forplus.co.kr/synthetic/file.pdf?signature=synthetic-query"
    sanitized = sanitize_community_record(
        {
            "board_no": 6,
            "article_no": 1001,
            "parent_article_no": 1000,
            "subject": "Synthetic Person",
            "content": "Synthetic address and contact",
            "writer": "Synthetic Customer",
            "email": "".join(("synthetic", "@example.test")),
            "phone": "-".join(("010", "0000", "0000")),
            "address": "Synthetic address",
            "attach_file_urls": [{"url": synthetic_url}],
        }
    )
    serialized = str(sanitized)
    assert sanitized["board_no"] == 6
    assert sanitized["article_no"] == 1001
    assert sanitized["parent_article_no"] == 1000
    assert sanitized["attachment_count"] == 1
    assert len(sanitized["attachment_source_sha256"][0]) == 64
    assert synthetic_url not in serialized
    assert "signature=" not in serialized
    for field in ("writer", "email", "phone", "address", "subject", "content"):
        assert field not in sanitized