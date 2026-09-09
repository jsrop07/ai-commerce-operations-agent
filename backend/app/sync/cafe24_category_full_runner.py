"""Cafe24 Category 전체 수집 Runner."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from backend.app.adapters.providers.base import (
    ProviderHttpError,
)
from backend.app.adapters.providers.cafe24.adapter import (
    Cafe24Adapter,
)
from backend.app.sync.cafe24_category_bootstrap import (
    Cafe24CategoryProbeResult,
    run_cafe24_category_probe,
)


@dataclass(frozen=True)
class Cafe24CategoryFullRunnerResult:
    run_id: str
    start_offset: int
    last_success_offset: int | None
    next_category_offset: int | None
    processed_category_count: int
    processed_batch_count: int
    request_count: int
    completed: bool
    progress_path: Path


def _require_root(
    protected_root: Path,
) -> Path:
    root = protected_root.resolve()

    if not root.is_absolute():
        raise ValueError(
            "protected_root must be absolute"
        )

    return root


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


def run_cafe24_category_full_runner(
    *,
    adapter_factory: Callable[
        [],
        Cafe24Adapter,
    ],
    protected_root: Path,
    start_offset: int = 0,
    max_categories: int = 2500,
    batch_delay_seconds: float = 2.0,
    max_rate_limit_retries: int = 3,
    cooldown_every_categories: int = 50,
    chunk_cooldown_seconds: float = 60.0,
) -> Cafe24CategoryFullRunnerResult:
    """카테고리를 25개씩 읽어 마지막 페이지까지 수집한다."""

    root = _require_root(
        protected_root
    )

    page_size = Cafe24Adapter.PAGE_SIZE

    if (
        type(start_offset) is not int
        or start_offset < 0
        or start_offset % page_size != 0
    ):
        raise ValueError(
            "start_offset must align with Cafe24 page size"
        )

    if (
        type(max_categories) is not int
        or max_categories < page_size
        or max_categories % page_size != 0
    ):
        raise ValueError(
            "max_categories must be a positive multiple "
            "of Cafe24 page size"
        )

    if batch_delay_seconds < 0:
        raise ValueError(
            "batch_delay_seconds must not be negative"
        )

    if max_rate_limit_retries < 0:
        raise ValueError(
            "max_rate_limit_retries must not be negative"
        )

    if (
        type(cooldown_every_categories) is not int
        or cooldown_every_categories < page_size
        or cooldown_every_categories % page_size != 0
    ):
        raise ValueError(
            "cooldown_every_categories must align "
            "with Cafe24 page size"
        )

    if chunk_cooldown_seconds < 0:
        raise ValueError(
            "chunk_cooldown_seconds must not be negative"
        )

    max_batch_count = (
        max_categories // page_size
    )

    run_id = (
        "category-full-run-"
        f"{start_offset:06d}-"
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

    current_offset = start_offset

    processed_category_count = 0
    processed_batch_count = 0
    request_count = 0

    last_success_offset: int | None = None
    next_category_offset: int | None = (
        start_offset
    )

    completed = False

    _write_progress(
        progress_path=progress_path,
        payload={
            "run_id": run_id,
            "status": "RUNNING",
            "start_offset": start_offset,
            "last_success_offset": None,
            "next_category_offset": start_offset,
            "processed_category_count": 0,
            "processed_batch_count": 0,
            "request_count": 0,
            "completed": False,
        },
    )

    for _ in range(
        max_batch_count
    ):
        rate_limit_retry_count = 0

        while True:
            batch_id = (
                "category-full-"
                f"{current_offset:06d}-"
                + datetime.now(UTC).strftime(
                    "%Y%m%dT%H%M%S%fZ"
                )
            )

            adapter = adapter_factory()

            try:
                result: Cafe24CategoryProbeResult = (
                    run_cafe24_category_probe(
                        adapter=adapter,
                        protected_root=root,
                        batch_id=batch_id,
                        category_offset=current_offset,
                    )
                )

                break

            except ProviderHttpError as exc:
                if exc.status_code != 429:
                    raise

                if (
                    rate_limit_retry_count
                    >= max_rate_limit_retries
                ):
                    _write_progress(
                        progress_path=progress_path,
                        payload={
                            "run_id": run_id,
                            "status": "FAILED_RATE_LIMIT",
                            "start_offset": start_offset,
                            "last_success_offset": (
                                last_success_offset
                            ),
                            "next_category_offset": (
                                current_offset
                            ),
                            "processed_category_count": (
                                processed_category_count
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

                rate_limit_retry_count += 1

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
                        "status": "RATE_LIMIT_WAIT",
                        "start_offset": start_offset,
                        "last_success_offset": (
                            last_success_offset
                        ),
                        "next_category_offset": (
                            current_offset
                        ),
                        "processed_category_count": (
                            processed_category_count
                        ),
                        "processed_batch_count": (
                            processed_batch_count
                        ),
                        "request_count": (
                            request_count
                        ),
                        "rate_limit_retry_count": (
                            rate_limit_retry_count
                        ),
                        "retry_after_seconds": (
                            wait_seconds
                        ),
                        "completed": False,
                    },
                )

                time.sleep(
                    wait_seconds
                )

        processed_category_count += (
            result.category_count
        )

        processed_batch_count += 1

        request_count += (
            result.request_count
        )

        last_success_offset = (
            current_offset
        )

        next_category_offset = (
            result.next_category_offset
        )

        completed = (
            not result.has_more
            or result.next_category_offset
            is None
        )

        _write_progress(
            progress_path=progress_path,
            payload={
                "run_id": run_id,
                "status": (
                    "COMPLETED"
                    if completed
                    else "RUNNING"
                ),
                "start_offset": start_offset,
                "last_success_offset": (
                    last_success_offset
                ),
                "next_category_offset": (
                    next_category_offset
                ),
                "processed_category_count": (
                    processed_category_count
                ),
                "processed_batch_count": (
                    processed_batch_count
                ),
                "request_count": (
                    request_count
                ),
                "completed": completed,
            },
        )

        if completed:
            break

        if next_category_offset is None:
            break

        current_offset = (
            next_category_offset
        )

        if (
            processed_category_count
            % cooldown_every_categories
            == 0
        ):
            _write_progress(
                progress_path=progress_path,
                payload={
                    "run_id": run_id,
                    "status": "CHUNK_COOLDOWN",
                    "start_offset": start_offset,
                    "last_success_offset": (
                        last_success_offset
                    ),
                    "next_category_offset": (
                        current_offset
                    ),
                    "processed_category_count": (
                        processed_category_count
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

    final_result = (
        Cafe24CategoryFullRunnerResult(
            run_id=run_id,
            start_offset=start_offset,
            last_success_offset=(
                last_success_offset
            ),
            next_category_offset=(
                next_category_offset
            ),
            processed_category_count=(
                processed_category_count
            ),
            processed_batch_count=(
                processed_batch_count
            ),
            request_count=request_count,
            completed=completed,
            progress_path=progress_path,
        )
    )

    _write_progress(
        progress_path=progress_path,
        payload={
            **asdict(final_result),
            "status": (
                "COMPLETED"
                if completed
                else "LIMIT_REACHED"
            ),
        },
    )

    return final_result