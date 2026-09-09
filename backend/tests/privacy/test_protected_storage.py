from pathlib import Path

import pytest

from backend.app.worker.privacy.protected_storage import (
    write_protected_snapshot,
    write_protected_raw_response,

)


def test_protected_snapshot_writes_raw_and_sanitized(
    tmp_path: Path,
) -> None:
    result = write_protected_snapshot(
        protected_root=tmp_path,
        provider="CAFE24",
        resource="orders",
        batch_id="synthetic-batch-001",
        records=[
            {
                "order_id": "ORDER-001",
                "product_no": 101,
                "receiver_name": "synthetic-name",
                "phone": "".join(('', '010', '-0000-0000', '')),
                "address": "synthetic-address",
            }
        ],
    )

    assert result.raw_count == 1
    assert result.sanitized_count == 1

    assert result.raw_path.exists()
    assert result.sanitized_path.exists()

    raw_text = result.raw_path.read_text(
        encoding="utf-8"
    )
    sanitized_text = result.sanitized_path.read_text(
        encoding="utf-8"
    )

    # Raw 보호영역에는 원본이 존재한다.
    assert "synthetic-name" in raw_text
    assert "".join(('', '010', '-0000-0000', '')) in raw_text

    # Sanitized export에는 민감필드가 없어야 한다.
    assert "synthetic-name" not in sanitized_text
    assert "".join(('', '010', '-0000-0000', '')) not in sanitized_text
    assert "synthetic-address" not in sanitized_text

    # 운영에 필요한 비민감 식별정보는 유지한다.
    assert "ORDER-001" in sanitized_text
    assert "101" in sanitized_text


def test_protected_snapshot_rejects_duplicate_batch(
    tmp_path: Path,
) -> None:
    kwargs = {
        "protected_root": tmp_path,
        "provider": "CAFE24",
        "resource": "products",
        "batch_id": "synthetic-batch-001",
        "records": [
            {
                "product_no": 101,
                "product_name": "Synthetic Product",
            }
        ],
    }

    write_protected_snapshot(**kwargs)

    with pytest.raises(FileExistsError):
        write_protected_snapshot(**kwargs)


def test_protected_snapshot_rejects_invalid_record(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError):
        write_protected_snapshot(
            protected_root=tmp_path,
            provider="CAFE24",
            resource="orders",
            batch_id="synthetic-batch-001",
            records=[
                "not-an-object",
            ],
        )

def test_protected_snapshot_redacts_free_text_pii(
    tmp_path: Path,
) -> None:
    result = write_protected_snapshot(
        protected_root=tmp_path,
        provider="CAFE24",
        resource="articles",
        batch_id="synthetic-inquiry-001",
        records=[
            {
                "article_no": 1001,
                "content": (
                    "".join(('', '010', '-1234-5678', ' 또는 customer@example.com으로 연락주세요.'))
                ),
            }
        ],
    )

    sanitized_text = result.sanitized_path.read_text(
        encoding="utf-8"
    )

    assert "".join(('', '010', '-1234-5678', '')) not in sanitized_text
    assert "".join(('', 'customer', '@example.com', '')) not in sanitized_text

    assert "<PHONE>" in sanitized_text
    assert "<EMAIL>" in sanitized_text

@pytest.mark.parametrize("component", ["provider", "resource", "batch_id"])
@pytest.mark.parametrize("value", ["../escape", "a/b", "a\\b", "a:stream", "CON", "".join(('', 'synthetic', '@example.test', ''))])
def test_snapshot_rejects_path_and_metadata_injection(tmp_path, component, value):
    kwargs = dict(protected_root=tmp_path, provider="CAFE24", resource="orders",
                  batch_id="synthetic-boundary", records=[])
    kwargs[component] = value
    with pytest.raises(ValueError):
        write_protected_snapshot(**kwargs)
    assert list(tmp_path.iterdir()) == []


def test_protected_root_rejects_repository_and_relative_paths(tmp_path):
    from backend.app.worker.privacy.protected_storage import _require_protected_root
    import backend.app.worker.privacy.protected_storage as storage
    repo = Path(storage.__file__).resolve().parents[4]
    for root in (repo, repo / "synthetic-protected", Path("relative-protected")):
        with pytest.raises(ValueError):
            _require_protected_root(root)
    (tmp_path / ".git").mkdir()
    with pytest.raises(ValueError):
        _require_protected_root(tmp_path / "protected")


def test_snapshot_rejects_symlink_escape(tmp_path):
    from backend.app.worker.privacy.protected_storage import _require_contained
    root = tmp_path / "protected"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    link = root / "alias"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation unavailable")
    with pytest.raises(ValueError):
        _require_contained(root, link / "synthetic.json")


def test_nested_tokens_are_removed_from_sanitized_export(tmp_path):
    result = write_protected_snapshot(
        protected_root=tmp_path, provider="CAFE24", resource="orders",
        batch_id="synthetic-token-boundary", records=[{"nested": {
            "refresh_token": "synthetic-refresh-secret", "client_secret": "synthetic-client-secret",
        }}],
    )
    text = result.sanitized_path.read_text(encoding="utf-8")
    assert "synthetic-refresh-secret" not in text
    assert "synthetic-client-secret" not in text
    assert str(tmp_path) not in repr(result)

def test_protected_storage_allows_ordinary_bearer_text(
    tmp_path,
) -> None:
    result = write_protected_raw_response(
        protected_root=tmp_path,
        provider="CAFE24",
        resource="products",
        batch_id="synthetic-bearer-text",
        page_id="page-000001",
        payload={
            "products": [
                {
                    "product_no": 1,
                    "product_name": (
                        "Synthetic Standard Bearer"
                    ),
                }
            ]
        },
        raw_count=1,
    )

    assert result.raw_count == 1


def test_protected_storage_rejects_authorization_bearer(
    tmp_path,
) -> None:
    with pytest.raises(
        ValueError
    ):
        write_protected_raw_response(
            protected_root=tmp_path,
            provider="CAFE24",
            resource="products",
            batch_id="synthetic-auth-bearer",
            page_id="page-000001",
            payload={
                "authorization": (
                    "Bearer synthetic-secret-token"
                )
            },
            raw_count=1,
        )
@pytest.mark.parametrize("field_name", ["token", "id_token"])
def test_protected_raw_rejects_generic_token_fields(tmp_path, field_name):
    with pytest.raises(ValueError):
        write_protected_raw_response(
            protected_root=tmp_path,
            provider="CAFE24",
            resource="products",
            batch_id=f"synthetic-{field_name.replace('_', '-')}",
            page_id="page-000001",
            payload={field_name: "synthetic-credential-value"},
            raw_count=1,
        )


def test_oauth_token_store_reuses_protected_root_boundary(tmp_path):
    import backend.app.worker.privacy.protected_storage as storage
    from backend.app.worker.privacy.oauth_token_store import _token_file_path

    repo = Path(storage.__file__).resolve().parents[4]
    with pytest.raises(ValueError):
        _token_file_path(str(repo / "synthetic-token-root"))
    allowed = _token_file_path(str(tmp_path / "synthetic-protected"))
    assert allowed.parent.exists()
    assert allowed.is_relative_to(tmp_path)