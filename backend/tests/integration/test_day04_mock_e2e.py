import json

from fastapi.testclient import TestClient

from backend.app.adapters.providers import TossPosMockProvider
from backend.app.core.config import Environment, Settings
from backend.app.main import create_app
from backend.app.services.demo import DEMO_SCENARIOS


def test_day04_offline_sale_e2e_duplicate_effect_once() -> None:
    app = create_app(Settings(environment=Environment.DEMO))
    client = TestClient(app)
    provider_page = TossPosMockProvider().read_offline_sales()
    assert provider_page.resource == "offline_sales"
    payload = provider_page.items[0]
    first = client.post("/api/v1/demo/events", json=payload)
    second = client.post("/api/v1/demo/events", json=payload)
    assert first.status_code == second.status_code == 202
    assert first.json()["status"] == "ACCEPTED"
    assert second.json()["status"] == "REPLAYED"

    response = client.get(
        "/api/v1/insights",
        headers={"x-request-id": "req_e2e", "x-trace-id": payload["correlation_id"]},
    )
    body = response.json()
    insight = body["data"][0]
    assert insight["calculation"]["expected_inventory"] == 7
    assert insight["correlation_id"] == payload["correlation_id"]
    assert app.state.pipeline.inbox.accepted_count == 1
    assert app.state.pipeline.inbox.replayed_count == 1
    assert app.state.pipeline.effects.business_effect_count == 1
    assert app.state.pipeline.external_write_count == 0
    assert all(payload["correlation_id"] in record for record in app.state.pipeline.trace)


def test_demo_event_api_denied_outside_demo() -> None:
    app = create_app(Settings(environment=Environment.PRODUCTION_READ))
    response = TestClient(app).post("/api/v1/demo/events", json=DEMO_SCENARIOS["offline_sale"])
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "POLICY_DENIED"

def test_day04_inquiry_http_to_ai_mock_preserves_trace_ids() -> None:
    app = create_app(Settings(environment=Environment.DEMO))
    client = TestClient(app)

    payload = DEMO_SCENARIOS["product_inquiry"]

    response = client.post(
        "/api/v1/demo/events",
        json=payload,
        headers={
            "x-request-id": "req_day04_inquiry_http",
            "x-trace-id": "trace_day04_inquiry_http",
        },
    )

    assert response.status_code == 202

    body = response.json()

    assert body["status"] == "ACCEPTED"
    assert body["request_id"] == "req_day04_inquiry_http"
    assert body["trace_id"] == "trace_day04_inquiry_http"

    assert (
        body["correlation_id"]
        == payload["correlation_id"]
    )

    assert len(app.state.pipeline.ai_results) == 1

    ai_result = app.state.pipeline.ai_results[0]

    assert (
        ai_result["request_id"]
        == "req_day04_inquiry_http"
    )

    assert (
        ai_result["trace_id"]
        == "trace_day04_inquiry_http"
    )

    assert "correlation_id" not in ai_result

    ai_trace = next(
        json.loads(record)
        for record in app.state.pipeline.trace
        if json.loads(record)["message"] == "mock_ai_inquiry_route"
    )
    assert ai_trace["request_id"] == "req_day04_inquiry_http"
    assert ai_trace["trace_id"] == "trace_day04_inquiry_http"
    assert ai_trace["correlation_id"] == payload["correlation_id"]

    assert ai_result["intent"] == "PRODUCT_INFO"
    assert ai_result["route"] == "RULE_SQL"

    assert ai_result["model"]["model_run_id"] is None
    assert ai_result["model"]["model_id"] is None

def test_day04_prohibited_inquiry_http_has_zero_external_actions() -> None:
    app = create_app(Settings(environment=Environment.DEMO))
    client = TestClient(app)

    payload = DEMO_SCENARIOS["risk_inquiry"]

    response = client.post(
        "/api/v1/demo/events",
        json=payload,
        headers={
            "x-request-id": "req_day04_prohibited_http",
            "x-trace-id": "trace_day04_prohibited_http",
        },
    )

    assert response.status_code == 202

    ai_result = app.state.pipeline.ai_results[0]

    assert ai_result["route"] == "POLICY_DENY"

    counters = app.state.pipeline.ai_consumer.runtime.counters

    assert counters.external_model_calls == 0
    assert counters.tool_calls == 0
    assert counters.provider_calls == 0
    assert counters.auto_send_count == 0

    assert app.state.pipeline.external_write_count == 0
