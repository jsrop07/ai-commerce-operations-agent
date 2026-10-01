import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from openai import APITimeoutError

from ai.services.grounded_explanation import (
    ExplanationEvidence,
    build_policy_grounded_explanation_input,
)
from ai.services.grounded_explanation_provider import (
    GroundedProviderError,
    GroundedProviderTimeout,
    run_grounded_explanation,
)


def make_config(
    tmp_path: Path,
    *,
    max_retries: int = 1,
) -> Path:
    path = tmp_path / "r06_runtime_config.json"

    path.write_text(
        json.dumps(
            {
                "provider": "openai",
                "model": "gpt-5.6-luna",
                "temperature": 0,
                "reasoning_effort": "none",
                "max_output_tokens": 600,
                "timeout_seconds": 30,
                "max_retries": max_retries,
            }
        ),
        encoding="utf-8",
    )

    return path


def make_input():
    return build_policy_grounded_explanation_input(
        question="예약상품은 언제 출고해?",
        data_mode="SYNTHETIC_DEMO",
        evidence=(
            ExplanationEvidence(
                source_type="POLICY",
                source_id="policy_shipping_demo",
                version="v2",
                excerpt=(
                    "예약상품은 상품 입고와 "
                    "검수 완료 후 순차적으로 출고합니다."
                ),
                as_of=None,
            ),
        ),
    )


def good_response():
    return SimpleNamespace(
        id="resp_fake_001",
        output_text=json.dumps(
            {
                "status": "ANSWER",
                "conclusion": (
                    "예약상품은 상품 입고와 "
                    "검수 완료 후 순차적으로 출고합니다."
                ),
                "used_facts": [
                    (
                        "예약상품은 상품 입고와 "
                        "검수 완료 후 순차적으로 출고합니다."
                    )
                ],
                "used_numeric_facts": [],
                "citations": [
                    {
                        "source_id": "policy_shipping_demo",
                        "version": "v2",
                    }
                ],
                "next_check": None,
            },
            ensure_ascii=False,
        ),
        usage=SimpleNamespace(
            input_tokens=100,
            output_tokens=30,
            input_tokens_details=SimpleNamespace(
                cached_tokens=10
            ),
        ),
    )


class FakeResponses:
    def __init__(self, actions):
        self.actions = list(actions)
        self.calls = 0
        self.last_kwargs = None

    def create(self, **kwargs):
        self.calls += 1
        self.last_kwargs = kwargs

        action = self.actions.pop(0)

        if isinstance(action, Exception):
            raise action

        return action


class FakeClient:
    def __init__(self, actions):
        self.responses = FakeResponses(actions)


def timeout_error():
    return APITimeoutError(
        request=httpx.Request(
            "POST",
            "https://example.invalid/v1/responses",
        )
    )


def test_success_returns_output_receipt_and_usage(
    tmp_path,
):
    client = FakeClient(
        [good_response()]
    )

    result = run_grounded_explanation(
        make_input(),
        condition="CITATION",
        config_path=make_config(
            tmp_path
        ),
        client=client,
    )

    assert result.model_used is True
    assert result.output.status.value == "ANSWER"

    assert (
        result.output.citations[0].source_id
        == "policy_shipping_demo"
    )

    assert result.receipt.provider == "openai"
    assert result.receipt.model == "gpt-5.6-luna"
    assert result.receipt.response_id == "resp_fake_001"

    assert result.receipt.attempts == 1
    assert result.receipt.retries == 0

    assert result.receipt.usage.input_tokens == 100
    assert (
        result.receipt.usage.cached_input_tokens
        == 10
    )
    assert result.receipt.usage.output_tokens == 30

    assert client.responses.calls == 1

    assert (
        client.responses.last_kwargs["store"]
        is False
    )


def test_timeout_retries_once_then_succeeds(
    tmp_path,
):
    client = FakeClient(
        [
            timeout_error(),
            good_response(),
        ]
    )

    result = run_grounded_explanation(
        make_input(),
        condition="CITATION",
        config_path=make_config(
            tmp_path,
            max_retries=1,
        ),
        client=client,
    )

    assert result.model_used is True
    assert result.receipt.attempts == 2
    assert result.receipt.retries == 1
    assert client.responses.calls == 2


def test_timeout_after_retry_raises_distinct_error(
    tmp_path,
):
    client = FakeClient(
        [
            timeout_error(),
            timeout_error(),
        ]
    )

    with pytest.raises(
        GroundedProviderTimeout,
        match="provider timeout",
    ):
        run_grounded_explanation(
            make_input(),
            condition="CITATION",
            config_path=make_config(
                tmp_path,
                max_retries=1,
            ),
            client=client,
        )

    assert client.responses.calls == 2


def test_malformed_output_raises_provider_error(
    tmp_path,
):
    response = SimpleNamespace(
        id="resp_bad",
        output_text="{not-json",
        usage=None,
    )

    client = FakeClient(
        [response]
    )

    with pytest.raises(
        GroundedProviderError,
        match="provider output schema invalid",
    ):
        run_grounded_explanation(
            make_input(),
            condition="BASIC",
            config_path=make_config(
                tmp_path
            ),
            client=client,
        )

    assert client.responses.calls == 1


def test_runtime_uses_approved_config(
    tmp_path,
):
    client = FakeClient(
        [good_response()]
    )

    run_grounded_explanation(
        make_input(),
        condition="CITATION",
        config_path=make_config(
            tmp_path
        ),
        client=client,
    )

    kwargs = client.responses.last_kwargs

    assert kwargs["model"] == "gpt-5.6-luna"
    assert kwargs["temperature"] == 0
    assert kwargs["max_output_tokens"] == 600
    assert kwargs["reasoning"] == {
        "effort": "none"
    }
    assert kwargs["timeout"] == 30.0

    assert (
        kwargs["text"]["format"]["strict"]
        is True
    )


def test_invalid_condition_rejected_before_provider_call(
    tmp_path,
):
    client = FakeClient(
        [good_response()]
    )

    with pytest.raises(
        ValueError,
        match="unsupported condition",
    ):
        run_grounded_explanation(
            make_input(),
            condition="INVALID",
            config_path=make_config(
                tmp_path
            ),
            client=client,
        )

    assert client.responses.calls == 0