"""Bounded retry policy for provider read operations."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from random import Random

from backend.app.adapters.providers.base import (
    ProviderHttpError,
    ProviderNonRetryableError,
    ProviderTransientError,
)


@dataclass(frozen=True)
class RetryDecision:
    retry: bool
    delay_seconds: float
    reason: str


class RetryPolicy:
    def __init__(
        self,
        *,
        max_attempts: int = 3,
        base_delay_seconds: float = 0.5,
        max_delay_seconds: float = 8.0,
        jitter_ratio: float = 0.2,
        random_seed: int | None = None,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if not isfinite(base_delay_seconds) or base_delay_seconds < 0:
            raise ValueError("base_delay_seconds must be >= 0")
        if not isfinite(max_delay_seconds) or max_delay_seconds < base_delay_seconds:
            raise ValueError("max_delay_seconds must be >= base_delay_seconds")
        if not 0 <= jitter_ratio <= 1:
            raise ValueError("jitter_ratio must be between 0 and 1")

        self.max_attempts = max_attempts
        self.base_delay_seconds = base_delay_seconds
        self.max_delay_seconds = max_delay_seconds
        self.jitter_ratio = jitter_ratio
        self._random = Random(random_seed)

    def decide(self, exc: Exception, *, attempt: int) -> RetryDecision:
        if attempt < 1:
            raise ValueError("attempt must be >= 1")

        if attempt >= self.max_attempts:
            return RetryDecision(
                retry=False,
                delay_seconds=0.0,
                reason="MAX_ATTEMPTS_EXHAUSTED",
            )

        if not self._is_retryable(exc):
            return RetryDecision(
                retry=False,
                delay_seconds=0.0,
                reason="NON_RETRYABLE",
            )

        retry_after = self._retry_after(exc)
        if retry_after is not None:
            if not isfinite(retry_after) or retry_after < 0:
                return RetryDecision(
                    retry=False,
                    delay_seconds=0.0,
                    reason="INVALID_RETRY_AFTER",
                )

            return RetryDecision(
                retry=True,
                delay_seconds=retry_after,
                reason="RETRY_AFTER",
            )

        exponential = min(
            self.max_delay_seconds,
            self.base_delay_seconds * (2 ** (attempt - 1)),
        )

        jitter = exponential * self.jitter_ratio * self._random.random()
        delay = min(self.max_delay_seconds, exponential + jitter)

        return RetryDecision(
            retry=True,
            delay_seconds=delay,
            reason="EXPONENTIAL_BACKOFF",
        )

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        if isinstance(exc, TimeoutError):
            return True

        if isinstance(exc, ProviderTransientError):
            return True

        if isinstance(exc, ProviderNonRetryableError):
            return False

        if isinstance(exc, ProviderHttpError):
            return exc.status_code == 429 or 500 <= exc.status_code <= 599

        return False

    @staticmethod
    def _retry_after(exc: Exception) -> float | None:
        if not isinstance(exc, ProviderHttpError):
            return None

        if exc.status_code != 429:
            return None

        return exc.retry_after_seconds
