"""Cafe24 Day 5 실제 Read-Only Smoke Test API."""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request, status

from backend.app.adapters.providers.base import ProviderNonRetryableError
from backend.app.adapters.providers.cafe24.adapter import Cafe24Adapter
from backend.app.adapters.providers.capability_guard import (
    CAFE24_ALLOWED_READ_PATHS,
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
    except httpx.HTTPError as exc:
        raise ProviderNonRetryableError(
            "Cafe24 HTTP 요청에 실패했습니다."
        ) from exc

    if response.status_code != 200:
        raise ProviderNonRetryableError(
            f"Cafe24 Read 요청이 실패했습니다. status={response.status_code}"
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise ProviderNonRetryableError(
            "Cafe24 응답이 올바른 JSON 형식이 아닙니다."
        ) from exc

    if not isinstance(payload, dict):
        raise ProviderNonRetryableError(
            "Cafe24 응답이 JSON Object 형식이 아닙니다."
        )

    return payload


@router.get("/smoke")
def cafe24_live_read_smoke(request: Request) -> dict[str, object]:
    """Cafe24 상품/주문을 각각 최대 25건 Read-Only로 검증한다."""

    settings = request.app.state.settings

    mall_id = settings.cafe24_mall_id
    access_token = getattr(
        request.app.state,
        "cafe24_access_token",
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
                "message": "Cafe24 OAuth Access Token이 현재 서버 메모리에 없습니다.",
            },
        )

    transport = ReadOnlyHttpTransport(
        request_fn=_request_json,
        granted_scopes={
            "mall.read_product",
            "mall.read_order",
        },
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
    )

    adapter = Cafe24Adapter(
        mall_id=mall_id,
        access_token=access_token,
        transport=transport,
    )

    try:
        products_page = adapter.read_products()
    except ProviderNonRetryableError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "CAFE24_PRODUCTS_READ_FAILED",
                "message": str(exc),
            },
        ) from exc

    try:
        orders_page = adapter.read_orders()
    except ProviderNonRetryableError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "CAFE24_ORDERS_READ_FAILED",
                "message": str(exc),
            },
        ) from exc

    product_count = len(products_page.items)
    order_count = len(orders_page.items)

    return {
        "status": "LIVE_READ_OK",
        "provider": "CAFE24",
        "mall_id": mall_id,
        "products": {
            "count": product_count,
            "has_more": products_page.has_more,
            "next_cursor_set": products_page.next_cursor is not None,
        },
        "orders": {
            "count": order_count,
            "has_more": orders_page.has_more,
            "next_cursor_set": orders_page.next_cursor is not None,
        },
        "total_items": product_count + order_count,
        "read_call_count": transport.request_count,
        "write_call_count": 0,
        "token_exposed": False,
    }