from backend.app.adapters.providers import (
    Cafe24MockProvider,
    EcountMockProvider,
    TossPosMockProvider,
)
from backend.app.services.provider_reads import ProviderReadCoordinator


def test_timeout_is_bounded_and_healthy_results_are_preserved() -> None:
    failed = TossPosMockProvider(failure="timeout")
    result = ProviderReadCoordinator(max_attempts=3).read_inventory(
        [Cafe24MockProvider(), failed, EcountMockProvider()]
    )
    assert result.status == "partial"
    assert len(result.items) == 2
    assert result.failures == {"TOSS_POS": "TimeoutError"}
    assert result.attempts["TOSS_POS"] == 3
    assert failed.request_attempts == 3


def test_5xx_retries_but_schema_failure_does_not() -> None:
    transient = Cafe24MockProvider(failure="5xx")
    nonretryable = EcountMockProvider(failure="schema")
    result = ProviderReadCoordinator(max_attempts=2).read_inventory([transient, nonretryable])
    assert result.status == "degraded"
    assert transient.request_attempts == 2
    assert nonretryable.request_attempts == 1
