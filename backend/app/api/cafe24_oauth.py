"""Cafe24 OAuth 승인 및 Access Token 발급을 위한 Day 5 내부 API."""

from __future__ import annotations

import base64
import hmac
from secrets import token_urlsafe
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Query, Request, status

router = APIRouter(
    prefix="/internal/cafe24/oauth",
    tags=["cafe24-oauth"],
)

ALLOWED_SCOPES = {
    "mall.read_product",
    "mall.read_order",
}


def _require_oauth_settings(request: Request) -> tuple[str, str, str, str]:
    """OAuth에 필요한 설정을 확인하되 실제 Secret 값은 노출하지 않는다."""

    settings = request.app.state.settings

    mall_id = settings.cafe24_mall_id
    client_id = settings.cafe24_client_id
    client_secret = settings.cafe24_client_secret
    redirect_uri = settings.cafe24_redirect_uri

    if not mall_id or not client_id or not client_secret or not redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CAFE24_OAUTH_CONFIG_MISSING",
                "message": "Cafe24 OAuth 설정이 준비되지 않았습니다.",
            },
        )

    return mall_id, client_id, client_secret, redirect_uri


@router.get("/start")
def cafe24_oauth_start(request: Request) -> dict[str, str]:
    """Cafe24 관리자 승인 URL을 생성한다."""

    mall_id, client_id, _, redirect_uri = _require_oauth_settings(request)

    state = token_urlsafe(32)

    request.app.state.cafe24_oauth_state = state
    request.app.state.cafe24_authorization_code = None
    request.app.state.cafe24_access_token = None
    request.app.state.cafe24_refresh_token = None

    query = urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "state": state,
            "redirect_uri": redirect_uri,
            "scope": "mall.read_product mall.read_order",
        }
    )

    return {
        "status": "ready",
        "authorization_url": (
            f"https://{mall_id}.cafe24api.com"
            f"/api/v2/oauth/authorize?{query}"
        ),
    }


def _validate_scopes(scopes: object) -> list[str]:
    """발급된 Scope가 우리가 요청한 읽기 권한 범위를 벗어나지 않는지 확인한다."""

    if isinstance(scopes, str):
        normalized = [scope for scope in scopes.split() if scope]
    elif isinstance(scopes, list):
        normalized = [str(scope) for scope in scopes]
    else:
        normalized = []

    unexpected = set(normalized) - ALLOWED_SCOPES

    if unexpected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "CAFE24_OAUTH_SCOPE_INVALID",
                "message": "허용하지 않은 Cafe24 OAuth 권한이 포함되어 있습니다.",
            },
        )

    missing = ALLOWED_SCOPES - set(normalized)

    if missing:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "CAFE24_OAUTH_SCOPE_MISSING",
                "message": "필수 Cafe24 읽기 권한이 발급되지 않았습니다.",
            },
        )

    return normalized


def _exchange_authorization_code(
    *,
    mall_id: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    code: str,
) -> dict[str, object]:
    """Authorization Code를 Cafe24 Access Token으로 교환한다."""

    basic_value = base64.b64encode(
        f"{client_id}:{client_secret}".encode()
    ).decode("ascii")

    token_url = f"https://{mall_id}.cafe24api.com/api/v2/oauth/token"

    try:
        response = httpx.post(
            token_url,
            headers={
                "Authorization": f"Basic {basic_value}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
            },
            timeout=10.0,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "CAFE24_OAUTH_TOKEN_REQUEST_FAILED",
                "message": "Cafe24 Token 서버 호출에 실패했습니다.",
            },
        ) from exc

    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "CAFE24_OAUTH_TOKEN_EXCHANGE_FAILED",
                "message": "Cafe24 Authorization Code를 Token으로 교환하지 못했습니다.",
            },
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "CAFE24_OAUTH_TOKEN_RESPONSE_INVALID",
                "message": "Cafe24 Token 응답 형식이 올바르지 않습니다.",
            },
        ) from exc

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "CAFE24_OAUTH_TOKEN_RESPONSE_INVALID",
                "message": "Cafe24 Token 응답 형식이 올바르지 않습니다.",
            },
        )

    return payload


@router.get("/callback")
def cafe24_oauth_callback(
    request: Request,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> dict[str, object]:
    """Cafe24 승인 결과를 검증하고 Access Token으로 교환한다."""

    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "CAFE24_OAUTH_DENIED",
                "message": "Cafe24 OAuth 승인이 거절되었거나 실패했습니다.",
            },
        )

    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "CAFE24_OAUTH_CODE_MISSING",
                "message": "Cafe24 Authorization Code가 없습니다.",
            },
        )

    if not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "CAFE24_OAUTH_STATE_MISSING",
                "message": "Cafe24 OAuth state가 없습니다.",
            },
        )

    expected_state = getattr(
        request.app.state,
        "cafe24_oauth_state",
        None,
    )

    if not expected_state:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CAFE24_OAUTH_STATE_NOT_PREPARED",
                "message": "사전에 생성된 OAuth state가 없습니다.",
            },
        )

    if not hmac.compare_digest(state, expected_state):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "CAFE24_OAUTH_STATE_INVALID",
                "message": "Cafe24 OAuth state가 일치하지 않습니다.",
            },
        )

    request.app.state.cafe24_oauth_state = None

    mall_id, client_id, client_secret, redirect_uri = _require_oauth_settings(
        request
    )

    token_data = _exchange_authorization_code(
        mall_id=mall_id,
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        code=code,
    )

    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")

    if not isinstance(access_token, str) or not access_token:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "CAFE24_OAUTH_ACCESS_TOKEN_MISSING",
                "message": "Cafe24 Access Token이 응답에 없습니다.",
            },
        )

    if not isinstance(refresh_token, str) or not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "CAFE24_OAUTH_REFRESH_TOKEN_MISSING",
                "message": "Cafe24 Refresh Token이 응답에 없습니다.",
            },
        )

    scopes = _validate_scopes(token_data.get("scopes"))

    # Day 5에서는 토큰을 파일/DB에 영구 저장하지 않는다.
    # 실제 값은 응답이나 로그에 절대 노출하지 않고 현재 프로세스 메모리에만 보관한다.
    request.app.state.cafe24_access_token = access_token
    request.app.state.cafe24_refresh_token = refresh_token
    request.app.state.cafe24_authorization_code = None

    return {
        "status": "authorized",
        "provider": "CAFE24",
        "token_received": True,
        "refresh_token_received": True,
        "scopes": scopes,
        "message": "Cafe24 OAuth 인증과 Token 발급이 정상 완료되었습니다.",
    }