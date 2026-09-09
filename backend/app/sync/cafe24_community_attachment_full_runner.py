"""Cafe24 Community 첨부파일 Protected Read-Only 수집 Runner."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import re
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx

from backend.app.sync.cafe24_bootstrap import (
    _require_contained,
    _require_protected_root,
)
from backend.app.worker.privacy.snapshot_manifest import (
    load_verified_community_attachment_sources,
    select_canonical_sanitized_artifacts,
)


_ALLOWED_ATTACHMENT_HOSTS = {
    "forplus.co.kr",
}

_MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024

_MAX_REDIRECTS = 3

_SAFE_EXTENSION = re.compile(
    r"^\.[a-zA-Z0-9]{1,10}$"
)


@dataclass(frozen=True)
class AttachmentRef:
    board_no: int
    article_no: int
    source_url: str


@dataclass(frozen=True)
class Cafe24CommunityAttachmentFullResult:
    run_id: str
    unique_article_count: int
    articles_with_attachments: int
    discovered_attachment_ref_count: int
    unique_attachment_count: int
    downloaded_count: int
    skipped_existing_count: int
    failed_count: int
    source_missing_count: int
    request_count: int
    total_downloaded_bytes: int
    completed: bool
    progress_path: Path
    index_path: Path


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


def _source_url_hash(
    url: str,
) -> str:
    return hashlib.sha256(
        url.encode("utf-8")
    ).hexdigest()


def _validate_attachment_url(
    url: str,
) -> None:
    if not isinstance(
        url,
        str,
    ) or not url:
        raise ValueError(
            "attachment URL must be non-empty string"
        )

    parsed = urlsplit(
        url
    )

    if parsed.scheme.lower() != "https":
        raise ValueError(
            "attachment URL must use HTTPS"
        )

    host = (
        parsed.hostname or ""
    ).lower()

    if host not in _ALLOWED_ATTACHMENT_HOSTS:
        raise ValueError(
            "attachment host is not allowed"
        )

    if parsed.username is not None:
        raise ValueError(
            "attachment URL userinfo is forbidden"
        )

    if parsed.password is not None:
        raise ValueError(
            "attachment URL userinfo is forbidden"
        )


def _safe_extension(
    *,
    url: str,
    content_type: str | None,
) -> str:
    suffix = Path(
        urlsplit(url).path
    ).suffix.lower()

    if (
        suffix
        and _SAFE_EXTENSION.fullmatch(
            suffix
        )
    ):
        return suffix

    if content_type:
        clean_type = (
            content_type
            .split(";", 1)[0]
            .strip()
            .lower()
        )

        guessed = (
            mimetypes.guess_extension(
                clean_type
            )
        )

        if (
            guessed
            and _SAFE_EXTENSION.fullmatch(
                guessed
            )
        ):
            return guessed.lower()

    return ".bin"


def _load_attachment_refs(
    *, root: Path,
) -> tuple[list[AttachmentRef], int, int, int]:
    selections = [
        select_canonical_sanitized_artifacts(
            protected_root=root, resource=f"board_{board_no}_articles"
        )
        for board_no in (5, 6)
    ]
    if any(selection.invalid_artifact_count for selection in selections):
        raise ValueError("invalid canonical article batch")
    article_keys: set[tuple[int, int]] = set()
    canonical_batches: list[tuple[str, str]] = []
    for selection in selections:
        for file_path in selection.artifacts:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
            batch_id = payload.get("batch_id")
            resource = payload.get("resource")
            records = payload.get("records")
            if not isinstance(batch_id, str) or not isinstance(resource, str) or not isinstance(records, list):
                raise ValueError("invalid canonical article export")
            canonical_batches.append((batch_id, resource))
            for record in records:
                if not isinstance(record, dict):
                    continue
                key = (record.get("board_no"), record.get("article_no"))
                if type(key[0]) is int and key[0] in {5, 6} and type(key[1]) is int and key[1] > 0:
                    article_keys.add(key)
    attached_keys: set[tuple[int, int]] = set()
    refs_by_url: dict[str, AttachmentRef] = {}
    raw_ref_count = 0
    for batch_id, resource in canonical_batches:
        sources = load_verified_community_attachment_sources(
            protected_root=root, resource=resource, batch_id=batch_id
        )
        for board_no, article_no, url in sources:
            article_key = (board_no, article_no)
            if article_key not in article_keys:
                continue
            _validate_attachment_url(url)
            raw_ref_count += 1
            attached_keys.add(article_key)
            refs_by_url.setdefault(
                url,
                AttachmentRef(board_no=board_no, article_no=article_no, source_url=url),
            )
    return list(refs_by_url.values()), len(article_keys), len(attached_keys), raw_ref_count

def _load_index(
    *,
    index_path: Path,
) -> dict[str, Any]:
    if not index_path.exists():
        return {
            "schema_version": (
                "cafe24-community-"
                "attachment-index.v1"
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
            "attachment index is invalid"
        ) from None

    if not isinstance(
        payload,
        dict,
    ):
        raise ValueError(
            "attachment index must be object"
        )

    items = payload.get(
        "items"
    )

    if not isinstance(
        items,
        dict,
    ):
        raise ValueError(
            "attachment index items "
            "must be object"
        )

    return payload

def _download_one(
    *,
    client: httpx.Client,
    source_url: str,
    destination_dir: Path,
) -> tuple[
    str,
    Path,
    int,
    int,
]:
    current_url = source_url
    request_count = 0

    for redirect_count in range(
        _MAX_REDIRECTS + 1
    ):
        _validate_attachment_url(
            current_url
        )

        with client.stream(
            "GET",
            current_url,
            timeout=30.0,
            follow_redirects=False,
        ) as response:
            request_count += 1

            if response.status_code in {
                301,
                302,
                303,
                307,
                308,
            }:
                if (
                    redirect_count
                    >= _MAX_REDIRECTS
                ):
                    raise RuntimeError(
                        "attachment redirect "
                        "limit exceeded"
                    )

                location = (
                    response.headers.get(
                        "location"
                    )
                )

                if not location:
                    raise RuntimeError(
                        "attachment redirect "
                        "missing location"
                    )

                next_url = urljoin(
                    current_url,
                    location,
                )

                _validate_attachment_url(
                    next_url
                )

                current_url = next_url

                continue

            if response.status_code == 429:
                retry_after = (
                    response.headers.get(
                        "retry-after"
                    )
                )

                wait_seconds = 60.0

                if retry_after:
                    try:
                        wait_seconds = max(
                            float(
                                retry_after
                            ),
                            60.0,
                        )
                    except ValueError:
                        wait_seconds = 60.0

                raise AttachmentRateLimitError(
                    wait_seconds
                )

            if (
                500
                <= response.status_code
                <= 599
            ):
                raise AttachmentServerError(
                    response.status_code
                )

            if response.status_code == 404:
                raise AttachmentSourceMissingError(
                    "attachment source missing"
                )
            
            if response.status_code != 200:
                raise RuntimeError(
                    "attachment download "
                    "returned non-success status"
                )

            content_length = (
                response.headers.get(
                    "content-length"
                )
            )

            if content_length:
                try:
                    declared_size = int(
                        content_length
                    )
                except ValueError:
                    declared_size = -1

                if (
                    declared_size
                    > _MAX_FILE_SIZE_BYTES
                ):
                    raise RuntimeError(
                        "attachment exceeds "
                        "size limit"
                    )

            hasher = hashlib.sha256()
            total_size = 0

            temporary_path = (
                destination_dir
                / (
                    "download-"
                    + _source_url_hash(
                        source_url
                    )
                    + ".tmp"
                )
            )

            destination_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            try:
                with temporary_path.open(
                    "xb"
                ) as output:
                    for chunk in (
                        response.iter_bytes(
                            chunk_size=65536
                        )
                    ):
                        if not chunk:
                            continue

                        total_size += len(
                            chunk
                        )

                        if (
                            total_size
                            > _MAX_FILE_SIZE_BYTES
                        ):
                            raise RuntimeError(
                                "attachment exceeds "
                                "size limit"
                            )

                        hasher.update(
                            chunk
                        )

                        output.write(
                            chunk
                        )

                content_hash = (
                    hasher.hexdigest()
                )

                extension = _safe_extension(
                    url=current_url,
                    content_type=(
                        response.headers.get(
                            "content-type"
                        )
                    ),
                )

                final_path = (
                    destination_dir
                    / (
                        content_hash
                        + extension
                    )
                )

                if final_path.exists():
                    temporary_path.unlink(
                        missing_ok=True
                    )
                else:
                    temporary_path.replace(
                        final_path
                    )

                return (
                    content_hash,
                    final_path,
                    total_size,
                    request_count,
                )

            except Exception:
                temporary_path.unlink(
                    missing_ok=True
                )
                raise

    raise RuntimeError(
        "attachment redirect resolution failed"
    )


class AttachmentRateLimitError(
    RuntimeError
):
    def __init__(
        self,
        wait_seconds: float,
    ) -> None:
        super().__init__(
            "attachment rate limited"
        )

        self.wait_seconds = (
            wait_seconds
        )

class AttachmentSourceMissingError(
    RuntimeError
):
    """원본 첨부 URL은 남아 있지만 실제 파일이 사라진 경우."""

class AttachmentServerError(
    RuntimeError
):
    def __init__(
        self,
        status_code: int,
    ) -> None:
        super().__init__(
            "attachment server error"
        )

        self.status_code = (
            status_code
        )


def run_cafe24_community_attachment_full_runner(
    *,
    protected_root: Path,
    batch_delay_seconds: float = 0.3,
    cooldown_every_requests: int = 50,
    chunk_cooldown_seconds: float = 60.0,
    max_retries: int = 3,
) -> Cafe24CommunityAttachmentFullResult:
    """Community 고유 첨부 URL을 Protected 영역에 다운로드한다."""

    root = _require_protected_root(
        protected_root
    )

    (
        attachment_refs,
        unique_article_count,
        articles_with_attachments,
        raw_ref_count,
    ) = _load_attachment_refs(
        root=root
    )

    run_id = (
        "community-attachment-full-run-"
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

    attachment_root = (
        root
        / "cafe24"
        / "attachments"
    )

    files_dir = (
        attachment_root
        / "files"
    )

    index_path = (
        attachment_root
        / "index.json"
    )

    manifest_path = (
        root
        / "cafe24"
        / "manifests"
        / (
            f"{run_id}"
            ".manifest.json"
        )
    )

    for path in (
        progress_path,
        attachment_root,
        files_dir,
        index_path,
        manifest_path,
    ):
        _require_contained(
            root,
            path,
        )

    index_payload = (
        _load_index(
            index_path=index_path
        )
    )

    index_items = (
        index_payload["items"]
    )

    downloaded_count = 0
    skipped_existing_count = 0
    failed_count = 0
    source_missing_count = 0
    request_count = 0
    total_downloaded_bytes = 0

    next_cooldown_at = (
        cooldown_every_requests
    )

    manifest_items: list[
        dict[str, Any]
    ] = []

    def write_progress(
        status_name: str,
    ) -> None:
        _write_json_atomic(
            progress_path,
            {
                "run_id": run_id,
                "status": status_name,
                "unique_article_count": (
                    unique_article_count
                ),
                "articles_with_attachments": (
                    articles_with_attachments
                ),
                "discovered_attachment_ref_count": (
                    raw_ref_count
                ),
                "unique_attachment_count": (
                    len(
                        attachment_refs
                    )
                ),
                "downloaded_count": (
                    downloaded_count
                ),
                "skipped_existing_count": (
                    skipped_existing_count
                ),
                "failed_count": (
                    failed_count
                ),
                "source_missing_count": (
                    source_missing_count
                ),
                "request_count": (
                    request_count
                ),
                "total_downloaded_bytes": (
                    total_downloaded_bytes
                ),
                "completed": False,
            },
        )

    write_progress(
        "RUNNING"
    )

    with httpx.Client(
        headers={
            "User-Agent": (
                "ai-commerce-operations-agent/"
                "cafe24-protected-read"
            ),
        },
    ) as client:
        for attachment_ref in (
            attachment_refs
        ):
            url_hash = (
                _source_url_hash(
                    attachment_ref.source_url
                )
            )

            existing = (
                index_items.get(
                    url_hash
                )
            )

            if isinstance(
                existing,
                dict,
            ):
                stored_relative_path = (
                    existing.get(
                        "stored_path"
                    )
                )

                if isinstance(
                    stored_relative_path,
                    str,
                ):
                    stored_path = (
                        root
                        / stored_relative_path
                    )

                    _require_contained(
                        root,
                        stored_path,
                    )

                    if stored_path.exists():
                        skipped_existing_count += 1

                        manifest_items.append(
                            {
                                "source_url_sha256": (
                                    url_hash
                                ),
                                "status": (
                                    "SKIPPED_EXISTING"
                                ),
                            }
                        )

                        continue

            retry_count = 0

            while True:
                try:
                    (
                        content_hash,
                        stored_path,
                        byte_size,
                        attempts,
                    ) = _download_one(
                        client=client,
                        source_url=(
                            attachment_ref.source_url
                        ),
                        destination_dir=(
                            files_dir
                        ),
                    )

                    request_count += (
                        attempts
                    )

                    total_downloaded_bytes += (
                        byte_size
                    )

                    downloaded_count += 1

                    relative_path = (
                        stored_path.relative_to(
                            root
                        )
                    )

                    index_items[
                        url_hash
                    ] = {
                        "content_sha256": (
                            content_hash
                        ),
                        "stored_path": (
                            relative_path.as_posix()
                        ),
                        "byte_size": (
                            byte_size
                        ),
                        "first_seen_board_no": (
                            attachment_ref.board_no
                        ),
                        "first_seen_article_no": (
                            attachment_ref.article_no
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

                    manifest_items.append(
                        {
                            "source_url_sha256": (
                                url_hash
                            ),
                            "content_sha256": (
                                content_hash
                            ),
                            "byte_size": (
                                byte_size
                            ),
                            "status": (
                                "DOWNLOADED"
                            ),
                        }
                    )

                    break
                except AttachmentSourceMissingError:
                    source_missing_count += 1

                    # 실제 GET 1회는 발생했다.
                    request_count += 1

                    manifest_items.append(
                        {
                            "source_url_sha256": (
                                url_hash
                            ),
                            "status": (
                                "SOURCE_MISSING"
                            ),
                        }
                    )

                    break
                except (
                    AttachmentRateLimitError
                ) as exc:
                    retry_count += 1

                    if (
                        retry_count
                        > max_retries
                    ):
                        failed_count += 1

                        manifest_items.append(
                            {
                                "source_url_sha256": (
                                    url_hash
                                ),
                                "status": (
                                    "FAILED_RATE_LIMIT"
                                ),
                            }
                        )

                        break

                    time.sleep(
                        max(
                            exc.wait_seconds,
                            60.0,
                        )
                    )

                except (
                    AttachmentServerError
                ):
                    retry_count += 1

                    if (
                        retry_count
                        > max_retries
                    ):
                        failed_count += 1

                        manifest_items.append(
                            {
                                "source_url_sha256": (
                                    url_hash
                                ),
                                "status": (
                                    "FAILED_SERVER"
                                ),
                            }
                        )

                        break

                    time.sleep(
                        min(
                            2 ** retry_count,
                            10,
                        )
                    )

                except (
                    httpx.HTTPError,
                    RuntimeError,
                    ValueError,
                    OSError,
                ):
                    failed_count += 1

                    manifest_items.append(
                        {
                            "source_url_sha256": (
                                url_hash
                            ),
                            "status": (
                                "FAILED_NONRETRYABLE"
                            ),
                        }
                    )

                    break

            if (
                request_count
                >= next_cooldown_at
            ):
                write_progress(
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
                downloaded_count
                + skipped_existing_count
                + failed_count
            ) % 10 == 0:
                write_progress(
                    "RUNNING"
                )

    completed = (
        failed_count == 0
        and (
            downloaded_count
            + skipped_existing_count
            + source_missing_count
        )
        == len(
            attachment_refs
        )
    )

    _write_json_atomic(
        manifest_path,
        {
            "schema_version": (
                "cafe24-community-"
                "attachment-manifest.v1"
            ),
            "run_id": run_id,
            "provider": "CAFE24",
            "allowed_hosts": sorted(
                _ALLOWED_ATTACHMENT_HOSTS
            ),
            "https_only": True,
            "max_file_size_bytes": (
                _MAX_FILE_SIZE_BYTES
            ),
            "unique_article_count": (
                unique_article_count
            ),
            "articles_with_attachments": (
                articles_with_attachments
            ),
            "raw_attachment_ref_count": (
                raw_ref_count
            ),
            "unique_attachment_count": (
                len(
                    attachment_refs
                )
            ),
            "source_missing_count": (
                source_missing_count
            ),
            "items": manifest_items,
            "completed": completed,
            "write_call_count": 0,
            "created_at": (
                datetime.now(
                    UTC
                ).isoformat()
            ),
        },
    )

    result = (
        Cafe24CommunityAttachmentFullResult(
            run_id=run_id,
            unique_article_count=(
                unique_article_count
            ),
            articles_with_attachments=(
                articles_with_attachments
            ),
            discovered_attachment_ref_count=(
                raw_ref_count
            ),
            unique_attachment_count=(
                len(
                    attachment_refs
                )
            ),
            downloaded_count=(
                downloaded_count
            ),
            skipped_existing_count=(
                skipped_existing_count
            ),
            failed_count=(
                failed_count
            ),
            source_missing_count=(
                source_missing_count
            ),
            request_count=request_count,
            total_downloaded_bytes=(
                total_downloaded_bytes
            ),
            completed=completed,
            progress_path=(
                progress_path
            ),
            index_path=index_path,
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
                else "COMPLETED_WITH_FAILURES"
            ),
        },
    )

    return result