"""Cafe24 Product 전체 수집용 500개 단위 Runner."""

from __future__ import annotations
import re
import time
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from backend.app.adapters.providers.cafe24.adapter import (
    Cafe24Adapter,
)
from backend.app.sync.cafe24_product_bootstrap import (
    Cafe24ProductBootstrapResult,
    run_cafe24_product_bootstrap,
)
from backend.app.adapters.providers.base import (
    ProviderHttpError,
    ProviderNonRetryableError,
    ProviderTransientError,
)

@dataclass(frozen=True)
class Cafe24ProductFullRunnerResult:
    run_id: str
    start_offset: int
    last_success_offset: int | None
    next_product_offset: int | None
    processed_product_count: int
    processed_batch_count: int
    variant_count: int
    inventory_count: int
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

def _find_first_missing_product_offset(
    *,
    root: Path,
    page_size: int,
) -> int | None:
    manifest_root = (
        root
        / "cafe24"
        / "manifests"
    )

    if not manifest_root.exists():
        return None

    existing_offsets: set[int] = set()

    for path in manifest_root.glob(
        "product-full-*.manifest.json"
    ):
        match = re.match(
            r"product-full-(\d{6})-",
            path.name,
        )

        if match is None:
            continue

        existing_offsets.add(
            int(match.group(1))
        )

    if not existing_offsets:
        return None

    highest_offset = max(
        existing_offsets
    )

    for offset in range(
        0,
        highest_offset + page_size,
        page_size,
    ):
        if offset not in existing_offsets:
            return offset

    return None


def run_cafe24_product_full_runner(
    *,
    adapter_factory: Callable[
        [],
        Cafe24Adapter,
    ],
    protected_root: Path,
    start_offset: int = 0,
    max_products: int = 2500,
    batch_delay_seconds: float = 2.0,
    max_rate_limit_retries: int = 3,
    cooldown_every_products: int = 50,
    chunk_cooldown_seconds: float = 90.0,
) -> Cafe24ProductFullRunnerResult:
    """상품을 25개씩 처리하고 200개마다 휴식하며 전체 수집한다."""

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

    missing_offset = (
        _find_first_missing_product_offset(
            root=root,
            page_size=page_size,
        )
    )

    if (
        missing_offset is not None
        and start_offset > missing_offset
    ):
        raise ValueError(
            "product resume cannot skip "
            f"unresolved offset {missing_offset}"
        )

    if (
        type(max_products) is not int
        or max_products < page_size
        or max_products % page_size != 0
    ):
        raise ValueError(
            "max_products must be a positive multiple "
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
        type(cooldown_every_products) is not int
        or cooldown_every_products < page_size
        or cooldown_every_products % page_size != 0
    ):
        raise ValueError(
            "cooldown_every_products must be a positive "
            "multiple of Cafe24 page size"
        )

    if chunk_cooldown_seconds < 0:
        raise ValueError(
            "chunk_cooldown_seconds must not be negative"
        )
    max_batch_count = (
        max_products // page_size
    )

    run_id = (
        "product-full-run-"
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

    processed_product_count = 0
    processed_batch_count = 0
    variant_count = 0
    inventory_count = 0
    request_count = 0

    last_success_offset: int | None = None
    next_product_offset: int | None = (
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
            "next_product_offset": start_offset,
            "processed_product_count": 0,
            "processed_batch_count": 0,
            "completed": False,
        },
    )

    for _ in range(
        max_batch_count
    ):
        rate_limit_retry_count = 0

        while True:
            batch_id = (
                "product-full-"
                f"{current_offset:06d}-"
                + datetime.now(UTC).strftime(
                    "%Y%m%dT%H%M%S%fZ"
                )
            )

            adapter = adapter_factory()

            try:
                result: Cafe24ProductBootstrapResult = (
                    run_cafe24_product_bootstrap(
                        adapter=adapter,
                        protected_root=root,
                        batch_id=batch_id,
                        max_pages=10,
                        product_offset=current_offset,
                        product_batch_size=page_size,
                    )
                )

                break

            except ProviderHttpError as exc:
                if exc.status_code != 429:
                    _write_progress(
                        progress_path=progress_path,
                        payload={
                            "run_id": run_id,
                            "status": "FAILED_HTTP",
                            "start_offset": start_offset,
                            "last_success_offset": last_success_offset,
                            "next_product_offset": current_offset,
                            "processed_product_count": processed_product_count,
                            "processed_batch_count": processed_batch_count,
                            "variant_count": variant_count,
                            "inventory_count": inventory_count,
                            "request_count": request_count,
                            "http_status_code": exc.status_code,
                            "completed": False,
                        },
                    )
                    raise

                if rate_limit_retry_count >= max_rate_limit_retries:
                    _write_progress(
                        progress_path=progress_path,
                        payload={
                            "run_id": run_id,
                            "status": "FAILED_RATE_LIMIT",
                            "start_offset": start_offset,
                            "last_success_offset": last_success_offset,
                            "next_product_offset": current_offset,
                            "processed_product_count": processed_product_count,
                            "processed_batch_count": processed_batch_count,
                            "variant_count": variant_count,
                            "inventory_count": inventory_count,
                            "request_count": request_count,
                            "rate_limit_retry_count": rate_limit_retry_count,
                            "completed": False,
                        },
                    )
                    raise

                rate_limit_retry_count += 1

                retry_after = (
                    exc.retry_after_seconds
                    if exc.retry_after_seconds is not None
                    else 90.0
                )

                wait_seconds = max(
                    retry_after,
                    90.0,
                )

                _write_progress(
                    progress_path=progress_path,
                    payload={
                        "run_id": run_id,
                        "status": "RATE_LIMIT_WAIT",
                        "start_offset": start_offset,
                        "last_success_offset": last_success_offset,
                        "next_product_offset": current_offset,
                        "processed_product_count": processed_product_count,
                        "processed_batch_count": processed_batch_count,
                        "variant_count": variant_count,
                        "inventory_count": inventory_count,
                        "request_count": request_count,
                        "rate_limit_retry_count": rate_limit_retry_count,
                        "retry_after_seconds": wait_seconds,
                        "completed": False,
                    },
                )

                time.sleep(
                    wait_seconds
                )

            except ProviderTransientError:
                _write_progress(
                    progress_path=progress_path,
                    payload={
                        "run_id": run_id,
                        "status": "FAILED_TRANSIENT",
                        "start_offset": start_offset,
                        "last_success_offset": last_success_offset,
                        "next_product_offset": current_offset,
                        "processed_product_count": processed_product_count,
                        "processed_batch_count": processed_batch_count,
                        "variant_count": variant_count,
                        "inventory_count": inventory_count,
                        "request_count": request_count,
                        "completed": False,
                    },
                )
                raise

            except ProviderNonRetryableError:
                _write_progress(
                    progress_path=progress_path,
                    payload={
                        "run_id": run_id,
                        "status": "FAILED_NON_RETRYABLE",
                        "start_offset": start_offset,
                        "last_success_offset": last_success_offset,
                        "next_product_offset": current_offset,
                        "processed_product_count": processed_product_count,
                        "processed_batch_count": processed_batch_count,
                        "variant_count": variant_count,
                        "inventory_count": inventory_count,
                        "request_count": request_count,
                        "completed": False,
                    },
                )
                raise

            except Exception:
                _write_progress(
                    progress_path=progress_path,
                    payload={
                        "run_id": run_id,
                        "status": "FAILED_UNEXPECTED",
                        "start_offset": start_offset,
                        "last_success_offset": last_success_offset,
                        "next_product_offset": current_offset,
                        "processed_product_count": processed_product_count,
                        "processed_batch_count": processed_batch_count,
                        "variant_count": variant_count,
                        "inventory_count": inventory_count,
                        "request_count": request_count,
                        "completed": False,
                    },
                )
                raise

        processed_product_count += (
            result.product_page_count
        )

        processed_batch_count += 1

        variant_count += (
            result.variant_count
        )

        inventory_count += (
            result.inventory_count
        )

        request_count += (
            result.request_count
        )

        last_success_offset = (
            current_offset
        )

        next_product_offset = (
            result.next_product_offset
        )

        completed = (
            not result.has_more
            or result.next_product_offset
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
                "start_offset": (
                    start_offset
                ),
                "last_success_offset": (
                    last_success_offset
                ),
                "next_product_offset": (
                    next_product_offset
                ),
                "processed_product_count": (
                    processed_product_count
                ),
                "processed_batch_count": (
                    processed_batch_count
                ),
                "variant_count": (
                    variant_count
                ),
                "inventory_count": (
                    inventory_count
                ),
                "request_count": (
                    request_count
                ),
                "completed": (
                    completed
                ),
            },
        )

        if completed:
            break

        if next_product_offset is None:
            break

        current_offset = (
            next_product_offset
        )

        if not completed:
            if (
                processed_product_count
                % cooldown_every_products
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
                        "next_product_offset": (
                            next_product_offset
                        ),
                        "processed_product_count": (
                            processed_product_count
                        ),
                        "processed_batch_count": (
                            processed_batch_count
                        ),
                        "variant_count": (
                            variant_count
                        ),
                        "inventory_count": (
                            inventory_count
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
        Cafe24ProductFullRunnerResult(
            run_id=run_id,
            start_offset=start_offset,
            last_success_offset=(
                last_success_offset
            ),
            next_product_offset=(
                next_product_offset
            ),
            processed_product_count=(
                processed_product_count
            ),
            processed_batch_count=(
                processed_batch_count
            ),
            variant_count=variant_count,
            inventory_count=inventory_count,
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