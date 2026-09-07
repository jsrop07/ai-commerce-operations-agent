import pytest

from backend.app.adapters.providers.base import (
    ProviderHttpError,
    ProviderNonRetryableError,
    ProviderTransientError,
)
from backend.app.sync.retry_policy import RetryPolicy


def test_timeout_and_transient_failures_are_retryable() -> None:
    policy = RetryPolicy(
        max_attempts=3,
        base_delay_seconds=1.0,
        max_delay_seconds=10.0,
        jitter_ratio=0.0,
    )

    timeout = policy.decide(TimeoutError("timeout"), attempt=1)
    transient = policy.decide(
        ProviderTransientError("temporary failure"),
        attempt=1,
    )

    assert timeout.retry is True
    assert timeout.delay_seconds == 1.0

    assert transient.retry is True
    assert transient.delay_seconds == 1.0


def test_429_uses_retry_after() -> None:
    policy = RetryPolicy(max_attempts=3)

    decision = policy.decide(
        ProviderHttpError(
            429,
            retry_after_seconds=2.5,
        ),
        attempt=1,
    )

    assert decision.retry is True
    assert decision.delay_seconds == 2.5
    assert decision.reason == "RETRY_AFTER"


@pytest.mark.parametrize("status_code", [500, 502, 503, 504])
def test_5xx_is_retryable(status_code: int) -> None:
    policy = RetryPolicy(
        max_attempts=3,
        base_delay_seconds=1.0,
        max_delay_seconds=10.0,
        jitter_ratio=0.0,
    )

    decision = policy.decide(
        ProviderHttpError(status_code),
        attempt=1,
    )

    assert decision.retry is True
    assert decision.delay_seconds == 1.0


@pytest.mark.parametrize("status_code", [400, 401, 403, 404])
def test_non_retryable_4xx_stops_immediately(status_code: int) -> None:
    policy = RetryPolicy(max_attempts=3)

    decision = policy.decide(
        ProviderHttpError(status_code),
        attempt=1,
    )

    assert decision.retry is False
    assert decision.delay_seconds == 0.0
    assert decision.reason == "NON_RETRYABLE"


def test_schema_error_stops_immediately() -> None:
    policy = RetryPolicy(max_attempts=3)

    decision = policy.decide(
        ProviderNonRetryableError("schema mismatch"),
        attempt=1,
    )

    assert decision.retry is False
    assert decision.reason == "NON_RETRYABLE"


def test_max_attempts_stops_retry() -> None:
    policy = RetryPolicy(max_attempts=3)

    decision = policy.decide(
        TimeoutError("still unavailable"),
        attempt=3,
    )

    assert decision.retry is False
    assert decision.delay_seconds == 0.0
    assert decision.reason == "MAX_ATTEMPTS_EXHAUSTED"


def test_backoff_is_bounded() -> None:
    policy = RetryPolicy(
        max_attempts=10,
        base_delay_seconds=1.0,
        max_delay_seconds=4.0,
        jitter_ratio=0.0,
    )

    first = policy.decide(TimeoutError(), attempt=1)
    second = policy.decide(TimeoutError(), attempt=2)
    third = policy.decide(TimeoutError(), attempt=3)
    fourth = policy.decide(TimeoutError(), attempt=4)

    assert first.delay_seconds == 1.0
    assert second.delay_seconds == 2.0
    assert third.delay_seconds == 4.0
    assert fourth.delay_seconds == 4.0
