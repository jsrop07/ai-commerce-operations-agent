"""Structured correlation context without raw payload logging."""

from __future__ import annotations

import contextlib
import contextvars
import json
import logging
from collections.abc import Iterator, Mapping
from dataclasses import asdict, dataclass
from urllib.parse import parse_qs


CAFE24_OAUTH_QUERY_STATE_KEY = "_cafe24_oauth_query"


class RedactCafe24OAuthQueryMiddleware:
    """Keep OAuth callback values in-memory while hiding them from access logs."""

    def __init__(self, app: object) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: object, send: object) -> None:
        if (
            scope.get("type") == "http"
            and scope.get("path") == "/internal/cafe24/oauth/callback"
        ):
            raw_query = scope.get("query_string", b"")
            parsed: dict[str, list[str]] = {}
            try:
                parsed = parse_qs(
                    raw_query.decode("ascii"),
                    keep_blank_values=True,
                    strict_parsing=True,
                )
            except (UnicodeDecodeError, ValueError):
                parsed = {}

            state = scope.setdefault("state", {})
            state[CAFE24_OAUTH_QUERY_STATE_KEY] = {
                key: values[0]
                for key, values in parsed.items()
                if key in {"code", "state", "error"} and len(values) == 1
            }
            scope["query_string"] = b""

        await self.app(scope, receive, send)


@dataclass(frozen=True)
class CorrelationContext:
    request_id: str
    trace_id: str
    correlation_id: str
    tenant_id: str
    environment: str
    event_id: str | None = None


_context: contextvars.ContextVar[CorrelationContext | None] = contextvars.ContextVar(
    "correlation_context", default=None
)


@contextlib.contextmanager
def bind_context(value: CorrelationContext) -> Iterator[None]:
    token = _context.set(value)
    try:
        yield
    finally:
        _context.reset(token)


def current_context() -> CorrelationContext | None:
    return _context.get()


def _contains_forbidden_field(value: object, forbidden: set[str]) -> bool:
    if isinstance(value, Mapping):
        return any(
            any(token in str(field).lower() for token in forbidden)
            or _contains_forbidden_field(nested, forbidden)
            for field, nested in value.items()
        )
    if isinstance(value, (list, tuple, set, frozenset)):
        return any(_contains_forbidden_field(item, forbidden) for item in value)
    return False


def structured_record(message: str, **safe_fields: object) -> str:
    forbidden = {
        "payload",
        "credential",
        "secret",
        "customer_name",
        "email",
        "phone",
        "address",
        "authorization",
        "access_token",
        "refresh_token",
        "api_key",
        "password",
        "cookie",
    }
    if _contains_forbidden_field(safe_fields, forbidden):
        raise ValueError("unsafe field supplied to structured logger")
    value = current_context()
    if value is not None and set(asdict(value)) & set(safe_fields):
        raise ValueError("correlation context fields cannot be overridden")
    record = {"message": message, **(asdict(value) if value else {}), **safe_fields}
    return json.dumps(record, ensure_ascii=False, sort_keys=True, default=str)


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(level=level, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    # Starlette TestClient in this runtime uses API-compatible fork names.
    logging.getLogger("httpx2").setLevel(logging.WARNING)
    logging.getLogger("httpcore2").setLevel(logging.WARNING)
