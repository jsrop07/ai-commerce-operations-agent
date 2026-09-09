import json
from pathlib import Path

import pytest

from backend.app.worker.privacy.protected_storage import (
    write_protected_raw_response,
    write_protected_snapshot,
    write_sanitized_export,
)
from backend.app.worker.privacy.staging import sanitize_community_record
from backend.app.worker.privacy.snapshot_manifest import (
    build_manifest_entry,
    build_raw_response_manifest_entry,
    load_verified_community_attachment_sources,
    select_canonical_sanitized_artifacts,
    write_snapshot_manifest,
)


def test_snapshot_manifest_contains_only_safe_metadata(
    tmp_path: Path,
) -> None:
    result = write_protected_snapshot(
        protected_root=tmp_path / "protected",
        provider="CAFE24",
        resource="orders",
        batch_id="synthetic-orders-001",
        records=[
            {
                "order_id": "ORDER-001",
                "receiver_name": "synthetic-name",
                "phone": "".join(('', '010', '-1234-5678', '')),
            },
            {
                "order_id": "ORDER-002",
                "receiver_name": "synthetic-name-2",
                "phone": "".join(('', '010', '-9999-9999', '')),
            },
        ],
    )

    entry = build_manifest_entry(result)

    output_path = (
        tmp_path
        / "artifacts"
        / "provider_read_manifest.json"
    )

    write_snapshot_manifest(
        output_path=output_path,
        entries=[entry],
    )

    payload = json.loads(
        output_path.read_text(
            encoding="utf-8"
        )
    )

    assert payload["snapshot_count"] == 1
    assert payload["raw_total"] == 2
    assert payload["sanitized_total"] == 2

    resource = payload["resources"][0]

    assert resource["provider"] == "CAFE24"
    assert resource["resource"] == "orders"
    assert resource["batch_id"] == "synthetic-orders-001"
    assert len(resource["raw_sha256"]) == 64

    manifest_text = output_path.read_text(
        encoding="utf-8"
    )

    assert "synthetic-name" not in manifest_text
    assert "".join(('', '010', '-1234-5678', '')) not in manifest_text
    assert "ORDER-001" not in manifest_text


def test_snapshot_manifest_aggregates_multiple_resources(
    tmp_path: Path,
) -> None:
    products = write_protected_snapshot(
        protected_root=tmp_path / "protected",
        provider="CAFE24",
        resource="products",
        batch_id="synthetic-products-001",
        records=[
            {"product_no": 101},
            {"product_no": 102},
        ],
    )

    orders = write_protected_snapshot(
        protected_root=tmp_path / "protected",
        provider="CAFE24",
        resource="orders",
        batch_id="synthetic-orders-001",
        records=[
            {"order_id": "ORDER-001"},
        ],
    )

    output_path = tmp_path / "manifest.json"

    write_snapshot_manifest(
        output_path=output_path,
        entries=[
            build_manifest_entry(products),
            build_manifest_entry(orders),
        ],
    )

    payload = json.loads(
        output_path.read_text(
            encoding="utf-8"
        )
    )

    assert payload["snapshot_count"] == 2
    assert payload["raw_total"] == 3
    assert payload["sanitized_total"] == 3

    resources = {
        item["resource"]
        for item in payload["resources"]
    }

    assert resources == {
        "products",
        "orders",
    }

def _write_canonical_order_batch(root: Path, batch_id: str = "order-full-synthetic") -> None:
    raw = write_protected_raw_response(
        protected_root=root,
        provider="CAFE24",
        resource="orders",
        batch_id=batch_id,
        page_id="page-000001",
        payload={"orders": [{"order_id": "20260101-000001"}]},
        raw_count=1,
    )
    write_sanitized_export(
        protected_root=root,
        provider="CAFE24",
        resource="orders",
        batch_id=batch_id,
        records=[{"order_id": "20260101-000001"}],
    )
    write_snapshot_manifest(
        output_path=root / "cafe24" / "manifests" / f"{batch_id}.manifest.json",
        entries=[build_raw_response_manifest_entry(raw, sanitized_count=1)],
    )


def test_canonical_selector_includes_success_and_excludes_orphan(tmp_path: Path) -> None:
    _write_canonical_order_batch(tmp_path)
    write_sanitized_export(
        protected_root=tmp_path,
        provider="CAFE24",
        resource="orders",
        batch_id="order-full-orphan",
        records=[{"order_id": "20260101-999999"}],
    )

    selection = select_canonical_sanitized_artifacts(
        protected_root=tmp_path,
        resource="orders",
        filename_pattern="order-full-*.sanitized.json",
    )
    assert [path.stem for path in selection.artifacts] == [
        "order-full-synthetic.sanitized"
    ]
    assert selection.missing_manifest_count == 1
    assert selection.invalid_artifact_count == 0


def test_canonical_selector_rejects_count_mismatch(tmp_path: Path) -> None:
    _write_canonical_order_batch(tmp_path)
    sanitized_path = (
        tmp_path / "cafe24" / "sanitized" / "orders"
        / "order-full-synthetic.sanitized.json"
    )
    payload = json.loads(sanitized_path.read_text(encoding="utf-8"))
    payload["records"].append({"order_id": "20260101-000002"})
    sanitized_path.write_text(json.dumps(payload), encoding="utf-8")

    selection = select_canonical_sanitized_artifacts(
        protected_root=tmp_path, resource="orders"
    )
    assert selection.artifacts == ()
    assert selection.invalid_artifact_count == 1


def test_canonical_selector_rejects_raw_hash_mismatch(tmp_path: Path) -> None:
    _write_canonical_order_batch(tmp_path)
    manifest_path = (
        tmp_path / "cafe24" / "manifests"
        / "order-full-synthetic.manifest.json"
    )
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["resources"][0]["raw_sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    selection = select_canonical_sanitized_artifacts(
        protected_root=tmp_path, resource="orders"
    )
    assert selection.artifacts == ()
    assert selection.invalid_artifact_count == 1

def _write_canonical_article_batch(
    root: Path,
    *,
    batch_id: str = "community-article-6-synthetic",
    include_manifest: bool = True,
) -> str:
    source_url = "https://forplus.co.kr/synthetic/file.pdf?ref=synthetic"
    resource = "board_6_articles"
    raw = write_protected_raw_response(
        protected_root=root,
        provider="CAFE24",
        resource=resource,
        batch_id=batch_id,
        page_id="page-000001",
        payload={
            "articles": [{
                "board_no": 6,
                "article_no": 1001,
                "attach_file_urls": [{"url": source_url}],
            }]
        },
        raw_count=1,
    )
    write_sanitized_export(
        protected_root=root,
        provider="CAFE24",
        resource=resource,
        batch_id=batch_id,
        records=[sanitize_community_record({
            "board_no": 6,
            "article_no": 1001,
            "attach_file_urls": [{"url": source_url}],
        })],
    )
    if include_manifest:
        write_snapshot_manifest(
            output_path=root / "cafe24" / "manifests" / f"{batch_id}.manifest.json",
            entries=[build_raw_response_manifest_entry(raw, sanitized_count=1)],
        )
    return source_url


def test_verified_attachment_reader_returns_only_minimal_fields(caplog, tmp_path: Path) -> None:
    source_url = _write_canonical_article_batch(tmp_path)
    sources = load_verified_community_attachment_sources(
        protected_root=tmp_path,
        resource="board_6_articles",
        batch_id="community-article-6-synthetic",
    )
    assert sources == [(6, 1001, source_url)]
    sanitized_text = next((tmp_path / "cafe24" / "sanitized").rglob("*.json")).read_text(encoding="utf-8")
    manifest_text = next((tmp_path / "cafe24" / "manifests").glob("*.json")).read_text(encoding="utf-8")
    assert source_url not in sanitized_text
    assert source_url not in manifest_text
    assert source_url not in caplog.text


def test_verified_attachment_reader_blocks_hash_mismatch(tmp_path: Path) -> None:
    _write_canonical_article_batch(tmp_path)
    raw_path = next((tmp_path / "cafe24" / "raw").rglob("*.json"))
    raw_path.write_bytes(raw_path.read_bytes() + b" ")
    with pytest.raises(ValueError):
        load_verified_community_attachment_sources(
            protected_root=tmp_path,
            resource="board_6_articles",
            batch_id="community-article-6-synthetic",
        )


def test_verified_attachment_reader_blocks_missing_manifest(tmp_path: Path) -> None:
    _write_canonical_article_batch(tmp_path, include_manifest=False)
    with pytest.raises(ValueError):
        load_verified_community_attachment_sources(
            protected_root=tmp_path,
            resource="board_6_articles",
            batch_id="community-article-6-synthetic",
        )


@pytest.mark.parametrize(
    "resource,batch_id",
    [
        ("board_5_articles", "community-article-6-synthetic"),
        ("board_6_articles", "community-article-6-wrong"),
        ("orders", "community-article-6-synthetic"),
    ],
)
def test_verified_attachment_reader_blocks_wrong_provenance(
    tmp_path: Path, resource: str, batch_id: str,
) -> None:
    _write_canonical_article_batch(tmp_path)
    with pytest.raises(ValueError):
        load_verified_community_attachment_sources(
            protected_root=tmp_path, resource=resource, batch_id=batch_id
        )


def test_verified_attachment_reader_blocks_repository_root() -> None:
    import backend.app.worker.privacy.protected_storage as storage

    repo = Path(storage.__file__).resolve().parents[4]
    with pytest.raises(ValueError):
        load_verified_community_attachment_sources(
            protected_root=repo,
            resource="board_6_articles",
            batch_id="community-article-6-synthetic",
        )

def test_attachment_loader_reconstructs_only_from_verified_source(tmp_path: Path) -> None:
    from backend.app.sync.cafe24_community_attachment_full_runner import (
        _load_attachment_refs,
    )

    source_url = _write_canonical_article_batch(tmp_path)
    refs, article_count, attached_count, raw_ref_count = _load_attachment_refs(
        root=tmp_path
    )
    assert [(item.board_no, item.article_no, item.source_url) for item in refs] == [
        (6, 1001, source_url)
    ]
    assert (article_count, attached_count, raw_ref_count) == (1, 1, 1)