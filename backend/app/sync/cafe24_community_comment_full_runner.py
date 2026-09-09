"""Cafe24 Board 5/6 Article Comment 전체 Read-Only 수집 Runner."""

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
class Cafe24CommunityCommentFullResult:
    run_id: str
    unique_article_count: int
    processed_article_count: int
    comment_count: int
    article_page_request_count: int
    comment_request_count: int
    skipped_comment_endpoint_count: int
    total_request_count: int
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


def _sanitize_comment(
    record: dict[str, Any],
) -> dict[str, Any]:
    sanitized = sanitize_community_record(
        record
    )

    sanitized.pop(
        "order_id",
        None,
    )

    return sanitized


def run_cafe24_community_comment_full_runner(
    *,
    adapter_factory: Callable[
        [],
        Cafe24Adapter,
    ],
    protected_root: Path,
    batch_delay_seconds: float = 0.3,
    cooldown_every_requests: int = 50,
    chunk_cooldown_seconds: float = 60.0,
    max_rate_limit_retries: int = 3,
) -> Cafe24CommunityCommentFullResult:
    """Board 5/6의 고유 Article을 찾고 모든 Comment를 수집한다."""

    root = _require_protected_root(
        protected_root
    )

    run_id = (
        "community-comment-full-run-"
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

    article_refs: list[
        tuple[int, int]
    ] = []

    seen_articles: set[
        tuple[int, int]
    ] = set()

    article_page_request_count = 0
    comment_request_count = 0
    processed_article_count = 0
    comment_count = 0
    skipped_comment_endpoint_count = 0

    next_cooldown_at = (
        cooldown_every_requests
    )

    def maybe_cooldown() -> None:
        nonlocal next_cooldown_at

        total_requests = (
            article_page_request_count
            + comment_request_count
        )

        if total_requests >= next_cooldown_at:
            _write_progress(
                progress_path=progress_path,
                payload={
                    "run_id": run_id,
                    "status": "CHUNK_COOLDOWN",
                    "unique_article_count": (
                        len(article_refs)
                    ),
                    "processed_article_count": (
                        processed_article_count
                    ),
                    "comment_count": (
                        comment_count
                    ),
                    "total_request_count": (
                        total_requests
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

            while (
                total_requests
                >= next_cooldown_at
            ):
                next_cooldown_at += (
                    cooldown_every_requests
                )

    _write_progress(
        progress_path=progress_path,
        payload={
            "run_id": run_id,
            "status": "DISCOVERING_ARTICLES",
            "unique_article_count": 0,
            "processed_article_count": 0,
            "comment_count": 0,
            "total_request_count": 0,
            "completed": False,
        },
    )

    # 1. Board 5/6 Article 전체를 다시 순회해
    #    고유 (board_no, article_no)를 만든다.
    for board_no in TARGET_BOARD_NOS:
        offset = 0

        while True:
            adapter = adapter_factory()

            cursor = (
                None
                if offset == 0
                else f"offset:{offset}"
            )

            page = adapter.read_articles(
                board_no=board_no,
                cursor=cursor,
            )

            article_page_request_count += (
                page.request_count
            )

            for article in page.items:
                article_no = (
                    article.get(
                        "article_no"
                    )
                )

                actual_board_no = (
                    article.get(
                        "board_no",
                        board_no,
                    )
                )

                if (
                    type(article_no)
                    is not int
                    or article_no < 1
                ):
                    continue

                if (
                    type(actual_board_no)
                    is not int
                    or actual_board_no
                    not in TARGET_BOARD_NOS
                ):
                    continue

                key = (
                    actual_board_no,
                    article_no,
                )

                if key in seen_articles:
                    continue

                seen_articles.add(
                    key
                )

                article_refs.append(
                    key
                )

            maybe_cooldown()

            if (
                not page.has_more
                or page.next_cursor is None
            ):
                break

            offset += (
                Cafe24Adapter.PAGE_SIZE
            )

            time.sleep(
                batch_delay_seconds
            )

    _write_progress(
        progress_path=progress_path,
        payload={
            "run_id": run_id,
            "status": "COLLECTING_COMMENTS",
            "unique_article_count": (
                len(article_refs)
            ),
            "processed_article_count": 0,
            "comment_count": 0,
            "article_page_request_count": (
                article_page_request_count
            ),
            "comment_request_count": 0,
            "total_request_count": (
                article_page_request_count
            ),
            "completed": False,
        },
    )

    # 2. 고유 Article별 Comment를 끝까지 수집한다.
    for board_no, article_no in article_refs:
        comment_offset = 0

        while True:
            retry_count = 0

            while True:
                batch_id = (
                    "community-comment-"
                    f"{board_no}-"
                    f"{article_no}-"
                    f"{comment_offset:06d}-"
                    + datetime.now(
                        UTC
                    ).strftime(
                        "%Y%m%dT%H%M%S%fZ"
                    )
                )

                adapter = (
                    adapter_factory()
                )

                raw_snapshots: list[
                    ProtectedRawResponse
                ] = []

                def capture(
                    path: str,
                    payload: Any,
                ) -> None:
                    response_key = (
                        path.rsplit(
                            "/",
                            1,
                        )[-1]
                    )

                    if (
                        response_key
                        != "comments"
                        or not isinstance(
                            payload,
                            dict,
                        )
                    ):
                        raise ValueError(
                            "unsupported comment response"
                        )

                    items = payload.get(
                        "comments"
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
                                "article_comments"
                            ),
                            batch_id=(
                                batch_id
                            ),
                            page_id=(
                                "page-000001"
                            ),
                            payload=payload,
                            raw_count=(
                                raw_count
                            ),
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
                    / (
                        f"{batch_id}"
                        ".manifest.json"
                    )
                )

                sanitized_target = (
                    root
                    / "cafe24"
                    / "sanitized"
                    / "article_comments"
                    / (
                        f"{batch_id}"
                        ".sanitized.json"
                    )
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
                        "comment batch already exists"
                    )

                raw_batch.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                raw_batch.mkdir()

                cursor = (
                    None
                    if comment_offset == 0
                    else (
                        f"offset:"
                        f"{comment_offset}"
                    )
                )

                try:
                    page = (
                        collecting_adapter
                        .read_article_comments(
                            board_no=board_no,
                            article_no=(
                                article_no
                            ),
                            cursor=cursor,
                        )
                    )

                    comment_request_count += (
                        page.request_count
                    )

                    break

                except ProviderHttpError as exc:
                    # 실제 운영 게시글 중 일부는
                    # Comment endpoint 자체가 지원되지 않을 수 있다.
                    if exc.status_code in {
                        404,
                        422,
                    }:
                        skipped_comment_endpoint_count += 1
                        page = None
                        break

                    if exc.status_code != 429:
                        raise

                    if (
                        retry_count
                        >= max_rate_limit_retries
                    ):
                        raise

                    retry_count += 1

                    wait_seconds = max(
                        (
                            exc.retry_after_seconds
                            if exc.retry_after_seconds
                            is not None
                            else 60.0
                        ),
                        60.0,
                    )

                    time.sleep(
                        wait_seconds
                    )

            if page is None:
                break

            comments = [
                _sanitize_comment(
                    item
                )
                for item in page.items
            ]

            write_sanitized_export(
                protected_root=root,
                provider="CAFE24",
                resource=(
                    "article_comments"
                ),
                batch_id=batch_id,
                records=comments,
            )

            entries = [
                build_raw_response_manifest_entry(
                    raw_page,
                    sanitized_count=(
                        raw_page.raw_count
                    ),
                )
                for raw_page
                in raw_snapshots
            ]

            write_snapshot_manifest(
                output_path=(
                    manifest_path
                ),
                entries=entries,
            )

            comment_count += len(
                comments
            )

            maybe_cooldown()

            if (
                not page.has_more
                or page.next_cursor is None
            ):
                break

            comment_offset += (
                Cafe24Adapter.PAGE_SIZE
            )

            time.sleep(
                batch_delay_seconds
            )

        processed_article_count += 1

        if (
            processed_article_count
            % 10
            == 0
        ):
            _write_progress(
                progress_path=progress_path,
                payload={
                    "run_id": run_id,
                    "status": (
                        "COLLECTING_COMMENTS"
                    ),
                    "unique_article_count": (
                        len(article_refs)
                    ),
                    "processed_article_count": (
                        processed_article_count
                    ),
                    "comment_count": (
                        comment_count
                    ),
                    "article_page_request_count": (
                        article_page_request_count
                    ),
                    "comment_request_count": (
                        comment_request_count
                    ),
                    "skipped_comment_endpoint_count": (
                        skipped_comment_endpoint_count
                    ),
                    "total_request_count": (
                        article_page_request_count
                        + comment_request_count
                    ),
                    "completed": False,
                },
            )

        time.sleep(
            batch_delay_seconds
        )

    result = (
        Cafe24CommunityCommentFullResult(
            run_id=run_id,
            unique_article_count=(
                len(article_refs)
            ),
            processed_article_count=(
                processed_article_count
            ),
            comment_count=(
                comment_count
            ),
            article_page_request_count=(
                article_page_request_count
            ),
            comment_request_count=(
                comment_request_count
            ),
            skipped_comment_endpoint_count=(
                skipped_comment_endpoint_count
            ),
            total_request_count=(
                article_page_request_count
                + comment_request_count
            ),
            completed=True,
            progress_path=(
                progress_path
            ),
        )
    )

    _write_progress(
        progress_path=progress_path,
        payload={
            **asdict(
                result
            ),
            "status": "COMPLETED",
        },
    )

    return result