"""Cafe24 실제 Read-Only Smoke Test API."""

from __future__ import annotations

from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request, status

from backend.app.api.cafe24_oauth import REQUIRED_READ_SCOPES
from backend.app.adapters.providers.base import (
    ProviderHttpError,
    ProviderNonRetryableError,
    ProviderTransientError,
)
from backend.app.adapters.providers.cafe24.adapter import Cafe24Adapter
from backend.app.adapters.providers.capability_guard import (
    CAFE24_ALLOWED_READ_PATH_PATTERNS,
    CAFE24_ALLOWED_READ_PATHS,
    CredentialScopeError,
    validate_read_scope,
)
from backend.app.adapters.providers.http_transport import ReadOnlyHttpTransport


router = APIRouter(
    prefix="/internal/cafe24",
    tags=["cafe24-smoke"],
)


def _request_json(
    *,
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    timeout: float = 10.0,
) -> dict[str, Any]:
    """실제 Cafe24 GET 응답을 JSON Object로 변환한다.

    응답 본문은 오류 메시지나 로그에 포함하지 않는다.
    주문 개인정보 또는 Token 노출을 방지하기 위함이다.
    """

    try:
        response = httpx.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            timeout=timeout,
        )
    except httpx.TimeoutException:
        raise ProviderTransientError(
            "Cafe24 HTTP 요청 시간이 초과되었습니다."
        ) from None
    except httpx.HTTPError:
        raise ProviderNonRetryableError(
            "Cafe24 HTTP 요청에 실패했습니다."
        ) from None

    if response.status_code == 429:
        retry_after: float | None = None
        raw_retry_after = response.headers.get("Retry-After")

        if raw_retry_after is not None:
            try:
                retry_after = float(raw_retry_after)
            except ValueError:
                try:
                    retry_at = parsedate_to_datetime(
                        raw_retry_after
                    )
                    retry_after = max(
                        0.0,
                        (
                            retry_at
                            - datetime.now(UTC)
                        ).total_seconds(),
                    )
                except (
                    TypeError,
                    ValueError,
                    OverflowError,
                ):
                    retry_after = None

        raise ProviderHttpError(
            429,
            retry_after_seconds=retry_after,
        )

    if 500 <= response.status_code <= 599:
        raise ProviderHttpError(
            response.status_code
        )

    if response.status_code != 200:
        raise ProviderNonRetryableError(
            "Cafe24 Read 요청이 실패했습니다. "
            f"status={response.status_code}"
        )

    try:
        payload = response.json()
    except ValueError:
        raise ProviderNonRetryableError(
            "Cafe24 응답이 올바른 JSON 형식이 아닙니다."
        ) from None

    if not isinstance(payload, dict):
        raise ProviderNonRetryableError(
            "Cafe24 응답이 JSON Object 형식이 아닙니다."
        )

    return payload


@router.get("/smoke")
def cafe24_live_read_smoke(
    request: Request,
) -> dict[str, object]:
    """Cafe24 핵심 Read Scope와 기본 리소스를 소량 검증한다."""

    settings = request.app.state.settings

    mall_id = settings.cafe24_mall_id

    access_token = getattr(
        request.app.state,
        "cafe24_access_token",
        None,
    )

    approved_scopes = getattr(
        request.app.state,
        "cafe24_approved_scopes",
        None,
    )

    if not mall_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CAFE24_MALL_ID_MISSING",
                "message": (
                    "Cafe24 Mall ID가 설정되지 않았습니다."
                ),
            },
        )

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CAFE24_ACCESS_TOKEN_MISSING",
                "message": (
                    "Cafe24 OAuth Access Token이 "
                    "현재 서버 메모리에 없습니다."
                ),
            },
        )

    if not approved_scopes:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CAFE24_APPROVED_SCOPES_MISSING",
                "message": (
                    "Cafe24 OAuth 승인 Scope 정보가 없습니다."
                ),
            },
        )

    if not isinstance(approved_scopes, (list, tuple, set, frozenset)) or any(
        not isinstance(scope, str) for scope in approved_scopes
    ) or set(approved_scopes) != REQUIRED_READ_SCOPES:
        raise HTTPException(status_code=403, detail={"code": "CAFE24_APPROVED_SCOPES_INVALID"})

    expires_at = getattr(request.app.state, "cafe24_access_token_expires_at", None)
    if (
        getattr(request.app.state, "cafe24_authorized_mall_id", None) != mall_id
        or getattr(request.app.state, "cafe24_shop_no", None) != "1"
        or not isinstance(expires_at, datetime)
        or expires_at.tzinfo is None
        or expires_at.utcoffset() is None
        or datetime.now(UTC) >= expires_at
    ):
        # Existing collectors use the provider default shop; other shops are unverified.
        raise HTTPException(status_code=403, detail={"code": "CAFE24_TOKEN_METADATA_INVALID"})

    transport = ReadOnlyHttpTransport(
        request_fn=_request_json,
        granted_scopes=set(
            approved_scopes
        ),
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=(
            CAFE24_ALLOWED_READ_PATH_PATTERNS
        ),
        max_request_count=4,
    )

    adapter = Cafe24Adapter(
        mall_id=mall_id,
        access_token=access_token,
        transport=transport,
    )

    try:
        products_page = adapter.read_products()
    except (ProviderNonRetryableError, ProviderTransientError, ProviderHttpError):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "CAFE24_PRODUCTS_READ_FAILED",
                "message": "Cafe24 Read 요청이 실패했습니다.",
            },
        ) from None

    try:
        orders_page = adapter.read_orders()
    except (ProviderNonRetryableError, ProviderTransientError, ProviderHttpError):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "CAFE24_ORDERS_READ_FAILED",
                "message": "Cafe24 Read 요청이 실패했습니다.",
            },
        ) from None

    try:
        categories_page = adapter.read_categories()
    except (ProviderNonRetryableError, ProviderTransientError, ProviderHttpError):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "CAFE24_CATEGORIES_READ_FAILED",
                "message": "Cafe24 Read 요청이 실패했습니다.",
            },
        ) from None

    try:
        boards_page = adapter.read_boards()
    except (ProviderNonRetryableError, ProviderTransientError, ProviderHttpError):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "CAFE24_BOARDS_READ_FAILED",
                "message": "Cafe24 Read 요청이 실패했습니다.",
            },
        ) from None

    product_count = len(
        products_page.items
    )
    order_count = len(
        orders_page.items
    )
    category_count = len(
        categories_page.items
    )
    board_count = len(
        boards_page.items
    )

    return {
        "status": "LIVE_READ_OK",
        "provider": "CAFE24",
        "mall_id": mall_id,
        "products": {
            "count": product_count,
            "has_more": products_page.has_more,
            "next_cursor_set": (
                products_page.next_cursor
                is not None
            ),
        },
        "orders": {
            "count": order_count,
            "has_more": orders_page.has_more,
            "next_cursor_set": (
                orders_page.next_cursor
                is not None
            ),
        },
        "categories": {
            "count": category_count,
            "has_more": categories_page.has_more,
            "next_cursor_set": (
                categories_page.next_cursor
                is not None
            ),
        },
        "boards": {
            "count": board_count,
            "has_more": boards_page.has_more,
            "next_cursor_set": (
                boards_page.next_cursor
                is not None
            ),
        },
        "total_items": (
            product_count
            + order_count
            + category_count
            + board_count
        ),
        "read_call_count": (
            transport.request_count
        ),
        "write_call_count": 0,
        "token_exposed": False,
    }

@router.get("/smoke-core")
def cafe24_live_read_core_smoke(
    request: Request,
) -> dict[str, object]:
    """현재 승인된 Product/Order 권한만 실제 Read-Only로 검증한다."""

    settings = request.app.state.settings

    mall_id = settings.cafe24_mall_id
    access_token = getattr(
        request.app.state,
        "cafe24_access_token",
        None,
    )
    approved_scopes = getattr(
        request.app.state,
        "cafe24_approved_scopes",
        None,
    )

    if not mall_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CAFE24_MALL_ID_MISSING",
                "message": "Cafe24 Mall ID가 설정되지 않았습니다.",
            },
        )

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CAFE24_ACCESS_TOKEN_MISSING",
                "message": "Cafe24 Access Token이 없습니다.",
            },
        )

    required_scopes = {
        "mall.read_product",
        "mall.read_order",
    }

    try:
        validate_read_scope(
            granted_scopes=approved_scopes,
            required_scopes=required_scopes,
        )
    except CredentialScopeError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CAFE24_CORE_SCOPES_INVALID",
                "message": "Cafe24 Core Read Scope가 유효하지 않습니다.",
            },
        ) from None

    transport = ReadOnlyHttpTransport(
        request_fn=_request_json,
        granted_scopes=set(approved_scopes),
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
        max_request_count=2,
    )

    adapter = Cafe24Adapter(
        mall_id=mall_id,
        access_token=access_token,
        transport=transport,
    )

    products_page = adapter.read_products()
    orders_page = adapter.read_orders()

    return {
        "status": "LIVE_CORE_READ_OK",
        "provider": "CAFE24",
        "products": {
            "count": len(products_page.items),
            "has_more": products_page.has_more,
            "next_cursor_set": products_page.next_cursor is not None,
        },
        "orders": {
            "count": len(orders_page.items),
            "has_more": orders_page.has_more,
            "next_cursor_set": orders_page.next_cursor is not None,
        },
        "read_call_count": transport.request_count,
        "write_call_count": 0,
        "token_exposed": False,
    }