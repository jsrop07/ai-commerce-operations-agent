from datetime import timedelta

import pytest

from backend.app.sync.cli import (
    build_sync_plan,
    execute_sync_plan,
    parse_args,
)
from backend.app.sync.run_lock import SyncRunLock


def test_cli_parses_required_sync_options() -> None:
    options = parse_args(
        [
            "--provider",
            "demo",
            "--resource",
            "sales",
            "--since",
            "2026-09-01T00:00:00+09:00",
            "--max-pages",
            "5",
            "--dry-run",
        ]
    )

    assert options.provider == "demo"
    assert options.resource == "sales"
    assert options.max_pages == 5
    assert options.dry_run is True

    assert options.since is not None
    assert options.since.utcoffset() == timedelta(hours=9)


def test_cli_defaults_to_bounded_max_pages() -> None:
    options = parse_args(
        [
            "--provider",
            "demo",
            "--resource",
            "sales",
        ]
    )

    assert options.max_pages == 100
    assert options.dry_run is False
    assert options.since is None


def test_cli_rejects_zero_max_pages() -> None:
    with pytest.raises(
        ValueError,
        match="max_pages must be >= 1",
    ):
        parse_args(
            [
                "--provider",
                "demo",
                "--resource",
                "sales",
                "--max-pages",
                "0",
            ]
        )


def test_cli_rejects_naive_since_datetime() -> None:
    with pytest.raises(SystemExit):
        parse_args(
            [
                "--provider",
                "demo",
                "--resource",
                "sales",
                "--since",
                "2026-09-01T00:00:00",
            ]
        )


def test_sync_plan_is_read_only_and_plan_only() -> None:
    options = parse_args(
        [
            "--provider",
            "demo",
            "--resource",
            "sales",
            "--dry-run",
        ]
    )

    plan = build_sync_plan(options)

    assert plan["provider"] == "demo"
    assert plan["resource"] == "sales"
    assert plan["dry_run"] is True
    assert plan["execution_status"] == "PLAN_ONLY"
    assert plan["external_write_count"] == 0


def test_execute_sync_plan_uses_run_lock() -> None:
    lock = SyncRunLock()

    options = parse_args(
        [
            "--provider",
            "demo",
            "--resource",
            "sales",
            "--dry-run",
        ]
    )

    assert (
        lock.acquire(
            tenant_id="store-a",
            provider="demo",
            resource="sales",
        )
        is True
    )

    result = execute_sync_plan(
        tenant_id="store-a",
        options=options,
        run_lock=lock,
    )

    assert result.status == "LOCKED"
    assert result.plan["execution_status"] == "LOCKED"


def test_execute_sync_plan_releases_lock_after_plan() -> None:
    lock = SyncRunLock()

    options = parse_args(
        [
            "--provider",
            "demo",
            "--resource",
            "sales",
            "--dry-run",
        ]
    )

    result = execute_sync_plan(
        tenant_id="store-a",
        options=options,
        run_lock=lock,
    )

    assert result.status == "PLAN_ONLY"

    assert (
        lock.is_locked(
            tenant_id="store-a",
            provider="demo",
            resource="sales",
        )
        is False
    )


def test_execute_sync_plan_releases_lock_when_result_creation_raises(monkeypatch) -> None:
    import backend.app.sync.cli as cli_module

    lock = SyncRunLock()
    options = parse_args(["--provider", "demo", "--resource", "sales", "--dry-run"])

    def fail_result_creation(**_kwargs):
        raise RuntimeError("synthetic result failure")

    monkeypatch.setattr(cli_module, "SyncExecutionResult", fail_result_creation)

    with pytest.raises(RuntimeError, match="synthetic result failure"):
        execute_sync_plan(tenant_id="store-a", options=options, run_lock=lock)

    assert lock.is_locked(tenant_id="store-a", provider="demo", resource="sales") is False
