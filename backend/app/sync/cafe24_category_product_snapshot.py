"""Cafe24 current category-product relation Read-Only snapshot."""

from __future__ import annotations

from copy import copy
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.app.adapters.providers.cafe24.adapter import (
    Cafe24Adapter,
)
from backend.app.adapters.providers.http_transport import (
    ReadOnlyHttpTransport,
)
from backend.app.worker.privacy.protected_storage import (
    ProtectedRawResponse,
    SanitizedSnapshotResult,
    _require_component,
    _require_contained,
    _require_protected_root,
    write_protected_raw_response,
    write_sanitized_export,
)
from backend.app.worker.privacy.snapshot_manifest import (
    build_raw_response_manifest_entry,
    write_snapshot_manifest,
)

RESOURCE = "category_product_relations"


@dataclass(frozen=True)
class Cafe24CategoryProductSnapshotResult:
    batch_id: str
    category_no: int
    display_group: int
    relation_count: int
    as_of: datetime
    source_classification: str
    evidence_type: str
    read_succeeded: bool
    request_count: int
    external_write_count: int
    raw_snapshot: ProtectedRawResponse = field(
        repr=False,
    )
    sanitized_snapshot: SanitizedSnapshotResult = field(
        repr=False,
    )
    manifest_path: Path = field(
        repr=False,
    )


def run_cafe24_category_product_snapshot(
    *,
    adapter: Cafe24Adapter,
    protected_root: Path,
    batch_id: str,
    category_no: int,
    display_group: int = 1,
    source_classification: str = "SANITIZED_REAL",
) -> Cafe24CategoryProductSnapshotResult:
    """Capture current category relations without any Provider write."""

    root = _require_protected_root(
        protected_root
    )
    _require_component(batch_id)
    if type(category_no) is not int or category_no < 1:
        raise ValueError(
            "category_no must be a positive integer"
        )
    if source_classification not in {
        "SANITIZED_REAL",
        "LIVE_READ",
        "FILE_IMPORT",
    }:
        raise ValueError(
            "unsupported source_classification"
        )
    if not isinstance(
        getattr(adapter, "transport", None),
        ReadOnlyHttpTransport,
    ):
        raise ValueError(
            "category product snapshot requires read-only HTTP transport"
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
        / RESOURCE
        / f"{batch_id}.sanitized.json"
    )
    raw_path = (
        root
        / "cafe24"
        / "raw"
        / batch_id
        / RESOURCE
        / "page-000001.json"
    )
    for target in (
        manifest_path,
        sanitized_path,
        raw_path,
    ):
        _require_contained(root, target)
        if target.exists():
            raise FileExistsError(
                "category product snapshot batch already exists"
            )

    captured: list[ProtectedRawResponse] = []

    def capture(
        path: str,
        payload: Any,
    ) -> None:
        expected_path = (
            f"/api/v2/admin/categories/{category_no}/products"
        )
        if path != expected_path or not isinstance(payload, dict):
            raise ValueError(
                "unsupported category product response"
            )
        products = payload.get("products")
        if not isinstance(products, list):
            raise ValueError(
                "category product response requires products"
            )
        captured.append(
            write_protected_raw_response(
                protected_root=root,
                provider="CAFE24",
                resource=RESOURCE,
                batch_id=batch_id,
                page_id="page-000001",
                payload=payload,
                raw_count=len(products),
            )
        )

    collecting_adapter = copy(adapter)
    collecting_adapter.transport = (
        adapter.transport.with_raw_capture(
            capture
        )
    )
    page = collecting_adapter.read_category_products(
        category_no,
        display_group=display_group,
    )
    if len(captured) != 1:
        raise RuntimeError(
            "category product protected raw evidence is incomplete"
        )

    raw_snapshot = captured[0]
    source_as_of = page.source_as_of
    as_of = source_as_of.isoformat()
    records = [
        {
            "category_no": relation["category_no"],
            "product_no": relation["product_no"],
            "as_of": as_of,
            "source_classification": source_classification,
            "evidence_type": "CURRENT_CATEGORY_EVIDENCE",
            "evidence_id": (
                "cafe24-category-product:"
                f"{raw_snapshot.raw_sha256}:"
                f"{relation['product_no']}"
            ),
            "provenance": {
                "provider": "CAFE24",
                "resource": RESOURCE,
                "batch_id": batch_id,
                "raw_sha256": raw_snapshot.raw_sha256,
            },
        }
        for relation in page.items
    ]
    sanitized_snapshot = write_sanitized_export(
        protected_root=root,
        provider="CAFE24",
        resource=RESOURCE,
        batch_id=batch_id,
        records=records,
        snapshot_metadata={
            "category_no": category_no,
            "display_group": display_group,
            "read_succeeded": True,
            "relation_count": len(records),
            "as_of": as_of,
            "source_classification": source_classification,
            "evidence_type": "CURRENT_CATEGORY_EVIDENCE",
            "external_write_count": 0,
        },
    )
    entry = build_raw_response_manifest_entry(
        raw_snapshot,
        sanitized_count=(
            sanitized_snapshot.sanitized_count
        ),
        sanitized_path=(
            sanitized_snapshot.sanitized_path
        ),
    )
    write_snapshot_manifest(
        output_path=manifest_path,
        entries=[entry],
    )

    return Cafe24CategoryProductSnapshotResult(
        batch_id=batch_id,
        category_no=category_no,
        display_group=display_group,
        relation_count=len(records),
        as_of=source_as_of,
        source_classification=source_classification,
        evidence_type="CURRENT_CATEGORY_EVIDENCE",
        read_succeeded=True,
        request_count=(
            collecting_adapter.transport.request_count
        ),
        external_write_count=0,
        raw_snapshot=raw_snapshot,
        sanitized_snapshot=sanitized_snapshot,
        manifest_path=manifest_path,
    )
