"""읽기 안전 Guard를 반드시 통과해야 하는 Provider HTTP Transport 경계."""

from __future__ import annotations

from collections.abc import Callable, Collection
from typing import Any

from backend.app.adapters.providers.capability_guard import (
    validate_provider_read_request,
)

RequestFunction = Callable[..., Any]


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
    ) -> None:
        self._request_fn = request_fn
        self._granted_scopes = (
            tuple(granted_scopes) if granted_scopes is not None else None
        )
        self._allowed_paths = tuple(allowed_paths)

        self.request_count = 0

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

        validate_provider_read_request(
            method="GET",
            path_or_url=url,
            granted_scopes=self._granted_scopes,
            required_scopes=required_scopes,
            allowed_paths=self._allowed_paths,
        )

        response = self._request_fn(
            method="GET",
            url=url,
            headers=headers,
            params=params,
            timeout=timeout,
        )

        self.request_count += 1

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

        validate_provider_read_request(
            method=method,
            path_or_url=url,
            granted_scopes=self._granted_scopes,
            required_scopes=required_scopes,
            allowed_paths=self._allowed_paths,
        )

        response = self._request_fn(
            method="GET",
            url=url,
            headers=headers,
            params=params,
            timeout=timeout,
        )

        self.request_count += 1

        return response