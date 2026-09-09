"""Cafe24 보호 Raw Snapshot 저장과 Sanitized Export 지원."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.app.worker.privacy.staging import sanitize_record


@dataclass(frozen=True)
class ProtectedSnapshotResult:
    provider: str
    resource: str
    batch_id: str
    raw_sha256: str
    raw_path: Path = field(repr=False)
    sanitized_path: Path = field(repr=False)
    raw_count: int
    sanitized_count: int


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def build_snapshot_sha256(payload: Any) -> str:
    return hashlib.sha256(
        _canonical_json_bytes(payload)
    ).hexdigest()


def _require_component(value: str) -> None:
    """Only opaque, non-sensitive identifiers may be used in snapshot metadata."""
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", value):
        raise ValueError("invalid snapshot identifier")
    if value.upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(10)), *(f"LPT{i}" for i in range(10))}:
        raise ValueError("invalid snapshot identifier")


def _require_protected_root(root: Path) -> Path:
    expanded = root.expanduser()
    if not expanded.is_absolute():
        raise ValueError("protected data root must be absolute")
    resolved = expanded.resolve()
    repo = Path(__file__).resolve().parents[4]
    if resolved.is_relative_to(repo) or any(
        (parent / ".git").exists() for parent in (resolved, *resolved.parents)
    ):
        raise ValueError("protected data root must be outside repositories")
    return resolved


def _require_contained(root: Path, target: Path) -> None:
    resolved = target.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("protected snapshot target escapes its root")
    _require_protected_root(resolved)


def write_protected_snapshot(
    *,
    protected_root: Path,
    provider: str,
    resource: str,
    batch_id: str,
    records: list[dict[str, Any]],
) -> ProtectedSnapshotResult:
    """Raw 원본과 Sanitized Export를 분리 저장한다."""

    if not provider.strip():
        raise ValueError("provider가 비어 있습니다.")

    if not resource.strip():
        raise ValueError("resource가 비어 있습니다.")

    if not batch_id.strip():
        raise ValueError("batch_id가 비어 있습니다.")

    if not all(isinstance(item, dict) for item in records):
        raise ValueError(
            "records의 모든 항목은 JSON Object여야 합니다."
        )

    for component in (provider, resource, batch_id):
        _require_component(component)
    root = _require_protected_root(protected_root)

    raw_dir = root / provider.lower() / "raw" / resource
    sanitized_dir = (
        root / provider.lower() / "sanitized" / resource
    )

    _require_contained(root, raw_dir / f"{batch_id}.json")
    _require_contained(root, sanitized_dir / f"{batch_id}.sanitized.json")
    raw_dir.mkdir(parents=True, exist_ok=True)
    sanitized_dir.mkdir(parents=True, exist_ok=True)

    raw_payload = {
        "provider": provider,
        "resource": resource,
        "batch_id": batch_id,
        "records": records,
    }

    raw_sha256 = build_snapshot_sha256(raw_payload)

    raw_path = raw_dir / f"{batch_id}.json"
    sanitized_path = (
        sanitized_dir / f"{batch_id}.sanitized.json"
    )

    # 동일 batch를 덮어써서 Raw 원본이 변하는 것을 금지한다.
    if raw_path.exists() or sanitized_path.exists():
        raise FileExistsError(
            "protected snapshot already exists"
        )

    sanitized_records = [
        sanitize_record(record)
        for record in records
    ]

    with raw_path.open("x", encoding="utf-8") as stream:
        json.dump(raw_payload, stream, ensure_ascii=False, indent=2)

    sanitized_payload = {
        "provider": provider,
        "resource": resource,
        "batch_id": batch_id,
        "raw_sha256": raw_sha256,
        "records": sanitized_records,
    }

    with sanitized_path.open("x", encoding="utf-8") as stream:
        json.dump(sanitized_payload, stream, ensure_ascii=False, indent=2)

    return ProtectedSnapshotResult(
        provider=provider,
        resource=resource,
        batch_id=batch_id,
        raw_sha256=raw_sha256,
        raw_path=raw_path,
        sanitized_path=sanitized_path,
        raw_count=len(records),
        sanitized_count=len(sanitized_records),
    )

class ResponseCredentialFieldError(ValueError):
    """응답 JSON의 필드명이 credential 필드 규칙에 걸린 경우."""


class ResponseCredentialTextError(ValueError):
    """응답 일반 문자열이 credential 텍스트 규칙에 걸린 경우."""

@dataclass(frozen=True)
class ProtectedRawResponse:
    provider: str
    resource: str
    batch_id: str
    raw_sha256: str
    raw_path: Path = field(repr=False)
    raw_count: int


@dataclass(frozen=True)
class SanitizedSnapshotResult:
    provider: str
    resource: str
    batch_id: str
    sanitized_path: Path = field(repr=False)
    sanitized_count: int


def _reject_response_credentials(value: Any) -> None:
    # Preserve actual response bytes/fields by rejecting, never editing, a credential body.
    forbidden = {
        "authorization", "headers", "header", "token", "idtoken",
        "accesstoken", "refreshtoken",
        "clientsecret", "password", "apikey", "cookie", "setcookie",
    }
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                raise ValueError(
                    "credential-bearing response cannot be captured"
                )

            normalized_key = re.sub(
                r"[\s_-]",
                "",
                key,
            ).lower()

            if normalized_key in forbidden:
                raise ResponseCredentialFieldError(
                    "credential field detected"
                )

            # Cafe24 Community Article의 secret은
            # credential이 아니라 비밀글 여부 flag이다.
            if normalized_key == "secret":
                allowed_secret_flags = {
                    None,
                    True,
                    False,
                    0,
                    1,
                    "T",
                    "F",
                    "Y",
                    "N",
                    "true",
                    "false",
                }

                if child not in allowed_secret_flags:
                    raise ValueError(
                        "unexpected secret-like response value"
                    )

                continue

            _reject_response_credentials(child)
    elif isinstance(value, list):
        for child in value:
            _reject_response_credentials(child)
    elif isinstance(value, str) and re.search(
        r"(?i)\bauthorization\s*:\s*bearer\b",
        value,
    ):
        raise ResponseCredentialTextError(
            "credential-like text detected"
        )


def write_protected_raw_response(
    *, protected_root: Path, provider: str, resource: str, batch_id: str,
    page_id: str, payload: dict[str, Any], raw_count: int,
) -> ProtectedRawResponse:
    """Persist only the actual HTTP JSON body; its canonical bytes define raw_sha256."""
    root = _require_protected_root(protected_root)
    for component in (provider, resource, batch_id, page_id):
        _require_component(component)
    if not isinstance(payload, dict) or type(raw_count) is not int or raw_count < 0:
        raise ValueError("invalid raw response metadata")
    _reject_response_credentials(payload)
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")
    target = root / provider.lower() / "raw" / batch_id / resource / f"{page_id}.json"
    _require_contained(root, target)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(body)
    except FileExistsError:
        raise FileExistsError("protected raw response already exists") from None
    except OSError:
        raise OSError("protected raw response write failed") from None
    return ProtectedRawResponse(
        provider=provider, resource=resource, batch_id=batch_id,
        raw_sha256=hashlib.sha256(body).hexdigest(), raw_path=target, raw_count=raw_count,
    )


def write_sanitized_export(
    *, protected_root: Path, provider: str, resource: str, batch_id: str,
    records: list[dict[str, Any]],
) -> SanitizedSnapshotResult:
    """Export adapter staging records without pretending they are provider raw."""
    root = _require_protected_root(protected_root)
    for component in (provider, resource, batch_id):
        _require_component(component)
    target = root / provider.lower() / "sanitized" / resource / f"{batch_id}.sanitized.json"
    _require_contained(root, target)
    payload = {"provider": provider, "resource": resource, "batch_id": batch_id,
               "records": [sanitize_record(record) for record in records]}
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("x", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
    except FileExistsError:
        raise FileExistsError("sanitized export already exists") from None
    except OSError:
        raise OSError("sanitized export write failed") from None
    return SanitizedSnapshotResult(
        provider=provider, resource=resource, batch_id=batch_id,
        sanitized_path=target, sanitized_count=len(records),
    )
