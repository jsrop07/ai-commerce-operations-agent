"""Cafe24 OAuth 승인 및 Access Token 발급을 위한 Day 5 내부 API."""

from __future__ import annotations

import base64
import hmac
import re
from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from backend.app.core.observability import CAFE24_OAUTH_QUERY_STATE_KEY
from backend.app.worker.privacy.oauth_token_store import (
    load_refresh_token,
    save_refresh_token,
)

router = APIRouter(
    prefix="/internal/cafe24/oauth",
    tags=["cafe24-oauth"],
)

REQUIRED_READ_SCOPES = frozenset(
    {
        "mall.read_product",
        "mall.read_order",
        "mall.read_category",
        "mall.read_community",
    }
)

OAUTH_STATE_TTL = timedelta(minutes=10)


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

    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", mall_id):
        raise HTTPException(status_code=409, detail={"code": "CAFE24_MALL_ID_INVALID"})
    return mall_id, client_id, client_secret, redirect_uri


@router.get("/start")
def cafe24_oauth_start(request: Request) -> dict[str, str]:
    """Cafe24 관리자 승인 URL을 생성한다."""

    mall_id, client_id, _, redirect_uri = _require_oauth_settings(request)

    state = token_urlsafe(32)

    request.app.state.cafe24_oauth_state = state
    request.app.state.cafe24_oauth_state_created_at = datetime.now(UTC)
    request.app.state.cafe24_authorization_code = None
    request.app.state.cafe24_access_token = None
    request.app.state.cafe24_refresh_token = None
    request.app.state.cafe24_approved_scopes = []
    request.app.state.cafe24_authorized_mall_id = None
    request.app.state.cafe24_shop_no = None
    request.app.state.cafe24_access_token_expires_at = None
    request.app.state.cafe24_refresh_token_expires_at = None

    query = urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "state": state,
            "redirect_uri": redirect_uri,
            "scope": " ".join(sorted(REQUIRED_READ_SCOPES)),
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
    elif isinstance(scopes, list) and all(isinstance(scope, str) for scope in scopes):
        normalized = scopes
    else:
        normalized = []

    unexpected = set(normalized) - REQUIRED_READ_SCOPES

    if unexpected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "CAFE24_OAUTH_SCOPE_INVALID",
                "message": "허용하지 않은 Cafe24 OAuth 권한이 포함되어 있습니다.",
            },
        )

    missing = REQUIRED_READ_SCOPES - set(normalized)

    if missing:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "CAFE24_OAUTH_SCOPE_MISSING",
                "message": "필수 Cafe24 읽기 권한이 발급되지 않았습니다.",
            },
        )

    return normalized

def _parse_oauth_timestamp(
    value: object,
    *,
    field_name: str,
) -> datetime:
    """Cafe24 OAuth timestamp를 timezone-aware UTC datetime으로 변환한다."""

    if not isinstance(value, str) or not value.strip():
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "CAFE24_OAUTH_TOKEN_METADATA_INVALID",
                "message": f"Cafe24 OAuth {field_name} 값이 없습니다.",
            },
        )

    text = value.strip()

    try:
        parsed = datetime.fromisoformat(
            text.replace("Z", "+00:00")
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "CAFE24_OAUTH_TOKEN_METADATA_INVALID",
                "message": f"Cafe24 OAuth {field_name} 형식이 올바르지 않습니다.",
            },
        ) from None

    # Cafe24 응답 예시는 timezone offset이 없는 ISO timestamp도 사용한다.
    # 이 경우 Cafe24 OAuth metadata 기준 시각으로 취급하되
    # 내부 비교를 위해 UTC aware datetime으로 정규화한다.
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=UTC)

    return parsed.astimezone(UTC)

def _store_oauth_token_metadata(
    request: Request,
    token_data: dict[str, object],
) -> list[str]:
    """검증된 OAuth token metadata만 app.state에 저장한다."""

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

    access_expires_at = _parse_oauth_timestamp(
        token_data.get("expires_at"),
        field_name="expires_at",
    )
    refresh_expires_at = _parse_oauth_timestamp(
        token_data.get("refresh_token_expires_at"),
        field_name="refresh_token_expires_at",
    )

    token_mall_id = token_data.get("mall_id")
    expected_mall_id = request.app.state.settings.cafe24_mall_id

    if (
        not isinstance(token_mall_id, str)
        or not token_mall_id
        or token_mall_id != expected_mall_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "CAFE24_OAUTH_MALL_ID_MISMATCH",
                "message": "Cafe24 OAuth mall_id가 설정값과 일치하지 않습니다.",
            },
        )

    shop_no = token_data.get("shop_no")

    if (
        type(shop_no) not in (str, int)
        or not re.fullmatch(r"[1-9][0-9]*", str(shop_no))
    ):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "CAFE24_OAUTH_SHOP_NO_MISSING",
                "message": "Cafe24 OAuth shop_no가 응답에 없습니다.",
            },
        )

    request.app.state.cafe24_access_token = access_token
    request.app.state.cafe24_refresh_token = refresh_token

    request.app.state.cafe24_access_token_expires_at = (
        access_expires_at
    )
    request.app.state.cafe24_refresh_token_expires_at = (
        refresh_expires_at
    )

    request.app.state.cafe24_approved_scopes = scopes
    request.app.state.cafe24_authorized_mall_id = token_mall_id
    request.app.state.cafe24_shop_no = str(shop_no)

    return scopes

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
    except httpx.HTTPError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "CAFE24_OAUTH_TOKEN_REQUEST_FAILED",
                "message": "Cafe24 Token 서버 호출에 실패했습니다.",
            },
        ) from None

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
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "CAFE24_OAUTH_TOKEN_RESPONSE_INVALID",
                "message": "Cafe24 Token 응답 형식이 올바르지 않습니다.",
            },
        ) from None

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "CAFE24_OAUTH_TOKEN_RESPONSE_INVALID",
                "message": "Cafe24 Token 응답 형식이 올바르지 않습니다.",
            },
        )

    return payload

def _refresh_access_token(
    *,
    mall_id: str,
    client_id: str,
    client_secret: str,
    refresh_token: str,
) -> dict[str, object]:
    """Refresh Token으로 Cafe24 Token을 재발급한다."""

    basic_value = base64.b64encode(
        f"{client_id}:{client_secret}".encode()
    ).decode("ascii")

    token_url = (
        f"https://{mall_id}.cafe24api.com/api/v2/oauth/token"
    )

    try:
        response = httpx.post(
            token_url,
            headers={
                "Authorization": f"Basic {basic_value}",
                "Content-Type": (
                    "application/x-www-form-urlencoded"
                ),
            },
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            timeout=10.0,
        )
    except httpx.HTTPError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "CAFE24_OAUTH_REFRESH_REQUEST_FAILED",
                "message": "Cafe24 Token 갱신 요청에 실패했습니다.",
            },
        ) from None

    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "CAFE24_OAUTH_REFRESH_FAILED",
                "message": "Cafe24 Token 갱신에 실패했습니다.",
            },
        )

    try:
        payload = response.json()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "CAFE24_OAUTH_REFRESH_RESPONSE_INVALID",
                "message": "Cafe24 Token 갱신 응답이 올바르지 않습니다.",
            },
        ) from None

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "CAFE24_OAUTH_REFRESH_RESPONSE_INVALID",
                "message": "Cafe24 Token 갱신 응답이 올바르지 않습니다.",
            },
        )

    return payload

@router.get("/callback")
def cafe24_oauth_callback(
    request: Request,
) -> dict[str, object]:
    """Cafe24 승인 결과를 검증하고 Access Token으로 교환한다."""

    oauth_query = getattr(request.state, CAFE24_OAUTH_QUERY_STATE_KEY, {})
    code = oauth_query.get("code") if isinstance(oauth_query, dict) else None
    state = oauth_query.get("state") if isinstance(oauth_query, dict) else None
    error = oauth_query.get("error") if isinstance(oauth_query, dict) else None

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
    state_created_at = getattr(
        request.app.state,
        "cafe24_oauth_state_created_at",
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
    if state_created_at is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CAFE24_OAUTH_STATE_NOT_PREPARED",
                "message": "Cafe24 OAuth state 생성 시각이 없습니다.",
            },
        )

    now = datetime.now(UTC)

    if (
        state_created_at.tzinfo is None
        or state_created_at.utcoffset() is None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CAFE24_OAUTH_STATE_INVALID_METADATA",
                "message": "Cafe24 OAuth state 시각 정보가 올바르지 않습니다.",
            },
        )

    if not timedelta(0) <= now - state_created_at <= OAUTH_STATE_TTL:
        request.app.state.cafe24_oauth_state = None
        request.app.state.cafe24_oauth_state_created_at = None

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "CAFE24_OAUTH_STATE_EXPIRED",
                "message": "Cafe24 OAuth state가 만료되었습니다.",
            },
        )
    if not hmac.compare_digest(state.encode(), expected_state.encode()):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "CAFE24_OAUTH_STATE_INVALID",
                "message": "Cafe24 OAuth state가 일치하지 않습니다.",
            },
        )

    request.app.state.cafe24_oauth_state = None
    request.app.state.cafe24_oauth_state_created_at = None

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

    scopes = _store_oauth_token_metadata(
        request,
        token_data,
    )
    request.app.state.cafe24_authorization_code = None

    return {
        "status": "authorized",
        "provider": "CAFE24",
        "token_received": True,
        "refresh_token_received": True,
        "scopes": scopes,
        "message": "Cafe24 OAuth 인증과 Token 발급이 정상 완료되었습니다.",
    }

@router.post("/refresh")
def cafe24_oauth_refresh(
    request: Request,
) -> dict[str, object]:
    """저장된 Refresh Token으로 Cafe24 Access Token을 갱신한다."""

    mall_id, client_id, client_secret, _ = (
        _require_oauth_settings(request)
    )

    refresh_token = getattr(
        request.app.state,
        "cafe24_refresh_token",
        None,
    )

    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CAFE24_OAUTH_REFRESH_TOKEN_NOT_AVAILABLE",
                "message": "Cafe24 Refresh Token이 준비되지 않았습니다.",
            },
        )

    refresh_expires_at = getattr(
        request.app.state,
        "cafe24_refresh_token_expires_at",
        None,
    )

    if (
        refresh_expires_at is not None
        and datetime.now(UTC) >= refresh_expires_at
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "CAFE24_OAUTH_REFRESH_TOKEN_EXPIRED",
                "message": "Cafe24 Refresh Token이 만료되었습니다.",
            },
        )

    token_data = _refresh_access_token(
        mall_id=mall_id,
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=refresh_token,
    )

    scopes = _store_oauth_token_metadata(
        request,
        token_data,
    )

    return {
        "status": "refreshed",
        "provider": "CAFE24",
        "token_received": True,
        "refresh_token_received": True,
        "scopes": scopes,
    }

@router.post("/persist-current")
def persist_current_cafe24_refresh_token(
    request: Request,
) -> dict[str, object]:
    """현재 메모리의 refresh token을 repo 밖 보호 영역에 저장한다."""

    settings = request.app.state.settings

    protected_root = (
        settings.cafe24_protected_data_dir
    )

    if not protected_root:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CAFE24_PROTECTED_DIR_MISSING",
                "message": (
                    "Cafe24 protected data dir가 "
                    "설정되지 않았습니다."
                ),
            },
        )

    refresh_token = getattr(
        request.app.state,
        "cafe24_refresh_token",
        None,
    )

    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CAFE24_REFRESH_TOKEN_MISSING",
                "message": (
                    "현재 메모리에 Cafe24 "
                    "refresh token이 없습니다."
                ),
            },
        )

    mall_id = getattr(
        request.app.state,
        "cafe24_authorized_mall_id",
        None,
    )

    shop_no = getattr(
        request.app.state,
        "cafe24_shop_no",
        None,
    )

    scopes = getattr(
        request.app.state,
        "cafe24_approved_scopes",
        None,
    )

    expires_at = getattr(
        request.app.state,
        "cafe24_refresh_token_expires_at",
        None,
    )

    if (
        not mall_id
        or not shop_no
        or not scopes
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CAFE24_TOKEN_METADATA_MISSING",
                "message": (
                    "Cafe24 OAuth metadata가 부족합니다."
                ),
            },
        )

    save_refresh_token(
        protected_root=protected_root,
        refresh_token=refresh_token,
        refresh_token_expires_at=(
            expires_at.isoformat()
            if hasattr(
                expires_at,
                "isoformat",
            )
            else (
                str(expires_at)
                if expires_at is not None
                else None
            )
        ),
        mall_id=str(mall_id),
        shop_no=str(shop_no),
        scopes=list(scopes),
    )

    return {
        "status": "CAFE24_REFRESH_TOKEN_PERSISTED",
        "provider": "CAFE24",
        "token_exposed": False,
        "protected_storage": True,
    }

@router.post("/restore")
def restore_cafe24_oauth(
    request: Request,
) -> dict[str, object]:
    """저장된 refresh token으로 access token을 재발급한다."""

    settings = request.app.state.settings

    protected_root = (
        settings.cafe24_protected_data_dir
    )

    if not protected_root:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CAFE24_PROTECTED_DIR_MISSING",
                "message": (
                    "Cafe24 protected data dir가 "
                    "설정되지 않았습니다."
                ),
            },
        )

    stored = load_refresh_token(
        protected_root=protected_root
    )

    stored_mall_id = stored.get("mall_id")

    if (
        stored_mall_id
        != settings.cafe24_mall_id
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CAFE24_MALL_ID_MISMATCH",
                "message": (
                    "저장된 OAuth Mall ID와 "
                    "현재 설정이 다릅니다."
                ),
            },
        )

    refresh_token = stored[
        "refresh_token"
    ]

    mall_id, client_id, client_secret, _ = (
        _require_oauth_settings(
            request
        )
    )

    token_data = _refresh_access_token(
        mall_id=mall_id,
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=refresh_token,
    )

    _store_oauth_token_metadata(
        request=request,
        token_data=token_data,
    )

    # Refresh 과정에서 새로운 refresh token이 발급됐으면
    # 기존 보호 파일도 최신 값으로 교체한다.
    new_refresh_token = getattr(
        request.app.state,
        "cafe24_refresh_token",
        None,
    )

    new_expires_at = getattr(
        request.app.state,
        "cafe24_refresh_token_expires_at",
        None,
    )

    save_refresh_token(
        protected_root=protected_root,
        refresh_token=new_refresh_token,
        refresh_token_expires_at=(
            new_expires_at.isoformat()
            if hasattr(
                new_expires_at,
                "isoformat",
            )
            else (
                str(new_expires_at)
                if new_expires_at is not None
                else None
            )
        ),
        mall_id=str(
            request.app.state.cafe24_authorized_mall_id
        ),
        shop_no=str(
            request.app.state.cafe24_shop_no
        ),
        scopes=list(
            request.app.state.cafe24_approved_scopes
        ),
    )

    return {
        "status": "CAFE24_OAUTH_RESTORED",
        "provider": "CAFE24",
        "token_received": True,
        "refresh_token_received": True,
        "scopes": list(
            request.app.state.cafe24_approved_scopes
        ),
        "token_exposed": False,
    }