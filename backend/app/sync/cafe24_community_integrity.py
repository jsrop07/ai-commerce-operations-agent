"""Cafe24 Community Pre-Day8 수집 결과 무결성 검증."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from backend.app.sync.cafe24_bootstrap import (
    _require_contained,
    _require_protected_root,
)
from backend.app.worker.privacy.snapshot_manifest import (
    select_canonical_sanitized_artifacts,
)


_COMMENT_BATCH_PATTERN = re.compile(
    r"^community-comment-(5|6)-(\d+)-(\d{6})-"
)


@dataclass(frozen=True)
class Cafe24CommunityIntegrityResult:
    article_record_count: int
    unique_article_count: int
    duplicate_article_record_count: int
    conflicting_duplicate_count: int

    reply_article_count: int
    parent_link_count: int
    missing_parent_count: int
    invalid_self_parent_count: int

    comment_record_count: int
    comment_batch_count: int
    comment_parent_link_count: int
    comment_missing_parent_count: int

    attachment_ref_count: int
    unique_attachment_ref_count: int
    attachment_index_count: int
    attachment_file_count: int
    attachment_missing_index_count: int
    attachment_missing_file_count: int
    attachment_hash_mismatch_count: int
    attachment_size_mismatch_count: int
    attachment_source_missing_count: int

    article_manifest_missing_count: int
    comment_manifest_missing_count: int
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


def _record_hash(
    record: dict[str, Any],
) -> str:
    body = json.dumps(
        record,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        body.encode("utf-8")
    ).hexdigest()


def _file_sha256(
    path: Path,
) -> str:
    hasher = hashlib.sha256()

    with path.open("rb") as stream:
        while True:
            chunk = stream.read(
                1024 * 1024
            )

            if not chunk:
                break

            hasher.update(
                chunk
            )

    return hasher.hexdigest()


def _attachment_url_hash(
    url: str,
) -> str:
    return hashlib.sha256(
        url.encode("utf-8")
    ).hexdigest()


def run_cafe24_community_integrity(
    *,
    protected_root: Path,
) -> Cafe24CommunityIntegrityResult:
    root = _require_protected_root(
        protected_root
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

    attachment_root = (
        cafe24_root
        / "attachments"
    )

    for path in (
        cafe24_root,
        sanitized_root,
        manifest_root,
        attachment_root,
    ):
        _require_contained(
            root,
            path,
        )

    article_selections = [
        select_canonical_sanitized_artifacts(
            protected_root=root,
            resource=f"board_{board_no}_articles",
        )
        for board_no in (5, 6)
    ]
    article_files = tuple(
        path
        for selection in article_selections
        for path in selection.artifacts
    )
    comment_selection = select_canonical_sanitized_artifacts(
        protected_root=root,
        resource="article_comments",
    )
    # -------------------------------------------------
    # 1. Article
    # -------------------------------------------------

    article_records: list[
        dict[str, Any]
    ] = []

    article_batches: set[str] = set()

    for article_file in article_files:

        _require_contained(
            root,
            article_file,
        )

        payload = _load_json(
            article_file
        )

        if not isinstance(
            payload,
            dict,
        ):
            raise ValueError(
                "article sanitized export "
                "must be object"
            )

        batch_id = payload.get(
            "batch_id"
        )

        if isinstance(
            batch_id,
            str,
        ):
            article_batches.add(
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
                "article records must be list"
            )

        for record in records:
            if isinstance(
                record,
                dict,
            ):
                article_records.append(
                    record
                )

    articles_by_key: dict[
        tuple[int, int],
        list[dict[str, Any]],
    ] = {}

    for record in article_records:
        board_no = record.get(
            "board_no"
        )

        article_no = record.get(
            "article_no"
        )

        if (
            type(board_no) is not int
            or board_no not in {5, 6}
            or type(article_no) is not int
            or article_no < 1
        ):
            continue

        articles_by_key.setdefault(
            (
                board_no,
                article_no,
            ),
            [],
        ).append(
            record
        )

    unique_article_count = len(
        articles_by_key
    )

    duplicate_article_record_count = sum(
        max(
            len(records) - 1,
            0,
        )
        for records
        in articles_by_key.values()
    )

    conflicting_duplicate_count = 0

    for records in (
        articles_by_key.values()
    ):
        if len(records) < 2:
            continue

        hashes = {
            _record_hash(record)
            for record in records
        }

        if len(hashes) > 1:
            conflicting_duplicate_count += 1

    article_keys = set(
        articles_by_key
    )

    # 가장 최근에 읽힌 동일 key 레코드를
    # integrity 관계 판정용으로만 사용한다.
    representative_articles = {
        key: records[-1]
        for key, records
        in articles_by_key.items()
    }

    reply_article_count = 0
    parent_link_count = 0
    missing_parent_count = 0
    invalid_self_parent_count = 0

    for (
        board_no,
        article_no,
    ), record in (
        representative_articles.items()
    ):
        parent_article_no = (
            record.get(
                "parent_article_no"
            )
        )

        reply_value = record.get(
            "reply"
        )

        reply_depth = record.get(
            "reply_depth"
        )

        is_reply = (
            reply_value in {
                "T",
                "Y",
                True,
                1,
                "1",
            }
            or (
                type(reply_depth) is int
                and reply_depth > 0
            )
            or (
                type(parent_article_no)
                is int
                and parent_article_no > 0
            )
        )

        if is_reply:
            reply_article_count += 1

        if (
            type(parent_article_no) is int
            and parent_article_no > 0
        ):
            parent_link_count += 1

            if (
                parent_article_no
                == article_no
            ):
                invalid_self_parent_count += 1

            elif (
                board_no,
                parent_article_no,
            ) not in article_keys:
                missing_parent_count += 1

    # -------------------------------------------------
    # 2. Comments
    # -------------------------------------------------

    comment_record_count = 0
    comment_batch_count = 0
    comment_parent_link_count = 0
    comment_missing_parent_count = 0

    comment_batches: set[str] = set()

    for comment_file in comment_selection.artifacts:

        _require_contained(
            root,
            comment_file,
        )

        payload = _load_json(
            comment_file
        )

        if not isinstance(
            payload,
            dict,
        ):
            raise ValueError(
                "comment sanitized export "
                "must be object"
            )

        batch_id = payload.get(
            "batch_id"
        )

        if not isinstance(
            batch_id,
            str,
        ):
            continue

        comment_batches.add(
            batch_id
        )

        match = (
            _COMMENT_BATCH_PATTERN.match(
                batch_id
            )
        )

        if match is None:
            continue

        board_no = int(
            match.group(1)
        )

        article_no = int(
            match.group(2)
        )

        comment_batch_count += 1
        comment_parent_link_count += 1

        if (
            board_no,
            article_no,
        ) not in article_keys:
            comment_missing_parent_count += 1

        records = payload.get(
            "records"
        )

        if not isinstance(
            records,
            list,
        ):
            raise ValueError(
                "comment records must be list"
            )

        comment_record_count += sum(
            1
            for record in records
            if isinstance(
                record,
                dict,
            )
        )

    # -------------------------------------------------
    # 3. Attachments
    # -------------------------------------------------

    attachment_ref_count = 0

    unique_attachment_hashes: set[
        str
    ] = set()

    for record in representative_articles.values():
        source_hashes = record.get("attachment_source_sha256")
        if isinstance(source_hashes, list):
            valid_hashes = [
                value for value in source_hashes
                if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
            ]
            attachment_ref_count += len(valid_hashes)
            unique_attachment_hashes.update(valid_hashes)
            continue

        # Backward-compatible read of historical sanitized artifacts. New exports
        # never retain URLs; the value is hashed in memory and never emitted.
        attachments = record.get("attach_file_urls")
        if not isinstance(attachments, list):
            continue
        for attachment in attachments:
            url = attachment.get("url") if isinstance(attachment, dict) else None
            if isinstance(url, str) and url:
                attachment_ref_count += 1
                unique_attachment_hashes.add(_attachment_url_hash(url))
    index_path = (
        attachment_root
        / "index.json"
    )

    attachment_index_count = 0
    attachment_file_count = 0
    attachment_missing_index_count = 0
    attachment_missing_file_count = 0
    attachment_hash_mismatch_count = 0
    attachment_size_mismatch_count = 0

    index_items: dict[
        str,
        Any,
    ] = {}

    if index_path.exists():
        index_payload = _load_json(
            index_path
        )

        if (
            isinstance(
                index_payload,
                dict,
            )
            and isinstance(
                index_payload.get(
                    "items"
                ),
                dict,
            )
        ):
            index_items = (
                index_payload[
                    "items"
                ]
            )

    attachment_index_count = len(
        index_items
    )

    for source_hash in (
        unique_attachment_hashes
    ):
        item = index_items.get(
            source_hash
        )

        if not isinstance(
            item,
            dict,
        ):
            attachment_missing_index_count += 1
            continue

        stored_path_raw = (
            item.get(
                "stored_path"
            )
        )

        expected_hash = (
            item.get(
                "content_sha256"
            )
        )

        expected_size = (
            item.get(
                "byte_size"
            )
        )

        if not isinstance(
            stored_path_raw,
            str,
        ):
            attachment_missing_file_count += 1
            continue

        stored_path = (
            root
            / stored_path_raw
        )

        _require_contained(
            root,
            stored_path,
        )

        if not stored_path.exists():
            attachment_missing_file_count += 1
            continue

        attachment_file_count += 1

        actual_hash = (
            _file_sha256(
                stored_path
            )
        )

        if (
            isinstance(
                expected_hash,
                str,
            )
            and actual_hash
            != expected_hash
        ):
            attachment_hash_mismatch_count += 1

        actual_size = (
            stored_path.stat().st_size
        )

        if (
            type(expected_size) is int
            and actual_size
            != expected_size
        ):
            attachment_size_mismatch_count += 1

    # SOURCE_MISSING는 attachment manifest에서 집계한다.
    source_missing_hashes: set[
        str
    ] = set()

    for manifest_file in sorted(
        manifest_root.glob(
            "community-attachment-full-run-"
            "*.manifest.json"
        )
    ):
        payload = _load_json(
            manifest_file
        )

        if (
            not isinstance(payload, dict)
            or payload.get("provider") != "CAFE24"
            or payload.get("completed") is not True
            or payload.get("run_id") not in manifest_file.name
        ):
            continue

        items = payload.get(
            "items"
        )

        if not isinstance(
            items,
            list,
        ):
            continue

        for item in items:
            if not isinstance(
                item,
                dict,
            ):
                continue

            if (
                item.get("status")
                != "SOURCE_MISSING"
            ):
                continue

            source_hash = (
                item.get(
                    "source_url_sha256"
                )
            )

            if isinstance(
                source_hash,
                str,
            ):
                source_missing_hashes.add(
                    source_hash
                )

    attachment_source_missing_count = (
        len(
            source_missing_hashes
            & unique_attachment_hashes
        )
    )

    # SOURCE_MISSING는 index가 없는 것이 정상이다.
    attachment_missing_index_count = max(
        attachment_missing_index_count
        - attachment_source_missing_count,
        0,
    )

    # -------------------------------------------------
    # 4. Manifest 존재성
    # -------------------------------------------------

    article_manifest_missing_count = sum(
        selection.missing_manifest_count for selection in article_selections
    )
    comment_manifest_missing_count = comment_selection.missing_manifest_count
    manifest_invalid_count = sum(
        selection.invalid_artifact_count for selection in article_selections
    ) + comment_selection.invalid_artifact_count
    # -------------------------------------------------
    # 5. 최종 판정
    # -------------------------------------------------

    blocking_finding_count = sum(
        (
            missing_parent_count,
            invalid_self_parent_count,
            comment_missing_parent_count,
            attachment_missing_index_count,
            attachment_missing_file_count,
            attachment_hash_mismatch_count,
            attachment_size_mismatch_count,
            article_manifest_missing_count,
            comment_manifest_missing_count,
            manifest_invalid_count,
        )
    )

    # conflicting duplicate는 즉시 데이터 유실은 아니지만
    # canonical 선택 전에 반드시 확인해야 해서 warning 처리한다.
    warning_count = (
        conflicting_duplicate_count
        + attachment_source_missing_count
    )

    passed = (
        blocking_finding_count == 0
    )

    return Cafe24CommunityIntegrityResult(
        article_record_count=len(
            article_records
        ),
        unique_article_count=(
            unique_article_count
        ),
        duplicate_article_record_count=(
            duplicate_article_record_count
        ),
        conflicting_duplicate_count=(
            conflicting_duplicate_count
        ),
        reply_article_count=(
            reply_article_count
        ),
        parent_link_count=(
            parent_link_count
        ),
        missing_parent_count=(
            missing_parent_count
        ),
        invalid_self_parent_count=(
            invalid_self_parent_count
        ),
        comment_record_count=(
            comment_record_count
        ),
        comment_batch_count=(
            comment_batch_count
        ),
        comment_parent_link_count=(
            comment_parent_link_count
        ),
        comment_missing_parent_count=(
            comment_missing_parent_count
        ),
        attachment_ref_count=(
            attachment_ref_count
        ),
        unique_attachment_ref_count=len(
            unique_attachment_hashes
        ),
        attachment_index_count=(
            attachment_index_count
        ),
        attachment_file_count=(
            attachment_file_count
        ),
        attachment_missing_index_count=(
            attachment_missing_index_count
        ),
        attachment_missing_file_count=(
            attachment_missing_file_count
        ),
        attachment_hash_mismatch_count=(
            attachment_hash_mismatch_count
        ),
        attachment_size_mismatch_count=(
            attachment_size_mismatch_count
        ),
        attachment_source_missing_count=(
            attachment_source_missing_count
        ),
        article_manifest_missing_count=(
            article_manifest_missing_count
        ),
        comment_manifest_missing_count=(
            comment_manifest_missing_count
        ),
        manifest_invalid_count=manifest_invalid_count,
        blocking_finding_count=(
            blocking_finding_count
        ),
        warning_count=warning_count,
        passed=passed,
    )