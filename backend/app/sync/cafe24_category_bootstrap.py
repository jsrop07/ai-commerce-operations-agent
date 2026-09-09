"""Cafe24 카테고리 소량 Read-Only Probe."""

from __future__ import annotations

from copy import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.app.adapters.providers.cafe24.adapter import Cafe24Adapter
from backend.app.adapters.providers.http_transport import ReadOnlyHttpTransport
from backend.app.worker.privacy.protected_storage import (
    ProtectedRawResponse,
    write_protected_raw_response,
    write_sanitized_export,
)
from backend.app.worker.privacy.snapshot_manifest import (
    build_raw_response_manifest_entry,
    write_snapshot_manifest,
)


@dataclass(frozen=True)
class Cafe24CategoryProbeResult:
    batch_id: str
    category_offset: int
    category_count: int
    next_category_offset: int | None
    has_more: bool
    request_count: int
    external_write_count: int
    manifest_path: Path

def _require_protected_root(
    path: Path,
) -> Path:
    root = path.resolve()

    if not root.is_absolute():
        raise ValueError(
            "protected_root must be absolute"
        )

    return root


def _require_component(
    value: str,
) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
    ):
        raise ValueError(
            "batch_id is required"
        )

    if (
        "/" in value
        or "\\" in value
        or value in {".", ".."}
    ):
        raise ValueError(
            "invalid batch_id"
        )

    return value


def _require_contained(
    root: Path,
    target: Path,
) -> None:
    resolved_root = root.resolve()
    resolved_target = target.resolve()

    try:
        resolved_target.relative_to(
            resolved_root
        )
    except ValueError:
        raise ValueError(
            "target path escapes protected root"
        ) from None


def run_cafe24_category_probe(
    *,
    adapter: Cafe24Adapter,
    protected_root: Path,
    batch_id: str,
    category_offset: int = 0,
) -> Cafe24CategoryProbeResult:
    """카테고리 첫 페이지를 소량 Read-Only로 수집한다."""

    root = _require_protected_root(
        protected_root
    )
    _require_component(
        batch_id
    )
    if (
        type(category_offset) is not int
        or category_offset < 0
        or category_offset % Cafe24Adapter.PAGE_SIZE != 0
    ):
        raise ValueError(
            "category_offset must align with Cafe24 page size"
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
            "category probe requires read-only HTTP transport"
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
            response_key != "categories"
            or not isinstance(
                payload,
                dict,
            )
        ):
            raise ValueError(
                "unsupported category probe response"
            )

        items = payload.get(
            "categories"
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
                resource="categories",
                batch_id=batch_id,
                page_id=(
                    "page-"
                    f"{len(raw_snapshots) + 1:06d}"
                ),
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
        / "categories"
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
            "category probe batch already exists"
        )

    raw_batch.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    raw_batch.mkdir()

    category_cursor = (
        None
        if category_offset == 0
        else f"offset:{category_offset}"
    )

    category_page = (
        collecting_adapter.read_categories(
            cursor=category_cursor,
        )
    )

    categories = list(
        category_page.items
    )

    next_category_offset: int | None = None

    if category_page.next_cursor is not None:
        prefix = "offset:"

        if not category_page.next_cursor.startswith(
            prefix
        ):
            raise ValueError(
                "unexpected category next cursor"
            )

        try:
            next_category_offset = int(
                category_page.next_cursor.removeprefix(
                    prefix
                )
            )
        except ValueError:
            raise ValueError(
                "invalid category next cursor"
            ) from None
    write_sanitized_export(
        protected_root=root,
        provider="CAFE24",
        resource="categories",
        batch_id=batch_id,
        records=categories,
    )

    entries = [
        build_raw_response_manifest_entry(
            page,
            sanitized_count=(
                page.raw_count
            ),
        )
        for page in raw_snapshots
    ]

    write_snapshot_manifest(
        output_path=manifest_path,
        entries=entries,
    )

    return Cafe24CategoryProbeResult(
        batch_id=batch_id,
        category_offset=category_offset,
        category_count=len(
            categories
        ),
        next_category_offset=next_category_offset,
        has_more=category_page.has_more,
        request_count=(
            collecting_adapter.transport.request_count
        ),
        external_write_count=0,
        manifest_path=manifest_path,
    )