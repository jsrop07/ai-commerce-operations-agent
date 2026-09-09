"""Cafe24 실제 Read-Only Bootstrap 실행 API."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, status

from backend.app.adapters.providers.cafe24.adapter import Cafe24Adapter
from backend.app.adapters.providers.capability_guard import (
    CAFE24_ALLOWED_READ_PATH_PATTERNS,
    CAFE24_ALLOWED_READ_PATHS,
)
from backend.app.adapters.providers.http_transport import ReadOnlyHttpTransport
from backend.app.api.cafe24_oauth import REQUIRED_READ_SCOPES
from backend.app.api.cafe24_smoke import _request_json
from backend.app.sync.cafe24_product_bootstrap import (
    run_cafe24_product_bootstrap,
)

from backend.app.sync.cafe24_community_bootstrap import (
    run_cafe24_community_probe,
)
from backend.app.sync.cafe24_community_article_full_runner import (
    run_cafe24_community_article_full_runner,
)
from backend.app.sync.cafe24_order_bootstrap import (
    run_cafe24_order_probe,
)
from backend.app.sync.cafe24_order_full_runner import (
    run_cafe24_order_full_runner,
)
from backend.app.sync.cafe24_category_bootstrap import (
    run_cafe24_category_probe,
)

from backend.app.sync.cafe24_category_full_runner import (
    run_cafe24_category_full_runner,
)

from backend.app.sync.cafe24_product_full_runner import (
    run_cafe24_product_full_runner,
)

from backend.app.sync.cafe24_community_comment_full_runner import (
    run_cafe24_community_comment_full_runner,
)

from backend.app.sync.cafe24_community_attachment_full_runner import (
    run_cafe24_community_attachment_full_runner,
)

from backend.app.sync.cafe24_order_item_full_runner import (
    run_cafe24_order_item_full_runner,
)

from backend.app.sync.cafe24_refund_full_runner import (
    run_cafe24_refund_full_runner,
)

router = APIRouter(
    prefix="/internal/cafe24/bootstrap",
    tags=["cafe24-bootstrap"],
)


@router.post("/products/probe")
def cafe24_product_probe(
    request: Request,
) -> dict[str, object]:
    """상품 1페이지 + 첫 10개 Variant/Inventory를 LIVE Read 검증한다."""

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

    expires_at = getattr(
        request.app.state,
        "cafe24_access_token_expires_at",
        None,
    )

    if not mall_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CAFE24_MALL_ID_MISSING",
            },
        )

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CAFE24_ACCESS_TOKEN_MISSING",
            },
        )

    if (
        not isinstance(
            approved_scopes,
            (list, tuple, set, frozenset),
        )
        or any(
            not isinstance(scope, str)
            for scope in approved_scopes
        )
        or set(approved_scopes) != REQUIRED_READ_SCOPES
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "CAFE24_APPROVED_SCOPES_INVALID",
            },
        )

    if (
        getattr(
            request.app.state,
            "cafe24_authorized_mall_id",
            None,
        )
        != mall_id
        or getattr(
            request.app.state,
            "cafe24_shop_no",
            None,
        )
        != "1"
        or not isinstance(expires_at, datetime)
        or expires_at.tzinfo is None
        or expires_at.utcoffset() is None
        or datetime.now(UTC) >= expires_at
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "CAFE24_TOKEN_METADATA_INVALID",
            },
        )

    protected_root = settings.cafe24_protected_data_dir

    if not protected_root:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CAFE24_PROTECTED_DIR_MISSING",
            },
        )

    # 첫 LIVE probe는 최대 60회의 실제 HTTP 요청으로 강제 제한한다.
    transport = ReadOnlyHttpTransport(
        request_fn=_request_json,
        granted_scopes=set(
            approved_scopes
        ),
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=(
            CAFE24_ALLOWED_READ_PATH_PATTERNS
        ),
        max_request_count=60,
    )

    adapter = Cafe24Adapter(
        mall_id=mall_id,
        access_token=access_token,
        transport=transport,
    )

    batch_id = (
        "product-probe-"
        + datetime.now(UTC).strftime(
            "%Y%m%dT%H%M%S%fZ"
        )
    )

    try:
        result = run_cafe24_product_bootstrap(
            adapter=adapter,
            protected_root=Path(
                protected_root
            ),
            batch_id=batch_id,

            # 중요:
            # 상품 전체 2,168개를 읽지 않는다.
            # 첫 페이지 25개까지만 읽는다.
            max_pages=1,

            product_offset=0,
            product_batch_size=10,
        )
    
    except Exception as exc:
        print(
            "[CAFE24 PRODUCT PROBE ERROR]",
            type(exc).__name__,
        )
        # 실제 Provider payload/token/PII는 응답에 넣지 않는다.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "CAFE24_PRODUCT_PROBE_FAILED",
                "error_type": type(exc).__name__,
                "write_call_count": 0,
                "token_exposed": False,
            },
        ) from None

    return {
        "status": "CAFE24_PRODUCT_PROBE_OK",
        "provider": "CAFE24",
        "batch_id": result.batch_id,
        "probe_product_count": (
            result.product_page_count
        ),
        "selected_product_count": (
            result.product_page_count
        ),
        "product_offset": (
            result.product_offset
        ),
        "next_product_offset": (
            result.next_product_offset
        ),
        "has_more": (
            result.has_more
        ),
        "variant_count": result.variant_count,
        "inventory_count": result.inventory_count,
        "request_count": result.request_count,
        "write_call_count": (
            result.external_write_count
        ),
        "token_exposed": False,
        "protected_storage": True,
    }

@router.post("/community/probe")
def cafe24_community_probe(
    request: Request,
) -> dict[str, object]:
    """게시판 2개 + 게시판별 글 3개 + 댓글을 소량 LIVE Read 검증한다."""

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

    expires_at = getattr(
        request.app.state,
        "cafe24_access_token_expires_at",
        None,
    )

    if not mall_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CAFE24_MALL_ID_MISSING"},
        )

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CAFE24_ACCESS_TOKEN_MISSING"},
        )

    if (
        not isinstance(
            approved_scopes,
            (list, tuple, set, frozenset),
        )
        or any(
            not isinstance(scope, str)
            for scope in approved_scopes
        )
        or set(approved_scopes) != REQUIRED_READ_SCOPES
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "CAFE24_APPROVED_SCOPES_INVALID"},
        )

    if (
        getattr(
            request.app.state,
            "cafe24_authorized_mall_id",
            None,
        )
        != mall_id
        or getattr(
            request.app.state,
            "cafe24_shop_no",
            None,
        )
        != "1"
        or not isinstance(expires_at, datetime)
        or expires_at.tzinfo is None
        or expires_at.utcoffset() is None
        or datetime.now(UTC) >= expires_at
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "CAFE24_TOKEN_METADATA_INVALID"},
        )

    protected_root = settings.cafe24_protected_data_dir

    if not protected_root:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CAFE24_PROTECTED_DIR_MISSING"},
        )

    # Boards 1 + Articles 2 + Comments 최대 6을 예상.
    # 여유를 두되 폭주 방지를 위해 20회로 제한한다.
    transport = ReadOnlyHttpTransport(
        request_fn=_request_json,
        granted_scopes=set(
            approved_scopes
        ),
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=(
            CAFE24_ALLOWED_READ_PATH_PATTERNS
        ),
        max_request_count=20,
    )

    adapter = Cafe24Adapter(
        mall_id=mall_id,
        access_token=access_token,
        transport=transport,
    )

    batch_id = (
        "community-probe-"
        + datetime.now(UTC).strftime(
            "%Y%m%dT%H%M%S%fZ"
        )
    )

    try:
        result = run_cafe24_community_probe(
            adapter=adapter,
            protected_root=Path(
                protected_root
            ),
            batch_id=batch_id,
            board_limit=2,
            article_limit_per_board=3,
        )
    except Exception as exc:
        print(
            "[CAFE24 COMMUNITY PROBE ERROR]",
            type(exc).__name__,
        )

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "CAFE24_COMMUNITY_PROBE_FAILED",
                "error_type": type(exc).__name__,
                "write_call_count": 0,
                "token_exposed": False,
            },
        ) from None

    return {
        "status": "CAFE24_COMMUNITY_PROBE_OK",
        "provider": "CAFE24",
        "batch_id": result.batch_id,
        "board_count": result.board_count,
        "selected_board_count": (
            result.selected_board_count
        ),
        "article_count": result.article_count,
        "selected_article_count": (
            result.selected_article_count
        ),
        "comment_count": result.comment_count,
        "request_count": result.request_count,
        "write_call_count": (
            result.external_write_count
        ),
        "token_exposed": False,
        "protected_storage": True,
    }
@router.post("/community/articles/full/run")
def cafe24_community_articles_full_run(
    request: Request,
    start_board_no: int = 5,
    start_offset: int = 0,
    max_articles: int = 10000,
) -> dict[str, object]:
    """게시판 5/6 Article을 마지막 페이지까지 Read-Only 수집한다."""

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

    expires_at = getattr(
        request.app.state,
        "cafe24_access_token_expires_at",
        None,
    )

    if not mall_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CAFE24_MALL_ID_MISSING",
            },
        )

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CAFE24_ACCESS_TOKEN_MISSING",
            },
        )

    if (
        not isinstance(
            approved_scopes,
            (list, tuple, set, frozenset),
        )
        or any(
            not isinstance(scope, str)
            for scope in approved_scopes
        )
        or set(approved_scopes)
        != REQUIRED_READ_SCOPES
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "CAFE24_APPROVED_SCOPES_INVALID",
            },
        )

    if (
        getattr(
            request.app.state,
            "cafe24_authorized_mall_id",
            None,
        )
        != mall_id
        or getattr(
            request.app.state,
            "cafe24_shop_no",
            None,
        )
        != "1"
        or not isinstance(
            expires_at,
            datetime,
        )
        or expires_at.tzinfo is None
        or expires_at.utcoffset() is None
        or datetime.now(UTC) >= expires_at
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "CAFE24_TOKEN_METADATA_INVALID",
            },
        )

    protected_root = (
        settings.cafe24_protected_data_dir
    )

    if not protected_root:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CAFE24_PROTECTED_DIR_MISSING",
            },
        )

    if start_board_no not in {5, 6}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": (
                    "CAFE24_COMMUNITY_BOARD_INVALID"
                ),
            },
        )

    if (
        type(start_offset) is not int
        or start_offset < 0
        or start_offset % 25 != 0
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": (
                    "CAFE24_COMMUNITY_OFFSET_INVALID"
                ),
            },
        )

    def adapter_factory() -> Cafe24Adapter:
        transport = ReadOnlyHttpTransport(
            request_fn=_request_json,
            granted_scopes=set(
                approved_scopes
            ),
            allowed_paths=(
                CAFE24_ALLOWED_READ_PATHS
            ),
            allowed_path_patterns=(
                CAFE24_ALLOWED_READ_PATH_PATTERNS
            ),

            # Article page 1개 = GET 1회
            max_request_count=1,
        )

        return Cafe24Adapter(
            mall_id=mall_id,
            access_token=access_token,
            transport=transport,
        )

    try:
        result = (
            run_cafe24_community_article_full_runner(
                adapter_factory=adapter_factory,
                protected_root=Path(
                    protected_root
                ),
                start_board_no=(
                    start_board_no
                ),
                start_offset=start_offset,
                max_articles=max_articles,
                batch_delay_seconds=2.0,
                cooldown_every_articles=50,
                chunk_cooldown_seconds=60.0,
                max_rate_limit_retries=3,
            )
        )

    except Exception as exc:
        print(
            "[CAFE24 COMMUNITY ARTICLE FULL ERROR]",
            type(exc).__name__,
        )

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": (
                    "CAFE24_COMMUNITY_ARTICLE_"
                    "FULL_FAILED"
                ),
                "error_type": (
                    type(exc).__name__
                ),
                "start_board_no": (
                    start_board_no
                ),
                "start_offset": start_offset,
                "write_call_count": 0,
                "token_exposed": False,
            },
        ) from None

    return {
        "status": (
            "CAFE24_COMMUNITY_ARTICLE_FULL_COMPLETED"
            if result.completed
            else (
                "CAFE24_COMMUNITY_ARTICLE_"
                "FULL_LIMIT_REACHED"
            )
        ),
        "provider": "CAFE24",
        "run_id": result.run_id,
        "board_5_count": (
            result.board_5_count
        ),
        "board_6_count": (
            result.board_6_count
        ),
        "total_article_count": (
            result.total_article_count
        ),
        "processed_batch_count": (
            result.processed_batch_count
        ),
        "request_count": (
            result.request_count
        ),
        "board_5_completed": (
            result.board_5_completed
        ),
        "board_6_completed": (
            result.board_6_completed
        ),
        "next_board_no": (
            result.next_board_no
        ),
        "next_article_offset": (
            result.next_article_offset
        ),
        "completed": (
            result.completed
        ),
        "write_call_count": 0,
        "token_exposed": False,
        "protected_storage": True,
    }

@router.post("/community/comments/full/run")
def cafe24_community_comments_full_run(
    request: Request,
) -> dict[str, object]:
    """Board 5/6 모든 고유 Article의 Comment를 Read-Only 수집한다."""

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

    expires_at = getattr(
        request.app.state,
        "cafe24_access_token_expires_at",
        None,
    )

    if not mall_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CAFE24_MALL_ID_MISSING",
            },
        )

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CAFE24_ACCESS_TOKEN_MISSING",
            },
        )

    if (
        not isinstance(
            approved_scopes,
            (list, tuple, set, frozenset),
        )
        or set(
            approved_scopes
        ) != REQUIRED_READ_SCOPES
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "CAFE24_APPROVED_SCOPES_INVALID",
            },
        )

    if (
        getattr(
            request.app.state,
            "cafe24_authorized_mall_id",
            None,
        )
        != mall_id
        or getattr(
            request.app.state,
            "cafe24_shop_no",
            None,
        )
        != "1"
        or not isinstance(
            expires_at,
            datetime,
        )
        or expires_at.tzinfo is None
        or expires_at.utcoffset() is None
        or datetime.now(UTC) >= expires_at
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "CAFE24_TOKEN_METADATA_INVALID",
            },
        )

    protected_root = (
        settings.cafe24_protected_data_dir
    )

    if not protected_root:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CAFE24_PROTECTED_DIR_MISSING",
            },
        )

    def adapter_factory() -> Cafe24Adapter:
        transport = ReadOnlyHttpTransport(
            request_fn=_request_json,
            granted_scopes=set(
                approved_scopes
            ),
            allowed_paths=(
                CAFE24_ALLOWED_READ_PATHS
            ),
            allowed_path_patterns=(
                CAFE24_ALLOWED_READ_PATH_PATTERNS
            ),
            max_request_count=1,
        )

        return Cafe24Adapter(
            mall_id=mall_id,
            access_token=access_token,
            transport=transport,
        )

    try:
        result = (
            run_cafe24_community_comment_full_runner(
                adapter_factory=adapter_factory,
                protected_root=Path(
                    protected_root
                ),
                batch_delay_seconds=0.3,
                cooldown_every_requests=50,
                chunk_cooldown_seconds=60.0,
                max_rate_limit_retries=3,
            )
        )

    except Exception as exc:
        print(
            "[CAFE24 COMMUNITY COMMENT FULL ERROR]",
            type(exc).__name__,
        )

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": (
                    "CAFE24_COMMUNITY_COMMENT_"
                    "FULL_FAILED"
                ),
                "error_type": (
                    type(exc).__name__
                ),
                "write_call_count": 0,
                "token_exposed": False,
            },
        ) from None

    return {
        "status": (
            "CAFE24_COMMUNITY_COMMENT_FULL_COMPLETED"
        ),
        "provider": "CAFE24",
        "run_id": result.run_id,
        "unique_article_count": (
            result.unique_article_count
        ),
        "processed_article_count": (
            result.processed_article_count
        ),
        "comment_count": (
            result.comment_count
        ),
        "article_page_request_count": (
            result.article_page_request_count
        ),
        "comment_request_count": (
            result.comment_request_count
        ),
        "skipped_comment_endpoint_count": (
            result.skipped_comment_endpoint_count
        ),
        "total_request_count": (
            result.total_request_count
        ),
        "completed": result.completed,
        "write_call_count": 0,
        "token_exposed": False,
        "protected_storage": True,
    }

@router.post("/community/attachments/full/run")
def cafe24_community_attachments_full_run(
    request: Request,
) -> dict[str, object]:
    """Community 첨부파일을 Protected 영역으로만 Read-Only 수집한다."""

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

    expires_at = getattr(
        request.app.state,
        "cafe24_access_token_expires_at",
        None,
    )

    if not mall_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CAFE24_MALL_ID_MISSING",
            },
        )

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CAFE24_ACCESS_TOKEN_MISSING",
            },
        )

    if (
        not isinstance(
            approved_scopes,
            (list, tuple, set, frozenset),
        )
        or any(
            not isinstance(
                scope,
                str,
            )
            for scope in approved_scopes
        )
        or set(
            approved_scopes
        ) != REQUIRED_READ_SCOPES
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "CAFE24_APPROVED_SCOPES_INVALID",
            },
        )

    if (
        getattr(
            request.app.state,
            "cafe24_authorized_mall_id",
            None,
        )
        != mall_id
        or getattr(
            request.app.state,
            "cafe24_shop_no",
            None,
        )
        != "1"
        or not isinstance(
            expires_at,
            datetime,
        )
        or expires_at.tzinfo is None
        or expires_at.utcoffset() is None
        or datetime.now(UTC) >= expires_at
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "CAFE24_TOKEN_METADATA_INVALID",
            },
        )

    protected_root = (
        settings.cafe24_protected_data_dir
    )

    if not protected_root:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CAFE24_PROTECTED_DIR_MISSING",
            },
        )

    try:
        result = (
            run_cafe24_community_attachment_full_runner(
                protected_root=Path(
                    protected_root
                ),
                batch_delay_seconds=0.3,
                cooldown_every_requests=50,
                chunk_cooldown_seconds=60.0,
                max_retries=3,
            )
        )

    except Exception as exc:
        # URL, 응답 body, 파일내용을 절대 로그에 출력하지 않는다.
        print(
            "[CAFE24 COMMUNITY ATTACHMENT FULL ERROR]",
            type(exc).__name__,
        )

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": (
                    "CAFE24_COMMUNITY_ATTACHMENT_"
                    "FULL_FAILED"
                ),
                "error_type": (
                    type(exc).__name__
                ),
                "write_call_count": 0,
                "token_exposed": False,
            },
        ) from None

    return {
        "status": (
            "CAFE24_COMMUNITY_ATTACHMENT_FULL_COMPLETED"
            if result.completed
            else (
                "CAFE24_COMMUNITY_ATTACHMENT_"
                "FULL_COMPLETED_WITH_FAILURES"
            )
        ),
        "provider": "CAFE24",
        "run_id": result.run_id,
        "unique_article_count": (
            result.unique_article_count
        ),
        "articles_with_attachments": (
            result.articles_with_attachments
        ),
        "discovered_attachment_ref_count": (
            result.discovered_attachment_ref_count
        ),
        "unique_attachment_count": (
            result.unique_attachment_count
        ),
        "downloaded_count": (
            result.downloaded_count
        ),
        "skipped_existing_count": (
            result.skipped_existing_count
        ),
        "failed_count": (
            result.failed_count
        ),
        "source_missing_count": (
            result.source_missing_count
        ),
        "request_count": (
            result.request_count
        ),
        "total_downloaded_bytes": (
            result.total_downloaded_bytes
        ),
        "completed": (
            result.completed
        ),
        "write_call_count": 0,
        "token_exposed": False,
        "protected_storage": True,
    }

@router.post("/orders/probe")
def cafe24_order_probe(
    request: Request,
) -> dict[str, object]:
    """주문 1페이지 + 주문 3건 품목 + 환불 1페이지를 LIVE Read 검증한다."""

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

    expires_at = getattr(
        request.app.state,
        "cafe24_access_token_expires_at",
        None,
    )

    if not mall_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CAFE24_MALL_ID_MISSING",
            },
        )

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CAFE24_ACCESS_TOKEN_MISSING",
            },
        )

    if (
        not isinstance(
            approved_scopes,
            (list, tuple, set, frozenset),
        )
        or any(
            not isinstance(scope, str)
            for scope in approved_scopes
        )
        or set(approved_scopes) != REQUIRED_READ_SCOPES
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "CAFE24_APPROVED_SCOPES_INVALID",
            },
        )

    if (
        getattr(
            request.app.state,
            "cafe24_authorized_mall_id",
            None,
        )
        != mall_id
        or getattr(
            request.app.state,
            "cafe24_shop_no",
            None,
        )
        != "1"
        or not isinstance(expires_at, datetime)
        or expires_at.tzinfo is None
        or expires_at.utcoffset() is None
        or datetime.now(UTC) >= expires_at
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "CAFE24_TOKEN_METADATA_INVALID",
            },
        )

    protected_root = (
        settings.cafe24_protected_data_dir
    )

    if not protected_root:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CAFE24_PROTECTED_DIR_MISSING",
            },
        )

    # Orders 1 + Order Items 최대 3 + Refunds 1
    # 정상 기준 최대 5회의 GET만 허용한다.
    transport = ReadOnlyHttpTransport(
        request_fn=_request_json,
        granted_scopes=set(
            approved_scopes
        ),
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=(
            CAFE24_ALLOWED_READ_PATH_PATTERNS
        ),
        max_request_count=5,
    )

    adapter = Cafe24Adapter(
        mall_id=mall_id,
        access_token=access_token,
        transport=transport,
    )

    batch_id = (
        "order-probe-"
        + datetime.now(UTC).strftime(
            "%Y%m%dT%H%M%S%fZ"
        )
    )

    try:
        result = run_cafe24_order_probe(
            adapter=adapter,
            protected_root=Path(
                protected_root
            ),
            batch_id=batch_id,
            order_limit=3,
        )

    except Exception as exc:
        print(
            "[CAFE24 ORDER PROBE ERROR]",
            type(exc).__name__,
        )

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "CAFE24_ORDER_PROBE_FAILED",
                "error_type": type(exc).__name__,
                "write_call_count": 0,
                "token_exposed": False,
            },
        ) from None

    return {
        "status": "CAFE24_ORDER_PROBE_OK",
        "provider": "CAFE24",
        "batch_id": result.batch_id,
        "order_count": result.order_count,
        "selected_order_count": (
            result.selected_order_count
        ),
        "order_item_count": (
            result.order_item_count
        ),
        "refund_count": (
            result.refund_count
        ),
        "request_count": (
            result.request_count
        ),
        "write_call_count": (
            result.external_write_count
        ),
        "token_exposed": False,
        "protected_storage": True,
    }

@router.post("/orders/full/run")
def cafe24_orders_full_run(
    request: Request,
    start_date: str = "2026-03-08",
    end_date: str = "2026-09-08",
    max_orders: int = 10000,
) -> dict[str, object]:
    """최근 주문을 날짜 window + offset으로 전체 Read-Only 수집한다."""

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

    expires_at = getattr(
        request.app.state,
        "cafe24_access_token_expires_at",
        None,
    )

    if not mall_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CAFE24_MALL_ID_MISSING",
            },
        )

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CAFE24_ACCESS_TOKEN_MISSING",
            },
        )

    if (
        not isinstance(
            approved_scopes,
            (list, tuple, set, frozenset),
        )
        or any(
            not isinstance(
                scope,
                str,
            )
            for scope
            in approved_scopes
        )
        or set(
            approved_scopes
        ) != REQUIRED_READ_SCOPES
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "CAFE24_APPROVED_SCOPES_INVALID",
            },
        )

    if (
        getattr(
            request.app.state,
            "cafe24_authorized_mall_id",
            None,
        )
        != mall_id
        or getattr(
            request.app.state,
            "cafe24_shop_no",
            None,
        )
        != "1"
        or not isinstance(
            expires_at,
            datetime,
        )
        or expires_at.tzinfo is None
        or expires_at.utcoffset() is None
        or datetime.now(UTC) >= expires_at
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "CAFE24_TOKEN_METADATA_INVALID",
            },
        )

    protected_root = (
        settings.cafe24_protected_data_dir
    )

    if not protected_root:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CAFE24_PROTECTED_DIR_MISSING",
            },
        )

    try:
        parsed_start_date = (
            datetime.strptime(
                start_date,
                "%Y-%m-%d",
            ).date()
        )

        parsed_end_date = (
            datetime.strptime(
                end_date,
                "%Y-%m-%d",
            ).date()
        )

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "CAFE24_ORDER_DATE_INVALID",
            },
        ) from None

    if (
        parsed_start_date
        > parsed_end_date
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "CAFE24_ORDER_DATE_RANGE_INVALID",
            },
        )

    def adapter_factory() -> Cafe24Adapter:
        transport = ReadOnlyHttpTransport(
            request_fn=_request_json,
            granted_scopes=set(
                approved_scopes
            ),
            allowed_paths=(
                CAFE24_ALLOWED_READ_PATHS
            ),
            allowed_path_patterns=(
                CAFE24_ALLOWED_READ_PATH_PATTERNS
            ),
            max_request_count=1,
        )

        return Cafe24Adapter(
            mall_id=mall_id,
            access_token=access_token,
            transport=transport,
        )

    try:
        result = (
            run_cafe24_order_full_runner(
                adapter_factory=adapter_factory,
                protected_root=Path(
                    protected_root
                ),
                range_start_date=(
                    parsed_start_date
                ),
                range_end_date=(
                    parsed_end_date
                ),
                max_orders=max_orders,
                batch_delay_seconds=0.3,
                cooldown_every_requests=50,
                chunk_cooldown_seconds=60.0,
                max_rate_limit_retries=3,
            )
        )

    except Exception as exc:
        print(
            "[CAFE24 ORDER FULL ERROR]",
            type(exc).__name__,
        )

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": (
                    "CAFE24_ORDER_FULL_FAILED"
                ),
                "error_type": (
                    type(exc).__name__
                ),
                "write_call_count": 0,
                "token_exposed": False,
            },
        ) from None

    return {
        "status": (
            "CAFE24_ORDER_FULL_COMPLETED"
            if result.completed
            else "CAFE24_ORDER_FULL_LIMIT_REACHED"
        ),
        "provider": "CAFE24",
        "run_id": result.run_id,
        "range_start_date": (
            result.range_start_date
        ),
        "range_end_date": (
            result.range_end_date
        ),
        "processed_window_count": (
            result.processed_window_count
        ),
        "processed_batch_count": (
            result.processed_batch_count
        ),
        "order_record_count": (
            result.order_record_count
        ),
        "request_count": (
            result.request_count
        ),
        "next_window_start_date": (
            result.next_window_start_date
        ),
        "next_order_offset": (
            result.next_order_offset
        ),
        "completed": (
            result.completed
        ),
        "write_call_count": 0,
        "token_exposed": False,
        "protected_storage": True,
    }

@router.post("/orders/items/full/run")
def cafe24_order_items_full_run(
    request: Request,
) -> dict[str, object]:
    """수집된 고유 주문 전체의 Order Items를 Read-Only 수집한다."""

    settings = request.app.state.settings

    mall_id = (
        settings.cafe24_mall_id
    )

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

    expires_at = getattr(
        request.app.state,
        "cafe24_access_token_expires_at",
        None,
    )

    if not mall_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": (
                    "CAFE24_MALL_ID_MISSING"
                ),
            },
        )

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": (
                    "CAFE24_ACCESS_TOKEN_MISSING"
                ),
            },
        )

    if (
        not isinstance(
            approved_scopes,
            (
                list,
                tuple,
                set,
                frozenset,
            ),
        )
        or any(
            not isinstance(
                scope,
                str,
            )
            for scope
            in approved_scopes
        )
        or set(
            approved_scopes
        ) != REQUIRED_READ_SCOPES
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_403_FORBIDDEN
            ),
            detail={
                "code": (
                    "CAFE24_APPROVED_SCOPES_INVALID"
                ),
            },
        )

    if (
        getattr(
            request.app.state,
            "cafe24_authorized_mall_id",
            None,
        )
        != mall_id
        or getattr(
            request.app.state,
            "cafe24_shop_no",
            None,
        )
        != "1"
        or not isinstance(
            expires_at,
            datetime,
        )
        or expires_at.tzinfo is None
        or expires_at.utcoffset()
        is None
        or datetime.now(
            UTC
        )
        >= expires_at
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_403_FORBIDDEN
            ),
            detail={
                "code": (
                    "CAFE24_TOKEN_METADATA_INVALID"
                ),
            },
        )

    protected_root = (
        settings
        .cafe24_protected_data_dir
    )

    if not protected_root:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail={
                "code": (
                    "CAFE24_PROTECTED_DIR_MISSING"
                ),
            },
        )

    def adapter_factory() -> Cafe24Adapter:
        transport = (
            ReadOnlyHttpTransport(
                request_fn=_request_json,
                granted_scopes=set(
                    approved_scopes
                ),
                allowed_paths=(
                    CAFE24_ALLOWED_READ_PATHS
                ),
                allowed_path_patterns=(
                    CAFE24_ALLOWED_READ_PATH_PATTERNS
                ),
                max_request_count=1,
            )
        )

        return Cafe24Adapter(
            mall_id=mall_id,
            access_token=access_token,
            transport=transport,
        )

    try:
        result = (
            run_cafe24_order_item_full_runner(
                adapter_factory=(
                    adapter_factory
                ),
                protected_root=Path(
                    protected_root
                ),
                batch_delay_seconds=0.3,
                cooldown_every_requests=50,
                chunk_cooldown_seconds=60.0,
                max_rate_limit_retries=3,
            )
        )

    except Exception as exc:
        print(
            "[CAFE24 ORDER ITEM FULL ERROR]",
            type(exc).__name__,
        )

        raise HTTPException(
            status_code=(
                status.HTTP_502_BAD_GATEWAY
            ),
            detail={
                "code": (
                    "CAFE24_ORDER_ITEM_FULL_FAILED"
                ),
                "error_type": (
                    type(exc).__name__
                ),
                "write_call_count": 0,
                "token_exposed": False,
            },
        ) from None

    return {
        "status": (
            "CAFE24_ORDER_ITEM_FULL_COMPLETED"
            if result.completed
            else (
                "CAFE24_ORDER_ITEM_FULL_"
                "COMPLETED_WITH_FAILURES"
            )
        ),
        "provider": "CAFE24",
        "run_id": (
            result.run_id
        ),
        "unique_order_count": (
            result.unique_order_count
        ),
        "processed_order_count": (
            result.processed_order_count
        ),
        "order_item_count": (
            result.order_item_count
        ),
        "empty_order_count": (
            result.empty_order_count
        ),
        "source_missing_count": (
            result.source_missing_count
        ),
        "skipped_existing_count": (
            result.skipped_existing_count
        ),
        "failed_count": (
            result.failed_count
        ),
        "request_count": (
            result.request_count
        ),
        "completed": (
            result.completed
        ),
        "write_call_count": 0,
        "token_exposed": False,
        "protected_storage": True,
    }

@router.post("/categories/probe")
def cafe24_category_probe(
    request: Request,
) -> dict[str, object]:
    """카테고리 첫 페이지를 LIVE Read 검증한다."""

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

    expires_at = getattr(
        request.app.state,
        "cafe24_access_token_expires_at",
        None,
    )

    if not mall_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CAFE24_MALL_ID_MISSING",
            },
        )

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CAFE24_ACCESS_TOKEN_MISSING",
            },
        )

    if (
        not isinstance(
            approved_scopes,
            (list, tuple, set, frozenset),
        )
        or any(
            not isinstance(scope, str)
            for scope in approved_scopes
        )
        or set(approved_scopes) != REQUIRED_READ_SCOPES
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "CAFE24_APPROVED_SCOPES_INVALID",
            },
        )

    if (
        getattr(
            request.app.state,
            "cafe24_authorized_mall_id",
            None,
        )
        != mall_id
        or getattr(
            request.app.state,
            "cafe24_shop_no",
            None,
        )
        != "1"
        or not isinstance(expires_at, datetime)
        or expires_at.tzinfo is None
        or expires_at.utcoffset() is None
        or datetime.now(UTC) >= expires_at
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "CAFE24_TOKEN_METADATA_INVALID",
            },
        )

    protected_root = (
        settings.cafe24_protected_data_dir
    )

    if not protected_root:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CAFE24_PROTECTED_DIR_MISSING",
            },
        )

    # Categories 첫 페이지 1회만 조회한다.
    transport = ReadOnlyHttpTransport(
        request_fn=_request_json,
        granted_scopes=set(
            approved_scopes
        ),
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=(
            CAFE24_ALLOWED_READ_PATH_PATTERNS
        ),
        max_request_count=1,
    )

    adapter = Cafe24Adapter(
        mall_id=mall_id,
        access_token=access_token,
        transport=transport,
    )

    batch_id = (
        "category-probe-"
        + datetime.now(UTC).strftime(
            "%Y%m%dT%H%M%S%fZ"
        )
    )

    try:
        result = run_cafe24_category_probe(
            adapter=adapter,
            protected_root=Path(
                protected_root
            ),
            batch_id=batch_id,
        )

    except Exception as exc:
        print(
            "[CAFE24 CATEGORY PROBE ERROR]",
            type(exc).__name__,
        )

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "CAFE24_CATEGORY_PROBE_FAILED",
                "error_type": type(exc).__name__,
                "write_call_count": 0,
                "token_exposed": False,
            },
        ) from None

    return {
        "status": "CAFE24_CATEGORY_PROBE_OK",
        "provider": "CAFE24",
        "batch_id": result.batch_id,
        "category_count": (
            result.category_count
        ),
        "request_count": (
            result.request_count
        ),
        "write_call_count": (
            result.external_write_count
        ),
        "token_exposed": False,
        "protected_storage": True,
    }

@router.post("/categories/full/run")
def cafe24_category_full_run(
    request: Request,
    start_offset: int = 0,
    max_categories: int = 2500,
) -> dict[str, object]:
    """Cafe24 카테고리를 25개씩 마지막 페이지까지 Read-Only 수집한다."""

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

    expires_at = getattr(
        request.app.state,
        "cafe24_access_token_expires_at",
        None,
    )

    if not mall_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CAFE24_MALL_ID_MISSING",
            },
        )

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CAFE24_ACCESS_TOKEN_MISSING",
            },
        )

    if (
        not isinstance(
            approved_scopes,
            (list, tuple, set, frozenset),
        )
        or any(
            not isinstance(scope, str)
            for scope in approved_scopes
        )
        or set(approved_scopes)
        != REQUIRED_READ_SCOPES
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "CAFE24_APPROVED_SCOPES_INVALID",
            },
        )

    if (
        getattr(
            request.app.state,
            "cafe24_authorized_mall_id",
            None,
        )
        != mall_id
        or getattr(
            request.app.state,
            "cafe24_shop_no",
            None,
        )
        != "1"
        or not isinstance(
            expires_at,
            datetime,
        )
        or expires_at.tzinfo is None
        or expires_at.utcoffset() is None
        or datetime.now(UTC) >= expires_at
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "CAFE24_TOKEN_METADATA_INVALID",
            },
        )

    protected_root = (
        settings.cafe24_protected_data_dir
    )

    if not protected_root:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CAFE24_PROTECTED_DIR_MISSING",
            },
        )

    if (
        type(start_offset) is not int
        or start_offset < 0
        or start_offset % 25 != 0
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "CAFE24_CATEGORY_OFFSET_INVALID",
            },
        )

    if (
        type(max_categories) is not int
        or max_categories < 25
        or max_categories % 25 != 0
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "CAFE24_MAX_CATEGORIES_INVALID",
            },
        )

    def adapter_factory() -> Cafe24Adapter:
        transport = ReadOnlyHttpTransport(
            request_fn=_request_json,
            granted_scopes=set(
                approved_scopes
            ),
            allowed_paths=(
                CAFE24_ALLOWED_READ_PATHS
            ),
            allowed_path_patterns=(
                CAFE24_ALLOWED_READ_PATH_PATTERNS
            ),

            # Category batch 하나는
            # GET /categories 1회만 사용한다.
            max_request_count=1,
        )

        return Cafe24Adapter(
            mall_id=mall_id,
            access_token=access_token,
            transport=transport,
        )

    try:
        result = (
            run_cafe24_category_full_runner(
                adapter_factory=adapter_factory,
                protected_root=Path(
                    protected_root
                ),
                start_offset=start_offset,
                max_categories=max_categories,

                # 일반 페이지 사이
                batch_delay_seconds=2.0,

                # 429 재시도
                max_rate_limit_retries=3,

                # 50개 성공마다
                cooldown_every_categories=50,

                # 요청한 60초 휴식
                chunk_cooldown_seconds=60.0,
            )
        )

    except Exception as exc:
        print(
            "[CAFE24 CATEGORY FULL RUN ERROR]",
            type(exc).__name__,
        )

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": (
                    "CAFE24_CATEGORY_FULL_RUN_FAILED"
                ),
                "error_type": (
                    type(exc).__name__
                ),
                "start_offset": start_offset,
                "write_call_count": 0,
                "token_exposed": False,
            },
        ) from None

    return {
        "status": (
            "CAFE24_CATEGORY_FULL_RUN_COMPLETED"
            if result.completed
            else (
                "CAFE24_CATEGORY_FULL_RUN_"
                "LIMIT_REACHED"
            )
        ),
        "provider": "CAFE24",
        "run_id": result.run_id,
        "start_offset": (
            result.start_offset
        ),
        "last_success_offset": (
            result.last_success_offset
        ),
        "next_category_offset": (
            result.next_category_offset
        ),
        "processed_category_count": (
            result.processed_category_count
        ),
        "processed_batch_count": (
            result.processed_batch_count
        ),
        "request_count": (
            result.request_count
        ),
        "completed": (
            result.completed
        ),
        "write_call_count": 0,
        "token_exposed": False,
        "protected_storage": True,
    }

@router.post("/products/full")
def cafe24_product_full(
    request: Request,
    product_offset: int = 0,
) -> dict[str, object]:
    """상품 25개 단위로 전체 수집을 진행한다."""

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

    expires_at = getattr(
        request.app.state,
        "cafe24_access_token_expires_at",
        None,
    )

    if not mall_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CAFE24_MALL_ID_MISSING"},
        )

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CAFE24_ACCESS_TOKEN_MISSING"},
        )

    if (
        not isinstance(
            approved_scopes,
            (list, tuple, set, frozenset),
        )
        or any(
            not isinstance(scope, str)
            for scope in approved_scopes
        )
        or set(approved_scopes) != REQUIRED_READ_SCOPES
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "CAFE24_APPROVED_SCOPES_INVALID"},
        )

    if (
        getattr(
            request.app.state,
            "cafe24_authorized_mall_id",
            None,
        )
        != mall_id
        or getattr(
            request.app.state,
            "cafe24_shop_no",
            None,
        )
        != "1"
        or not isinstance(expires_at, datetime)
        or expires_at.tzinfo is None
        or expires_at.utcoffset() is None
        or datetime.now(UTC) >= expires_at
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "CAFE24_TOKEN_METADATA_INVALID"},
        )

    protected_root = (
        settings.cafe24_protected_data_dir
    )

    if not protected_root:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CAFE24_PROTECTED_DIR_MISSING"},
        )

    if (
        type(product_offset) is not int
        or product_offset < 0
        or product_offset % 25 != 0
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "CAFE24_PRODUCT_OFFSET_INVALID",
            },
        )

    # Product 1회 + Variant/Inventory fan-out.
    # 25개 기준으로 넉넉하게 잡되 무한 요청은 막는다.
    transport = ReadOnlyHttpTransport(
        request_fn=_request_json,
        granted_scopes=set(
            approved_scopes
        ),
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=(
            CAFE24_ALLOWED_READ_PATH_PATTERNS
        ),
        max_request_count=150,
    )

    adapter = Cafe24Adapter(
        mall_id=mall_id,
        access_token=access_token,
        transport=transport,
    )

    batch_id = (
        "product-full-"
        f"{product_offset:06d}-"
        + datetime.now(UTC).strftime(
            "%Y%m%dT%H%M%S%fZ"
        )
    )

    try:
        result = run_cafe24_product_bootstrap(
            adapter=adapter,
            protected_root=Path(
                protected_root
            ),
            batch_id=batch_id,
            max_pages=10,
            product_offset=product_offset,
            product_batch_size=25,
        )

    except Exception as exc:
        print(
            "[CAFE24 PRODUCT FULL ERROR]",
            type(exc).__name__,
        )

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "CAFE24_PRODUCT_FULL_FAILED",
                "error_type": type(exc).__name__,
                "product_offset": product_offset,
                "write_call_count": 0,
                "token_exposed": False,
            },
        ) from None

    return {
        "status": "CAFE24_PRODUCT_FULL_BATCH_OK",
        "provider": "CAFE24",
        "batch_id": result.batch_id,
        "product_offset": (
            result.product_offset
        ),
        "product_page_count": (
            result.product_page_count
        ),
        "next_product_offset": (
            result.next_product_offset
        ),
        "has_more": (
            result.has_more
        ),
        "variant_count": (
            result.variant_count
        ),
        "inventory_count": (
            result.inventory_count
        ),
        "request_count": (
            result.request_count
        ),
        "write_call_count": (
            result.external_write_count
        ),
        "token_exposed": False,
        "protected_storage": True,
    }

@router.post("/products/full/run")
def cafe24_product_full_run(
    request: Request,
    start_offset: int = 0,
    max_products: int = 2500,
) -> dict[str, object]:
    """상품을 25개씩 처리하고 200개마다 휴식하며 전체 수집한다."""

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

    expires_at = getattr(
        request.app.state,
        "cafe24_access_token_expires_at",
        None,
    )

    if not mall_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CAFE24_MALL_ID_MISSING"},
        )

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CAFE24_ACCESS_TOKEN_MISSING"},
        )

    if (
        not isinstance(
            approved_scopes,
            (list, tuple, set, frozenset),
        )
        or any(
            not isinstance(scope, str)
            for scope in approved_scopes
        )
        or set(approved_scopes) != REQUIRED_READ_SCOPES
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "CAFE24_APPROVED_SCOPES_INVALID"},
        )

    if (
        getattr(
            request.app.state,
            "cafe24_authorized_mall_id",
            None,
        )
        != mall_id
        or getattr(
            request.app.state,
            "cafe24_shop_no",
            None,
        )
        != "1"
        or not isinstance(expires_at, datetime)
        or expires_at.tzinfo is None
        or expires_at.utcoffset() is None
        or datetime.now(UTC) >= expires_at
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "CAFE24_TOKEN_METADATA_INVALID"},
        )

    protected_root = (
        settings.cafe24_protected_data_dir
    )

    if not protected_root:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CAFE24_PROTECTED_DIR_MISSING"},
        )

    if (
        type(start_offset) is not int
        or start_offset < 0
        or start_offset % 25 != 0
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "CAFE24_PRODUCT_OFFSET_INVALID",
            },
        )

    if (
        type(max_products) is not int
        or max_products < 25
        or max_products % 25 != 0
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "CAFE24_MAX_PRODUCTS_INVALID",
            },
        )

    def adapter_factory() -> Cafe24Adapter:
        transport = ReadOnlyHttpTransport(
            request_fn=_request_json,
            granted_scopes=set(
                approved_scopes
            ),
            allowed_paths=CAFE24_ALLOWED_READ_PATHS,
            allowed_path_patterns=(
                CAFE24_ALLOWED_READ_PATH_PATTERNS
            ),
            max_request_count=150,
        )

        return Cafe24Adapter(
            mall_id=mall_id,
            access_token=access_token,
            transport=transport,
        )

    try:
        result = run_cafe24_product_full_runner(
            adapter_factory=adapter_factory,
            protected_root=Path(
                protected_root
            ),
            start_offset=start_offset,
            max_products=max_products,
            batch_delay_seconds=2.0,
            max_rate_limit_retries=3,
            cooldown_every_products=50,
            chunk_cooldown_seconds=90.0,
        )

    except Exception as exc:
        print(
            "[CAFE24 PRODUCT FULL RUN ERROR]",
            type(exc).__name__,
        )

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "CAFE24_PRODUCT_FULL_RUN_FAILED",
                "error_type": type(exc).__name__,
                "start_offset": start_offset,
                "write_call_count": 0,
                "token_exposed": False,
            },
        ) from None

    return {
        "status": (
            "CAFE24_PRODUCT_FULL_RUN_COMPLETED"
            if result.completed
            else "CAFE24_PRODUCT_FULL_RUN_LIMIT_REACHED"
        ),
        "provider": "CAFE24",
        "run_id": result.run_id,
        "start_offset": result.start_offset,
        "last_success_offset": (
            result.last_success_offset
        ),
        "next_product_offset": (
            result.next_product_offset
        ),
        "processed_product_count": (
            result.processed_product_count
        ),
        "processed_batch_count": (
            result.processed_batch_count
        ),
        "variant_count": (
            result.variant_count
        ),
        "inventory_count": (
            result.inventory_count
        ),
        "request_count": (
            result.request_count
        ),
        "completed": (
            result.completed
        ),
        "write_call_count": 0,
        "token_exposed": False,
        "protected_storage": True,
    }

@router.post("/refunds/full/run")
def cafe24_refunds_full_run(
    request: Request,
    start_date: str = "2026-03-08",
    end_date: str = "2026-09-08",
    max_refunds: int = 10000,
) -> dict[str, object]:
    """최근 Refund를 날짜 window + offset으로 전체 Read-Only 수집한다."""

    settings = request.app.state.settings

    mall_id = (
        settings.cafe24_mall_id
    )

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

    expires_at = getattr(
        request.app.state,
        "cafe24_access_token_expires_at",
        None,
    )

    if not mall_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CAFE24_MALL_ID_MISSING",
            },
        )

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CAFE24_ACCESS_TOKEN_MISSING",
            },
        )

    if (
        not isinstance(
            approved_scopes,
            (
                list,
                tuple,
                set,
                frozenset,
            ),
        )
        or set(
            approved_scopes
        ) != REQUIRED_READ_SCOPES
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "CAFE24_APPROVED_SCOPES_INVALID",
            },
        )

    if (
        getattr(
            request.app.state,
            "cafe24_authorized_mall_id",
            None,
        )
        != mall_id
        or getattr(
            request.app.state,
            "cafe24_shop_no",
            None,
        )
        != "1"
        or not isinstance(
            expires_at,
            datetime,
        )
        or expires_at.tzinfo is None
        or expires_at.utcoffset() is None
        or datetime.now(UTC) >= expires_at
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "CAFE24_TOKEN_METADATA_INVALID",
            },
        )

    protected_root = (
        settings.cafe24_protected_data_dir
    )

    if not protected_root:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CAFE24_PROTECTED_DIR_MISSING",
            },
        )

    try:
        parsed_start_date = (
            datetime.strptime(
                start_date,
                "%Y-%m-%d",
            ).date()
        )

        parsed_end_date = (
            datetime.strptime(
                end_date,
                "%Y-%m-%d",
            ).date()
        )

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "CAFE24_REFUND_DATE_INVALID",
            },
        ) from None

    def adapter_factory() -> Cafe24Adapter:
        transport = (
            ReadOnlyHttpTransport(
                request_fn=_request_json,
                granted_scopes=set(
                    approved_scopes
                ),
                allowed_paths=(
                    CAFE24_ALLOWED_READ_PATHS
                ),
                allowed_path_patterns=(
                    CAFE24_ALLOWED_READ_PATH_PATTERNS
                ),
                max_request_count=1,
            )
        )

        return Cafe24Adapter(
            mall_id=mall_id,
            access_token=access_token,
            transport=transport,
        )

    try:
        result = (
            run_cafe24_refund_full_runner(
                adapter_factory=(
                    adapter_factory
                ),
                protected_root=Path(
                    protected_root
                ),
                range_start_date=(
                    parsed_start_date
                ),
                range_end_date=(
                    parsed_end_date
                ),
                max_refunds=max_refunds,
                batch_delay_seconds=0.3,
                cooldown_every_requests=50,
                chunk_cooldown_seconds=60.0,
                max_rate_limit_retries=3,
            )
        )

    except Exception as exc:
        print(
            "[CAFE24 REFUND FULL ERROR]",
            type(exc).__name__,
        )

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "CAFE24_REFUND_FULL_FAILED",
                "error_type": (
                    type(exc).__name__
                ),
                "write_call_count": 0,
                "token_exposed": False,
            },
        ) from None

    return {
        "status": (
            "CAFE24_REFUND_FULL_COMPLETED"
            if result.completed
            else "CAFE24_REFUND_FULL_LIMIT_REACHED"
        ),
        "provider": "CAFE24",
        "run_id": result.run_id,
        "range_start_date": (
            result.range_start_date
        ),
        "range_end_date": (
            result.range_end_date
        ),
        "processed_window_count": (
            result.processed_window_count
        ),
        "processed_batch_count": (
            result.processed_batch_count
        ),
        "refund_record_count": (
            result.refund_record_count
        ),
        "request_count": (
            result.request_count
        ),
        "next_window_start_date": (
            result.next_window_start_date
        ),
        "next_refund_offset": (
            result.next_refund_offset
        ),
        "completed": (
            result.completed
        ),
        "write_call_count": 0,
        "token_exposed": False,
        "protected_storage": True,
    }