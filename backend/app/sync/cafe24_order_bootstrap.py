"""Cafe24 주문 계열 소량 Read-Only Probe."""

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



_RESPONSE_RESOURCES = {
    "orders": "orders",
    "items": "order_items",
    "refunds": "refunds",
}


@dataclass(frozen=True)
class Cafe24OrderProbeResult:
    batch_id: str
    order_count: int
    selected_order_count: int
    order_item_count: int
    refund_count: int
    request_count: int
    external_write_count: int
    manifest_path: Path


def _require_protected_root(path: Path) -> Path:
    root = path.resolve()

    if not root.is_absolute():
        raise ValueError("protected_root must be absolute")

    return root


def _require_component(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("batch_id is required")

    if "/" in value or "\\" in value or value in {".", ".."}:
        raise ValueError("invalid batch_id")

    return value


def _require_contained(root: Path, target: Path) -> None:
    resolved_root = root.resolve()
    resolved_target = target.resolve()

    try:
        resolved_target.relative_to(resolved_root)
    except ValueError:
        raise ValueError(
            "target path escapes protected root"
        ) from None


def _require_text(
    record: dict[str, Any],
    key: str,
) -> str:
    value = record.get(key)

    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"{key} must be non-empty text"
        )

    return value.strip()


def run_cafe24_order_probe(
    *,
    adapter: Cafe24Adapter,
    protected_root: Path,
    batch_id: str,
    order_limit: int = 3,
) -> Cafe24OrderProbeResult:
    """주문/주문품목/환불을 소량 Read-Only로 수집한다."""

    root = _require_protected_root(
        protected_root
    )
    _require_component(batch_id)

    if order_limit < 1:
        raise ValueError(
            "order_limit must be positive"
        )

    if not isinstance(
        getattr(adapter, "transport", None),
        ReadOnlyHttpTransport,
    ):
        raise ValueError(
            "order probe requires read-only HTTP transport"
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

        resource = _RESPONSE_RESOURCES.get(
            response_key
        )

        if (
            resource is None
            or not isinstance(payload, dict)
        ):
            raise ValueError(
                "unsupported order probe response"
            )

        items = payload.get(
            response_key
        )

        raw_count = (
            len(items)
            if isinstance(items, list)
            else 0
        )

        raw_snapshots.append(
            write_protected_raw_response(
                protected_root=root,
                provider="CAFE24",
                resource=resource,
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

    resources = (
        "orders",
        "order_items",
        "refunds",
    )

    sanitized_targets = [
        root
        / "cafe24"
        / "sanitized"
        / resource
        / f"{batch_id}.sanitized.json"
        for resource in resources
    ]

    _require_contained(
        root,
        raw_batch,
    )

    _require_contained(
        root,
        manifest_path,
    )

    for target in sanitized_targets:
        _require_contained(
            root,
            target,
        )

    if (
        raw_batch.exists()
        or manifest_path.exists()
        or any(
            target.exists()
            for target in sanitized_targets
        )
    ):
        raise FileExistsError(
            "order probe batch already exists"
        )

    raw_batch.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    raw_batch.mkdir()

    # 1. 최근 30일 주문 목록 첫 페이지
    order_page = (
        collecting_adapter.read_orders()
    )

    orders = list(
        order_page.items
    )

    selected_orders = orders[
        :order_limit
    ]

    # 2. 선택 주문의 품목
    order_items: list[
        dict[str, Any]
    ] = []

    for order in selected_orders:
        order_id = _require_text(
            order,
            "order_id",
        )

        page = (
            collecting_adapter.read_order_items(
                order_id=order_id,
            )
        )

        if (
            page.has_more
            or page.next_cursor is not None
        ):
            raise RuntimeError(
                "order item pagination is unsupported"
            )

        order_items.extend(
            page.items
        )

    # 3. 최근 30일 환불 목록 첫 페이지
    refund_page = (
        collecting_adapter.read_refunds()
    )

    refunds = list(
        refund_page.items
    )

    collected = {
        "orders": orders,
        "order_items": order_items,
        "refunds": refunds,
    }

    for (
        resource,
        records,
    ) in collected.items():
        write_sanitized_export(
            protected_root=root,
            provider="CAFE24",
            resource=resource,
            batch_id=batch_id,
            records=records,
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

    return Cafe24OrderProbeResult(
        batch_id=batch_id,
        order_count=len(orders),
        selected_order_count=len(
            selected_orders
        ),
        order_item_count=len(
            order_items
        ),
        refund_count=len(
            refunds
        ),
        request_count=(
            collecting_adapter.transport.request_count
        ),
        external_write_count=0,
        manifest_path=manifest_path,
    )