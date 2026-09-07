import httpx
import pytest

from backend.app.adapters.providers.base import (
    ProviderHttpError,
    ProviderNonRetryableError,
    ProviderTransientError,
)
from backend.app.api import cafe24_smoke


def test_cafe24_429_preserves_retry_after(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_request(**_: object) -> httpx.Response:
        return httpx.Response(
            429,
            headers={"Retry-After": "2.5"},
        )

    monkeypatch.setattr(cafe24_smoke.httpx, "request", fake_request)

    with pytest.raises(ProviderHttpError) as exc_info:
        cafe24_smoke._request_json(
            method="GET",
            url="https://example.invalid",
        )

    assert exc_info.value.status_code == 429
    assert exc_info.value.retry_after_seconds == 2.5


def test_cafe24_503_is_retryable_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_request(**_: object) -> httpx.Response:
        return httpx.Response(503)

    monkeypatch.setattr(cafe24_smoke.httpx, "request", fake_request)

    with pytest.raises(ProviderHttpError) as exc_info:
        cafe24_smoke._request_json(
            method="GET",
            url="https://example.invalid",
        )

    assert exc_info.value.status_code == 503


def test_cafe24_timeout_is_transient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_request(**_: object) -> httpx.Response:
        raise httpx.ReadTimeout("timeout")

    monkeypatch.setattr(cafe24_smoke.httpx, "request", fake_request)

    with pytest.raises(ProviderTransientError):
        cafe24_smoke._request_json(
            method="GET",
            url="https://example.invalid",
        )


def test_cafe24_401_is_not_retryable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_request(**_: object) -> httpx.Response:
        return httpx.Response(401)

    monkeypatch.setattr(cafe24_smoke.httpx, "request", fake_request)

    with pytest.raises(ProviderNonRetryableError):
        cafe24_smoke._request_json(
            method="GET",
            url="https://example.invalid",
        )
