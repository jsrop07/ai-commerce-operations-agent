from pathlib import Path

import pytest
import json
import backend.app.sync.cafe24_product_full_runner as product_runner

from backend.app.sync.cafe24_product_full_runner import (
    _find_first_missing_product_offset,
    run_cafe24_product_full_runner,
)

from backend.app.adapters.providers.base import (
    ProviderHttpError,
    ProviderNonRetryableError,
    ProviderTransientError,
)
from backend.app.sync.cafe24_product_bootstrap import (
    Cafe24ProductBootstrapResult,
)
from backend.app.sync.cafe24_community_integrity import (
    run_cafe24_community_integrity,
)
def _write_product_manifest(
    root: Path,
    offset: int,
) -> None:
    manifest_root = (
        root
        / "cafe24"
        / "manifests"
    )
    manifest_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    path = (
        manifest_root
        / (
            "product-full-"
            f"{offset:06d}-"
            "20260909T000000000000Z."
            "manifest.json"
        )
    )

    path.write_text(
        "{}",
        encoding="utf-8",
    )


def test_find_first_missing_product_offset(
    tmp_path: Path,
) -> None:
    _write_product_manifest(tmp_path, 0)
    _write_product_manifest(tmp_path, 25)
    _write_product_manifest(tmp_path, 75)

    result = (
        _find_first_missing_product_offset(
            root=tmp_path,
            page_size=25,
        )
    )

    assert result == 50


def test_resume_after_gap_is_rejected_before_adapter_call(
    tmp_path: Path,
) -> None:
    _write_product_manifest(tmp_path, 0)
    _write_product_manifest(tmp_path, 25)
    _write_product_manifest(tmp_path, 75)

    adapter_called = False

    def adapter_factory():
        nonlocal adapter_called
        adapter_called = True
        raise AssertionError(
            "adapter must not be called"
        )

    with pytest.raises(
        ValueError,
        match=(
            "product resume cannot skip "
            "unresolved offset 50"
        ),
    ):
        run_cafe24_product_full_runner(
            adapter_factory=adapter_factory,
            protected_root=tmp_path,
            start_offset=75,
            max_products=25,
            batch_delay_seconds=0,
            cooldown_every_products=25,
            chunk_cooldown_seconds=0,
        )

    assert adapter_called is False


def test_resume_at_gap_is_not_rejected_by_gap_guard(
    tmp_path: Path,
) -> None:
    _write_product_manifest(tmp_path, 0)
    _write_product_manifest(tmp_path, 25)
    _write_product_manifest(tmp_path, 75)

    class ExpectedAdapterCall(RuntimeError):
        pass

    def adapter_factory():
        raise ExpectedAdapterCall

    with pytest.raises(ExpectedAdapterCall):
        run_cafe24_product_full_runner(
            adapter_factory=adapter_factory,
            protected_root=tmp_path,
            start_offset=50,
            max_products=25,
            batch_delay_seconds=0,
            cooldown_every_products=25,
            chunk_cooldown_seconds=0,
        )

@pytest.mark.parametrize(
    ("exc", "expected_status"),
    [
        (
            ProviderHttpError(
                status_code=500,
            ),
            "FAILED_HTTP",
        ),
        (
            ProviderTransientError(
                "temporary failure"
            ),
            "FAILED_TRANSIENT",
        ),
        (
            ProviderNonRetryableError(
                "invalid response"
            ),
            "FAILED_NON_RETRYABLE",
        ),
        (
            RuntimeError(
                "unexpected failure"
            ),
            "FAILED_UNEXPECTED",
        ),
    ],
)
def test_product_failure_preserves_current_offset(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    exc: Exception,
    expected_status: str,
) -> None:
    def fake_bootstrap(**kwargs):
        raise exc

    monkeypatch.setattr(
        product_runner,
        "run_cafe24_product_bootstrap",
        fake_bootstrap,
    )

    with pytest.raises(type(exc)):
        product_runner.run_cafe24_product_full_runner(
            adapter_factory=lambda: object(),
            protected_root=tmp_path,
            start_offset=0,
            max_products=25,
            batch_delay_seconds=0,
            cooldown_every_products=25,
            chunk_cooldown_seconds=0,
        )

    progress_files = list(
        (
            tmp_path
            / "cafe24"
            / "progress"
        ).glob(
            "product-full-run-*.json"
        )
    )

    assert len(progress_files) == 1

    progress = json.loads(
        progress_files[0].read_text(
            encoding="utf-8"
        )
    )

    assert progress["status"] == expected_status
    assert progress["last_success_offset"] is None
    assert progress["next_product_offset"] == 0
    assert progress["processed_product_count"] == 0
    assert progress["processed_batch_count"] == 0
    assert progress["completed"] is False

def test_product_rate_limit_failure_preserves_current_offset(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_bootstrap(**kwargs):
        raise ProviderHttpError(
            status_code=429,
            retry_after_seconds=0,
        )

    monkeypatch.setattr(
        product_runner,
        "run_cafe24_product_bootstrap",
        fake_bootstrap,
    )

    with pytest.raises(ProviderHttpError):
        product_runner.run_cafe24_product_full_runner(
            adapter_factory=lambda: object(),
            protected_root=tmp_path,
            start_offset=0,
            max_products=25,
            batch_delay_seconds=0,
            max_rate_limit_retries=0,
            cooldown_every_products=25,
            chunk_cooldown_seconds=0,
        )

    progress_files = list(
        (
            tmp_path
            / "cafe24"
            / "progress"
        ).glob(
            "product-full-run-*.json"
        )
    )

    assert len(progress_files) == 1

    progress = json.loads(
        progress_files[0].read_text(
            encoding="utf-8"
        )
    )

    assert progress["status"] == "FAILED_RATE_LIMIT"
    assert progress["last_success_offset"] is None
    assert progress["next_product_offset"] == 0
    assert progress["completed"] is False


def test_product_cursor_advances_only_after_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_bootstrap(**kwargs):
        return Cafe24ProductBootstrapResult(
            batch_id="product-full-test",
            product_offset=0,
            product_page_count=25,
            next_product_offset=25,
            has_more=True,
            variant_count=0,
            inventory_count=0,
            request_count=1,
            external_write_count=0,
            manifest_path=(
                tmp_path
                / "cafe24"
                / "manifests"
                / "product-full-test.manifest.json"
            ),
        )

    monkeypatch.setattr(
        product_runner,
        "run_cafe24_product_bootstrap",
        fake_bootstrap,
    )

    result = (
        product_runner.run_cafe24_product_full_runner(
            adapter_factory=lambda: object(),
            protected_root=tmp_path,
            start_offset=0,
            max_products=25,
            batch_delay_seconds=0,
            cooldown_every_products=25,
            chunk_cooldown_seconds=0,
        )
    )

    assert result.last_success_offset == 0
    assert result.next_product_offset == 25
    assert result.processed_product_count == 25
    assert result.processed_batch_count == 1
    assert result.completed is False

def test_day08_community_canonical_deduplication() -> None:
    protected_root = Path(
        r"C:\ai-commerce-private\cafe24"
    )

    result = run_cafe24_community_integrity(
        protected_root=protected_root,
    )

    assert result.article_record_count == 700
    assert result.unique_article_count == 624
    assert result.duplicate_article_record_count == 76
    assert result.conflicting_duplicate_count == 0

    assert result.missing_parent_count == 0
    assert result.invalid_self_parent_count == 0

    assert result.comment_missing_parent_count == 0

    assert result.blocking_finding_count == 0
    assert result.passed is True

def test_day08_product_two_pages_advance_sequentially(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen_offsets: list[int] = []

    def fake_bootstrap(**kwargs):
        offset = kwargs["product_offset"]
        seen_offsets.append(offset)

        if offset == 0:
            return Cafe24ProductBootstrapResult(
                batch_id="product-full-test-000000",
                product_offset=0,
                product_page_count=25,
                next_product_offset=25,
                has_more=True,
                variant_count=25,
                inventory_count=25,
                request_count=51,
                external_write_count=0,
                manifest_path=(
                    tmp_path
                    / "cafe24"
                    / "manifests"
                    / "product-full-test-000000.manifest.json"
                ),
            )

        return Cafe24ProductBootstrapResult(
            batch_id="product-full-test-000025",
            product_offset=25,
            product_page_count=25,
            next_product_offset=50,
            has_more=True,
            variant_count=25,
            inventory_count=25,
            request_count=51,
            external_write_count=0,
            manifest_path=(
                tmp_path
                / "cafe24"
                / "manifests"
                / "product-full-test-000025.manifest.json"
            ),
        )

    monkeypatch.setattr(
        product_runner,
        "run_cafe24_product_bootstrap",
        fake_bootstrap,
    )

    result = (
        product_runner.run_cafe24_product_full_runner(
            adapter_factory=lambda: object(),
            protected_root=tmp_path,
            start_offset=0,
            max_products=50,
            batch_delay_seconds=0,
            cooldown_every_products=50,
            chunk_cooldown_seconds=0,
        )
    )

    assert seen_offsets == [0, 25]

    assert result.last_success_offset == 25
    assert result.next_product_offset == 50

    assert result.processed_product_count == 50
    assert result.processed_batch_count == 2

    assert result.variant_count == 50
    assert result.inventory_count == 50

    assert result.completed is False

def test_day08_partial_failure_keeps_failed_page_for_resume(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    call_count = 0

    def fake_bootstrap(**kwargs):
        nonlocal call_count

        call_count += 1
        offset = kwargs["product_offset"]

        if offset == 0:
            return Cafe24ProductBootstrapResult(
                batch_id="product-full-test-000000",
                product_offset=0,
                product_page_count=25,
                next_product_offset=25,
                has_more=True,
                variant_count=25,
                inventory_count=25,
                request_count=51,
                external_write_count=0,
                manifest_path=(
                    tmp_path
                    / "cafe24"
                    / "manifests"
                    / "product-full-test-000000.manifest.json"
                ),
            )

        raise ProviderTransientError(
            "synthetic partial failure"
        )

    monkeypatch.setattr(
        product_runner,
        "run_cafe24_product_bootstrap",
        fake_bootstrap,
    )

    with pytest.raises(
        ProviderTransientError
    ):
        product_runner.run_cafe24_product_full_runner(
            adapter_factory=lambda: object(),
            protected_root=tmp_path,
            start_offset=0,
            max_products=50,
            batch_delay_seconds=0,
            cooldown_every_products=50,
            chunk_cooldown_seconds=0,
        )

    progress_files = list(
        (
            tmp_path
            / "cafe24"
            / "progress"
        ).glob(
            "product-full-run-*.json"
        )
    )

    assert len(progress_files) == 1

    progress = json.loads(
        progress_files[0].read_text(
            encoding="utf-8"
        )
    )

    assert call_count == 2

    assert progress["status"] == (
        "FAILED_TRANSIENT"
    )

    assert progress["last_success_offset"] == 0
    assert progress["next_product_offset"] == 25

    assert progress[
        "processed_product_count"
    ] == 25

    assert progress[
        "processed_batch_count"
    ] == 1

    assert progress["completed"] is False