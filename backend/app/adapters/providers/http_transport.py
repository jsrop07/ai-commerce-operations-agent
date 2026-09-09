"""읽기 안전 Guard를 반드시 통과해야 하는 Provider HTTP Transport 경계."""

from __future__ import annotations

from collections.abc import Callable, Collection
from copy import deepcopy
import json
import re
from typing import Any

from backend.app.adapters.providers.base import ProviderNonRetryableError
from backend.app.adapters.providers.capability_guard import (
    validate_provider_read_request,
)

RequestFunction = Callable[..., Any]
RawCaptureFunction = Callable[[str, Any], None]


class RawCaptureError(ProviderNonRetryableError):
    """Capture failures must stop collection without retrying or exposing payloads."""


class ProviderRequestLimitError(ProviderNonRetryableError):
    """The configured absolute HTTP request limit has been reached."""


class ReadOnlyHttpTransport:
    """실제 HTTP 요청 전에 Scope, Method, Path를 강제 검증한다.

    실제 네트워크 라이브러리는 주입받는다.
    따라서 단위시험에서는 외부 Provider를 호출하지 않고
    호출 여부를 정확하게 검증할 수 있다.
    """

    def __init__(
        self,
        *,
        request_fn: RequestFunction,
        granted_scopes: Collection[str] | None,
        allowed_paths: Collection[str],
        allowed_path_patterns: Collection[re.Pattern[str]] | None = None,
        raw_capture_fn: RawCaptureFunction | None = None,
        max_request_count: int | None = None,
    ) -> None:
        if max_request_count is not None and (
            type(max_request_count) is not int or max_request_count < 1
        ):
            raise ValueError("max_request_count must be at least 1")

        self._request_fn = request_fn
        self._raw_capture_fn = raw_capture_fn
        self._max_request_count = max_request_count
        self._granted_scopes = (
            tuple(granted_scopes) if granted_scopes is not None else None
        )
        self._allowed_paths = tuple(allowed_paths)

        self._allowed_path_patterns = (
            tuple(allowed_path_patterns)
            if allowed_path_patterns is not None
            else ()
        )

        self.request_count = 0

    def with_raw_capture(self, capture_fn: RawCaptureFunction) -> ReadOnlyHttpTransport:
        """Create an isolated transport; never change a shared adapter's capture hook."""
        if self._raw_capture_fn is not None:
            raise RawCaptureError("raw response capture is already configured")
        return ReadOnlyHttpTransport(
            request_fn=self._request_fn,
            granted_scopes=self._granted_scopes,
            allowed_paths=self._allowed_paths,
            allowed_path_patterns=self._allowed_path_patterns,
            raw_capture_fn=capture_fn,
            max_request_count=self._max_request_count,
        )

    def _reserve_request(self) -> None:
        """Count every real attempt and block before an over-limit request."""
        if (
            self._max_request_count is not None
            and self.request_count >= self._max_request_count
        ):
            raise ProviderRequestLimitError("provider HTTP request limit reached")
        self.request_count += 1

    def _capture(
        self,
        path: str,
        response: Any,
        headers: dict[str, str] | None,
    ) -> None:
        if self._raw_capture_fn is None:
            return

        try:
            body = json.dumps(
                response,
                ensure_ascii=False,
                allow_nan=False,
            )
        except Exception as exc:
            raise RawCaptureError(
                "protected raw response capture failed "
                "during serialization: "
                f"{type(exc).__name__}"
            ) from None

        try:
            for key, value in (headers or {}).items():
                if key.lower() in {
                    "authorization",
                    "cookie",
                    "x-api-key",
                }:
                    candidates = [value]

                    if key.lower() == "authorization":
                        candidates.append(
                            value.split(" ", 1)[-1]
                        )

                    if any(
                        candidate
                        and candidate in body
                        for candidate in candidates
                    ):
                        raise ValueError(
                            "credential echo"
                        )

        except Exception as exc:
            raise RawCaptureError(
                "protected raw response capture failed "
                "during credential check: "
                f"{type(exc).__name__}"
            ) from None

        try:
            self._raw_capture_fn(
                path,
                deepcopy(response),
            )

        except Exception as exc:
            raise RawCaptureError(
                "protected raw response capture failed "
                "during raw callback: "
                f"{type(exc).__name__}"
            ) from None

    def get(
        self,
        *,
        url: str,
        required_scopes: Collection[str],
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        timeout: float = 10.0,
    ) -> Any:
        """검증을 통과한 GET 요청만 실제 Request Function으로 전달한다."""

        path = validate_provider_read_request(
            method="GET",
            path_or_url=url,
            granted_scopes=self._granted_scopes,
            required_scopes=required_scopes,
            allowed_paths=self._allowed_paths,
            allowed_path_patterns=self._allowed_path_patterns,
        )

        self._reserve_request()
        response = self._request_fn(
            method="GET",
            url=url,
            headers=headers,
            params=params,
            timeout=timeout,
        )

        self._capture(path, response, headers)

        return response

    def request(
        self,
        *,
        method: str,
        url: str,
        required_scopes: Collection[str],
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        timeout: float = 10.0,
    ) -> Any:
        """GET 이외 Method도 입력은 받지만 Guard가 실제 호출 전에 차단한다."""

        path = validate_provider_read_request(
            method=method,
            path_or_url=url,
            granted_scopes=self._granted_scopes,
            required_scopes=required_scopes,
            allowed_paths=self._allowed_paths,
            allowed_path_patterns=self._allowed_path_patterns,
        )

        self._reserve_request()
        response = self._request_fn(
            method="GET",
            url=url,
            headers=headers,
            params=params,
            timeout=timeout,
        )

        self._capture(path, response, headers)

        return response
