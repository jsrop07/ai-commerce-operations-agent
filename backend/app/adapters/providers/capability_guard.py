"""외부 Provider 읽기 요청을 실제 Transport 전에 검증하는 안전 Guard."""

from __future__ import annotations

from collections.abc import Collection
import re
from urllib.parse import parse_qsl, urlsplit


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
        "/api/v2/admin/categories",
        "/api/v2/admin/refunds",
        "/api/v2/admin/boards",
    }
)

CAFE24_ALLOWED_READ_PATH_PATTERNS = (
    re.compile(
        r"^/api/v2/admin/products/[1-9][0-9]*/variants$"
    ),
    re.compile(
        r"^/api/v2/admin/products/[1-9][0-9]*/variants/"
        r"[A-Za-z0-9_-]+/inventories$"
    ),
    re.compile(
        r"^/api/v2/admin/categories/[1-9][0-9]*$"
    ),
    re.compile(
        r"^/api/v2/admin/orders/[A-Za-z0-9_-]+/items$"
    ),
    re.compile(
        r"^/api/v2/admin/boards/[1-9][0-9]*/articles$"
    ),
    re.compile(
        r"^/api/v2/admin/boards/[1-9][0-9]*/articles/"
        r"[1-9][0-9]*/comments$"
    ),
)
CAFE24_ALLOWED_READ_SCOPES = frozenset(
    {
        "mall.read_product",
        "mall.read_order",
        "mall.read_category",
        "mall.read_community",
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

    if granted - CAFE24_ALLOWED_READ_SCOPES:
        raise CredentialScopeError(
            "AUTH_SCOPE_INVALID: 허용하지 않은 Credential Scope가 포함되어 있습니다."
        )

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
    allowed_path_patterns: Collection[re.Pattern[str]] | None = None,
) -> str:
    """정적 또는 명시적으로 허용한 동적 GET Path만 통과시킨다."""

    # Reject before URL parsing can discard control characters or URL suffixes.
    if any(char in path_or_url for char in ("%", "\\", "#")) or any(
        ord(char) <= 32 or ord(char) == 127 for char in path_or_url
    ):
        raise ProviderWriteBlockedError("PROVIDER_WRITE_BLOCKED: invalid Provider URL")
    try:
        parsed = urlsplit(path_or_url)
    except ValueError:
        raise ProviderWriteBlockedError("PROVIDER_WRITE_BLOCKED: invalid Provider URL") from None
    if parsed.query:
        try:
            pairs = parse_qsl(parsed.query, strict_parsing=True)
        except ValueError:
            raise ProviderWriteBlockedError("PROVIDER_WRITE_BLOCKED: invalid query") from None
        if not pairs or len({key for key, _ in pairs}) != len(pairs) or any(
            key not in {"limit", "offset"} or not re.fullmatch(r"[0-9]+", value)
            for key, value in pairs
        ):
            raise ProviderWriteBlockedError("PROVIDER_WRITE_BLOCKED: invalid query")
    if (parsed.scheme or parsed.netloc) and (
        parsed.scheme != "https"
        or not re.fullmatch(r"[a-z0-9][a-z0-9-]*\.cafe24api\.com", parsed.netloc)
    ):
        raise ProviderWriteBlockedError("PROVIDER_WRITE_BLOCKED: invalid Provider origin")
    path = parsed.path
    if any(segment in {".", ".."} for segment in path.split("/")):
        raise ProviderWriteBlockedError("PROVIDER_WRITE_BLOCKED: invalid Provider Path")

    if path in set(allowed_paths):
        return path

    if allowed_path_patterns is not None:
        for pattern in allowed_path_patterns:
            if pattern.fullmatch(path):
                return path

    raise ProviderWriteBlockedError(
        "PROVIDER_WRITE_BLOCKED: 허용되지 않은 Provider Path입니다: "
    )


def validate_provider_read_request(
    *,
    method: str,
    path_or_url: str,
    granted_scopes: Collection[str] | None,
    required_scopes: Collection[str],
    allowed_paths: Collection[str],
    allowed_path_patterns: Collection[re.Pattern[str]] | None = None,
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
        allowed_path_patterns=allowed_path_patterns,
    )