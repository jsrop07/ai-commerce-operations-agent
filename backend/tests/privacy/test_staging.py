from backend.app.worker.privacy.staging import (
    build_raw_sha256,
    build_staging_record,
    sanitize_record,
)


def test_sanitize_record_removes_direct_sensitive_fields() -> None:
    raw = {
        "order_id": "order-demo-001",
        "buyer_name": "CUSTOMER_VALUE",
        "phone": "PHONE_VALUE",
        "email": "EMAIL_VALUE",
        "product_no": 101,
        "quantity": 2,
    }

    sanitized = sanitize_record(raw)

    assert sanitized == {
        "order_id": "order-demo-001",
        "product_no": 101,
        "quantity": 2,
    }


def test_sanitize_record_removes_nested_sensitive_fields() -> None:
    raw = {
        "order_id": "order-demo-002",
        "receiver": {
            "receiver_name": "CUSTOMER_VALUE",
            "address1": "ADDRESS_VALUE",
            "zipcode": "ZIP_VALUE",
        },
        "items": [
            {
                "product_no": 101,
                "quantity": 1,
            }
        ],
    }

    sanitized = sanitize_record(raw)

    assert sanitized == {
        "order_id": "order-demo-002",
        "receiver": {},
        "items": [
            {
                "product_no": 101,
                "quantity": 1,
            }
        ],
    }


def test_raw_hash_is_deterministic() -> None:
    first = {
        "order_id": "order-demo-003",
        "quantity": 2,
    }

    second = {
        "quantity": 2,
        "order_id": "order-demo-003",
    }

    assert build_raw_sha256(first) == build_raw_sha256(second)


def test_staging_record_keeps_only_raw_reference_and_sanitized_payload() -> None:
    raw = {
        "order_id": "order-demo-004",
        "buyer_name": "CUSTOMER_VALUE",
        "phone": "PHONE_VALUE",
        "product_no": 202,
        "quantity": 3,
    }

    staging = build_staging_record(
        provider="CAFE24",
        resource="orders",
        raw_payload=raw,
        storage_ref="protected://cafe24/orders/batch-demo-001",
    )

    assert staging.provider == "CAFE24"
    assert staging.resource == "orders"

    assert staging.raw_ref.provider == "CAFE24"
    assert staging.raw_ref.resource == "orders"
    assert len(staging.raw_ref.raw_sha256) == 64
    assert staging.raw_ref.storage_ref == (
        "protected://cafe24/orders/batch-demo-001"
    )

    assert staging.sanitized_payload == {
        "order_id": "order-demo-004",
        "product_no": 202,
        "quantity": 3,
    }


def test_sanitized_payload_does_not_contain_sensitive_field_names() -> None:
    raw = {
        "order_id": "order-demo-005",
        "customer_name": "CUSTOMER_VALUE",
        "mobile": "PHONE_VALUE",
        "authorization": "AUTH_VALUE",
        "items": [
            {
                "product_no": 303,
                "quantity": 1,
                "api_key": "KEY_VALUE",
            }
        ],
    }

    staging = build_staging_record(
        provider="CAFE24",
        resource="orders",
        raw_payload=raw,
        storage_ref="protected://cafe24/orders/batch-demo-002",
    )

    text = str(staging.sanitized_payload).lower()

    assert "customer_name" not in text
    assert "mobile" not in text
    assert "authorization" not in text
    assert "api_key" not in text