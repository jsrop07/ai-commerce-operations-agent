"""Day 8 Community legacy sanitized artifact repair."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.app.worker.privacy.staging import (
    sanitize_community_record,
)


_REPAIR_RESOURCES = {
    "board_5_articles": "articles",
    "board_6_articles": "articles",
    "article_comments": "comments",
}


@dataclass(frozen=True)
class Day08CommunityRepairResult:
    artifact_count: int
    record_count: int
    article_record_count: int
    comment_record_count: int
    title_removed_count: int
    content_removed_count: int
    subject_sha256_count: int
    content_sha256_count: int


def _load_json(
    path: Path,
) -> Any:
    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def _resolve_data_root(
    protected_root: Path,
) -> Path:
    direct = protected_root.resolve()

    nested = (
        direct
        / "cafe24"
    )

    if (
        nested
        / "raw"
    ).exists():
        return nested

    if (
        direct
        / "raw"
    ).exists():
        return direct

    raise FileNotFoundError(
        "Cafe24 protected data root "
        "could not be resolved"
    )


def _load_raw_records(
    *,
    data_root: Path,
    batch_id: str,
    resource: str,
    payload_key: str,
) -> list[dict[str, Any]]:
    raw_dir = (
        data_root
        / "raw"
        / batch_id
        / resource
    )

    page_files = sorted(
        raw_dir.glob(
            "page-*.json"
        )
    )

    if not page_files:
        raise FileNotFoundError(
            f"raw pages missing: "
            f"{batch_id}/{resource}"
        )

    records: list[
        dict[str, Any]
    ] = []

    for page in page_files:
        payload = _load_json(
            page
        )

        if not isinstance(
            payload,
            dict,
        ):
            raise ValueError(
                f"raw payload must be object: "
                f"{page}"
            )

        rows = payload.get(
            payload_key
        )

        if not isinstance(
            rows,
            list,
        ):
            raise ValueError(
                f"{payload_key} must be list: "
                f"{page}"
            )

        for row in rows:
            if not isinstance(
                row,
                dict,
            ):
                raise ValueError(
                    "community record "
                    "must be object"
                )

            records.append(
                row
            )

    return records


def _sanitize_record(
    record: dict[str, Any],
) -> dict[str, Any]:
    sanitized = (
        sanitize_community_record(
            record
        )
    )

    # Community sanitized artifact에는
    # 원본 주문번호를 절대 남기지 않는다.
    sanitized.pop(
        "order_id",
        None,
    )

    return sanitized


def repair_day08_community_sanitized(
    *,
    protected_root: Path,
) -> Day08CommunityRepairResult:
    data_root = _resolve_data_root(
        protected_root
    )

    manifest_root = (
        data_root
        / "manifests"
    )

    repaired_artifacts = 0
    repaired_records = 0

    article_records = 0
    comment_records = 0

    title_removed = 0
    content_removed = 0

    subject_hashes = 0
    content_hashes = 0

    for manifest_path in sorted(
        manifest_root.glob(
            "community-*.manifest.json"
        )
    ):
        manifest = _load_json(
            manifest_path
        )

        if not isinstance(
            manifest,
            dict,
        ):
            continue

        resources = manifest.get(
            "resources"
        )

        if not isinstance(
            resources,
            list,
        ):
            continue

        for entry in resources:
            if not isinstance(
                entry,
                dict,
            ):
                continue

            resource = entry.get(
                "resource"
            )

            if resource not in (
                _REPAIR_RESOURCES
            ):
                continue

            batch_id = entry.get(
                "batch_id"
            )

            if not isinstance(
                batch_id,
                str,
            ) or not batch_id:
                raise ValueError(
                    "community manifest "
                    "batch_id missing"
                )

            payload_key = (
                _REPAIR_RESOURCES[
                    resource
                ]
            )

            raw_records = (
                _load_raw_records(
                    data_root=data_root,
                    batch_id=batch_id,
                    resource=resource,
                    payload_key=payload_key,
                )
            )

            expected_raw_count = (
                entry.get(
                    "raw_count"
                )
            )

            if (
                type(expected_raw_count)
                is int
                and len(raw_records)
                != expected_raw_count
            ):
                raise ValueError(
                    f"raw count mismatch: "
                    f"{batch_id}"
                )

            sanitized_records = [
                _sanitize_record(
                    record
                )
                for record in raw_records
            ]

            target = (
                data_root
                / "sanitized"
                / resource
                / (
                    f"{batch_id}"
                    ".sanitized.json"
                )
            )

            target.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            payload = {
                "provider": (
                    entry.get(
                        "provider",
                        "CAFE24",
                    )
                ),
                "resource": resource,
                "batch_id": batch_id,
                "records": sanitized_records,
            }

            temporary = (
                target.with_suffix(
                    target.suffix
                    + ".tmp"
                )
            )

            temporary.write_text(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

            temporary.replace(
                target
            )

            repaired_artifacts += 1
            repaired_records += len(
                sanitized_records
            )

            if resource in {
                "board_5_articles",
                "board_6_articles",
            }:
                article_records += len(
                    sanitized_records
                )
            else:
                comment_records += len(
                    sanitized_records
                )

            for original, sanitized in zip(
                raw_records,
                sanitized_records,
                strict=True,
            ):
                if (
                    "title" in original
                    and "title"
                    not in sanitized
                ):
                    title_removed += 1

                if (
                    "content" in original
                    and "content"
                    not in sanitized
                ):
                    content_removed += 1

                if (
                    "subject_sha256"
                    in sanitized
                ):
                    subject_hashes += 1

                if (
                    "content_sha256"
                    in sanitized
                ):
                    content_hashes += 1

    return Day08CommunityRepairResult(
        artifact_count=(
            repaired_artifacts
        ),
        record_count=(
            repaired_records
        ),
        article_record_count=(
            article_records
        ),
        comment_record_count=(
            comment_records
        ),
        title_removed_count=(
            title_removed
        ),
        content_removed_count=(
            content_removed
        ),
        subject_sha256_count=(
            subject_hashes
        ),
        content_sha256_count=(
            content_hashes
        ),
    )