"""Historical aggregates only. No AI search/model/evaluation execution."""

import builtins
import json
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import Settings
from backend.app.main import create_app
from backend.app.services import corpus_restore as cr
from backend.app.services import retrieval_summary as rs

PATH = "/api/v1/retrieval/summary"


@pytest.fixture
def files(tmp_path, monkeypatch):
    paths = {}
    for module, names in (
        (rs, ("RESULT_PATH", "EXPERIMENT_MANIFEST_PATH", "EXPERIMENT_SNAPSHOT_PATH")),
        (cr, ("HANDOFF_PATH", "MANIFEST_PATH", "SNAPSHOT_PATH", "CORPUS_PATH")),
    ):
        for name in names:
            path = tmp_path / name
            path.write_bytes(getattr(module, name).read_bytes())
            monkeypatch.setattr(module, name, path)
            paths[name] = path
    return paths


def client(**settings):
    return TestClient(create_app(Settings(
        _env_file=None, environment="TEST", database_url="sqlite://", **settings,
    )))


def update(path, mutate):
    data = json.loads(path.read_bytes())
    mutate(data)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_real_aggregate_only_no_ai_invocation(monkeypatch):
    c = client()
    monkeypatch.setattr(c.app.state.retrieval_runtime, "_execute",
                        lambda *a: pytest.fail("summary must never search"))
    original = builtins.__import__

    def no_ai(name, *args, **kwargs):
        if name.startswith("ai."):
            pytest.fail("summary must not import AI runtime")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_ai)
    response = c.get(PATH)
    assert response.status_code == 200
    data = response.json()["data"]
    result = json.loads(rs.RESULT_PATH.read_bytes())
    handoff = json.loads(cr.HANDOFF_PATH.read_bytes())
    assert data["selection"] == {k: handoff["selection"][k] for k in ("method", "status")}
    assert data["query_count"] == result["query_count"]
    assert data["execution_count"] == result["execution_count"]
    assert data["all_executed"] is True and data["error_count"] == 0
    assert data["external_embedding_api_calls"] == (
        handoff["execution"]["external_embedding_api_calls"]
    )
    assert data["actual_retrieval_executed_in_experiment"] is True
    assert data["runtime_search_available"] is True
    assert data["actual_scale_retrieval_validation_required"] is True
    assert data["corpus_version"] is None
    assert data["experiment_snapshot"]["version"] == "r05-grounded-semantic-v2"
    assert data["runtime_snapshot"]["version"] == "r05-grounded-semantic-v3-metadata"
    for method in data["methods"]:
        expected = result["summaries"][method["method"]]
        for metric in rs.METRICS:
            assert method[metric] == expected[metric]
        assert method["full_evidence_numerator"] == expected["full_evidence_cases"]
        assert method["full_evidence_denominator"] == expected["answerable_cases"]
        assert method["execution_status"] == "EXECUTED"


@pytest.mark.parametrize("status", ["NOT_EXECUTED", "UNMEASURED", "HOLD", "NOT_APPLICABLE"])
def test_unmeasured_and_unexecuted_are_null(files, status):
    result = json.loads(files["RESULT_PATH"].read_bytes())
    handoff = json.loads(files["HANDOFF_PATH"].read_bytes())
    method = result["summaries"]["dense"]
    for field in (*rs.METRICS, "full_evidence_cases", "answerable_cases"):
        method[field] = None
    method["status"] = status
    if status == "NOT_EXECUTED":
        for row in result["rows"]:
            if row["method"] == "dense":
                row["executed"] = False
                row["latency_ms"] = None
        handoff["execution"]["all_executed"] = False
    handoff["results"]["dense"] = deepcopy(method)
    for name, value in (("RESULT_PATH", result), ("HANDOFF_PATH", handoff)):
        files[name].write_text(json.dumps(value), encoding="utf-8")
    data = client().get(PATH).json()["data"]
    dense = next(m for m in data["methods"] if m["method"] == "dense")
    assert all(dense[m] is None for m in rs.METRICS)
    assert dense["full_evidence_numerator"] is None
    assert set(dense["metric_status"].values()) == {status}
    if status == "NOT_EXECUTED":
        assert dense["executed"] is False and dense["execution_status"] == status


def test_absent_measurement_is_not_zero(files):
    for name, key in (("RESULT_PATH", "summaries"), ("HANDOFF_PATH", "results")):
        update(files[name], lambda d, key=key: d[key]["bm25"].pop("mean_latency_ms"))
    update(files["HANDOFF_PATH"], lambda d: d["execution"].pop("external_embedding_api_calls"))
    data = client().get(PATH).json()["data"]
    bm25 = next(m for m in data["methods"] if m["method"] == "bm25")
    assert bm25["mean_latency_ms"] is None
    assert bm25["metric_status"]["mean_latency_ms"] == "UNMEASURED"
    assert data["external_embedding_api_calls"] is None


@pytest.mark.parametrize("name", ["RESULT_PATH", "HANDOFF_PATH", "EXPERIMENT_MANIFEST_PATH"])
@pytest.mark.parametrize("corrupt", [False, True])
def test_unavailable_or_corrupt(files, name, corrupt):
    c = client()
    if corrupt:
        files[name].write_bytes(b"{broken")
    else:
        files[name].unlink()
    response = c.get(PATH)
    assert response.status_code == 503
    assert response.json()["detail"] == (
        "RETRIEVAL_SUMMARY_INVALID" if corrupt else "RETRIEVAL_SUMMARY_UNAVAILABLE"
    )


@pytest.mark.parametrize("name,key", [
    ("RESULT_PATH", "experiment_id"), ("HANDOFF_PATH", "handoff_id"),
])
def test_identity_mismatch(files, name, key):
    update(files[name], lambda d: d.update({key: "wrong"}))
    assert client().get(PATH).json() == {"detail": "RETRIEVAL_SUMMARY_IDENTITY_MISMATCH"}


@pytest.mark.parametrize("mutation", ["version", "hash", "metrics", "count", "selection"])
def test_inconsistency_fails_closed(files, mutation):
    if mutation == "version":
        update(files["EXPERIMENT_MANIFEST_PATH"], lambda d: d.update(snapshot_version="wrong"))
    elif mutation == "hash":
        update(files["HANDOFF_PATH"], lambda d: d["dataset"].update(snapshot_sha256="a" * 64))
    elif mutation == "metrics":
        update(files["RESULT_PATH"], lambda d: d["summaries"]["bm25"].update(mean_recall_at_5=0.1))
    elif mutation == "count":
        update(files["RESULT_PATH"], lambda d: d.update(execution_count=0))
    else:
        update(files["RESULT_PATH"], lambda d: d["dev_selection"].update(selected_method="dense"))
    assert client().get(PATH).status_code == 503


def test_no_questions_evidence_paths_or_final_data_exposed(files):
    sentinel = "PRIVATE_QUESTION_OR_GOLD_MUST_NOT_LEAK"
    update(files["RESULT_PATH"], lambda d: d.update(
        question=sentinel, expected_answer=sentinel, final12=sentinel,
    ))
    update(files["RESULT_PATH"], lambda d: d["rows"][0].update(
        query=sentinel, required_evidence=[{"secret": sentinel}],
    ))
    text = client().get(PATH).text
    for forbidden in (sentinel, "required_evidence", "expected_answer", "GE-D-001",
                      "dev_path", "snapshot_path", ".jsonl", "FINAL12", "final12"):
        assert forbidden not in text


@pytest.mark.parametrize("params", [
    {"path": "secret"}, {"artifact_path": "secret"}, {"url": "https://example.com"},
    {"tenant_id": "foreign"}, {"split": "FINAL12"},
])
def test_no_path_input(params):
    assert client().get(PATH, params=params).status_code == 422


def test_no_body_or_write():
    c = client()
    assert c.request("GET", PATH, json={"path": "secret"}).status_code == 422
    assert c.post(PATH, json={}).status_code == 405


def test_runtime_availability_is_separate():
    c = client()
    c.app.state.retrieval_runtime = None
    data = c.get(PATH).json()["data"]
    assert data["runtime_search_available"] is False
    assert data["actual_retrieval_executed_in_experiment"] is True
    other = client(retrieval_method="VECTOR").get(PATH).json()["data"]
    assert other["runtime_search_available"] is False


def test_tenant_boundary():
    assert client(tenant_id="foreign").get(PATH).status_code == 503


def test_focused_openapi():
    schema = client().get("/openapi.json").json()
    path = schema["paths"][PATH]
    assert set(path) == {"get"}
    assert set(path["get"]["responses"]) == {"200", "403", "422", "503"}
    assert "parameters" not in path["get"] and "requestBody" not in path["get"]
    fields = schema["components"]["schemas"]["DevSummary"]["properties"]
    assert not {"rows", "query", "expected_answer", "path"} & fields.keys()
