import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RedactionFinding:
    pii_type: str
    original: str
    replacement: str
    field_path: str | None = None


PHONE_PATTERN = re.compile(
    r"(?<!\d)(?:01[016789])[- ]?\d{3,4}[- ]?\d{4}(?!\d)"
)

EMAIL_PATTERN = re.compile(
    r"(?<![A-Za-z0-9._%+-])"
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
)

RESIDENT_ID_PATTERN = re.compile(
    r"(?<!\d)\d{6}-[1-4]\d{6}(?!\d)"
)

CARD_PATTERN = re.compile(
    r"(?<!\d)(?:\d{4}[- ]?){3}\d{4}(?!\d)"
)


PATTERNS = (
    ("RESIDENT_ID", RESIDENT_ID_PATTERN, "<RESIDENT_ID>"),
    ("CARD", CARD_PATTERN, "<CARD>"),
    ("PHONE", PHONE_PATTERN, "<PHONE>"),
    ("EMAIL", EMAIL_PATTERN, "<EMAIL>"),
)


STRUCTURED_FIELD_TOKENS = {
    "customer_name": ("CUSTOMER", "<CUSTOMER>"),
    "recipient_name": ("CUSTOMER", "<CUSTOMER>"),
    "shipping_name": ("CUSTOMER", "<CUSTOMER>"),

    "address": ("ADDRESS", "<ADDRESS>"),
    "shipping_address": ("ADDRESS", "<ADDRESS>"),
    "billing_address": ("ADDRESS", "<ADDRESS>"),
    "recipient_address": ("ADDRESS", "<ADDRESS>"),

    "phone": ("PHONE", "<PHONE>"),
    "mobile": ("PHONE", "<PHONE>"),
    "telephone": ("PHONE", "<PHONE>"),

    "email": ("EMAIL", "<EMAIL>"),

    "order_id": ("ORDER_REF", "<ORDER_REF>"),
    "external_order_id": ("ORDER_REF", "<ORDER_REF>"),
    "order_number": ("ORDER_REF", "<ORDER_REF>"),
    "external_order_number": ("ORDER_REF", "<ORDER_REF>"),
}


def redact_text(text: str) -> tuple[str, list[RedactionFinding]]:
    if not isinstance(text, str):
        raise TypeError("text must be str")

    redacted = text
    findings: list[RedactionFinding] = []

    for pii_type, pattern, replacement in PATTERNS:

        def replace(match: re.Match[str]) -> str:
            original = match.group(0)

            findings.append(
                RedactionFinding(
                    pii_type=pii_type,
                    original=original,
                    replacement=replacement,
                )
            )

            return replacement

        redacted = pattern.sub(replace, redacted)

    return redacted, findings


def contains_pii(text: str) -> bool:
    if not isinstance(text, str):
        raise TypeError("text must be str")

    return any(
        pattern.search(text) is not None
        for _, pattern, _ in PATTERNS
    )


def _sanitize_value(
    value: Any,
    field_path: str,
) -> tuple[Any, list[RedactionFinding]]:
    if isinstance(value, dict):
        return sanitize_record(
            value,
            parent_path=field_path,
        )

    if isinstance(value, list):
        sanitized_items = []
        findings: list[RedactionFinding] = []

        for index, item in enumerate(value):
            sanitized, child_findings = _sanitize_value(
                item,
                f"{field_path}[{index}]",
            )
            sanitized_items.append(sanitized)
            findings.extend(child_findings)

        return sanitized_items, findings

    if isinstance(value, str):
        redacted, findings = redact_text(value)

        findings = [
            RedactionFinding(
                pii_type=item.pii_type,
                original=item.original,
                replacement=item.replacement,
                field_path=field_path,
            )
            for item in findings
        ]

        return redacted, findings

    return value, []


def sanitize_record(
    record: dict[str, Any],
    parent_path: str = "",
) -> tuple[dict[str, Any], list[RedactionFinding]]:
    if not isinstance(record, dict):
        raise TypeError("record must be dict")

    sanitized: dict[str, Any] = {}
    findings: list[RedactionFinding] = []

    for key, value in record.items():
        normalized_key = key.strip().lower()
        field_path = (
            f"{parent_path}.{key}"
            if parent_path
            else key
        )

        if normalized_key in STRUCTURED_FIELD_TOKENS:
            pii_type, replacement = STRUCTURED_FIELD_TOKENS[
                normalized_key
            ]

            if value is not None:
                findings.append(
                    RedactionFinding(
                        pii_type=pii_type,
                        original=str(value),
                        replacement=replacement,
                        field_path=field_path,
                    )
                )

                sanitized[key] = replacement
            else:
                sanitized[key] = None

            continue

        sanitized_value, child_findings = _sanitize_value(
            value,
            field_path,
        )

        sanitized[key] = sanitized_value
        findings.extend(child_findings)

    return sanitized, findings


def redact_record(
    record: dict[str, Any],
) -> dict[str, Any]:
    sanitized, _ = sanitize_record(record)
    return sanitized