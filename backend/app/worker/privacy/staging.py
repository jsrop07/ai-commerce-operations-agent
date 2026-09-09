"""Provider raw 데이터와 일반 처리 데이터 사이의 개인정보 보호 경계."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any
from backend.app.worker.privacy.text_redaction import redact_free_text

# 일반 파이프라인으로 그대로 전달하지 않는 대표 민감 필드명.
SENSITIVE_FIELD_NAMES = frozenset(
    {
        "name",
        "customer_name",
        "buyer_name",
        "receiver_name",
        "email",
        "phone",
        "mobile",
        "cellphone",
        "address",
        "address1",
        "address2",
        "zipcode",
        "password",
        "secret",
        "access_token",
        "refresh_token",
        "client_secret",
        "id_token",
        "token",
        "client_ip",
        "ip_address",

        "member_id",
        "writer_email",
        "writer",
        "nick_name",
        "reply_user_id",

        "api_key",
        "authorization",

        "buyer_email",
        "receiver_email",
        "buyer_cellphone",
        "receiver_cellphone",
    }
)


@dataclass(frozen=True)
class ProtectedRawReference:
    """Raw payload용 비민감 논리 참조.

    Day 5의 protected scheme 값은 보호 저장소에 실제 저장되었다는 증명이
    아니며, 저장소 연동 전의 경계 식별자일 뿐이다.
    """

    provider: str
    resource: str
    raw_sha256: str
    storage_ref: str


@dataclass(frozen=True)
class SanitizedStagingRecord:
    """일반 Mapper/Inbox로 전달할 수 있는 비식별 staging 레코드."""

    provider: str
    resource: str
    raw_ref: ProtectedRawReference
    sanitized_payload: dict[str, Any]


def build_raw_sha256(payload: dict[str, Any]) -> str:
    """raw 원문 자체 대신 추적 가능한 SHA-256 hash를 생성한다."""

    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(canonical).hexdigest()


def sanitize_value(value: Any) -> Any:
    """중첩 데이터와 자유입력 문자열을 재귀적으로 비식별한다."""

    if isinstance(value, dict):
        return sanitize_record(value)

    if isinstance(value, list):
        return [sanitize_value(item) for item in value]

    if isinstance(value, str):
        return redact_free_text(value)

    return value


def sanitize_record(payload: dict[str, Any]) -> dict[str, Any]:
    """민감 필드를 제거하고 일반 파이프라인용 payload를 만든다."""

    sanitized: dict[str, Any] = {}

    for key, value in payload.items():
        normalized_key = key.strip().lower()

        if normalized_key in SENSITIVE_FIELD_NAMES:
            continue

        # Structured routing identifiers must survive; references inside prose are redacted.
        identifier_pattern = {
            "order_id": r"[0-9]{8}-[0-9]{6,}",
            "order_item_code": r"[0-9]{8}-[0-9]{6,}-[0-9]+",
        }.get(normalized_key)
        if identifier_pattern and isinstance(value, str) and re.fullmatch(identifier_pattern, value):
            sanitized[key] = value
        else:
            sanitized[key] = sanitize_value(value)

    return sanitized


COMMUNITY_IDENTIFIER_FIELDS = frozenset(
    {
        "board_no",
        "article_no",
        "comment_no",
        "parent_article_no",
        "parent_comment_no",
        "category_no",
        "reply",
        "reply_depth",
        "created_date",
        "updated_date",
        "subject_sha256",
        "content_sha256",
        "has_attachments",
        "attachment_count",
        "attachment_source_sha256",
    }
)


def sanitize_community_record(payload: dict[str, Any]) -> dict[str, Any]:
    """Allowlist relationship fields and retain only hashes for free text/URLs."""

    sanitized = {
        key: sanitize_value(value)
        for key, value in payload.items()
        if key.strip().lower() in COMMUNITY_IDENTIFIER_FIELDS
    }

    for field_name in ("subject", "content"):
        value = payload.get(field_name)
        if isinstance(value, str) and value:
            sanitized[f"{field_name}_sha256"] = hashlib.sha256(
                value.encode("utf-8")
            ).hexdigest()

    attachments = payload.get("attach_file_urls")
    source_hashes: list[str] = []
    if isinstance(attachments, list):
        for item in attachments:
            if not isinstance(item, dict):
                continue
            url = item.get("url")
            if isinstance(url, str) and url:
                source_hashes.append(hashlib.sha256(url.encode("utf-8")).hexdigest())

    if source_hashes:
        sanitized["has_attachments"] = True
        sanitized["attachment_count"] = len(source_hashes)
        sanitized["attachment_source_sha256"] = source_hashes
    else:
        sanitized["has_attachments"] = False
        sanitized["attachment_count"] = 0

    return sanitized
def build_staging_record(
    *,
    provider: str,
    resource: str,
    raw_payload: dict[str, Any],
    storage_ref: str,
) -> SanitizedStagingRecord:
    """raw 보호 참조와 sanitized payload를 하나의 staging 객체로 만든다."""

    raw_ref = ProtectedRawReference(
        provider=provider,
        resource=resource,
        raw_sha256=build_raw_sha256(raw_payload),
        storage_ref=storage_ref,
    )

    return SanitizedStagingRecord(
        provider=provider,
        resource=resource,
        raw_ref=raw_ref,
        sanitized_payload=sanitize_record(raw_payload),
    )
