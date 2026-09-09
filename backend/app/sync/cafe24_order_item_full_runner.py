"""Cafe24 Order Items 전체 Protected Read-Only 수집 Runner."""

from __future__ import annotations

import hashlib
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
    select_canonical_sanitized_artifacts,
    write_snapshot_manifest,
)
from backend.app.worker.privacy.staging import (
    sanitize_record,
)


@dataclass(frozen=True)
class Cafe24OrderItemFullResult:
    run_id: str
    unique_order_count: int
    processed_order_count: int
    order_item_count: int
    empty_order_count: int
    source_missing_count: int
    skipped_existing_count: int
    failed_count: int
    request_count: int
    completed: bool
    progress_path: Path


def _write_json_atomic(
    path: Path,
    payload: dict[str, Any],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = (
        path.with_suffix(
            path.suffix + ".tmp"
        )
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
        path
    )


def _order_hash(
    order_id: str,
) -> str:
    return hashlib.sha256(
        order_id.encode("utf-8")
    ).hexdigest()


def _load_order_ids(
    *,
    root: Path,
) -> list[str]:
    selection = select_canonical_sanitized_artifacts(
        protected_root=root,
        resource="orders",
        filename_pattern="order-full-*.sanitized.json",
    )
    if selection.invalid_artifact_count:
        raise ValueError("invalid canonical order batch")

    order_ids: set[str] = set()

    for file_path in selection.artifacts:
        _require_contained(
            root,
            file_path,
        )

        try:
            payload = json.loads(
                file_path.read_text(
                    encoding="utf-8"
                )
            )
        except (
            OSError,
            json.JSONDecodeError,
        ):
            raise ValueError(
                "invalid sanitized order export"
            ) from None

        if not isinstance(
            payload,
            dict,
        ):
            raise ValueError(
                "sanitized order export must be object"
            )

        records = payload.get(
            "records"
        )

        if not isinstance(
            records,
            list,
        ):
            raise ValueError(
                "sanitized order records must be list"
            )

        for record in records:
            if not isinstance(
                record,
                dict,
            ):
                continue

            order_id = record.get(
                "order_id"
            )

            if (
                isinstance(
                    order_id,
                    str,
                )
                and order_id
            ):
                order_ids.add(
                    order_id
                )

    return sorted(
        order_ids
    )


def _load_index(
    index_path: Path,
) -> dict[str, Any]:
    if not index_path.exists():
        return {
            "schema_version": (
                "cafe24-order-items-index.v1"
            ),
            "items": {},
        }

    try:
        payload = json.loads(
            index_path.read_text(
                encoding="utf-8"
            )
        )
    except (
        OSError,
        json.JSONDecodeError,
    ):
        raise ValueError(
            "order item index is invalid"
        ) from None

    if (
        not isinstance(
            payload,
            dict,
        )
        or not isinstance(
            payload.get("items"),
            dict,
        )
    ):
        raise ValueError(
            "order item index structure is invalid"
        )

    return payload


def _run_order_item_one(
    *,
    adapter: Cafe24Adapter,
    root: Path,
    order_id: str,
    batch_id: str,
) -> tuple[
    int,
    int,
]:
    """주문 한 건의 품목을 보호 저장하고 (item_count, request_count)를 반환한다."""

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
            "order item collection requires read-only transport"
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
                "order item raw response must be object"
            )

        items = payload.get(
            "items"
        )

        if not isinstance(
            items,
            list,
        ):
            raise ValueError(
                "order item raw response has no items list"
            )

        raw_snapshots.append(
            write_protected_raw_response(
                protected_root=root,
                provider="CAFE24",
                resource="order_items",
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

    sanitized_path = (
        root
        / "cafe24"
        / "sanitized"
        / "order_items"
        / f"{batch_id}.sanitized.json"
    )

    manifest_path = (
        root
        / "cafe24"
        / "manifests"
        / f"{batch_id}.manifest.json"
    )

    for path in (
        raw_dir,
        sanitized_path,
        manifest_path,
    ):
        _require_contained(
            root,
            path,
        )

    if (
        raw_dir.exists()
        or sanitized_path.exists()
        or manifest_path.exists()
    ):
        raise FileExistsError(
            "order item batch already exists"
        )

    raw_dir.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    raw_dir.mkdir()

    page = (
        collecting_adapter
        .read_order_items(
            order_id=order_id
        )
    )

    items = [
        sanitize_record(
            item
        )
        for item in page.items
        if isinstance(
            item,
            dict,
        )
    ]

    write_sanitized_export(
        protected_root=root,
        provider="CAFE24",
        resource="order_items",
        batch_id=batch_id,
        records=items,
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

    return (
        len(items),
        collecting_adapter
        .transport
        .request_count,
    )


def run_cafe24_order_item_full_runner(
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
) -> Cafe24OrderItemFullResult:
    """수집된 모든 고유 주문의 Order Items를 fan-out으로 수집한다."""

    root = _require_protected_root(
        protected_root
    )

    order_ids = _load_order_ids(
        root=root
    )

    run_id = (
        "order-item-full-run-"
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

    index_path = (
        root
        / "cafe24"
        / "order_items"
        / "index.json"
    )

    _require_contained(
        root,
        progress_path,
    )

    _require_contained(
        root,
        index_path,
    )

    index_payload = _load_index(
        index_path
    )

    index_items = (
        index_payload["items"]
    )

    processed_order_count = 0
    order_item_count = 0
    empty_order_count = 0
    source_missing_count = 0
    skipped_existing_count = 0
    failed_count = 0
    request_count = 0

    next_cooldown_at = (
        cooldown_every_requests
    )

    def save_progress(
        status_name: str,
    ) -> None:
        _write_json_atomic(
            progress_path,
            {
                "run_id": run_id,
                "status": status_name,
                "unique_order_count": (
                    len(order_ids)
                ),
                "processed_order_count": (
                    processed_order_count
                ),
                "order_item_count": (
                    order_item_count
                ),
                "empty_order_count": (
                    empty_order_count
                ),
                "source_missing_count": (
                    source_missing_count
                ),
                "skipped_existing_count": (
                    skipped_existing_count
                ),
                "failed_count": (
                    failed_count
                ),
                "request_count": (
                    request_count
                ),
                "completed": False,
            },
        )

    save_progress(
        "RUNNING"
    )

    for order_id in order_ids:
        order_key = _order_hash(
            order_id
        )

        existing = index_items.get(
            order_key
        )

        if isinstance(
            existing,
            dict,
        ) and existing.get(
            "status"
        ) in {
            "COMPLETED",
            "EMPTY",
            "SOURCE_MISSING",
        }:
            skipped_existing_count += 1
            processed_order_count += 1
            continue

        retry_count = 0

        while True:
            batch_id = (
                "order-item-full-"
                + order_key[:16]
                + "-"
                + datetime.now(
                    UTC
                ).strftime(
                    "%Y%m%dT%H%M%S%fZ"
                )
            )

            adapter = (
                adapter_factory()
            )

            before_requests = (
                getattr(
                    adapter.transport,
                    "request_count",
                    0,
                )
            )

            try:
                (
                    item_count,
                    used_requests,
                ) = _run_order_item_one(
                    adapter=adapter,
                    root=root,
                    order_id=order_id,
                    batch_id=batch_id,
                )

                request_count += (
                    used_requests
                )

                processed_order_count += 1
                order_item_count += (
                    item_count
                )

                if item_count == 0:
                    empty_order_count += 1
                    item_status = "EMPTY"
                else:
                    item_status = "COMPLETED"

                index_items[
                    order_key
                ] = {
                    "status": (
                        item_status
                    ),
                    "item_count": (
                        item_count
                    ),
                    "batch_id": (
                        batch_id
                    ),
                    "captured_at": (
                        datetime.now(
                            UTC
                        ).isoformat()
                    ),
                }

                _write_json_atomic(
                    index_path,
                    index_payload,
                )

                break

            except ProviderHttpError as exc:
                used_requests = max(
                    getattr(
                        adapter.transport,
                        "request_count",
                        0,
                    )
                    - before_requests,
                    1,
                )

                request_count += (
                    used_requests
                )

                if exc.status_code == 404:
                    processed_order_count += 1
                    source_missing_count += 1

                    index_items[
                        order_key
                    ] = {
                        "status": (
                            "SOURCE_MISSING"
                        ),
                        "captured_at": (
                            datetime.now(
                                UTC
                            ).isoformat()
                        ),
                    }

                    _write_json_atomic(
                        index_path,
                        index_payload,
                    )

                    break

                if exc.status_code != 429:
                    failed_count += 1
                    processed_order_count += 1
                    break

                retry_count += 1

                if (
                    retry_count
                    > max_rate_limit_retries
                ):
                    failed_count += 1
                    processed_order_count += 1
                    break

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

            except Exception:
                # order_id, payload, 응답 body를 로그에 남기지 않는다.
                used_requests = (
                    getattr(
                        adapter.transport,
                        "request_count",
                        0,
                    )
                    - before_requests
                )

                request_count += max(
                    used_requests,
                    0,
                )

                failed_count += 1
                processed_order_count += 1

                break

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
            processed_order_count
            % 25
            == 0
        ):
            save_progress(
                "RUNNING"
            )

    completed = (
        failed_count == 0
        and processed_order_count
        == len(order_ids)
    )

    result = (
        Cafe24OrderItemFullResult(
            run_id=run_id,
            unique_order_count=len(
                order_ids
            ),
            processed_order_count=(
                processed_order_count
            ),
            order_item_count=(
                order_item_count
            ),
            empty_order_count=(
                empty_order_count
            ),
            source_missing_count=(
                source_missing_count
            ),
            skipped_existing_count=(
                skipped_existing_count
            ),
            failed_count=(
                failed_count
            ),
            request_count=(
                request_count
            ),
            completed=completed,
            progress_path=(
                progress_path
            ),
        )
    )

    _write_json_atomic(
        progress_path,
        {
            **asdict(
                result
            ),
            "status": (
                "COMPLETED"
                if completed
                else (
                    "COMPLETED_WITH_FAILURES"
                )
            ),
        },
    )

    return result