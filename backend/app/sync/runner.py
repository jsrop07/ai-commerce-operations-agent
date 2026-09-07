"""Bounded paginated provider sync runner."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from math import isfinite
from typing import Any

from backend.app.adapters.providers.base import CommerceProvider
from backend.app.sync.retry_policy import RetryPolicy
from contracts.providers import ProviderReadPage

ReadPageFunction = Callable[
    [CommerceProvider, str | None],
    ProviderReadPage[dict[str, Any]],
]

CommitPageFunction = Callable[
    [ProviderReadPage[dict[str, Any]], str | None],
    None,
]


@dataclass(frozen=True)
class SyncBudget:
    max_pages: int = 100
    max_items: int = 10_000
    max_elapsed_seconds: float = 60.0

    def __post_init__(self) -> None:
        if self.max_pages < 1:
            raise ValueError("max_pages must be >= 1")
        if self.max_items < 1:
            raise ValueError("max_items must be >= 1")
        if not isfinite(self.max_elapsed_seconds) or self.max_elapsed_seconds <= 0:
            raise ValueError("max_elapsed_seconds must be > 0")


@dataclass
class SyncRunResult:
    items: list[dict[str, Any]] = field(default_factory=list)
    pages_succeeded: int = 0
    attempts: int = 0
    last_success_cursor: str | None = None
    next_cursor: str | None = None
    completed: bool = False
    stop_reason: str | None = None
    error_type: str | None = None


class ProviderSyncRunner:
    def __init__(
        self,
        *,
        retry_policy: RetryPolicy,
        budget: SyncBudget,
        sleep_fn: Callable[[float], None] = time.sleep,
        monotonic_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        self.retry_policy = retry_policy
        self.budget = budget
        self.sleep_fn = sleep_fn
        self.monotonic_fn = monotonic_fn

    def run(
        self,
        *,
        provider: CommerceProvider,
        read_page: ReadPageFunction,
        start_cursor: str | None = None,
        commit_page: CommitPageFunction | None = None,
    ) -> SyncRunResult:
        result = SyncRunResult(
            last_success_cursor=start_cursor,
            next_cursor=start_cursor,
        )

        cursor = start_cursor
        seen_cursors = {start_cursor}
        started_at = self.monotonic_fn()

        while True:
            if result.pages_succeeded >= self.budget.max_pages:
                result.stop_reason = "MAX_PAGES"
                result.next_cursor = cursor
                return result

            if len(result.items) >= self.budget.max_items:
                result.stop_reason = "MAX_ITEMS"
                result.next_cursor = cursor
                return result

            if self.monotonic_fn() - started_at >= self.budget.max_elapsed_seconds:
                result.stop_reason = "MAX_ELAPSED"
                result.next_cursor = cursor
                return result

            page: ProviderReadPage[dict[str, Any]] | None = None

            for attempt in range(1, self.retry_policy.max_attempts + 1):
                if self.monotonic_fn() - started_at >= self.budget.max_elapsed_seconds:
                    result.stop_reason = "MAX_ELAPSED"
                    return result
                result.attempts += 1

                try:
                    page = read_page(provider, cursor)
                    break
                except Exception as exc:
                    decision = self.retry_policy.decide(exc, attempt=attempt)

                    if not decision.retry:
                        result.stop_reason = decision.reason
                        result.error_type = type(exc).__name__
                        result.next_cursor = cursor
                        return result

                    if (
                        self.monotonic_fn() - started_at + decision.delay_seconds
                        >= self.budget.max_elapsed_seconds
                    ):
                        result.stop_reason = "MAX_ELAPSED"
                        result.error_type = type(exc).__name__
                        result.next_cursor = cursor
                        return result

                    self.sleep_fn(decision.delay_seconds)

            if page is None:
                result.stop_reason = "NO_PAGE"
                result.next_cursor = cursor
                return result

            if self.monotonic_fn() - started_at >= self.budget.max_elapsed_seconds:
                result.stop_reason = "MAX_ELAPSED"
                return result
            if page.has_more and (page.next_cursor is None or page.next_cursor in seen_cursors):
                result.stop_reason = "INVALID_PAGINATION_CURSOR"
                return result

            remaining = self.budget.max_items - len(result.items)

            # 이 page 전체를 처리할 예산이 없으면 page 자체를 commit하지 않는다.
            if len(page.items) > remaining:
                result.stop_reason = "MAX_ITEMS"
                result.next_cursor = cursor
                return result

            if commit_page is not None:
                try:
                    commit_page(page, cursor)
                except Exception as exc:
                    result.stop_reason = "CANONICAL_COMMIT_FAILED"
                    result.error_type = type(exc).__name__
                    result.next_cursor = cursor
                    return result

            result.items.extend(page.items)
            result.pages_succeeded += 1

            previous_cursor = cursor
            cursor = page.next_cursor
            seen_cursors.add(cursor)

            result.last_success_cursor = previous_cursor
            result.next_cursor = cursor

            if not page.has_more or page.next_cursor is None:
                result.completed = True
                result.stop_reason = "COMPLETED"
                return result
