"""Cafe24 OAuth refresh token을 repo 밖 보호 경로에 저장한다."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.app.worker.privacy.protected_storage import _require_protected_root


TOKEN_FILENAME = "cafe24_refresh_token.json"


def _token_file_path(protected_root: str) -> Path:
    root = _require_protected_root(Path(protected_root))

    secret_dir = root / "secrets"
    secret_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    return secret_dir / TOKEN_FILENAME


def save_refresh_token(
    *,
    protected_root: str,
    refresh_token: str,
    refresh_token_expires_at: str | None,
    mall_id: str,
    shop_no: str,
    scopes: list[str],
) -> Path:
    """Refresh token과 복구에 필요한 최소 metadata만 저장한다."""

    if not refresh_token:
        raise ValueError("refresh_token이 비어 있습니다.")

    payload: dict[str, Any] = {
        "refresh_token": refresh_token,
        "refresh_token_expires_at": refresh_token_expires_at,
        "mall_id": mall_id,
        "shop_no": shop_no,
        "scopes": sorted(scopes),
    }

    path = _token_file_path(
        protected_root
    )

    temp_path = path.with_suffix(".tmp")

    temp_path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    temp_path.replace(path)

    return path


def load_refresh_token(
    *,
    protected_root: str,
) -> dict[str, Any]:
    """저장된 Cafe24 refresh token metadata를 읽는다."""

    path = _token_file_path(
        protected_root
    )

    if not path.exists():
        raise FileNotFoundError(
            "저장된 Cafe24 refresh token이 없습니다."
        )

    payload = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(payload, dict):
        raise ValueError(
            "Cafe24 refresh token 저장 형식이 잘못되었습니다."
        )

    refresh_token = payload.get(
        "refresh_token"
    )

    if (
        not isinstance(refresh_token, str)
        or not refresh_token
    ):
        raise ValueError(
            "저장된 refresh_token이 없습니다."
        )

    return payload