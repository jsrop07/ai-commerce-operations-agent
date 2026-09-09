"""자유입력 텍스트에서 기본 개인정보 패턴을 비식별한다."""

from __future__ import annotations

import re


EMAIL_PATTERN = re.compile(
    r"(?<![A-Za-z0-9._%+-])"
    r"[A-Za-z0-9._%+-]+"
    r"@[A-Za-z0-9.-]+"
    r"\.[A-Za-z]{2,}"
    r"(?![A-Za-z0-9.-])"
)

PHONE_PATTERN = re.compile(
    r"(?<!\d)"
    r"(?:01[016789])"
    r"[-.\s]?\d{3,4}"
    r"[-.\s]?\d{4}"
    r"(?!\d)"
)

IPV4_PATTERN = re.compile(
    r"\b"
    r"(?:\d{1,3}\.){3}\d{1,3}"
    r"\b"
)

ORDER_ID_PATTERN = re.compile(
    r"\b\d{8}-\d{6,}\b"
)


def redact_free_text(value: str) -> str:
    """문의/댓글 등 자유입력 문자열에서 명확한 PII 패턴을 치환한다."""

    redacted = EMAIL_PATTERN.sub("<EMAIL>", value)
    redacted = PHONE_PATTERN.sub("<PHONE>", redacted)
    redacted = IPV4_PATTERN.sub("<IP>", redacted)
    redacted = ORDER_ID_PATTERN.sub("<ORDER_REF>", redacted)

    return redacted