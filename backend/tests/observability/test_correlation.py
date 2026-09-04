import json

import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import Environment, Settings
from backend.app.core.observability import CorrelationContext, bind_context, structured_record
from backend.app.main import create_app
from backend.app.services.demo import DEMO_SCENARIOS


def test_context_is_searchable_across_flow() -> None:
    context = CorrelationContext(
        request_id="req_demo",
        trace_id="trace_demo",
        correlation_id="corr_demo",
        tenant_id="demo_store",
        environment="TEST",
        event_id="evt_demo",
    )
    with bind_context(context):
        first = json.loads(structured_record("inbox"))
        second = json.loads(structured_record("api", status="ok"))
    assert first["correlation_id"] == second["correlation_id"] == "corr_demo"
    assert first["tenant_id"] == second["tenant_id"] == "demo_store"
    assert first["request_id"] == second["request_id"] == "req_demo"
    assert first["trace_id"] == second["trace_id"] == "trace_demo"

def test_logger_rejects_sensitive_field_names() -> None:
    with pytest.raises(ValueError, match="unsafe field"):
        structured_record("bad", raw_payload="not logged")


@pytest.mark.parametrize(
    "field_name",
    [
        "authorization",
        "access_token",
        "provider_api_key",
        "password",
        "customer_address",
    ],
)
def test_logger_rejects_secret_and_pii_field_names(field_name: str) -> None:
    with pytest.raises(ValueError, match="unsafe field"):
        structured_record("bad", **{field_name: "must-not-be-logged"})


def test_logger_rejects_nested_sensitive_field_names() -> None:
    with pytest.raises(ValueError, match="unsafe field"):
        structured_record(
            "bad",
            metadata={"provider": {"headers": {"Authorization": "Bearer secret"}}},
        )


def test_logger_rejects_correlation_context_override() -> None:
    context = CorrelationContext(
        request_id="req_original",
        trace_id="trace_original",
        correlation_id="corr_original",
        tenant_id="demo_store",
        environment="TEST",
    )
    with bind_context(context):
        with pytest.raises(ValueError, match="cannot be overridden"):
            structured_record("bad", request_id="req_replaced")


def test_http_request_ids_are_preserved_in_pipeline_trace() -> None:
    app = create_app(Settings(environment=Environment.DEMO))
    client = TestClient(app)

    response = client.post(
        "/api/v1/demo/events",
        json=DEMO_SCENARIOS["offline_sale"],
        headers={
            "x-request-id": "req_day3_observability",
            "x-trace-id": "trace_day3_observability",
        },
    )

    assert response.status_code == 202

    body = response.json()
    assert body["request_id"] == "req_day3_observability"
    assert body["trace_id"] == "trace_day3_observability"

    trace_records = [json.loads(record) for record in app.state.pipeline.trace]

    assert trace_records

    for record in trace_records:
        assert record["request_id"] == "req_day3_observability"
        assert record["trace_id"] == "trace_day3_observability"
        assert record["correlation_id"] == DEMO_SCENARIOS["offline_sale"]["correlation_id"]
        assert record["tenant_id"] == DEMO_SCENARIOS["offline_sale"]["tenant_id"]
        assert record["environment"] == "DEMO"
