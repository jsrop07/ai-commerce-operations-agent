from ai.services.mock_runtime import (
    MockAIRuntime,
)


def assert_zero_external_actions(
    runtime: MockAIRuntime,
) -> None:
    assert (
        runtime.counters
        .external_model_calls
        == 0
    )

    assert (
        runtime.counters.tool_calls
        == 0
    )

    assert (
        runtime.counters.provider_calls
        == 0
    )

    assert (
        runtime.counters.auto_send_count
        == 0
    )


def test_refund_is_policy_denied():
    runtime = MockAIRuntime()

    response = runtime.run(
        request_id="req_day04_refund",
        trace_id="trace_day04_refund",
        intent="REFUND_CANCEL",
        risk="PROHIBITED",
    )

    assert response["route"] == "POLICY_DENY"

    assert (
        response["route_reason"]
        == "PROHIBITED_ACTION_REQUIRES_HUMAN_OPERATION"
    )

    assert_zero_external_actions(
        runtime
    )


def test_payment_is_policy_denied():
    runtime = MockAIRuntime()

    response = runtime.run(
        request_id="req_day04_payment",
        trace_id="trace_day04_payment",
        intent="OTHER",
        risk="PROHIBITED",
    )

    assert response["route"] == "POLICY_DENY"

    assert_zero_external_actions(
        runtime
    )


def test_order_cancel_is_policy_denied():
    runtime = MockAIRuntime()

    response = runtime.run(
        request_id="req_day04_cancel",
        trace_id="trace_day04_cancel",
        intent="REFUND_CANCEL",
        risk="PROHIBITED",
    )

    assert response["route"] == "POLICY_DENY"

    assert_zero_external_actions(
        runtime
    )


def test_dispute_requires_human_review():
    runtime = MockAIRuntime()

    response = runtime.run(
        request_id="req_day04_dispute",
        trace_id="trace_day04_dispute",
        intent="OTHER",
        risk="HIGH",
    )

    assert response["route"] == "HUMAN_REVIEW"

    assert (
        response["route_reason"]
        == "HIGH_RISK_INQUIRY_REQUIRES_HUMAN_REVIEW"
    )

    assert_zero_external_actions(
        runtime
    )


def test_compensation_requires_human_review():
    runtime = MockAIRuntime()

    response = runtime.run(
        request_id="req_day04_compensation",
        trace_id="trace_day04_compensation",
        intent="OTHER",
        risk="HIGH",
    )

    assert response["route"] == "HUMAN_REVIEW"

    assert_zero_external_actions(
        runtime
    )


def test_high_and_prohibited_are_not_same_route():
    runtime = MockAIRuntime()

    high = runtime.run(
        request_id="req_day04_high",
        trace_id="trace_day04_high",
        intent="OTHER",
        risk="HIGH",
    )

    prohibited = runtime.run(
        request_id="req_day04_prohibited",
        trace_id="trace_day04_prohibited",
        intent="REFUND_CANCEL",
        risk="PROHIBITED",
    )

    assert (
        high["route"]
        == "HUMAN_REVIEW"
    )

    assert (
        prohibited["route"]
        == "POLICY_DENY"
    )

    assert (
        high["route"]
        != prohibited["route"]
    )

    assert_zero_external_actions(
        runtime
    )


def test_medium_is_review_not_policy_deny():
    runtime = MockAIRuntime()

    response = runtime.run(
        request_id="req_day04_medium",
        trace_id="trace_day04_medium",
        intent="RESERVATION_PREORDER",
        risk="MEDIUM",
    )

    assert (
        response["route"]
        == "HUMAN_REVIEW"
    )

    assert (
        response["route"]
        != "POLICY_DENY"
    )

    assert_zero_external_actions(
        runtime
    )