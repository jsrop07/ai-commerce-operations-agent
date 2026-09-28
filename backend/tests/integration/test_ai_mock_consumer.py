import json
from unittest.mock import Mock

import pytest

from backend.app.services.ai_mock_consumer import (
    AIMockConsumer,
)
from backend.app.services.demo import DEMO_SCENARIOS
from backend.app.services.offline_sale import OfflineSalePipeline


def test_backend_consumes_validated_ai_mock_response() -> None:
    consumer = AIMockConsumer()

    result = consumer.classify_inquiry(
        request_id="req_day04_backend_ai_001",
        trace_id="trace_day04_backend_ai_001",
        intent="PRODUCT_INFO",
        risk="LOW",
        evidence_ids=["evt_demo_04"],
    )

    assert result["schema_version"] == "ai-response.v0.1"

    assert (
        result["request_id"]
        == "req_day04_backend_ai_001"
    )

    assert (
        result["trace_id"]
        == "trace_day04_backend_ai_001"
    )

    assert (
        result["task_type"]
        == "inquiry_classification"
    )

    assert result["route"] == "RULE_SQL"

    assert (
        result["model"]["model_run_id"]
        is None
    )

    assert (
        result["model"]["model_id"]
        is None
    )

    assert result["token"] == {
        "input": 0,
        "output": 0,
        "cache": 0,
    }

    assert result["cost"]["estimated"] == 0.0

def test_backend_ai_consumer_preserves_prohibited_route() -> None:
    consumer = AIMockConsumer()

    result = consumer.classify_inquiry(
        request_id="req_day04_backend_ai_deny",
        trace_id="trace_day04_backend_ai_deny",
        intent="REFUND_CANCEL",
        risk="PROHIBITED",
    )

    assert result["route"] == "POLICY_DENY"

    assert (
        consumer.runtime.counters.external_model_calls
        == 0
    )

    assert (
        consumer.runtime.counters.tool_calls
        == 0
    )

    assert (
        consumer.runtime.counters.provider_calls
        == 0
    )

    assert (
        consumer.runtime.counters.auto_send_count
        == 0
    )

def test_inquiry_event_does_not_flow_to_ai_mock_consumer() -> None:
    pipeline = OfflineSalePipeline()

    event = DEMO_SCENARIOS["product_inquiry"]

    receipt = pipeline.process(
        event,
        environment="DEMO",
        request_id="req_day04_inquiry_e2e",
        trace_id="trace_day04_inquiry_e2e",
    )

    assert receipt.status == "ACCEPTED"

    assert pipeline.ai_results == []

    route_record = next(
        json.loads(record)
        for record in pipeline.trace
        if json.loads(record)["message"] == "INQUIRY_AI_DISABLED"
    )
    assert route_record["correlation_id"] == event["correlation_id"]


def test_inquiry_ai_consumer_call_count_is_zero() -> None:
    pipeline = OfflineSalePipeline()
    consumer = Mock()
    pipeline.ai_consumer = consumer

    pipeline.process(DEMO_SCENARIOS["product_inquiry"])

    consumer.classify_inquiry.assert_not_called()

def test_prohibited_inquiry_event_does_not_call_ai() -> None:
    pipeline = OfflineSalePipeline()

    event = DEMO_SCENARIOS["risk_inquiry"]

    receipt = pipeline.process(
        event,
        environment="DEMO",
        request_id="req_day04_risk_e2e",
        trace_id="trace_day04_risk_e2e",
    )

    assert receipt.status == "ACCEPTED"

    assert pipeline.ai_results == []

    assert (
        pipeline.ai_consumer.runtime.counters
        .external_model_calls
        == 0
    )

    assert (
        pipeline.ai_consumer.runtime.counters
        .tool_calls
        == 0
    )

    assert (
        pipeline.ai_consumer.runtime.counters
        .provider_calls
        == 0
    )

    assert (
        pipeline.ai_consumer.runtime.counters
        .auto_send_count
        == 0
    )

    assert pipeline.external_write_count == 0


@pytest.mark.parametrize("scenario_name", ["product_inquiry", "risk_inquiry"])
def test_duplicate_inquiry_has_zero_ai_effects_and_external_actions(
    scenario_name: str,
) -> None:
    pipeline = OfflineSalePipeline()
    event = DEMO_SCENARIOS[scenario_name]

    first = pipeline.process(event)
    second = pipeline.process(event)

    assert first.status == "ACCEPTED"
    assert second.status == "REPLAYED"
    assert pipeline.ai_results == []
    assert pipeline.effects.business_effect_count == 0
    assert pipeline.inbox.accepted_count == 1
    assert pipeline.inbox.replayed_count == 1
    counters = pipeline.ai_consumer.runtime.counters
    assert counters.external_model_calls == 0
    assert counters.tool_calls == 0
    assert counters.provider_calls == 0
    assert counters.auto_send_count == 0
    assert pipeline.external_write_count == 0


def test_backend_ai_consumer_rejects_mismatched_runtime_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    consumer = AIMockConsumer()
    response = consumer.runtime.run(
        request_id="req_wrong",
        trace_id="trace_expected",
        intent="PRODUCT_INFO",
        risk="LOW",
    )
    monkeypatch.setattr(consumer.runtime, "run", lambda **_: response)

    with pytest.raises(ValueError, match="request/trace ID mismatch"):
        consumer.classify_inquiry(
            request_id="req_expected",
            trace_id="trace_expected",
            intent="PRODUCT_INFO",
            risk="LOW",
        )
