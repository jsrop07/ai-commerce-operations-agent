"""Focused runtime boundary checks. Substituted responses are explicitly canaries."""

import json
import subprocess
import sys
from dataclasses import replace
from threading import Event
from types import MappingProxyType

import pytest
from fastapi.testclient import TestClient

from ai.retrieval.bm25 import BM25Index
from ai.services.retrieval_service import RetrievalRequest, RetrievalService
from backend.app.core.config import Settings
from backend.app.main import create_app

PATH = "/api/v1/retrieval/search"
QUERY = "황혼의 요새 확장 세트 기본 세트"


def client(**settings):
    return TestClient(create_app(Settings(
        _env_file=None, environment="TEST", database_url="sqlite://", **settings,
    )))


def test_real_bm25_and_exact_readback(monkeypatch):
    calls = []
    original_service = RetrievalService.search
    original_index = BM25Index.search

    def service(self, request):
        calls.append("RetrievalService.search")
        assert self._dense_index is None
        return original_service(self, request)

    def index(self, query, **kwargs):
        calls.append("BM25Index.search")
        assert self.document_count == 15
        assert {d.metadata["tenant_id"] for d in self.documents} == {"demo_store"}
        assert {d.metadata["visibility"] for d in self.documents} == {"DEMO_PUBLIC"}
        return original_index(self, query, **kwargs)

    monkeypatch.setattr(RetrievalService, "search", service)
    monkeypatch.setattr(BM25Index, "search", index)
    c = client()
    response = c.post(PATH, json={"query": QUERY, "top_k": 1})
    assert response.status_code == 200
    body = response.json()
    data = body["data"]
    assert calls == ["RetrievalService.search", "BM25Index.search"]
    assert body["request_id"] and body["trace_id"]
    assert data["actual_retrieval_executed"] is True
    assert data["method"] == "BM25"
    assert data["selection_status"] == "PROVISIONAL_DEV_SELECTION"
    assert data["index_version"] == "r05-grounded-semantic-v3-metadata"
    citation = data["citations"][0]
    exact = c.get("/api/v1/c04/lookup", params=citation["c04_lookup"])
    assert exact.status_code == 200
    assert citation["source_id"] == exact.json()["data"]["source_id"]
    assert citation["c04_excerpt_hash"] == exact.json()["data"]["excerpt_hash"]
    assert citation["semantic_chunk_id"] != citation["c04_lookup"]["chunk_id"]


@pytest.mark.parametrize("payload", [
    {}, {"query": ""}, {"query": "   "}, {"query": "x" * 2001},
    {"query": 42}, {"query": "ok", "top_k": 0}, {"query": "ok", "top_k": 51},
    {"query": "ok", "top_k": True}, {"query": "ok", "top_k": "5"},
    {"query": "ok", "method": "hybrid"}, {"query": "ok", "method": "VECTOR"},
    {"query": "ok", "tenant_id": "other"}, {"query": "ok", "source_type": "ORDER_STATUS"},
    {"query": "ok", "snapshot_path": "file"}, {"query": "ok", "filters": {"customer": "a"}},
])
def test_validation_before_ai(monkeypatch, payload):
    monkeypatch.setattr(RetrievalService, "search", lambda *a: pytest.fail("must not search"))
    assert client().post(PATH, json=payload).status_code == 422


@pytest.mark.parametrize("top_k", [1, 5, 50])
def test_top_k_bounds(top_k):
    response = client().post(PATH, json={"query": QUERY, "top_k": top_k})
    assert response.status_code == 200
    assert len(response.json()["data"]["citations"]) <= top_k


@pytest.mark.parametrize("query", [
    "order_id=123", "order_line=123", "customer_id=123", "배송지 서울", "결제정보 조회",
    "inquiry: private text", "affected_order_ids 123", "reservation_id=123",
    "feedback: private memo", "주문번호 20260927-123456", "20260927-123456 조회",
    "order #12345", "customer: Jane", "ORD-123456", "010-" + "1234-5678",
    "jane@" + "example.com", "order\u200b_id=123", "ｏｒｄｅｒ＿ｉｄ＝123",
])
def test_private_query_blocked_before_index(monkeypatch, query):
    monkeypatch.setattr(BM25Index, "__init__", lambda *a: pytest.fail("must not build index"))
    response = client().post(PATH, json={"query": query})
    assert response.status_code == 403
    assert response.json() == {"detail": "RETRIEVAL_SAFETY_BLOCKED"}


def test_general_order_policy_allowed():
    assert client().post(PATH, json={"query": "general order shipping policy"}).status_code == 200


def test_tenant_and_production_boundaries(monkeypatch):
    monkeypatch.setattr(RetrievalService, "search", lambda *a: pytest.fail("must not search"))
    assert client(tenant_id="foreign").post(PATH, json={"query": QUERY}).status_code == 503
    app = create_app(Settings(_env_file=None, environment="PRODUCTION_READ", database_url="sqlite://"))
    assert TestClient(app).post(PATH, json={"query": QUERY}).status_code == 503


def test_server_tenant_ignores_header():
    response = client().post(PATH, json={"query": QUERY}, headers={"X-Tenant-ID": "foreign"})
    assert response.json()["tenant_id"] == "demo_store"


def test_source_filter_and_stale_preserved():
    data = client().post(PATH, json={
        "query": "확보수량", "source_type": "INVENTORY_SNAPSHOT",
    }).json()["data"]
    assert {c["source_type"] for c in data["citations"]} == {"INVENTORY_SNAPSHOT"}
    assert data["answer_status"] == "HOLD"
    assert "STALE_EVIDENCE" in data["human_review_reason"]
    assert data["citations"][0]["as_of"] is not None


def test_missing_mapping_does_not_fabricate_key():
    c = client()
    runtime = c.app.state.retrieval_runtime
    runtime.corpus = replace(runtime.corpus, mappings=MappingProxyType({}))
    data = c.post(PATH, json={"query": QUERY, "top_k": 1}).json()["data"]
    assert data["citations"][0]["c04_lookup"] is None
    assert data["citations"][0]["mapping_status"] == "MAPPING_MISSING"


def test_zero_results_contract_canary(monkeypatch):
    # AI service executes, but index results are deliberately empty: not a real DEV outcome.
    monkeypatch.setattr(BM25Index, "search", lambda *a, **k: [])
    data = client().post(PATH, json={"query": QUERY}).json()["data"]
    assert data["citations"] == [] and data["result_status"] == "ZERO_CITATIONS"
    assert data["answer_status"] == "INSUFFICIENT_EVIDENCE"
    assert "NO_SOURCE" not in str(data)


@pytest.mark.parametrize("reason", [
    "MAPPING_AMBIGUOUS", "SOURCE_CONFLICT", "ORDER_LINKED_LOOKUP_FORBIDDEN",
])
def test_safety_projection_canary(monkeypatch, reason):
    original = RetrievalService.search

    def canary(self, request):
        return replace(original(self, request), answer_status="HUMAN_REVIEW",
                       warnings=("test-warning",), human_review_required=True,
                       human_review_reason=(reason,), required_lookup=("test-lookup",))

    monkeypatch.setattr(RetrievalService, "search", canary)
    data = client().post(PATH, json={"query": QUERY}).json()["data"]
    assert data["answer_status"] == "HUMAN_REVIEW"
    assert data["human_review_required"] is True
    assert data["human_review_reason"] == [reason]
    assert data["warnings"] == ["test-warning"]
    assert data["required_lookup"] == ["test-lookup"]


def test_runtime_and_index_unavailable():
    c = client()
    c.app.state.retrieval_runtime = None
    assert c.post(PATH, json={"query": QUERY}).json()["detail"] == "RETRIEVAL_RUNTIME_UNAVAILABLE"
    response = client(retrieval_method="VECTOR").post(PATH, json={"query": QUERY})
    assert response.status_code == 503
    assert response.json()["detail"] == "RETRIEVAL_INDEX_UNAVAILABLE"


def test_timeout_canary_discards_late_output(monkeypatch):
    release, started, finished = Event(), Event(), Event()
    c = client(retrieval_timeout_seconds=0.05)
    runtime = c.app.state.retrieval_runtime

    def delayed(request):
        started.set()
        try:
            release.wait(2)
            return None, {"canary": True}
        finally:
            finished.set()

    monkeypatch.setattr(runtime, "_execute", delayed)
    with c:
        try:
            response = c.post(PATH, json={"query": QUERY})
            assert started.is_set()
            assert response.status_code == 504
            assert response.json() == {"detail": "RETRIEVAL_TIMEOUT"}
            assert c.post(PATH, json={"query": QUERY}).status_code == 503
        finally:
            release.set()
            assert finished.wait(2)


def test_optional_index_fails_explicitly_without_dense():
    with pytest.raises(RuntimeError, match="RETRIEVAL_INDEX_UNAVAILABLE"):
        RetrievalService().search(RetrievalRequest(query="test"))
    with pytest.raises(RuntimeError, match="RETRIEVAL_INDEX_UNAVAILABLE"):
        RetrievalService().search(RetrievalRequest(query="test", method="VECTOR"))


def test_focused_openapi_contract():
    schema = client().get("/openapi.json").json()
    operation = schema["paths"][PATH]
    assert set(operation) == {"post"}
    assert set(operation["post"]["responses"]) == {"200", "403", "422", "503", "504"}
    request = schema["components"]["schemas"]["SearchInput"]
    assert request["additionalProperties"] is False
    assert set(request["properties"]) == {"query", "top_k", "method", "source_type"}


def test_fresh_process_real_dev_smoke_no_dense_or_external_embedding():
    completed = subprocess.run(
        [sys.executable, "-m", "scripts.check_retrieval_runtime"],
        capture_output=True, text=True, check=True, timeout=30,
    )
    report = json.loads(completed.stdout)
    assert report["real_call_counts"]["RetrievalService.search"] == 1
    assert report["real_call_counts"]["BM25Index.search"] == 1
    assert report["external_embedding_calls"] == 0
    assert report["forbidden_import_attempts"] == []
