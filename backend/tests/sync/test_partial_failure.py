from typing import Any

from backend.app.adapters.providers.mock import Cafe24MockProvider
from backend.app.sync.retry_policy import (
    ProviderHttpError,
    RetryPolicy,
)
from backend.app.sync.runner import ProviderSyncRunner, SyncBudget
from contracts.providers import ProviderReadPage


def test_two_pages_complete_without_infinite_calls() -> None:
    provider = Cafe24MockProvider()

    runner = ProviderSyncRunner(
        retry_policy=RetryPolicy(
            max_attempts=3,
            jitter_ratio=0.0,
        ),
        budget=SyncBudget(
            max_pages=10,
            max_items=100,
            max_elapsed_seconds=30,
        ),
        sleep_fn=lambda _: None,
    )

    result = runner.run(
        provider=provider,
        read_page=lambda p, cursor: p.read_products(cursor),
    )

    assert result.completed is True
    assert result.stop_reason == "COMPLETED"
    assert result.pages_succeeded == 2
    assert len(result.items) == 2
    assert provider.request_attempts == 2


def test_max_pages_stops_pagination() -> None:
    provider = Cafe24MockProvider()

    runner = ProviderSyncRunner(
        retry_policy=RetryPolicy(max_attempts=3),
        budget=SyncBudget(
            max_pages=1,
            max_items=100,
            max_elapsed_seconds=30,
        ),
        sleep_fn=lambda _: None,
    )

    result = runner.run(
        provider=provider,
        read_page=lambda p, cursor: p.read_products(cursor),
    )

    assert result.completed is False
    assert result.stop_reason == "MAX_PAGES"
    assert result.pages_succeeded == 1
    assert result.next_cursor == "page-2"
    assert provider.request_attempts == 1


def test_max_items_stops_without_extra_page_call() -> None:
    provider = Cafe24MockProvider()

    runner = ProviderSyncRunner(
        retry_policy=RetryPolicy(max_attempts=3),
        budget=SyncBudget(
            max_pages=10,
            max_items=1,
            max_elapsed_seconds=30,
        ),
        sleep_fn=lambda _: None,
    )

    result = runner.run(
        provider=provider,
        read_page=lambda p, cursor: p.read_products(cursor),
    )

    assert result.completed is False
    assert result.stop_reason == "MAX_ITEMS"
    assert len(result.items) == 1
    assert result.next_cursor == "page-2"
    assert provider.request_attempts == 1


def test_second_page_failure_preserves_resume_cursor() -> None:
    provider = Cafe24MockProvider()
    calls = 0

    def read_page(
        p: Cafe24MockProvider,
        cursor: str | None,
    ) -> ProviderReadPage[dict[str, Any]]:
        nonlocal calls
        calls += 1

        if cursor == "page-2":
            raise ProviderHttpError(503)

        return p.read_products(cursor)

    runner = ProviderSyncRunner(
        retry_policy=RetryPolicy(
            max_attempts=2,
            base_delay_seconds=0,
            max_delay_seconds=0,
            jitter_ratio=0,
        ),
        budget=SyncBudget(
            max_pages=10,
            max_items=100,
            max_elapsed_seconds=30,
        ),
        sleep_fn=lambda _: None,
    )

    result = runner.run(
        provider=provider,
        read_page=read_page,
    )

    assert result.completed is False
    assert result.pages_succeeded == 1
    assert len(result.items) == 1

    # page-2는 아직 성공하지 않았으므로 재개 위치로 남아야 한다.
    assert result.next_cursor == "page-2"

    assert result.error_type == "ProviderHttpError"
    assert result.stop_reason == "MAX_ATTEMPTS_EXHAUSTED"

    # page1 1회 + page2 2회
    assert calls == 3


def test_non_retryable_error_stops_after_one_attempt() -> None:
    provider = Cafe24MockProvider()

    def read_page(
        _: Cafe24MockProvider,
        __: str | None,
    ) -> ProviderReadPage[dict[str, Any]]:
        raise ProviderHttpError(401)

    runner = ProviderSyncRunner(
        retry_policy=RetryPolicy(max_attempts=5),
        budget=SyncBudget(),
        sleep_fn=lambda _: None,
    )

    result = runner.run(
        provider=provider,
        read_page=read_page,
    )

    assert result.completed is False
    assert result.attempts == 1
    assert result.stop_reason == "NON_RETRYABLE"


def test_checkpoint_hook_runs_only_after_successful_page_commit() -> None:
    provider = Cafe24MockProvider()
    committed: list[str | None] = []

    runner = ProviderSyncRunner(
        retry_policy=RetryPolicy(max_attempts=2),
        budget=SyncBudget(
            max_pages=10,
            max_items=100,
            max_elapsed_seconds=30,
        ),
        sleep_fn=lambda _: None,
    )

    result = runner.run(
        provider=provider,
        read_page=lambda p, cursor: p.read_products(cursor),
        commit_page=lambda page, cursor: committed.append(page.next_cursor),
    )

    assert result.completed is True
    assert committed == ["page-2", None]


def test_canonical_commit_failure_does_not_advance_page() -> None:
    provider = Cafe24MockProvider()

    def fail_commit(
        page: ProviderReadPage[dict[str, Any]],
        cursor: str | None,
    ) -> None:
        if cursor == "page-2":
            raise RuntimeError("db commit failed")

    runner = ProviderSyncRunner(
        retry_policy=RetryPolicy(max_attempts=2),
        budget=SyncBudget(
            max_pages=10,
            max_items=100,
            max_elapsed_seconds=30,
        ),
        sleep_fn=lambda _: None,
    )

    result = runner.run(
        provider=provider,
        read_page=lambda p, cursor: p.read_products(cursor),
        commit_page=fail_commit,
    )

    assert result.completed is False
    assert result.stop_reason == "CANONICAL_COMMIT_FAILED"
    assert result.error_type == "RuntimeError"

    # 첫 page만 성공 처리
    assert result.pages_succeeded == 1
    assert len(result.items) == 1

    # 두 번째 page는 읽었어도 DB commit 실패이므로
    # 재개 위치는 page-2
    assert result.next_cursor == "page-2"
