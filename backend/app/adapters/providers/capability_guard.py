"""외부 Provider 읽기 요청을 실제 Transport 전에 검증하는 안전 Guard."""

from __future__ import annotations

from collections.abc import Collection
from urllib.parse import urlsplit


class ProviderReadGuardError(RuntimeError):
    """Provider 읽기 안전조건을 만족하지 못했을 때 발생한다."""

    retryable = False


class CredentialScopeError(ProviderReadGuardError):
    """필수 읽기 Scope가 없거나 Scope가 불명확할 때 발생한다."""

    code = "AUTH_SCOPE_INVALID"


class ProviderWriteBlockedError(ProviderReadGuardError):
    """읽기 전용 정책에서 허용하지 않는 Method/Path를 차단한다."""

    code = "PROVIDER_WRITE_BLOCKED"


CAFE24_ALLOWED_READ_PATHS = frozenset(
    {
        "/api/v2/admin/products",
        "/api/v2/admin/orders",
    }
)


def validate_read_scope(
    *,
    granted_scopes: Collection[str] | None,
    required_scopes: Collection[str],
) -> None:
    """필요한 Read Scope가 모두 명시적으로 존재하는지 확인한다."""

    if not granted_scopes:
        raise CredentialScopeError(
            "AUTH_SCOPE_INVALID: 부여된 Credential Scope를 확인할 수 없습니다."
        )

    granted = set(granted_scopes)
    required = set(required_scopes)

    missing = required - granted

    if missing:
        missing_text = ", ".join(sorted(missing))
        raise CredentialScopeError(
            f"AUTH_SCOPE_INVALID: 필요한 Read Scope가 없습니다: {missing_text}"
        )


def validate_read_method(method: str) -> None:
    """Core Build 외부 Provider 요청은 GET만 허용한다."""

    normalized = method.strip().upper()

    if normalized != "GET":
        raise ProviderWriteBlockedError(
            f"PROVIDER_WRITE_BLOCKED: 허용되지 않은 HTTP Method입니다: {normalized}"
        )


def validate_read_path(
    path_or_url: str,
    *,
    allowed_paths: Collection[str],
) -> str:
    """Query string을 제외한 Path가 Read Allowlist에 있는지 확인한다."""

    parsed = urlsplit(path_or_url)

    path = parsed.path

    if path not in set(allowed_paths):
        raise ProviderWriteBlockedError(
            f"PROVIDER_WRITE_BLOCKED: 허용되지 않은 Provider Path입니다: {path}"
        )

    return path


def validate_provider_read_request(
    *,
    method: str,
    path_or_url: str,
    granted_scopes: Collection[str] | None,
    required_scopes: Collection[str],
    allowed_paths: Collection[str],
) -> str:
    """Scope → Method → Path 순으로 실제 외부 요청 전에 검증한다."""

    validate_read_scope(
        granted_scopes=granted_scopes,
        required_scopes=required_scopes,
    )

    validate_read_method(method)

    return validate_read_path(
        path_or_url,
        allowed_paths=allowed_paths,
    )