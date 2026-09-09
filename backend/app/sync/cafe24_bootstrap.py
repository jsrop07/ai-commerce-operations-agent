"""Cafe24 Read Bootstrap Snapshot 실행기."""

from __future__ import annotations

from copy import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from backend.app.adapters.providers.cafe24.adapter import Cafe24Adapter
from backend.app.adapters.providers.http_transport import ReadOnlyHttpTransport
from backend.app.sync.retry_policy import RetryPolicy
from backend.app.sync.runner import (
    ProviderSyncRunner,
    SyncBudget,
)
from backend.app.worker.privacy.protected_storage import (
    ProtectedRawResponse,
    SanitizedSnapshotResult,
    write_protected_raw_response,
    write_sanitized_export,
    _require_contained,
    _require_protected_root,
    _require_component,
)
from backend.app.worker.privacy.snapshot_manifest import (
    build_raw_response_manifest_entry,
    write_snapshot_manifest,
)

@dataclass(frozen=True)
class Cafe24BootstrapResult:
    batch_id: str
    snapshots: tuple[SanitizedSnapshotResult, ...]
    raw_snapshots: tuple[ProtectedRawResponse, ...]
    manifest_path: Path = field(repr=False)
    product_start: int
    product_batch_size: int
    product_batch_count: int
    next_product_start: int | None
    product_batch_completed: bool
    request_count: int
    external_write_count: int = 0


def _require_int(
    record: dict[str, Any],
    field: str,
) -> int:
    value = record.get(field)

    if type(value) is not int or value < 1:
        raise ValueError(
            f"Cafe24 Bootstrap 필수 정수 식별자가 없습니다: {field}"
        )

    return value


def _require_text(
    record: dict[str, Any],
    field: str,
) -> str:
    value = record.get(field)

    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"Cafe24 Bootstrap 필수 문자열 식별자가 없습니다: {field}"
        )

    return value.strip()


def _collect_paginated(
    *,
    adapter: Cafe24Adapter,
    read_page: Callable[
        [Cafe24Adapter, str | None],
        Any,
    ],
    max_pages: int,
) -> list[dict[str, Any]]:
    runner = ProviderSyncRunner(
        retry_policy=RetryPolicy(),
        budget=SyncBudget(
            max_pages=max_pages,
            max_items=10_000,
            max_elapsed_seconds=300.0,
        ),
    )

    result = runner.run(
        provider=adapter,
        read_page=read_page,
    )

    if not result.completed:
        raise RuntimeError(
            "Cafe24 Bootstrap pagination이 완료되지 않았습니다: "
            f"{result.stop_reason}"
        )

    return result.items


def _collect_cafe24_resources(
    *,
    adapter: Cafe24Adapter,
    max_pages: int,
    product_start: int,
    product_batch_size: int,
) -> dict[str, list[dict[str, Any]]]:
    """Existing bounded collector/fan-out sequence; all results are sanitized."""

    collected: dict[str, list[dict[str, Any]]] = {}

    # 1. Product
    products = _collect_paginated(
        adapter=adapter,
        read_page=lambda provider, cursor: provider.read_products(
            cursor
        ),
        max_pages=max_pages,
    )
    collected["products"] = products

    product_batch = products[
        product_start:product_start + product_batch_size
    ]

    # 2. Variant
    variants: list[dict[str, Any]] = []

    for product in product_batch:
        product_no = _require_int(
            product,
            "product_no",
        )

        variants.extend(_collect_paginated(
            adapter=adapter,
            read_page=lambda provider, cursor, product_no=product_no: provider.read_variants(
                product_no=product_no, cursor=cursor,
            ),
            max_pages=max_pages,
        ))

    collected["variants"] = variants

    # 3. Variant Inventory
    inventories: list[dict[str, Any]] = []

    for variant in variants:
        product_no = _require_int(
            variant,
            "product_no",
        )
        variant_code = _require_text(
            variant,
            "variant_code",
        )

        page = adapter.read_variant_inventory(
            product_no=product_no,
            variant_code=variant_code,
        )

        if page.has_more or page.next_cursor is not None:
            raise RuntimeError("Cafe24 Bootstrap detail pagination is not supported")
        inventories.extend(page.items)

    collected["variant_inventories"] = inventories

    # 4. Category
    categories = _collect_paginated(
        adapter=adapter,
        read_page=lambda provider, cursor: provider.read_categories(
            cursor
        ),
        max_pages=max_pages,
    )
    collected["categories"] = categories

    # 5. Order
    orders = _collect_paginated(
        adapter=adapter,
        read_page=lambda provider, cursor: provider.read_orders(
            cursor
        ),
        max_pages=max_pages,
    )
    collected["orders"] = orders

    # 6. Order Item
    order_items: list[dict[str, Any]] = []

    for order in orders:
        order_id = _require_text(
            order,
            "order_id",
        )

        page = adapter.read_order_items(
            order_id=order_id,
        )

        if page.has_more or page.next_cursor is not None:
            raise RuntimeError("Cafe24 Bootstrap detail pagination is not supported")
        order_items.extend(page.items)

    collected["order_items"] = order_items

    # 7. Refund
    refunds = _collect_paginated(
        adapter=adapter,
        read_page=lambda provider, cursor: provider.read_refunds(
            cursor
        ),
        max_pages=max_pages,
    )
    collected["refunds"] = refunds

    # 8. Board
    boards = _collect_paginated(
        adapter=adapter,
        read_page=lambda provider, cursor: provider.read_boards(
            cursor
        ),
        max_pages=max_pages,
    )
    collected["boards"] = boards

    # 9. Article
    articles: list[dict[str, Any]] = []

    for board in boards:
        board_no = _require_int(
            board,
            "board_no",
        )

        board_articles = _collect_paginated(
            adapter=adapter,
            read_page=lambda provider, cursor, board_no=board_no:
                provider.read_articles(
                    board_no=board_no,
                    cursor=cursor,
                ),
            max_pages=max_pages,
        )

        articles.extend(board_articles)

    collected["articles"] = articles

    # 10. Comment / Reply
    comments: list[dict[str, Any]] = []

    for article in articles:
        board_no = _require_int(
            article,
            "board_no",
        )
        article_no = _require_int(
            article,
            "article_no",
        )

        article_comments = _collect_paginated(
            adapter=adapter,
            read_page=(
                lambda provider, cursor,
                board_no=board_no,
                article_no=article_no:
                    provider.read_article_comments(
                        board_no=board_no,
                        article_no=article_no,
                        cursor=cursor,
                    )
            ),
            max_pages=max_pages,
        )

        comments.extend(article_comments)

    collected["article_comments"] = comments

    return collected


_RESPONSE_RESOURCES = {
    "products": "products", "variants": "variants", "inventories": "variant_inventories",
    "categories": "categories", "orders": "orders", "items": "order_items",
    "refunds": "refunds", "boards": "boards", "articles": "articles",
    "comments": "article_comments",
}


def _product_batch_resume(
    *, product_total: int, product_start: int, product_batch_size: int,
) -> tuple[int, int | None]:
    batch_count = len(
        range(product_total)[product_start:product_start + product_batch_size]
    )
    next_start = (
        product_start + batch_count
        if batch_count > 0 and product_start + batch_count < product_total
        else None
    )
    return batch_count, next_start


def run_cafe24_read_bootstrap(
    *,
    adapter: Cafe24Adapter,
    protected_root: Path,
    batch_id: str,
    max_pages: int = 100,
    product_start: int = 0,
    product_batch_size: int = 250,
) -> Cafe24BootstrapResult:
    """Capture raw HTTP pages before staging and export sanitized collector results.

    Product historical/full backfill: Cafe24 Product Export CSV.
    Order historical 6-month backfill: Cafe24 Order Export CSV.
    API: enrichment / reconciliation / latest-state / identifiers / inventory /
    variants / inquiry / incremental sync validation. The existing 30-day API
    window is not a historical coverage blocker. CSV ingestion and reconciliation
    remain Official Backend/Data Day 8 work (NOT_STARTED).
    """
    root = _require_protected_root(protected_root)
    _require_component(batch_id)
    if max_pages < 1:
        raise ValueError("max_pages must be positive")
    if type(product_start) is not int or product_start < 0:
        raise ValueError("product_start must be at least 0")
    if type(product_batch_size) is not int or product_batch_size < 1:
        raise ValueError("product_batch_size must be at least 1")
    if not isinstance(getattr(adapter, "transport", None), ReadOnlyHttpTransport):
        raise ValueError("bootstrap requires a capture-capable read-only HTTP transport")

    raw_snapshots: list[ProtectedRawResponse] = []

    def capture(
        path: str,
        payload: Any,
    ) -> None:
        """실제 Provider 응답을 Adapter sanitize 이전에 Protected Raw로 보존한다."""

        response_key = (
            path.rsplit("/", 1)[-1]
        )

        resource = (
            _RESPONSE_RESOURCES.get(
                response_key
            )
        )

        if (
            resource is None
            or not isinstance(
                payload,
                dict,
            )
        ):
            raise ValueError(
                "unsupported bootstrap response"
            )

        # 대부분 Cafe24 list endpoint는
        # {
        #     "products": [...],
        #     "orders": [...],
        #     ...
        # }
        # 형태다.
        #
        # 단 Variant Inventory detail endpoint는
        # {
        #     "inventory": {...}
        # }
        # 단건 Object 계약이다.
        if (
            response_key
            == "inventories"
        ):
            inventory = (
                payload.get(
                    "inventory"
                )
            )

            if inventory is None:
                raw_count = 0

            elif isinstance(
                inventory,
                dict,
            ):
                raw_count = 1

            else:
                raise ValueError(
                    "unsupported variant inventory response"
                )

        else:
            items = payload.get(
                response_key
            )

            if items is None:
                raw_count = 0

            elif isinstance(
                items,
                list,
            ):
                raw_count = len(
                    items
                )

            else:
                raise ValueError(
                    "unsupported bootstrap list response"
                )

        try:
            raw_snapshot = (
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

        except Exception:
            # Protected 위치, payload, credential 등
            # 민감 내용을 예외 문자열로 외부에 노출하지 않는다.
            raise RuntimeError(
                "bootstrap protected raw capture failed"
            ) from None

        raw_snapshots.append(
            raw_snapshot
        )

    # The caller's adapter/transport remains unchanged, including its optional hook.
    collecting_adapter = copy(adapter)
    collecting_adapter.transport = adapter.transport.with_raw_capture(capture)
    manifest_path = root / "cafe24" / "manifests" / f"{batch_id}.manifest.json"
    raw_batch = root / "cafe24" / "raw" / batch_id
    _require_contained(root, raw_batch)
    _require_contained(root, manifest_path)
    targets = [manifest_path]
    for resource in _RESPONSE_RESOURCES.values():
        target = root / "cafe24" / "sanitized" / resource / f"{batch_id}.sanitized.json"
        _require_contained(root, target)
        targets.append(target)
    if raw_batch.exists() or any(target.exists() for target in targets):
        raise FileExistsError("bootstrap batch already exists")
    # Reserve a batch before reads. Partial raw pages remain immutable evidence;
    # an incomplete batch has no success manifest and cannot be silently replayed.
    try:
        raw_batch.parent.mkdir(parents=True, exist_ok=True)
        raw_batch.mkdir()
    except FileExistsError:
        raise FileExistsError("bootstrap batch already exists") from None
    except OSError:
        raise OSError("bootstrap protected batch reservation failed") from None

    collected = _collect_cafe24_resources(
        adapter=collecting_adapter,
        max_pages=max_pages,
        product_start=product_start,
        product_batch_size=product_batch_size,
    )
    observed = {page.resource for page in raw_snapshots}
    if not {"products", "orders", "categories", "refunds", "boards"} <= observed:
        raise RuntimeError("bootstrap raw response evidence is incomplete")
    for resource, records in collected.items():
        raw_count = sum(page.raw_count for page in raw_snapshots if page.resource == resource)
        if raw_count != len(records):
            raise RuntimeError("bootstrap raw and sanitized counts differ")

    snapshots = tuple(write_sanitized_export(
        protected_root=root, provider="CAFE24", resource=resource, batch_id=batch_id,
        records=records,
    ) for resource, records in collected.items())
    snapshots_by_resource = {
        snapshot.resource: snapshot
        for snapshot in snapshots
    }
    entries = [
        build_raw_response_manifest_entry(
            page,
            sanitized_count=page.raw_count,
            sanitized_path=snapshots_by_resource[page.resource].sanitized_path,
        )
        for page in raw_snapshots
    ]
    write_snapshot_manifest(output_path=manifest_path, entries=entries)
    product_batch_count, next_product_start = _product_batch_resume(
        product_total=len(collected["products"]),
        product_start=product_start,
        product_batch_size=product_batch_size,
    )
    return Cafe24BootstrapResult(
        batch_id=batch_id, snapshots=snapshots, raw_snapshots=tuple(raw_snapshots),
        manifest_path=manifest_path,
        product_start=product_start,
        product_batch_size=product_batch_size,
        product_batch_count=product_batch_count,
        next_product_start=next_product_start,
        product_batch_completed=True,
        request_count=collecting_adapter.transport.request_count,
        external_write_count=0,
    )
