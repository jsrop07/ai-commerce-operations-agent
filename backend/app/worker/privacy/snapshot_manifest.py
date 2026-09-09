"""Cafe24 보호 Snapshot의 비민감 Manifest 생성."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from backend.app.worker.privacy.protected_storage import (
    ProtectedSnapshotResult,
    ProtectedRawResponse,
    _require_component,
    _require_contained,
    _require_protected_root,
)

@dataclass(frozen=True)
class SnapshotManifestEntry:
    provider: str
    resource: str
    batch_id: str
    raw_sha256: str
    raw_count: int
    sanitized_count: int

def build_manifest_entry(
    result: ProtectedSnapshotResult,
) -> SnapshotManifestEntry:
    """보호 Snapshot 결과에서 공개 가능한 메타데이터만 추출한다."""

    return SnapshotManifestEntry(
        provider=result.provider,
        resource=result.resource,
        batch_id=result.batch_id,
        raw_sha256=result.raw_sha256,
        raw_count=result.raw_count,
        sanitized_count=result.sanitized_count,
    )

def write_snapshot_manifest(
    *,
    output_path: Path,
    entries: list[SnapshotManifestEntry],
) -> None:
    """Snapshot Manifest를 JSON으로 저장한다."""

    for entry in entries:
        for component in (entry.provider, entry.resource, entry.batch_id):
            _require_component(component)
    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    payload = {
        "snapshot_count": len(entries),
        "raw_total": sum(
            item.raw_count
            for item in entries
        ),
        "sanitized_total": sum(
            item.sanitized_count
            for item in entries
        ),
        "resources": [
            asdict(item)
            for item in entries
        ],
    }

    with output_path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)


def build_raw_response_manifest_entry(
    result: ProtectedRawResponse,
    *,
    sanitized_count: int,
) -> SnapshotManifestEntry:
    """Use the raw HTTP body hash, never a hash of sanitized adapter records."""
    if sanitized_count != result.raw_count:
        raise ValueError("raw and sanitized response counts differ")

    return SnapshotManifestEntry(
        provider=result.provider,
        resource=result.resource,
        batch_id=result.batch_id,
        raw_sha256=result.raw_sha256,
        raw_count=result.raw_count,
        sanitized_count=sanitized_count,
    )

@dataclass(frozen=True)
class CanonicalSanitizedSelection:
    artifacts: tuple[Path, ...]
    missing_manifest_count: int
    invalid_artifact_count: int


def _raw_resource_count(body: bytes, resource: str) -> int:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise ValueError("invalid protected raw artifact") from None
    if not isinstance(payload, dict):
        raise ValueError("invalid protected raw artifact")
    response_key = {
        "products": "products",
        "variants": "variants",
        "variant_inventories": "inventory",
        "categories": "categories",
        "boards": "boards",
        "article_comments": "comments",
        "orders": "orders",
        "order_items": "items",
        "refunds": "refunds",
    }.get(resource)
    if resource.startswith("board_") and resource.endswith("_articles"):
        response_key = "articles"
    if response_key is None or response_key not in payload:
        raise ValueError("invalid protected raw resource")
    value = payload[response_key]
    if resource == "variant_inventories":
        return 1 if isinstance(value, dict) else 0
    if not isinstance(value, list):
        raise ValueError("invalid protected raw resource")
    return len(value)

def select_canonical_sanitized_artifacts(
    *,
    protected_root: Path,
    resource: str,
    filename_pattern: str = "*.sanitized.json",
) -> CanonicalSanitizedSelection:
    """Select only sanitized batches proven by a complete, matching manifest/raw set."""

    root = _require_protected_root(protected_root)
    _require_component(resource)
    sanitized_dir = root / "cafe24" / "sanitized" / resource
    manifest_dir = root / "cafe24" / "manifests"
    selected: list[Path] = []
    missing = 0
    invalid = 0

    for sanitized_path in sorted(sanitized_dir.glob(filename_pattern)):
        _require_contained(root, sanitized_path)
        try:
            sanitized = json.loads(sanitized_path.read_text(encoding="utf-8"))
            if not isinstance(sanitized, dict):
                raise ValueError
            batch_id = sanitized.get("batch_id")
            _require_component(batch_id)
            if (
                sanitized.get("provider") != "CAFE24"
                or sanitized.get("resource") != resource
                or sanitized_path.name != f"{batch_id}.sanitized.json"
                or not isinstance(sanitized.get("records"), list)
                or not all(isinstance(item, dict) for item in sanitized["records"])
            ):
                raise ValueError
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            invalid += 1
            continue

        manifest_path = manifest_dir / f"{batch_id}.manifest.json"
        _require_contained(root, manifest_path)
        if not manifest_path.exists():
            missing += 1
            continue

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            entries = manifest.get("resources") if isinstance(manifest, dict) else None
            if not isinstance(entries, list) or not entries:
                raise ValueError
            if manifest.get("completed") is False or manifest.get("status") in {
                "RUNNING", "FAILED", "PARTIAL", "COMPLETED_WITH_FAILURES"
            }:
                raise ValueError

            normalized: list[dict[str, object]] = []
            for entry in entries:
                if not isinstance(entry, dict):
                    raise ValueError
                entry_provider = entry.get("provider")
                entry_resource = entry.get("resource")
                entry_batch = entry.get("batch_id")
                raw_sha256 = entry.get("raw_sha256")
                raw_count = entry.get("raw_count")
                sanitized_count = entry.get("sanitized_count")
                if (
                    entry_provider != "CAFE24"
                    or not isinstance(entry_resource, str)
                    or not isinstance(entry_batch, str)
                    or not isinstance(raw_sha256, str)
                    or not re.fullmatch(r"[0-9a-f]{64}", raw_sha256)
                    or type(raw_count) is not int
                    or type(sanitized_count) is not int
                    or raw_count < 0
                    or sanitized_count < 0
                    or raw_count != sanitized_count
                ):
                    raise ValueError
                _require_component(entry_resource)
                _require_component(entry_batch)
                normalized.append(entry)

            if (
                manifest.get("snapshot_count") != len(normalized)
                or manifest.get("raw_total") != sum(int(item["raw_count"]) for item in normalized)
                or manifest.get("sanitized_total") != sum(int(item["sanitized_count"]) for item in normalized)
            ):
                raise ValueError

            matching = [
                entry for entry in normalized
                if entry["resource"] == resource and entry["batch_id"] == batch_id
            ]
            if not matching or sum(int(item["sanitized_count"]) for item in matching) != len(sanitized["records"]):
                raise ValueError

            raw_dir = root / "cafe24" / "raw" / batch_id / resource
            _require_contained(root, raw_dir)
            raw_files = sorted(raw_dir.glob("*.json"))
            if len(raw_files) != len(matching):
                raise ValueError
            expected_by_hash: dict[str, list[int]] = {}
            for item in matching:
                expected_by_hash.setdefault(str(item["raw_sha256"]), []).append(
                    int(item["raw_count"])
                )
            for path in raw_files:
                body = path.read_bytes()
                digest = hashlib.sha256(body).hexdigest()
                counts = expected_by_hash.get(digest)
                if not counts:
                    raise ValueError
                expected_count = counts.pop()
                if _raw_resource_count(body, resource) != expected_count:
                    raise ValueError
            if any(counts for counts in expected_by_hash.values()):
                raise ValueError
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            invalid += 1
            continue

        selected.append(sanitized_path)

    return CanonicalSanitizedSelection(
        artifacts=tuple(selected),
        missing_manifest_count=missing,
        invalid_artifact_count=invalid,
    )

def load_verified_community_attachment_sources(
    *, protected_root: Path, resource: str, batch_id: str,
) -> list[tuple[int, int, str]]:
    """Extract only attachment routing fields after canonical provenance verification."""

    root = _require_protected_root(protected_root)
    for component in (resource, batch_id):
        _require_component(component)
    if resource not in {"board_5_articles", "board_6_articles"}:
        raise ValueError("unsupported protected attachment resource")
    selection = select_canonical_sanitized_artifacts(
        protected_root=root, resource=resource,
        filename_pattern=f"{batch_id}.sanitized.json",
    )
    if selection.missing_manifest_count or selection.invalid_artifact_count or len(selection.artifacts) != 1:
        raise ValueError("canonical protected attachment source is unavailable")
    manifest_path = root / "cafe24" / "manifests" / f"{batch_id}.manifest.json"
    _require_contained(root, manifest_path)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise ValueError("invalid protected attachment provenance") from None
    if not isinstance(manifest, dict):
        raise ValueError("invalid protected attachment provenance")
    entries = [entry for entry in manifest.get("resources", [])
               if isinstance(entry, dict) and entry.get("provider") == "CAFE24"
               and entry.get("resource") == resource and entry.get("batch_id") == batch_id]
    if not entries:
        raise ValueError("invalid protected attachment provenance")
    raw_dir = root / "cafe24" / "raw" / batch_id / resource
    _require_contained(root, raw_dir)
    raw_paths = sorted(raw_dir.glob("*.json"))
    if len(raw_paths) != len(entries):
        raise ValueError("invalid protected attachment provenance")
    expected_hashes = Counter(str(entry["raw_sha256"]) for entry in entries)
    expected_count = sum(int(entry["raw_count"]) for entry in entries)
    expected_board_no = int(resource.split("_")[1])
    sources: list[tuple[int, int, str]] = []
    observed_count = 0
    for raw_path in raw_paths:
        _require_contained(root, raw_path)
        try:
            body = raw_path.read_bytes()
        except OSError:
            raise ValueError("protected attachment source read failed") from None
        digest = hashlib.sha256(body).hexdigest()
        if expected_hashes[digest] < 1:
            raise ValueError("protected attachment source hash mismatch")
        expected_hashes[digest] -= 1
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            raise ValueError("invalid protected attachment source") from None
        articles = payload.get("articles") if isinstance(payload, dict) else None
        if not isinstance(articles, list):
            raise ValueError("invalid protected attachment source")
        observed_count += len(articles)
        for record in articles:
            if not isinstance(record, dict):
                continue
            board_no, article_no = record.get("board_no"), record.get("article_no")
            attachments = record.get("attach_file_urls")
            if (
                board_no != expected_board_no
                or type(article_no) is not int
                or article_no < 1
            ):
                raise ValueError("protected attachment source identity mismatch")
            if not isinstance(attachments, list):
                continue
            for item in attachments:
                url = item.get("url") if isinstance(item, dict) else None
                if isinstance(url, str) and url:
                    sources.append((board_no, article_no, url))
    if any(expected_hashes.values()) or observed_count != expected_count:
        raise ValueError("protected attachment source count mismatch")
    return sources