"""Cafe24 Board 5/6 Article 전체 Read-Only 수집 Runner."""

from __future__ import annotations

import json
import time
from copy import copy
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from backend.app.adapters.providers.base import (
    ProviderHttpError,
)
from backend.app.adapters.providers.cafe24.adapter import (
    Cafe24Adapter,
)
from backend.app.adapters.providers.http_transport import (
    ReadOnlyHttpTransport,
)
from backend.app.sync.cafe24_bootstrap import (
    _require_contained,
    _require_protected_root,
)
from backend.app.worker.privacy.protected_storage import (
    ProtectedRawResponse,
    write_protected_raw_response,
    write_sanitized_export,
)
from backend.app.worker.privacy.snapshot_manifest import (
    build_raw_response_manifest_entry,
    write_snapshot_manifest,
)
from backend.app.worker.privacy.staging import (
    sanitize_community_record,
)


TARGET_BOARD_NOS = (5, 6)


@dataclass(frozen=True)
class Cafe24CommunityArticlePageResult:
    batch_id: str
    board_no: int
    article_offset: int
    article_count: int
    next_article_offset: int | None
    has_more: bool
    request_count: int
    external_write_count: int
    manifest_path: Path


@dataclass(frozen=True)
class Cafe24CommunityArticleFullResult:
    run_id: str
    board_5_count: int
    board_6_count: int
    total_article_count: int
    processed_batch_count: int
    request_count: int
    board_5_completed: bool
    board_6_completed: bool
    next_board_no: int | None
    next_article_offset: int | None
    completed: bool
    progress_path: Path


def _write_progress(
    *,
    progress_path: Path,
    payload: dict[str, object],
) -> None:
    progress_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = (
        progress_path.with_suffix(".tmp")
    )

    temporary_path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    temporary_path.replace(
        progress_path
    )


def _sanitize_community_record(
    record: dict[str, Any],
) -> dict[str, Any]:
    sanitized = sanitize_community_record(
        record
    )

    # Community 개발용 Sanitized 데이터에서는
    # 원본 주문번호를 직접 노출하지 않는다.
    sanitized.pop(
        "order_id",
        None,
    )

    return sanitized


def run_cafe24_article_page(
    *,
    adapter: Cafe24Adapter,
    protected_root: Path,
    batch_id: str,
    board_no: int,
    article_offset: int,
) -> Cafe24CommunityArticlePageResult:
    """게시판 하나의 Article 25개 페이지를 안전하게 수집한다."""

    root = _require_protected_root(
        protected_root
    )

    if board_no not in TARGET_BOARD_NOS:
        raise ValueError(
            "unsupported target board"
        )

    if (
        type(article_offset) is not int
        or article_offset < 0
        or article_offset % Cafe24Adapter.PAGE_SIZE != 0
    ):
        raise ValueError(
            "article_offset must align with Cafe24 page size"
        )

    if not isinstance(
        getattr(
            adapter,
            "transport",
            None,
        ),
        ReadOnlyHttpTransport,
    ):
        raise ValueError(
            "community article collection requires "
            "read-only HTTP transport"
        )

    raw_snapshots: list[
        ProtectedRawResponse
    ] = []

    def capture(
        path: str,
        payload: Any,
    ) -> None:
        response_key = path.rsplit(
            "/",
            1,
        )[-1]

        if (
            response_key != "articles"
            or not isinstance(
                payload,
                dict,
            )
        ):
            raise ValueError(
                "unsupported article response"
            )

        items = payload.get(
            "articles"
        )

        raw_count = (
            len(items)
            if isinstance(
                items,
                list,
            )
            else 0
        )

        raw_snapshots.append(
            write_protected_raw_response(
                protected_root=root,
                provider="CAFE24",
                resource=(
                    f"board_{board_no}_articles"
                ),
                batch_id=batch_id,
                page_id="page-000001",
                payload=payload,
                raw_count=raw_count,
            )
        )

    collecting_adapter = copy(
        adapter
    )

    collecting_adapter.transport = (
        adapter.transport.with_raw_capture(
            capture
        )
    )

    raw_batch = (
        root
        / "cafe24"
        / "raw"
        / batch_id
    )

    manifest_path = (
        root
        / "cafe24"
        / "manifests"
        / f"{batch_id}.manifest.json"
    )

    sanitized_target = (
        root
        / "cafe24"
        / "sanitized"
        / f"board_{board_no}_articles"
        / f"{batch_id}.sanitized.json"
    )

    _require_contained(
        root,
        raw_batch,
    )

    _require_contained(
        root,
        manifest_path,
    )

    _require_contained(
        root,
        sanitized_target,
    )

    if (
        raw_batch.exists()
        or manifest_path.exists()
        or sanitized_target.exists()
    ):
        raise FileExistsError(
            "community article batch already exists"
        )

    raw_batch.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    raw_batch.mkdir()

    cursor = (
        None
        if article_offset == 0
        else f"offset:{article_offset}"
    )

    article_page = (
        collecting_adapter.read_articles(
            board_no=board_no,
            cursor=cursor,
        )
    )

    articles = list(
        article_page.items
    )

    sanitized_articles = [
        _sanitize_community_record(
            article
        )
        for article in articles
    ]

    sanitized_snapshot = write_sanitized_export(
        protected_root=root,
        provider="CAFE24",
        resource=(
            f"board_{board_no}_articles"
        ),
        batch_id=batch_id,
        records=sanitized_articles,
    )

    entries = [
        build_raw_response_manifest_entry(
            page,
            sanitized_count=sanitized_snapshot.sanitized_count,
            sanitized_path=sanitized_snapshot.sanitized_path,
        )
        for page in raw_snapshots
    ]

    write_snapshot_manifest(
        output_path=manifest_path,
        entries=entries,
    )

    next_article_offset: int | None = None

    if article_page.next_cursor is not None:
        prefix = "offset:"

        if not article_page.next_cursor.startswith(
            prefix
        ):
            raise ValueError(
                "unexpected article next cursor"
            )

        try:
            next_article_offset = int(
                article_page.next_cursor.removeprefix(
                    prefix
                )
            )
        except ValueError:
            raise ValueError(
                "invalid article next cursor"
            ) from None

    return Cafe24CommunityArticlePageResult(
        batch_id=batch_id,
        board_no=board_no,
        article_offset=article_offset,
        article_count=len(
            articles
        ),
        next_article_offset=(
            next_article_offset
        ),
        has_more=article_page.has_more,
        request_count=(
            collecting_adapter.transport.request_count
        ),
        external_write_count=0,
        manifest_path=manifest_path,
    )


def run_cafe24_community_article_full_runner(
    *,
    adapter_factory: Callable[
        [],
        Cafe24Adapter,
    ],
    protected_root: Path,
    start_board_no: int = 5,
    start_offset: int = 0,
    max_articles: int = 10000,
    batch_delay_seconds: float = 2.0,
    cooldown_every_articles: int = 50,
    chunk_cooldown_seconds: float = 60.0,
    max_rate_limit_retries: int = 3,
) -> Cafe24CommunityArticleFullResult:
    """게시판 5와 6의 Article을 마지막 페이지까지 수집한다."""

    root = _require_protected_root(
        protected_root
    )

    page_size = Cafe24Adapter.PAGE_SIZE

    if start_board_no not in TARGET_BOARD_NOS:
        raise ValueError(
            "start_board_no must be 5 or 6"
        )

    if (
        type(start_offset) is not int
        or start_offset < 0
        or start_offset % page_size != 0
    ):
        raise ValueError(
            "start_offset must align with Cafe24 page size"
        )

    if (
        type(max_articles) is not int
        or max_articles < page_size
        or max_articles % page_size != 0
    ):
        raise ValueError(
            "max_articles must align with Cafe24 page size"
        )

    if (
        type(cooldown_every_articles) is not int
        or cooldown_every_articles < page_size
        or cooldown_every_articles % page_size != 0
    ):
        raise ValueError(
            "cooldown_every_articles must align "
            "with Cafe24 page size"
        )

    run_id = (
        "community-article-full-run-"
        + datetime.now(UTC).strftime(
            "%Y%m%dT%H%M%S%fZ"
        )
    )

    progress_path = (
        root
        / "cafe24"
        / "progress"
        / f"{run_id}.json"
    )

    board_counts = {
        5: 0,
        6: 0,
    }

    board_completed = {
        5: False,
        6: False,
    }

    total_article_count = 0
    processed_batch_count = 0
    request_count = 0

    board_sequence = (
        (5, 6)
        if start_board_no == 5
        else (6,)
    )

    current_offset = start_offset

    next_board_no: int | None = (
        start_board_no
    )

    next_article_offset: int | None = (
        start_offset
    )

    completed = False

    _write_progress(
        progress_path=progress_path,
        payload={
            "run_id": run_id,
            "status": "RUNNING",
            "next_board_no": (
                next_board_no
            ),
            "next_article_offset": (
                next_article_offset
            ),
            "board_5_count": 0,
            "board_6_count": 0,
            "total_article_count": 0,
            "processed_batch_count": 0,
            "request_count": 0,
            "completed": False,
        },
    )

    for board_no in board_sequence:
        if board_no != start_board_no:
            current_offset = 0

        while True:
            if (
                total_article_count
                >= max_articles
            ):
                break

            retry_count = 0

            while True:
                batch_id = (
                    "community-board-"
                    f"{board_no}-"
                    f"{current_offset:06d}-"
                    + datetime.now(UTC).strftime(
                        "%Y%m%dT%H%M%S%fZ"
                    )
                )

                adapter = (
                    adapter_factory()
                )

                try:
                    result = (
                        run_cafe24_article_page(
                            adapter=adapter,
                            protected_root=root,
                            batch_id=batch_id,
                            board_no=board_no,
                            article_offset=(
                                current_offset
                            ),
                        )
                    )

                    break

                except ProviderHttpError as exc:
                    if exc.status_code != 429:
                        raise

                    if (
                        retry_count
                        >= max_rate_limit_retries
                    ):
                        _write_progress(
                            progress_path=progress_path,
                            payload={
                                "run_id": run_id,
                                "status": (
                                    "FAILED_RATE_LIMIT"
                                ),
                                "next_board_no": (
                                    board_no
                                ),
                                "next_article_offset": (
                                    current_offset
                                ),
                                "board_5_count": (
                                    board_counts[5]
                                ),
                                "board_6_count": (
                                    board_counts[6]
                                ),
                                "total_article_count": (
                                    total_article_count
                                ),
                                "processed_batch_count": (
                                    processed_batch_count
                                ),
                                "request_count": (
                                    request_count
                                ),
                                "completed": False,
                            },
                        )

                        raise

                    retry_count += 1

                    retry_after = (
                        exc.retry_after_seconds
                        if exc.retry_after_seconds
                        is not None
                        else 60.0
                    )

                    wait_seconds = max(
                        retry_after,
                        60.0,
                    )

                    _write_progress(
                        progress_path=progress_path,
                        payload={
                            "run_id": run_id,
                            "status": (
                                "RATE_LIMIT_WAIT"
                            ),
                            "next_board_no": (
                                board_no
                            ),
                            "next_article_offset": (
                                current_offset
                            ),
                            "retry_after_seconds": (
                                wait_seconds
                            ),
                            "retry_count": (
                                retry_count
                            ),
                            "board_5_count": (
                                board_counts[5]
                            ),
                            "board_6_count": (
                                board_counts[6]
                            ),
                            "total_article_count": (
                                total_article_count
                            ),
                            "completed": False,
                        },
                    )

                    time.sleep(
                        wait_seconds
                    )

            board_counts[board_no] += (
                result.article_count
            )

            total_article_count += (
                result.article_count
            )

            processed_batch_count += 1

            request_count += (
                result.request_count
            )

            next_article_offset = (
                result.next_article_offset
            )

            page_completed = (
                not result.has_more
                or result.next_article_offset
                is None
            )

            if page_completed:
                board_completed[
                    board_no
                ] = True

                if board_no == 5:
                    next_board_no = 6
                    next_article_offset = 0
                else:
                    next_board_no = None
                    next_article_offset = None

                _write_progress(
                    progress_path=progress_path,
                    payload={
                        "run_id": run_id,
                        "status": (
                            "BOARD_COMPLETED"
                        ),
                        "next_board_no": (
                            next_board_no
                        ),
                        "next_article_offset": (
                            next_article_offset
                        ),
                        "board_5_count": (
                            board_counts[5]
                        ),
                        "board_6_count": (
                            board_counts[6]
                        ),
                        "total_article_count": (
                            total_article_count
                        ),
                        "processed_batch_count": (
                            processed_batch_count
                        ),
                        "request_count": (
                            request_count
                        ),
                        "completed": False,
                    },
                )

                break

            current_offset = (
                result.next_article_offset
            )

            next_board_no = board_no
            next_article_offset = (
                current_offset
            )

            if (
                total_article_count
                % cooldown_every_articles
                == 0
            ):
                _write_progress(
                    progress_path=progress_path,
                    payload={
                        "run_id": run_id,
                        "status": (
                            "CHUNK_COOLDOWN"
                        ),
                        "next_board_no": (
                            board_no
                        ),
                        "next_article_offset": (
                            current_offset
                        ),
                        "board_5_count": (
                            board_counts[5]
                        ),
                        "board_6_count": (
                            board_counts[6]
                        ),
                        "total_article_count": (
                            total_article_count
                        ),
                        "processed_batch_count": (
                            processed_batch_count
                        ),
                        "request_count": (
                            request_count
                        ),
                        "cooldown_seconds": (
                            chunk_cooldown_seconds
                        ),
                        "completed": False,
                    },
                )

                time.sleep(
                    chunk_cooldown_seconds
                )

            else:
                time.sleep(
                    batch_delay_seconds
                )

        if (
            total_article_count
            >= max_articles
        ):
            break

    completed = (
        board_completed[5]
        and board_completed[6]
    )

    final_result = (
        Cafe24CommunityArticleFullResult(
            run_id=run_id,
            board_5_count=(
                board_counts[5]
            ),
            board_6_count=(
                board_counts[6]
            ),
            total_article_count=(
                total_article_count
            ),
            processed_batch_count=(
                processed_batch_count
            ),
            request_count=request_count,
            board_5_completed=(
                board_completed[5]
            ),
            board_6_completed=(
                board_completed[6]
            ),
            next_board_no=(
                next_board_no
            ),
            next_article_offset=(
                next_article_offset
            ),
            completed=completed,
            progress_path=progress_path,
        )
    )

    _write_progress(
        progress_path=progress_path,
        payload={
            **asdict(
                final_result
            ),
            "status": (
                "COMPLETED"
                if completed
                else "LIMIT_REACHED"
            ),
        },
    )

    return final_result
