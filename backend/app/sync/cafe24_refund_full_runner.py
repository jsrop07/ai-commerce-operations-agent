"""Cafe24 최근 Refund 전체 Read-Only 수집 Runner."""

from __future__ import annotations

import json
import time
from copy import copy
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
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
    sanitize_record,
)


@dataclass(frozen=True)
class Cafe24RefundPageResult:
    batch_id: str
    start_date: date
    end_date: date
    refund_offset: int
    refund_count: int
    next_refund_offset: int | None
    has_more: bool
    request_count: int
    external_write_count: int
    manifest_path: Path


@dataclass(frozen=True)
class Cafe24RefundFullResult:
    run_id: str
    range_start_date: date
    range_end_date: date
    processed_window_count: int
    processed_batch_count: int
    refund_record_count: int
    request_count: int
    next_window_start_date: date | None
    next_refund_offset: int | None
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


def run_cafe24_refund_page(
    *,
    adapter: Cafe24Adapter,
    protected_root: Path,
    batch_id: str,
    start_date: date,
    end_date: date,
    refund_offset: int,
) -> Cafe24RefundPageResult:
    root = _require_protected_root(
        protected_root
    )

    if (
        type(refund_offset) is not int
        or refund_offset < 0
        or refund_offset
        % Cafe24Adapter.PAGE_SIZE
        != 0
    ):
        raise ValueError(
            "refund_offset must align with Cafe24 page size"
        )

    transport = getattr(
        adapter,
        "transport",
        None,
    )

    if not isinstance(
        transport,
        ReadOnlyHttpTransport,
    ):
        raise ValueError(
            "refund collection requires read-only HTTP transport"
        )

    raw_snapshots: list[
        ProtectedRawResponse
    ] = []

    def capture(
        path: str,
        payload: Any,
    ) -> None:
        if not isinstance(
            payload,
            dict,
        ):
            raise ValueError(
                "refund raw response must be object"
            )

        items = payload.get(
            "refunds"
        )

        if not isinstance(
            items,
            list,
        ):
            raise ValueError(
                "refund raw response has no refunds list"
            )

        raw_snapshots.append(
            write_protected_raw_response(
                protected_root=root,
                provider="CAFE24",
                resource="refunds",
                batch_id=batch_id,
                page_id="page-000001",
                payload=payload,
                raw_count=len(items),
            )
        )

    collecting_adapter = copy(
        adapter
    )

    collecting_adapter.transport = (
        transport.with_raw_capture(
            capture
        )
    )

    raw_dir = (
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

    sanitized_path = (
        root
        / "cafe24"
        / "sanitized"
        / "refunds"
        / f"{batch_id}.sanitized.json"
    )

    for path in (
        raw_dir,
        manifest_path,
        sanitized_path,
    ):
        _require_contained(
            root,
            path,
        )

    if (
        raw_dir.exists()
        or manifest_path.exists()
        or sanitized_path.exists()
    ):
        raise FileExistsError(
            "refund batch already exists"
        )

    raw_dir.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    raw_dir.mkdir()

    cursor = (
        None
        if refund_offset == 0
        else f"offset:{refund_offset}"
    )

    page = (
        collecting_adapter
        .read_refunds(
            cursor=cursor,
            start_date=start_date,
            end_date=end_date,
        )
    )

    refunds = [
        sanitize_record(
            item
        )
        for item in page.items
        if isinstance(
            item,
            dict,
        )
    ]

    sanitized_snapshot = write_sanitized_export(
        protected_root=root,
        provider="CAFE24",
        resource="refunds",
        batch_id=batch_id,
        records=refunds,
    )

    entries = [
        build_raw_response_manifest_entry(
            raw_page,
            sanitized_count=sanitized_snapshot.sanitized_count,
            sanitized_path=sanitized_snapshot.sanitized_path,
        )
        for raw_page
        in raw_snapshots
    ]

    write_snapshot_manifest(
        output_path=manifest_path,
        entries=entries,
    )

    next_refund_offset: int | None = None

    if page.next_cursor is not None:
        if not page.next_cursor.startswith(
            "offset:"
        ):
            raise ValueError(
                "unexpected refund next cursor"
            )

        try:
            next_refund_offset = int(
                page.next_cursor.removeprefix(
                    "offset:"
                )
            )
        except ValueError:
            raise ValueError(
                "invalid refund next cursor"
            ) from None

    return Cafe24RefundPageResult(
        batch_id=batch_id,
        start_date=start_date,
        end_date=end_date,
        refund_offset=refund_offset,
        refund_count=len(
            refunds
        ),
        next_refund_offset=(
            next_refund_offset
        ),
        has_more=page.has_more,
        request_count=(
            collecting_adapter
            .transport
            .request_count
        ),
        external_write_count=0,
        manifest_path=manifest_path,
    )


def _build_windows(
    *,
    start_date: date,
    end_date: date,
) -> list[
    tuple[date, date]
]:
    windows: list[
        tuple[date, date]
    ] = []

    current_start = (
        start_date
    )

    while current_start <= end_date:
        current_end = min(
            current_start
            + timedelta(days=30),
            end_date,
        )

        windows.append(
            (
                current_start,
                current_end,
            )
        )

        current_start = (
            current_end
            + timedelta(days=1)
        )

    return windows


def run_cafe24_refund_full_runner(
    *,
    adapter_factory: Callable[
        [],
        Cafe24Adapter,
    ],
    protected_root: Path,
    range_start_date: date,
    range_end_date: date,
    max_refunds: int = 10000,
    batch_delay_seconds: float = 0.3,
    cooldown_every_requests: int = 50,
    chunk_cooldown_seconds: float = 60.0,
    max_rate_limit_retries: int = 3,
) -> Cafe24RefundFullResult:
    root = _require_protected_root(
        protected_root
    )

    if (
        range_start_date
        > range_end_date
    ):
        raise ValueError(
            "invalid refund date range"
        )

    windows = _build_windows(
        start_date=(
            range_start_date
        ),
        end_date=(
            range_end_date
        ),
    )

    run_id = (
        "refund-full-run-"
        + datetime.now(
            UTC
        ).strftime(
            "%Y%m%dT%H%M%S%fZ"
        )
    )

    progress_path = (
        root
        / "cafe24"
        / "progress"
        / f"{run_id}.json"
    )

    processed_window_count = 0
    processed_batch_count = 0
    refund_record_count = 0
    request_count = 0

    next_cooldown_at = (
        cooldown_every_requests
    )

    next_window_start_date: (
        date | None
    ) = windows[0][0]

    next_refund_offset: (
        int | None
    ) = 0

    def save_progress(
        status_name: str,
    ) -> None:
        _write_progress(
            progress_path=progress_path,
            payload={
                "run_id": run_id,
                "status": status_name,
                "range_start_date": (
                    range_start_date
                ),
                "range_end_date": (
                    range_end_date
                ),
                "processed_window_count": (
                    processed_window_count
                ),
                "processed_batch_count": (
                    processed_batch_count
                ),
                "refund_record_count": (
                    refund_record_count
                ),
                "request_count": (
                    request_count
                ),
                "next_window_start_date": (
                    next_window_start_date
                ),
                "next_refund_offset": (
                    next_refund_offset
                ),
                "completed": False,
            },
        )

    save_progress(
        "RUNNING"
    )

    for window_index, (
        window_start,
        window_end,
    ) in enumerate(
        windows
    ):
        current_offset = 0

        while True:
            if (
                refund_record_count
                >= max_refunds
            ):
                break

            retry_count = 0

            while True:
                batch_id = (
                    "refund-full-"
                    f"{window_start.isoformat()}-"
                    f"{window_end.isoformat()}-"
                    f"{current_offset:06d}-"
                    + datetime.now(
                        UTC
                    ).strftime(
                        "%Y%m%dT%H%M%S%fZ"
                    )
                )

                adapter = (
                    adapter_factory()
                )

                try:
                    result = (
                        run_cafe24_refund_page(
                            adapter=adapter,
                            protected_root=root,
                            batch_id=batch_id,
                            start_date=(
                                window_start
                            ),
                            end_date=(
                                window_end
                            ),
                            refund_offset=(
                                current_offset
                            ),
                        )
                    )

                    break

                except ProviderHttpError as exc:
                    if exc.status_code != 429:
                        raise

                    retry_count += 1

                    if (
                        retry_count
                        > max_rate_limit_retries
                    ):
                        save_progress(
                            "FAILED_RATE_LIMIT"
                        )
                        raise

                    wait_seconds = max(
                        (
                            exc.retry_after_seconds
                            if exc.retry_after_seconds
                            is not None
                            else 60.0
                        ),
                        60.0,
                    )

                    save_progress(
                        "RATE_LIMIT_WAIT"
                    )

                    time.sleep(
                        wait_seconds
                    )

            processed_batch_count += 1

            refund_record_count += (
                result.refund_count
            )

            request_count += (
                result.request_count
            )

            page_completed = (
                not result.has_more
                or result.next_refund_offset
                is None
            )

            if page_completed:
                processed_window_count += 1

                next_index = (
                    window_index + 1
                )

                if next_index < len(
                    windows
                ):
                    next_window_start_date = (
                        windows[
                            next_index
                        ][0]
                    )

                    next_refund_offset = 0

                else:
                    next_window_start_date = None
                    next_refund_offset = None

                save_progress(
                    "WINDOW_COMPLETED"
                )

                break

            current_offset = (
                result.next_refund_offset
            )

            next_window_start_date = (
                window_start
            )

            next_refund_offset = (
                current_offset
            )

            save_progress(
                "RUNNING"
            )

            if (
                request_count
                >= next_cooldown_at
            ):
                save_progress(
                    "CHUNK_COOLDOWN"
                )

                time.sleep(
                    chunk_cooldown_seconds
                )

                while (
                    request_count
                    >= next_cooldown_at
                ):
                    next_cooldown_at += (
                        cooldown_every_requests
                    )

            else:
                time.sleep(
                    batch_delay_seconds
                )

        if (
            refund_record_count
            >= max_refunds
        ):
            break

    completed = (
        next_window_start_date
        is None
        and next_refund_offset
        is None
    )

    result = (
        Cafe24RefundFullResult(
            run_id=run_id,
            range_start_date=(
                range_start_date
            ),
            range_end_date=(
                range_end_date
            ),
            processed_window_count=(
                processed_window_count
            ),
            processed_batch_count=(
                processed_batch_count
            ),
            refund_record_count=(
                refund_record_count
            ),
            request_count=(
                request_count
            ),
            next_window_start_date=(
                next_window_start_date
            ),
            next_refund_offset=(
                next_refund_offset
            ),
            completed=completed,
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
            "status": (
                "COMPLETED"
                if completed
                else "LIMIT_REACHED"
            ),
        },
    )

    return result
