"""Cafe24 최근 주문 전체 Read-Only 수집 Runner."""

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
class Cafe24OrderPageResult:
    batch_id: str
    start_date: date
    end_date: date
    order_offset: int
    order_count: int
    next_order_offset: int | None
    has_more: bool
    request_count: int
    external_write_count: int
    manifest_path: Path


@dataclass(frozen=True)
class Cafe24OrderFullResult:
    run_id: str
    range_start_date: date
    range_end_date: date
    processed_window_count: int
    processed_batch_count: int
    order_record_count: int
    request_count: int
    next_window_start_date: date | None
    next_order_offset: int | None
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


def _sanitize_order(
    record: dict[str, Any],
) -> dict[str, Any]:
    return sanitize_record(
        record
    )


def run_cafe24_order_page(
    *,
    adapter: Cafe24Adapter,
    protected_root: Path,
    batch_id: str,
    start_date: date,
    end_date: date,
    order_offset: int,
) -> Cafe24OrderPageResult:
    """주문 한 페이지를 Protected Raw + Sanitized로 저장한다."""

    root = _require_protected_root(
        protected_root
    )

    if (
        type(order_offset) is not int
        or order_offset < 0
        or order_offset
        % Cafe24Adapter.PAGE_SIZE
        != 0
    ):
        raise ValueError(
            "order_offset must align with Cafe24 page size"
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
            "order collection requires read-only HTTP transport"
        )

    raw_snapshots: list[
        ProtectedRawResponse
    ] = []

    def capture(
        path: str,
        payload: Any,
    ) -> None:
        response_key = (
            path.rsplit("/", 1)[-1]
        )

        if (
            response_key != "orders"
            or not isinstance(
                payload,
                dict,
            )
        ):
            raise ValueError(
                "unsupported order response"
            )

        items = payload.get(
            "orders"
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
                resource="orders",
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
        / "orders"
        / f"{batch_id}.sanitized.json"
    )

    for path in (
        raw_batch,
        manifest_path,
        sanitized_target,
    ):
        _require_contained(
            root,
            path,
        )

    if (
        raw_batch.exists()
        or manifest_path.exists()
        or sanitized_target.exists()
    ):
        raise FileExistsError(
            "order batch already exists"
        )

    raw_batch.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    raw_batch.mkdir()

    cursor = (
        None
        if order_offset == 0
        else f"offset:{order_offset}"
    )

    page = (
        collecting_adapter.read_orders(
            cursor=cursor,
            start_date=start_date,
            end_date=end_date,
        )
    )

    orders = list(
        page.items
    )

    sanitized_orders = [
        _sanitize_order(
            order
        )
        for order in orders
    ]

    write_sanitized_export(
        protected_root=root,
        provider="CAFE24",
        resource="orders",
        batch_id=batch_id,
        records=sanitized_orders,
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
        output_path=manifest_path,
        entries=entries,
    )

    next_order_offset: int | None = None

    if page.next_cursor is not None:
        prefix = "offset:"

        if not page.next_cursor.startswith(
            prefix
        ):
            raise ValueError(
                "unexpected order next cursor"
            )

        try:
            next_order_offset = int(
                page.next_cursor.removeprefix(
                    prefix
                )
            )
        except ValueError:
            raise ValueError(
                "invalid order next cursor"
            ) from None

    return Cafe24OrderPageResult(
        batch_id=batch_id,
        start_date=start_date,
        end_date=end_date,
        order_offset=order_offset,
        order_count=len(
            orders
        ),
        next_order_offset=(
            next_order_offset
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


def run_cafe24_order_full_runner(
    *,
    adapter_factory: Callable[
        [],
        Cafe24Adapter,
    ],
    protected_root: Path,
    range_start_date: date,
    range_end_date: date,
    resume_window_start_date: date | None = None,
    resume_order_offset: int = 0,
    max_orders: int = 10000,
    batch_delay_seconds: float = 0.3,
    cooldown_every_requests: int = 50,
    chunk_cooldown_seconds: float = 60.0,
    max_rate_limit_retries: int = 3,
) -> Cafe24OrderFullResult:
    """날짜 window + offset pagination으로 주문 전체를 수집한다."""

    root = _require_protected_root(
        protected_root
    )

    if (
        range_start_date
        > range_end_date
    ):
        raise ValueError(
            "invalid order date range"
        )

    if (
        type(resume_order_offset)
        is not int
        or resume_order_offset < 0
        or resume_order_offset
        % Cafe24Adapter.PAGE_SIZE
        != 0
    ):
        raise ValueError(
            "resume_order_offset must align with page size"
        )

    windows = _build_windows(
        start_date=(
            range_start_date
        ),
        end_date=(
            range_end_date
        ),
    )

    if resume_window_start_date is not None:
        windows = [
            window
            for window in windows
            if window[0]
            >= resume_window_start_date
        ]

        if not windows:
            raise ValueError(
                "resume window is outside range"
            )

        if (
            windows[0][0]
            != resume_window_start_date
        ):
            raise ValueError(
                "resume window must match generated window boundary"
            )

    run_id = (
        "order-full-run-"
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
    order_record_count = 0
    request_count = 0

    next_cooldown_at = (
        cooldown_every_requests
    )

    next_window_start_date: (
        date | None
    ) = (
        windows[0][0]
        if windows
        else None
    )

    next_order_offset: (
        int | None
    ) = (
        resume_order_offset
    )

    completed = False

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
                "order_record_count": (
                    order_record_count
                ),
                "request_count": (
                    request_count
                ),
                "next_window_start_date": (
                    next_window_start_date
                ),
                "next_order_offset": (
                    next_order_offset
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
        current_offset = (
            resume_order_offset
            if (
                window_index == 0
                and resume_window_start_date
                is not None
            )
            else 0
        )

        while True:
            if (
                order_record_count
                >= max_orders
            ):
                break

            retry_count = 0

            while True:
                batch_id = (
                    "order-full-"
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
                        run_cafe24_order_page(
                            adapter=adapter,
                            protected_root=root,
                            batch_id=batch_id,
                            start_date=(
                                window_start
                            ),
                            end_date=(
                                window_end
                            ),
                            order_offset=(
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
                        save_progress(
                            "FAILED_RATE_LIMIT"
                        )
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

                    save_progress(
                        "RATE_LIMIT_WAIT"
                    )

                    time.sleep(
                        wait_seconds
                    )

            processed_batch_count += 1

            order_record_count += (
                result.order_count
            )

            request_count += (
                result.request_count
            )

            page_completed = (
                not result.has_more
                or result.next_order_offset
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

                    next_order_offset = 0

                else:
                    next_window_start_date = None
                    next_order_offset = None

                save_progress(
                    "WINDOW_COMPLETED"
                )

                break

            current_offset = (
                result.next_order_offset
            )

            next_window_start_date = (
                window_start
            )

            next_order_offset = (
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
            order_record_count
            >= max_orders
        ):
            break

    completed = (
        next_window_start_date
        is None
        and next_order_offset
        is None
    )

    result = (
        Cafe24OrderFullResult(
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
            order_record_count=(
                order_record_count
            ),
            request_count=(
                request_count
            ),
            next_window_start_date=(
                next_window_start_date
            ),
            next_order_offset=(
                next_order_offset
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