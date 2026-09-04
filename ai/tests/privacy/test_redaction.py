import json
from pathlib import Path

from ai.data.redaction import (
    contains_pii,
    redact_text,
    sanitize_record,
)


ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PATH = ROOT / "ai" / "tests" / "fixtures" / "privacy_cases.json"


def load_fixture():
    with FIXTURE_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def test_privacy_fixture_exists():
    assert FIXTURE_PATH.exists()


def test_all_pii_cases_are_detected():
    fixture = load_fixture()

    for case in fixture["pii_cases"]:
        assert contains_pii(case["input"]), case["case_id"]


def test_all_pii_cases_are_redacted():
    fixture = load_fixture()

    for case in fixture["pii_cases"]:
        redacted, findings = redact_text(case["input"])

        assert findings, case["case_id"]

        for token in case["expected_tokens"]:
            assert token in redacted, case["case_id"]

        assert contains_pii(redacted) is False, case["case_id"]


def test_safe_cases_are_not_redacted():
    fixture = load_fixture()

    for case in fixture["safe_cases"]:
        redacted, findings = redact_text(case["input"])

        assert redacted == case["input"], case["case_id"]
        assert findings == [], case["case_id"]


def test_phone_is_replaced_with_placeholder():
    redacted, findings = redact_text(
        "연락처는 010-1234-5678입니다."
    )

    assert redacted == "연락처는 <PHONE>입니다."
    assert findings[0].pii_type == "PHONE"


def test_email_is_replaced_with_placeholder():
    redacted, findings = redact_text(
        "메일은 demo.user@example.com 입니다."
    )

    assert "<EMAIL>" in redacted
    assert findings[0].pii_type == "EMAIL"


def test_non_string_input_is_rejected():
    try:
        redact_text(123)  # type: ignore[arg-type]
    except TypeError:
        pass
    else:
        raise AssertionError("non-string input must raise TypeError")

def test_structured_sensitive_fields_are_tokenized():
    fixture = load_fixture()

    for case in fixture["structured_cases"]:
        sanitized, findings = sanitize_record(
            case["input"]
        )

        assert sanitized == case["expected"]
        assert findings, case["case_id"]


def test_structured_raw_private_values_do_not_survive():
    fixture = load_fixture()

    for case in fixture["structured_cases"]:
        sanitized, _ = sanitize_record(
            case["input"]
        )

        serialized = json.dumps(
            sanitized,
            ensure_ascii=False,
        )

        for key, value in case["input"].items():
            if key in {
                "customer_name",
                "shipping_address",
                "phone",
                "email",
                "order_id",
            }:
                assert str(value) not in serialized


def test_safe_product_and_sku_fields_are_preserved():
    record = {
        "product_name": "별빛 탐험대",
        "sku_id": "sku_demo_001",
        "category": "BOARD_GAME",
    }

    sanitized, findings = sanitize_record(record)

    assert sanitized == record
    assert findings == []