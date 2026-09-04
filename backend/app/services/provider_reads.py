"""Bounded retries and partial-provider result aggregation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.app.adapters.providers.base import CommerceProvider, ProviderTransientError
from contracts.events import Provider


@dataclass
class ProviderReadResult:
    status: str
    items: list[dict[str, Any]] = field(default_factory=list)
    failures: dict[str, str] = field(default_factory=dict)
    attempts: dict[str, int] = field(default_factory=dict)


class ProviderReadCoordinator:
    def __init__(self, max_attempts: int = 3) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        self.max_attempts = max_attempts

    def read_inventory(self, providers: list[CommerceProvider]) -> ProviderReadResult:
        result = ProviderReadResult(status="success")
        for provider in providers:
            name = Provider(provider.capabilities().provider).value
            for attempt in range(1, self.max_attempts + 1):
                result.attempts[name] = attempt
                try:
                    result.items.extend(provider.read_inventory().items)
                    break
                except (TimeoutError, ProviderTransientError) as exc:
                    if attempt == self.max_attempts:
                        result.failures[name] = type(exc).__name__
                except Exception as exc:  # non-retryable contract/provider error
                    result.failures[name] = type(exc).__name__
                    break
        if result.failures and result.items:
            result.status = "partial"
        elif result.failures:
            result.status = "degraded"
        return result
