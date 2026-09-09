"""Cafe24 Product/Variant/Inventory 전용 LIVE Read Bootstrap."""

from __future__ import annotations

from copy import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.app.adapters.providers.cafe24.adapter import Cafe24Adapter
from backend.app.adapters.providers.http_transport import ReadOnlyHttpTransport
from backend.app.sync.cafe24_bootstrap import (
    _collect_paginated,
    _require_component,
    _require_contained,
    _require_int,
    _require_protected_root,
    _require_text,
)

from backend.app.worker.privacy.snapshot_manifest import (
    build_raw_response_manifest_entry,
    write_snapshot_manifest,
)
from backend.app.worker.privacy.protected_storage import (
    ProtectedRawResponse,
    write_protected_raw_response,
    write_sanitized_export,
)


_RESPONSE_RESOURCES = {
    "products": "products",
    "variants": "variants",
    "inventories": "variant_inventories",
}


@dataclass(frozen=True)
class Cafe24ProductBootstrapResult:
    batch_id: str
    product_offset: int
    product_page_count: int
    next_product_offset: int | None
    has_more: bool
    variant_count: int
    inventory_count: int
    request_count: int
    external_write_count: int
    manifest_path: Path


def run_cafe24_product_bootstrap(
    *,
    adapter: Cafe24Adapter,
    protected_root: Path,
    batch_id: str,
    max_pages: int = 100,
    product_offset: int = 0,
    product_batch_size: int = 25,
) -> Cafe24ProductBootstrapResult:
    """상품/Variant/Inventory만 보호 수집한다."""

    root = _require_protected_root(protected_root)
    _require_component(batch_id)

    if max_pages < 1:
        raise ValueError("max_pages must be positive")

    if type(product_offset) is not int or product_offset < 0:
        raise ValueError("product_offset must be at least 0")

    if product_offset % adapter.PAGE_SIZE != 0:
        raise ValueError(
            "product_offset must align with Cafe24 page size"
        )

    if (
        type(product_batch_size) is not int
        or product_batch_size < 1
        or product_batch_size > adapter.PAGE_SIZE
    ):
        raise ValueError(
            "product_batch_size must be between 1 and Cafe24 page size"
        )

    if not isinstance(
        getattr(adapter, "transport", None),
        ReadOnlyHttpTransport,
    ):
        raise ValueError(
            "product bootstrap requires read-only HTTP transport"
        )

    raw_snapshots: list[ProtectedRawResponse] = []

    def capture(path: str, payload: Any) -> None:
        response_key = path.rsplit("/", 1)[-1]
        resource = _RESPONSE_RESOURCES.get(response_key)

        if resource is None or not isinstance(payload, dict):
            raise ValueError("unsupported product bootstrap response")

        if response_key == "inventories":
            inventory = payload.get("inventory")
            raw_count = 1 if isinstance(inventory, dict) else 0
        else:
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

    sanitized_targets = [
        root
        / "cafe24"
        / "sanitized"
        / resource
        / f"{batch_id}.sanitized.json"
        for resource in _RESPONSE_RESOURCES.values()
    ]

    for target in sanitized_targets:
        _require_contained(root, target)

    if (
        raw_batch.exists()
        or manifest_path.exists()
        or any(target.exists() for target in sanitized_targets)
    ):
        raise FileExistsError("product bootstrap batch already exists")

    raw_batch.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    raw_batch.mkdir()

    product_cursor = (
        None
        if product_offset == 0
        else f"offset:{product_offset}"
    )

    product_page = collecting_adapter.read_products(
        cursor=product_cursor
    )

    products = list(product_page.items)

    product_batch = products[
        :product_batch_size
    ]

    variants: list[dict[str, Any]] = []

    for product in product_batch:
        product_no = _require_int(
            product,
            "product_no",
        )

        variants.extend(
            _collect_paginated(
                adapter=collecting_adapter,
                read_page=(
                    lambda provider, cursor, product_no=product_no:
                    provider.read_variants(
                        product_no=product_no,
                        cursor=cursor,
                    )
                ),
                max_pages=max_pages,
            )
        )

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

        page = collecting_adapter.read_variant_inventory(
            product_no=product_no,
            variant_code=variant_code,
        )

        if page.has_more or page.next_cursor is not None:
            raise RuntimeError(
                "Cafe24 Product Bootstrap inventory pagination "
                "is not supported"
            )

        inventories.extend(page.items)

    collected = {
        "products": products,
        "variants": variants,
        "variant_inventories": inventories,
    }

    observed = {
        page.resource
        for page in raw_snapshots
    }

    if "products" not in observed:
        raise RuntimeError(
            "product raw response evidence is incomplete"
        )

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

    next_product_offset: int | None = None

    if product_page.next_cursor is not None:
        prefix = "offset:"

        if not product_page.next_cursor.startswith(prefix):
            raise RuntimeError(
                "unexpected Cafe24 product cursor"
            )

        try:
            next_product_offset = int(
                product_page.next_cursor.removeprefix(prefix)
            )
        except ValueError:
            raise RuntimeError(
                "invalid Cafe24 product cursor offset"
            ) from None

    return Cafe24ProductBootstrapResult(
        batch_id=batch_id,
        product_offset=product_offset,
        product_page_count=len(product_batch),
        next_product_offset=next_product_offset,
        has_more=product_page.has_more,
        variant_count=len(variants),
        inventory_count=len(inventories),
        request_count=collecting_adapter.transport.request_count,
        external_write_count=0,
        manifest_path=manifest_path,
    )
