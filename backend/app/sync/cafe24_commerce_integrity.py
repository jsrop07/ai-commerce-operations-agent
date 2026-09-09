"""Cafe24 Pre-Day8 Commerce 수집 결과 무결성 검증."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.app.sync.cafe24_bootstrap import (
    _require_contained,
    _require_protected_root,
)
from backend.app.worker.privacy.snapshot_manifest import (
    select_canonical_sanitized_artifacts,
)


@dataclass(frozen=True)
class Cafe24CommerceIntegrityResult:
    api_order_record_count: int
    api_unique_order_count: int
    api_duplicate_order_count: int

    api_order_item_record_count: int
    api_unique_order_item_count: int
    api_duplicate_order_item_count: int
    order_item_missing_parent_count: int

    refund_record_count: int
    unique_refund_code_count: int
    duplicate_refund_record_count: int
    unique_refund_order_count: int
    refund_missing_parent_count: int

    csv_row_count: int
    csv_unique_order_count: int
    csv_unique_order_item_count: int

    csv_order_intersection_count: int
    csv_order_only_count: int
    api_order_only_count: int

    csv_item_intersection_count: int
    csv_item_only_count: int
    api_item_only_count: int

    order_manifest_missing_count: int
    order_item_manifest_missing_count: int
    refund_manifest_missing_count: int
    manifest_invalid_count: int

    blocking_finding_count: int
    warning_count: int
    passed: bool


def _load_json(
    path: Path,
) -> Any:
    try:
        return json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except (
        OSError,
        json.JSONDecodeError,
    ):
        raise ValueError(
            "invalid protected JSON artifact"
        ) from None


def run_cafe24_commerce_integrity(
    *,
    protected_root: Path,
    csv_path: Path,
) -> Cafe24CommerceIntegrityResult:
    root = _require_protected_root(
        protected_root
    )

    _require_contained(
        root,
        csv_path,
    )

    cafe24_root = (
        root
        / "cafe24"
    )

    sanitized_root = (
        cafe24_root
        / "sanitized"
    )

    manifest_root = (
        cafe24_root
        / "manifests"
    )

    order_selection = select_canonical_sanitized_artifacts(
        protected_root=root,
        resource="orders",
        filename_pattern="order-full-*.sanitized.json",
    )
    order_item_selection = select_canonical_sanitized_artifacts(
        protected_root=root,
        resource="order_items",
        filename_pattern="order-item-full-*.sanitized.json",
    )
    refund_selection = select_canonical_sanitized_artifacts(
        protected_root=root,
        resource="refunds",
        filename_pattern="refund-full-*.sanitized.json",
    )
    # -------------------------------------------------
    # Orders
    # -------------------------------------------------

    order_ids: list[str] = []
    order_batch_ids: set[str] = set()

    for file_path in order_selection.artifacts:

        payload = _load_json(
            file_path
        )

        if not isinstance(
            payload,
            dict,
        ):
            raise ValueError(
                "order sanitized export must be object"
            )

        batch_id = payload.get(
            "batch_id"
        )

        if isinstance(
            batch_id,
            str,
        ):
            order_batch_ids.add(
                batch_id
            )

        records = payload.get(
            "records"
        )

        if not isinstance(
            records,
            list,
        ):
            raise ValueError(
                "order records must be list"
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
                order_ids.append(
                    order_id
                )

    api_order_record_count = len(
        order_ids
    )

    api_order_set = set(
        order_ids
    )

    api_unique_order_count = len(
        api_order_set
    )

    api_duplicate_order_count = (
        api_order_record_count
        - api_unique_order_count
    )

    # -------------------------------------------------
    # Order Items
    # -------------------------------------------------

    item_codes: list[str] = []

    item_parent_order_ids: list[
        str
    ] = []

    order_item_batch_ids: set[
        str
    ] = set()

    for file_path in order_item_selection.artifacts:

        payload = _load_json(
            file_path
        )

        if not isinstance(
            payload,
            dict,
        ):
            raise ValueError(
                "order item sanitized export must be object"
            )

        batch_id = payload.get(
            "batch_id"
        )

        if isinstance(
            batch_id,
            str,
        ):
            order_item_batch_ids.add(
                batch_id
            )

        records = payload.get(
            "records"
        )

        if not isinstance(
            records,
            list,
        ):
            raise ValueError(
                "order item records must be list"
            )

        for record in records:
            if not isinstance(
                record,
                dict,
            ):
                continue

            item_code = record.get(
                "order_item_code"
            )

            if (
                isinstance(
                    item_code,
                    str,
                )
                and item_code
            ):
                item_codes.append(
                    item_code
                )

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
                item_parent_order_ids.append(
                    order_id
                )
            elif (
                isinstance(
                    item_code,
                    str,
                )
                and item_code
            ):
                # Cafe24 item code가 주문번호 prefix를
                # 포함하는 현재 계약에 한해 fallback.
                parts = (
                    item_code.rsplit(
                        "-",
                        1,
                    )
                )

                if len(parts) == 2:
                    item_parent_order_ids.append(
                        parts[0]
                    )

    api_order_item_record_count = (
        len(
            item_codes
        )
    )

    api_item_set = set(
        item_codes
    )

    api_unique_order_item_count = (
        len(
            api_item_set
        )
    )

    api_duplicate_order_item_count = (
        api_order_item_record_count
        - api_unique_order_item_count
    )

    order_item_missing_parent_count = sum(
        1
        for order_id
        in item_parent_order_ids
        if order_id
        not in api_order_set
    )

    # -------------------------------------------------
    # Refunds
    # -------------------------------------------------

    refund_codes: list[str] = []
    refund_order_ids: list[str] = []

    refund_batch_ids: set[
        str
    ] = set()

    for file_path in refund_selection.artifacts:

        payload = _load_json(
            file_path
        )

        if not isinstance(
            payload,
            dict,
        ):
            raise ValueError(
                "refund sanitized export must be object"
            )

        batch_id = payload.get(
            "batch_id"
        )

        if isinstance(
            batch_id,
            str,
        ):
            refund_batch_ids.add(
                batch_id
            )

        records = payload.get(
            "records"
        )

        if not isinstance(
            records,
            list,
        ):
            raise ValueError(
                "refund records must be list"
            )

        for record in records:
            if not isinstance(
                record,
                dict,
            ):
                continue

            refund_code = record.get(
                "refund_code"
            )

            if (
                isinstance(
                    refund_code,
                    str,
                )
                and refund_code
            ):
                refund_codes.append(
                    refund_code
                )

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
                refund_order_ids.append(
                    order_id
                )

    refund_record_count = len(
        refund_codes
    )

    unique_refund_codes = set(
        refund_codes
    )

    unique_refund_code_count = len(
        unique_refund_codes
    )

    duplicate_refund_record_count = (
        refund_record_count
        - unique_refund_code_count
    )

    unique_refund_order_count = len(
        set(
            refund_order_ids
        )
    )

    refund_missing_parent_count = sum(
        1
        for order_id
        in set(
            refund_order_ids
        )
        if order_id
        not in api_order_set
    )

    # -------------------------------------------------
    # CSV
    # -------------------------------------------------

    try:
        with csv_path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as stream:
            csv_rows = list(
                csv.DictReader(
                    stream
                )
            )
    except OSError:
        raise ValueError(
            "CSV read failed"
        ) from None

    csv_order_ids = {
        (
            row.get(
                "주문번호",
                "",
            )
            or ""
        ).strip()
        for row in csv_rows
        if (
            row.get(
                "주문번호",
                "",
            )
            or ""
        ).strip()
    }

    csv_item_ids = {
        (
            row.get(
                "품목별 주문번호",
                "",
            )
            or ""
        ).strip()
        for row in csv_rows
        if (
            row.get(
                "품목별 주문번호",
                "",
            )
            or ""
        ).strip()
    }

    csv_row_count = len(
        csv_rows
    )

    csv_unique_order_count = len(
        csv_order_ids
    )

    csv_unique_order_item_count = len(
        csv_item_ids
    )

    csv_order_intersection_count = len(
        csv_order_ids
        & api_order_set
    )

    csv_order_only_count = len(
        csv_order_ids
        - api_order_set
    )

    api_order_only_count = len(
        api_order_set
        - csv_order_ids
    )

    csv_item_intersection_count = len(
        csv_item_ids
        & api_item_set
    )

    csv_item_only_count = len(
        csv_item_ids
        - api_item_set
    )

    api_item_only_count = len(
        api_item_set
        - csv_item_ids
    )

    # -------------------------------------------------
    # Manifest
    # -------------------------------------------------

    order_manifest_missing_count = order_selection.missing_manifest_count
    order_item_manifest_missing_count = order_item_selection.missing_manifest_count
    refund_manifest_missing_count = refund_selection.missing_manifest_count
    manifest_invalid_count = sum(
        (
            order_selection.invalid_artifact_count,
            order_item_selection.invalid_artifact_count,
            refund_selection.invalid_artifact_count,
        )
    )
    # -------------------------------------------------
    # 판정
    # -------------------------------------------------

    blocking_finding_count = sum(
        (
            api_duplicate_order_count,
            api_duplicate_order_item_count,
            order_item_missing_parent_count,
            refund_missing_parent_count,
            csv_order_only_count,
            csv_item_only_count,
            order_manifest_missing_count,
            order_item_manifest_missing_count,
            refund_manifest_missing_count,
            manifest_invalid_count,
        )
    )

    warning_count = (
        duplicate_refund_record_count
        + api_order_only_count
        + api_item_only_count
    )

    passed = (
        blocking_finding_count == 0
    )

    return Cafe24CommerceIntegrityResult(
        api_order_record_count=(
            api_order_record_count
        ),
        api_unique_order_count=(
            api_unique_order_count
        ),
        api_duplicate_order_count=(
            api_duplicate_order_count
        ),
        api_order_item_record_count=(
            api_order_item_record_count
        ),
        api_unique_order_item_count=(
            api_unique_order_item_count
        ),
        api_duplicate_order_item_count=(
            api_duplicate_order_item_count
        ),
        order_item_missing_parent_count=(
            order_item_missing_parent_count
        ),
        refund_record_count=(
            refund_record_count
        ),
        unique_refund_code_count=(
            unique_refund_code_count
        ),
        duplicate_refund_record_count=(
            duplicate_refund_record_count
        ),
        unique_refund_order_count=(
            unique_refund_order_count
        ),
        refund_missing_parent_count=(
            refund_missing_parent_count
        ),
        csv_row_count=(
            csv_row_count
        ),
        csv_unique_order_count=(
            csv_unique_order_count
        ),
        csv_unique_order_item_count=(
            csv_unique_order_item_count
        ),
        csv_order_intersection_count=(
            csv_order_intersection_count
        ),
        csv_order_only_count=(
            csv_order_only_count
        ),
        api_order_only_count=(
            api_order_only_count
        ),
        csv_item_intersection_count=(
            csv_item_intersection_count
        ),
        csv_item_only_count=(
            csv_item_only_count
        ),
        api_item_only_count=(
            api_item_only_count
        ),
        order_manifest_missing_count=(
            order_manifest_missing_count
        ),
        order_item_manifest_missing_count=(
            order_item_manifest_missing_count
        ),
        refund_manifest_missing_count=(
            refund_manifest_missing_count
        ),
        manifest_invalid_count=manifest_invalid_count,
        blocking_finding_count=(
            blocking_finding_count
        ),
        warning_count=(
            warning_count
        ),
        passed=passed,
    )