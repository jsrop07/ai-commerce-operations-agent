"""Cafe24 Board/Article/Comment 전용 LIVE Read Probe."""

from __future__ import annotations

from copy import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.app.adapters.providers.cafe24.adapter import Cafe24Adapter
from backend.app.adapters.providers.http_transport import ReadOnlyHttpTransport
from backend.app.sync.cafe24_bootstrap import (
    _require_component,
    _require_contained,
    _require_int,
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

_RESPONSE_RESOURCES = {
    "boards": "boards",
    "articles": "articles",
    "comments": "article_comments",
}


@dataclass(frozen=True)
class Cafe24CommunityProbeResult:
    batch_id: str
    board_count: int
    selected_board_count: int
    article_count: int
    selected_article_count: int
    comment_count: int
    request_count: int
    external_write_count: int
    manifest_path: Path


def run_cafe24_community_probe(
    *,
    adapter: Cafe24Adapter,
    protected_root: Path,
    batch_id: str,
    board_limit: int = 2,
    article_limit_per_board: int = 3,
) -> Cafe24CommunityProbeResult:
    """게시판/글/댓글을 소량 Read-Only로 수집한다."""

    root = _require_protected_root(protected_root)
    _require_component(batch_id)

    if board_limit < 1:
        raise ValueError("board_limit must be positive")

    if article_limit_per_board < 1:
        raise ValueError("article_limit_per_board must be positive")

    if not isinstance(
        getattr(adapter, "transport", None),
        ReadOnlyHttpTransport,
    ):
        raise ValueError(
            "community probe requires read-only HTTP transport"
        )

    raw_snapshots: list[ProtectedRawResponse] = []

    def capture(path: str, payload: Any) -> None:
        response_key = path.rsplit("/", 1)[-1]
        resource = _RESPONSE_RESOURCES.get(response_key)

        if resource is None or not isinstance(payload, dict):
            raise ValueError("unsupported community probe response")

        items = payload.get(response_key)
        raw_count = len(items) if isinstance(items, list) else 0

        raw_snapshots.append(
            write_protected_raw_response(
                protected_root=root,
                provider="CAFE24",
                resource=resource,
                batch_id=batch_id,
                page_id=f"page-{len(raw_snapshots) + 1:06d}",
                payload=payload,
                raw_count=raw_count,
            )
        )

    collecting_adapter = copy(adapter)
    collecting_adapter.transport = adapter.transport.with_raw_capture(
        capture
    )

    raw_batch = root / "cafe24" / "raw" / batch_id
    manifest_path = (
        root
        / "cafe24"
        / "manifests"
        / f"{batch_id}.manifest.json"
    )

    _require_contained(root, raw_batch)
    _require_contained(root, manifest_path)

    resources = (
        "boards",
        "articles",
        "article_comments",
    )

    sanitized_targets = [
        root
        / "cafe24"
        / "sanitized"
        / resource
        / f"{batch_id}.sanitized.json"
        for resource in resources
    ]

    for target in sanitized_targets:
        _require_contained(root, target)

    if (
        raw_batch.exists()
        or manifest_path.exists()
        or any(
            target.exists()
            for target in sanitized_targets
        )
    ):
        raise FileExistsError(
            "community probe batch already exists"
        )

    raw_batch.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    raw_batch.mkdir()

    board_page = collecting_adapter.read_boards()
    boards = list(board_page.items)

    comment_enabled_boards = [
        board
        for board in boards
        if board.get("use_comment") == "T"
    ]

    selected_boards = comment_enabled_boards[:board_limit]

    articles: list[dict[str, Any]] = []

    selected_articles: list[dict[str, Any]] = []

    for board in selected_boards:
        board_no = _require_int(
            board,
            "board_no",
        )

        article_page = collecting_adapter.read_articles(
            board_no=board_no,
        )

        board_articles = list(
            article_page.items
        )

        articles.extend(
            board_articles
        )

        selected_articles.extend(
            board_articles[
                :article_limit_per_board
            ]
        )

    comments: list[dict[str, Any]] = []

    for article in selected_articles:
        board_no = _require_int(
            article,
            "board_no",
        )

        article_no = _require_int(
            article,
            "article_no",
        )

        comment_page = (
            collecting_adapter.read_article_comments(
                board_no=board_no,
                article_no=article_no,
            )
        )

        comments.extend(
            comment_page.items
        )
    collected = {
        "boards": [
            sanitize_community_record(item)
            for item in boards
        ],
        "articles": [
            sanitize_community_record(item)
            for item in articles
        ],
        "article_comments": [
            sanitize_community_record(item)
            for item in comments
        ],
    }

    sanitized_snapshots = {
        resource: write_sanitized_export(
            protected_root=root,
            provider="CAFE24",
            resource=resource,
            batch_id=batch_id,
            records=records,
        )
        for resource, records in collected.items()
    }

    entries = [
        build_raw_response_manifest_entry(
            page,
            sanitized_count=page.raw_count,
            sanitized_path=(
                sanitized_snapshots[page.resource].sanitized_path
            ),
        )
        for page in raw_snapshots
    ]

    write_snapshot_manifest(
        output_path=manifest_path,
        entries=entries,
    )

    return Cafe24CommunityProbeResult(
        batch_id=batch_id,
        board_count=len(boards),
        selected_board_count=len(
            selected_boards
        ),
        article_count=len(articles),
        selected_article_count=len(
            selected_articles
        ),
        comment_count=len(comments),
        request_count=(
            collecting_adapter.transport.request_count
        ),
        external_write_count=0,
        manifest_path=manifest_path,
    )
