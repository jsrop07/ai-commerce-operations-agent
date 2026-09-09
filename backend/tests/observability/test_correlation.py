import json
import logging

import httpx

import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import Environment, Settings
from backend.app.core.observability import (
    CAFE24_OAUTH_QUERY_STATE_KEY, CorrelationContext,
    RedactCafe24OAuthQueryMiddleware, bind_context, configure_logging,
    structured_record,
)
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


def test_httpx_info_logs_do_not_expose_provider_urls(caplog) -> None:
    synthetic_order_id = "SYNTHETIC-ORDER-LOG-001"
    synthetic_attachment_url = (
        "https://forplus.co.kr/synthetic/file.pdf?signature=synthetic-query"
    )

    caplog.set_level(logging.INFO)
    configure_logging("INFO")
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, request=request, json={})
    )
    with httpx.Client(transport=transport) as client:
        client.get(
            f"https://synthetic-mall.cafe24api.com/api/v2/admin/orders/"
            f"{synthetic_order_id}/items"
        )
        client.get(synthetic_attachment_url)

    captured = caplog.text
    assert synthetic_order_id not in captured
    assert synthetic_attachment_url not in captured
    assert "signature=synthetic-query" not in captured

def test_oauth_query_middleware_redacts_uvicorn_visible_scope(caplog) -> None:
    captured: dict[str, object] = {}

    async def downstream(scope, receive, send):
        captured["query_string"] = scope["query_string"]
        captured["oauth_query"] = scope["state"][CAFE24_OAUTH_QUERY_STATE_KEY]
        logging.getLogger("uvicorn.access").info("target=%r", scope["query_string"])
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    synthetic_code = "synthetic-code-visible-only-in-memory"
    synthetic_state = "synthetic-state-visible-only-in-memory"
    caplog.set_level(logging.INFO)
    configure_logging("INFO")
    client = TestClient(RedactCafe24OAuthQueryMiddleware(downstream))
    response = client.get(
        "/internal/cafe24/oauth/callback",
        params={"code": synthetic_code, "state": synthetic_state},
    )
    assert response.status_code == 204
    assert captured["query_string"] == b""
    assert captured["oauth_query"] == {"code": synthetic_code, "state": synthetic_state}
    assert synthetic_code not in caplog.text
    assert synthetic_state not in caplog.text