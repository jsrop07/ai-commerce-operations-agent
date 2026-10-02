"""C06 Backend boundary tests. Every provider result here is a fake."""

from dataclasses import replace
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from ai.services.grounded_explanation_output import (
    ClaimCitation,
    ExplanationStatus,
    GroundedExplanationOutput,
    NumericFact,
)
from ai.services.grounded_explanation_provider import (
    GroundedProviderResult,
    ProviderReceipt,
    ProviderUsage,
)
from backend.app.core.config import Settings
from backend.app.main import create_app
from backend.app.services.grounded_explanation_bridge import (
    explain_policy,
    forbidden_structure,
)

QUESTION = "예약상품은 언제 출고해?"
EXCERPT = "예약상품은 상품 입고와 검수 완료 후 순차적으로 출고합니다."
PATH = "/api/v1/retrieval/explanations"
TEST_CRED = "dummy-test-" + "credential"

class Lookup:
    def __init__(self, *, stale=False, tenant="tenant", version="v1"):
        self.stale, self.tenant, self.version = stale, tenant, version

    def lookup(self, *, tenant_id, source_id, version):
        if tenant_id != self.tenant or version != self.version:
            raise ValueError("mismatch")
        return SimpleNamespace(
            data_mode="SYNTHETIC_DEMO", visibility="DEMO_PUBLIC",
            source_type=("INCOMING_STOCK" if source_id.startswith("incoming")
                         else "POLICY"), stale=self.stale, as_of=None,
            chunk_id="c1",
        )


def citation(*, source_id="policy-1", excerpt=EXCERPT):
    return dict(
        source_type="POLICY", source_id=source_id, version="v1",
        semantic_excerpt=excerpt, mapping_status="MAPPED",
        c04_lookup=dict(source_id=source_id, version="v1", chunk_id="c1"),
    )


def incoming():
    item = citation(source_id="incoming-1", excerpt=(
        "상태는 TENTATIVE이며 아직 확정입고가 아닙니다."))
    item["source_type"] = "INCOMING_STOCK"
    return item


def projection(citations=None):
    return dict(data_mode="SYNTHETIC_DEMO",
                citations=[citation()] if citations is None else citations)


def answer(**changes):
    output = GroundedExplanationOutput(
        status=ExplanationStatus.ANSWER, conclusion=EXCERPT,
        used_facts=(EXCERPT,), citations=(ClaimCitation("policy-1", "v1"),),
        next_check=None,
    )
    return replace(output, **changes)


def fake_result(output=None):
    return GroundedProviderResult(
        output=answer() if output is None else output,
        model_used=True,
        receipt=ProviderReceipt(
            provider="openai", model="gpt-5.6-luna",
            response_id="resp_FAKE_001", latency_ms=2.0,
            attempts=1, retries=0,
            usage=ProviderUsage(input_tokens=10, cached_input_tokens=0,
                                output_tokens=5),
        ),
    )


def run(*, p=None, lookup=None, provider=None, question=QUESTION):
    calls = []

    def fake(model_input, *, condition):
        calls.append((model_input, condition))
        return provider(model_input, condition) if provider else fake_result()

    result = explain_policy(
        question=question, condition="CITATION",
        projection=projection() if p is None else p,
        lookup_service=lookup or Lookup(), tenant_id="tenant",
        request_id="req_test", provider=fake,
    )
    return result, calls


def test_supported_claim_calls_fake_once_and_filters_evidence():
    p = projection([citation(), citation(
        source_id="irrelevant", excerpt="교환 신청 정책입니다.")])
    result, calls = run(p=p)
    assert result["status"] == "ANSWER" and result["model_used"] is True
    assert len(calls) == 1 and calls[0][1] == "CITATION"
    model_input = calls[0][0]
    assert [item.source_id for item in model_input.evidence] == ["policy-1"]
    assert model_input.required_qty is None
    assert not forbidden_structure(model_input.to_dict())


@pytest.mark.parametrize("question,items,expected", [
    ("잠정입고가 3개 있는데 왜 예약 부족수량에서 안 빼?", [citation(
        excerpt=("잠정입고 수량은 아직 확정되지 않았으므로 "
                 "예약 부족수량 차감에 사용하지 않습니다."))],
     {"policy-1"}),
    ("잠정입고 상태인 물량을 근거로 예약상품 출고 준비가 끝났다고 봐도 돼?",
     [incoming(), citation()], {"incoming-1", "policy-1"}),
])
def test_other_supported_claims(question, items, expected):
    def matching_output(model_input, _condition):
        citations = tuple(ClaimCitation(x.source_id, x.version)
                          for x in model_input.evidence)
        return fake_result(answer(citations=citations))
    result, calls = run(question=question, p=projection(items), provider=matching_output)
    assert result["status"] == "ANSWER" and len(calls) == 1
    assert {item.source_id for item in calls[0][0].evidence} == expected


@pytest.mark.parametrize("p,lookup,question,reason", [
    (projection(), Lookup(), "이 상품 재밌어?", "UNSUPPORTED_CLAIM"),
    (projection([citation(excerpt="교환 정책입니다.")]), Lookup(), QUESTION,
     "CLAIM_SUPPORT_INSUFFICIENT"),
    (projection([incoming()]), Lookup(),
     "잠정입고 상태인 물량을 근거로 예약상품 출고 준비가 끝났다고 봐도 돼?",
     "CLAIM_SUPPORT_INSUFFICIENT:RESERVATION_SHIPPING_POLICY"),
    (projection([]), Lookup(), QUESTION, "NO_SOURCE"),
    (projection(), Lookup(stale=True), QUESTION, "STALE_EVIDENCE"),
    (projection(), Lookup(tenant="other"), QUESTION, "TARGET_UNVERIFIED"),
    (projection(), Lookup(version="v2"), QUESTION, "TARGET_UNVERIFIED"),
    (projection([{**citation(), "mapping_status": "MAPPING_MISSING",
                 "c04_lookup": None}]), Lookup(), QUESTION, "MAPPING_AMBIGUOUS"),
    (projection([{**citation(), "c04_lookup": {
        **citation()["c04_lookup"], "chunk_id": "wrong"}}]),
     Lookup(), QUESTION, "MAPPING_AMBIGUOUS"),
    ({**projection(), "data_mode": "PRODUCTION"}, Lookup(), QUESTION,
     "RUNTIME_UNAVAILABLE"),
    (projection([citation(), {**citation(), "version": "v2"}]), Lookup(),
     QUESTION, "SOURCE_CONFLICT"),
    ({**projection(), "order_id": "secret-canary"}, Lookup(), QUESTION,
     "FORBIDDEN_INPUT"),
    ({**projection(), "nested": [{"order_line_id": "secret-canary"}]},
     Lookup(), QUESTION, "FORBIDDEN_INPUT"),
])
def test_prehold_never_calls_provider(p, lookup, question, reason):
    result, calls = run(p=p, lookup=lookup, question=question)
    assert result["status"] == "HOLD" and result["model_used"] is False
    assert result["warnings"][0].startswith(reason)
    assert not calls and "secret-canary" not in str(result)


@pytest.mark.parametrize("output", [
    answer(used_numeric_facts=(NumericFact("required_qty", 3),)),
    answer(used_numeric_facts=(NumericFact("required_qty", 0),)),
    answer(citations=(ClaimCitation("false", "v9"),)),
    answer(conclusion="잠정입고는 확정입고로 봅니다"),
    {"broken": True},
])
def test_post_validator_blocks_invalid_fake_output(output):
    result, calls = run(provider=lambda *_: fake_result(output))
    assert result["status"] == "HOLD" and result["model_used"] is True
    assert len(calls) == 1


@pytest.mark.parametrize("error", [TimeoutError("canary"), RuntimeError("canary")])
def test_fake_provider_failures_hold(error):
    def failing(*_):
        raise error
    result, calls = run(provider=failing)
    assert result["status"] == "HOLD" and result["model_used"] is True
    assert len(calls) == 1 and "canary" not in str(result)


def test_http_default_wiring_uses_ai_runtime_replacement(monkeypatch, caplog):
    import backend.app.services.grounded_explanation_bridge as bridge
    from ai.services.grounded_explanation_provider import run_grounded_explanation

    assert bridge.run_grounded_explanation is run_grounded_explanation
    caplog.set_level("INFO", logger=bridge.__name__)
    
    app = create_app(Settings(
        _env_file=None, environment="TEST", database_url="sqlite://",
        openai_api_key=TEST_CRED
    ))
    async def search(_):
        return SimpleNamespace(request_id="req_search"), projection()
    monkeypatch.setattr(app.state.retrieval_runtime, "search", search)
    app.state.c04_lookup_service = Lookup(tenant=app.state.settings.tenant_id)
    calls = []

    clients = []

    def fake_client(*, api_key, max_retries):
        assert api_key == TEST_CRED and max_retries == 0
        client = object()
        clients.append(client)
        return client

    def fake_ai_runtime(model_input, *, condition, client):
        calls.append((model_input, condition, client))
        return fake_result()

    monkeypatch.setattr(bridge, "OpenAI", fake_client)
    monkeypatch.setattr(bridge, "run_grounded_explanation", fake_ai_runtime)
    client = TestClient(app)
    response = client.post(PATH, json={"question": QUESTION, "condition": "CITATION"})
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "ANSWER"
    assert response.json()["data"]["model_used"] is True
    assert len(calls) == 1 and calls[0][1] == "CITATION"
    assert calls[0][0].question == QUESTION
    assert calls[0][2] is clients[0]
    assert response.json()["request_id"] in caplog.text
    assert "resp_FAKE_001" in caplog.text

    for payload, reason in (
        ({"question": "이 상품 재밌어?"}, "UNSUPPORTED_CLAIM"),
        ({"question": QUESTION, "scope": "C02_AGGREGATE"},
         "NOT_SUPPORTED_C02_RUNTIME_SOURCE_MISSING"),
        ({"question": QUESTION, "nested": {"order_line_id": "secret-canary"}},
         "FORBIDDEN_INPUT"),
    ):
        held = client.post(PATH, json=payload)
        assert held.status_code == 200
        assert held.json()["data"]["status"] == "HOLD"
        assert held.json()["data"]["model_used"] is False
        assert held.json()["data"]["warnings"][0] == reason
        assert "secret-canary" not in held.text
    assert len(calls) == 1

    for error in (TimeoutError("canary"), RuntimeError("canary")):
        def failing(*_, error=error, **__):
            raise error
        monkeypatch.setattr(bridge, "run_grounded_explanation", failing)
        failed = client.post(PATH, json={"question": QUESTION})
        assert failed.status_code == 200
        assert failed.json()["data"]["status"] == "HOLD"
        assert failed.json()["data"]["model_used"] is True
        assert client.get("/api/v1/inventory").status_code == 200
        assert client.get("/api/v1/reservations").status_code == 200


def test_settings_secret_contract(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", TEST_CRED)
    settings = Settings(_env_file=None, environment="TEST", database_url="sqlite://")
    assert isinstance(settings.openai_api_key, SecretStr)
    assert settings.openai_api_key.get_secret_value() == "dummy-test-credential"
    assert "dummy-test-credential" not in repr(settings)
    assert "dummy-test-credential" not in str(settings)


def test_missing_credential_holds_before_client_or_provider(monkeypatch, caplog):
    import backend.app.services.grounded_explanation_bridge as bridge

    def forbidden(*_, **__):
        pytest.fail("provider or client must not be called")

    monkeypatch.setattr(bridge, "OpenAI", forbidden)
    monkeypatch.setattr(bridge, "run_grounded_explanation", forbidden)
    caplog.set_level("INFO", logger=bridge.__name__)
    result = explain_policy(
        question=QUESTION, condition="CITATION", projection=projection(),
        lookup_service=Lookup(), tenant_id="tenant", request_id="req_missing",
        settings=Settings(_env_file=None, openai_api_key=None),
    )
    assert result["status"] == "HOLD"
    assert result["warnings"] == ["RUNTIME_UNAVAILABLE"]
    assert result["model_used"] is False
    assert "C06 OpenAI credential configured=false" in caplog.text
    assert "dummy-test-credential" not in str(result) + caplog.text
    app = create_app(Settings(
        _env_file=None, environment="TEST", database_url="sqlite://",
        openai_api_key=None,
    ))
    response = TestClient(app).post(PATH, json={"question": QUESTION})
    assert response.status_code == 200
    assert response.json()["data"]["warnings"] == ["RUNTIME_UNAVAILABLE"]
    assert response.json()["data"]["model_used"] is False


def test_http_real_c05_retrieval_with_fake_provider():
    app = create_app(Settings(_env_file=None, environment="TEST", database_url="sqlite://"))
    calls = []

    def fake(model_input, *, condition):
        calls.append((model_input, condition))
        evidence = model_input.evidence[0]
        output = answer(citations=(ClaimCitation(evidence.source_id, evidence.version),))
        return fake_result(output)

    app.state.c06_provider = fake
    response = TestClient(app).post(PATH, json={"question": QUESTION})
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "ANSWER"
    assert response.json()["data"]["model_used"] is True
    assert len(calls) == 1
