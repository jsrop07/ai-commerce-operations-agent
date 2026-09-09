from backend.app.worker.privacy.staging import sanitize_record
from backend.app.worker.privacy.text_redaction import (
    redact_free_text,
)


def test_redact_free_text_removes_email() -> None:
    text = "".join(('문의 답변은 ', 'customer', '@example.com', ' 으로 부탁드립니다.'))

    result = redact_free_text(text)

    assert "".join(('', 'customer', '@example.com', '')) not in result
    assert "<EMAIL>" in result


def test_redact_free_text_removes_phone() -> None:
    text = "".join(('연락처는 ', '010', '-1234-5678', ' 입니다.'))

    result = redact_free_text(text)

    assert "".join(('', '010', '-1234-5678', '')) not in result
    assert "<PHONE>" in result


def test_redact_free_text_removes_order_reference() -> None:
    text = "주문번호 20260907-000001 관련 문의입니다."

    result = redact_free_text(text)

    assert "20260907-000001" not in result
    assert "<ORDER_REF>" in result


def test_redact_free_text_removes_ipv4() -> None:
    text = "작성 IP는 192.168.0.10 입니다."

    result = redact_free_text(text)

    assert "192.168.0.10" not in result
    assert "<IP>" in result


def test_sanitize_record_redacts_nested_free_text() -> None:
    payload = {
        "article_no": 1001,
        "subject": "배송 문의",
        "content": (
            "".join(('', '010', '-1234-5678', ' 또는 customer@example.com으로 연락해주세요.'))
        ),
        "comments": [
            {
                "content": "주문번호 20260907-000001 확인 부탁드립니다."
            }
        ],
    }

    result = sanitize_record(payload)

    assert result["article_no"] == 1001
    assert result["subject"] == "배송 문의"

    assert "".join(('', '010', '-1234-5678', '')) not in result["content"]
    assert "".join(('', 'customer', '@example.com', '')) not in result["content"]

    nested = result["comments"][0]["content"]

    assert "20260907-000001" not in nested
    assert "<ORDER_REF>" in nested


def test_structured_order_routing_survives_but_free_text_reference_does_not():
    from backend.app.worker.privacy.staging import sanitize_record
    result = sanitize_record({
        "order_id": "20260101-000001", "order_item_code": "20260101-000001-01",
        "content": "synthetic reference 20260101-000001",
        "nested": {"order_id": "".join(('email ', 'synthetic', '@example.test', ' or 20260101-000001'))},
    })
    assert result["order_id"] == "20260101-000001"
    assert result["order_item_code"] == "20260101-000001-01"
    assert result["content"] == "synthetic reference <ORDER_REF>"
    assert "20260101-000001" not in result["nested"]["order_id"]
    assert "".join(('', 'synthetic', '@example.test', '')) not in result["nested"]["order_id"]
