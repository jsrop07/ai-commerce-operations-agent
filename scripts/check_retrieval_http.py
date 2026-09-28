"""Real loopback Uvicorn HTTP C2 verification in two isolated Demo processes.

No TestClient, existing DB, provider calls, or public listener. Server telemetry
and HTTP evidence are written to docs. The parent stops only children it owns.
"""

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
SEARCH = "/api/v1/retrieval/search"
LOOKUP = "/api/v1/c04/lookup"
QUERY = "황혼의 요새 확장 세트만으로 게임할 수 있어?"


def server(port, generation):
    from scripts.check_retrieval_runtime import NoModels

    guard = NoModels()
    sys.meta_path.insert(0, guard)
    counters = {"RetrievalService.search": 0, "BM25Index.search": 0,
                "DenseIndex.search": 0, "LLM": 0, "embedding_model_load": 0,
                "external_embedding_api_calls": 0, "external_network_attempts": 0}
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def allowed(address):
        if isinstance(address, tuple) and address[0] not in {"127.0.0.1", "::1", "localhost"}:
            counters["external_network_attempts"] += 1
            raise RuntimeError("External network denied in C2")

    def connect(sock, address):
        allowed(address)
        return original_connect(sock, address)

    def connect_ex(sock, address):
        allowed(address)
        return original_connect_ex(sock, address)

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    # Explicitly isolate even the module-level default application.
    os.environ.update(ENVIRONMENT="DEMO", DATABASE_URL="sqlite://", TENANT_ID="demo_store",
                      WRITE_MODE="disabled", GLOBAL_WRITE_KILL="true")
    import uvicorn

    from ai.retrieval.bm25 import BM25Index
    from ai.services.retrieval_service import RetrievalService
    from backend.app.core.config import Settings
    from backend.app.main import create_app

    original_service, original_index = RetrievalService.search, BM25Index.search

    def service(self, request):
        counters["RetrievalService.search"] += 1
        assert self._dense_index is None
        return original_service(self, request)

    def index(self, query, **kwargs):
        counters["BM25Index.search"] += 1
        return original_index(self, query, **kwargs)

    RetrievalService.search, BM25Index.search = service, index
    app = create_app(Settings(_env_file=None, environment="DEMO", tenant_id="demo_store",
                              database_url="sqlite://", log_level="WARNING"))
    telemetry_path = ROOT / f"docs/retrieval_http_generation_{generation}.json"
    requests = []

    def save():
        telemetry_path.write_text(json.dumps({
            "pid": os.getpid(), "generation": generation, "environment": "DEMO",
            "database": "isolated in-memory SQLite; no existing database",
            "counters": counters, "requests": requests,
            "forbidden_import_attempts": guard.attempts,
            "dense_module_loaded": "ai.retrieval.dense" in sys.modules,
            "restore_status": app.state.c04_corpus_restore.status,
        }, indent=2), encoding="utf-8")

    @app.middleware("http")
    async def observe(request, call_next):
        before = counters["RetrievalService.search"]
        response = await call_next(request)
        requests.append({"method": request.method, "path": request.url.path,
                         "status": response.status_code,
                         "retrieval_calls_delta": counters["RetrievalService.search"] - before})
        save()
        return response

    runner = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port,
                                         log_level="warning", access_log=False))

    def stop_on_stdin():
        sys.stdin.readline()
        runner.should_exit = True

    Thread(target=stop_on_stdin, daemon=True).start()
    try:
        runner.run()
    finally:
        save()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", action="store_true")
    parser.add_argument("--port", type=int)
    parser.add_argument("--generation", type=int)
    args = parser.parse_args()
    if args.server:
        server(args.port, args.generation)
        return
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    opener = build_opener(ProxyHandler({}))

    def http(method, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        request = Request(base + path, data=data, method=method,
                          headers={"Content-Type": "application/json"})
        try:
            response = opener.open(request, timeout=10)
        except HTTPError as exc:
            response = exc
        with response:
            return {"status": response.status, "body": json.loads(response.read())}

    def start(generation):
        log = (ROOT / f"docs/retrieval_http_generation_{generation}.log").open("w")
        child = subprocess.Popen(
            [sys.executable, "-m", "scripts.check_retrieval_http", "--server", "--port", str(port),
             "--generation", str(generation)], cwd=ROOT, stdin=subprocess.PIPE,
            stdout=log, stderr=log, text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            for _ in range(150):
                if child.poll() is not None:
                    raise AssertionError("Isolated server exited during startup")
                try:
                    if http("GET", "/api/v1/health")["status"] == 200:
                        return child, log
                except (URLError, TimeoutError):
                    pass
                time.sleep(0.1)
            raise AssertionError("Isolated server startup deadline exceeded")
        except BaseException:
            stop(child, log)
            raise

    def stop(child, log):
        try:
            if child.poll() is None:
                child.stdin.write("stop\n")
                child.stdin.flush()
                try:
                    child.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    child.terminate()
                    child.wait(timeout=5)
        finally:
            child.stdin.close()
            log.close()

    request_body = {"query": QUERY, "top_k": 5, "method": "BM25"}
    child, log = start(1)
    try:
        search = http("POST", SEARCH, request_body)
        assert search["status"] == 200
        data = search["body"]["data"]
        assert data["actual_retrieval_executed"] is True
        assert data["method"] == "BM25" and data["selection_status"] == "PROVISIONAL_DEV_SELECTION"
        assert data["data_mode"] == "SYNTHETIC_DEMO" and data["citations"]
        citation = next(c for c in data["citations"] if c["source_id"] == "product_demo_long_003")
        key = citation["c04_lookup"]
        exact = http("GET", LOOKUP + "?" + urlencode(key))
        assert exact["status"] == 200
        for name in ("source_id", "version", "chunk_id"):
            assert exact["body"]["data"][name] == key[name]
        assert exact["body"]["data"]["excerpt"]
        assert exact["body"]["data"]["excerpt_hash"] == citation["c04_excerpt_hash"]
        summary = http("GET", "/api/v1/retrieval/summary")
        assert summary["status"] == 200
        aggregate = summary["body"]["data"]
        assert aggregate["selection"] == {"method": "bm25", "status": "PROVISIONAL_DEV_SELECTION"}
        assert (aggregate["query_count"], aggregate["execution_count"], aggregate["error_count"]
                ) == (24, 72, 0)
        assert aggregate["all_executed"] is True
        assert aggregate["actual_scale_retrieval_validation_required"] is True
        assert aggregate["data_mode"] == "SYNTHETIC_DEMO"
        bm25 = next(m for m in aggregate["methods"] if m["method"] == "bm25")
        assert (bm25["mean_recall_at_5"], bm25["mean_mrr_at_5"],
                bm25["full_evidence_numerator"], bm25["full_evidence_denominator"]
                ) == (1.0, 0.9375, 16, 16)
        invalid = http("POST", SEARCH, {"query": ""})
        assert invalid["status"] == 422
        blocked = []
        for value in ("order_id=synthetic", "customer_id=synthetic", "inquiry: synthetic",
                      "payment_id=synthetic", "shipping_id=synthetic",
                      "affected_order_ids=synthetic", "reservation_id=synthetic"):
            response = http("POST", SEARCH, {"query": value})
            assert response["status"] == 403
            blocked.append(response)
        stale = http("POST", SEARCH, {"query": "확보수량", "source_type": "INVENTORY_SNAPSHOT"})
        assert stale["status"] == 200
        assert stale["body"]["data"]["answer_status"] == "HOLD"
        assert "STALE_EVIDENCE" in stale["body"]["data"]["human_review_reason"]
    finally:
        stop(child, log)
    first_exit = child.returncode
    child, log = start(2)
    try:
        restored = http("GET", LOOKUP + "?" + urlencode(key))
        assert restored["status"] == 200
        assert restored["body"]["data"] == exact["body"]["data"]
    finally:
        stop(child, log)
    telemetry = [json.loads((ROOT / f"docs/retrieval_http_generation_{n}.json").read_bytes())
                 for n in (1, 2)]
    assert telemetry[0]["pid"] != telemetry[1]["pid"]
    assert telemetry[0]["counters"]["BM25Index.search"] == 2
    assert telemetry[0]["counters"]["RetrievalService.search"] == 2
    assert telemetry[1]["counters"]["BM25Index.search"] == 0
    for run in telemetry:
        assert not run["forbidden_import_attempts"] and not run["dense_module_loaded"]
        assert run["restore_status"] == "READY"
        for name in ("DenseIndex.search", "LLM", "embedding_model_load",
                     "external_embedding_api_calls", "external_network_attempts"):
            assert run["counters"][name] == 0
        assert all(r["retrieval_calls_delta"] == 0 for r in run["requests"]
                   if r["status"] in {403, 422})
    report = {"transport": "real loopback HTTP / Uvicorn", "base_url": base,
              "environment": "DEMO / isolated in-memory SQLite / existing PostgreSQL untouched",
              "request_body": request_body, "search": search, "selected_citation": citation,
              "c04_before_restart": exact, "c04_after_restart": restored,
              "restore_mechanism": "canonical v3 file-based reload; not DB persistence",
              "summary": summary, "invalid": invalid, "blocked": blocked, "stale": stale,
              "telemetry": telemetry, "server_exit_codes": [first_exit, child.returncode]}
    (ROOT / "docs/retrieval_http_c2.json").write_text(
        json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8",
    )
    print(json.dumps({"result": "PASS", "base_url": base,
                      "request_id": search["body"]["request_id"],
                      "citation": {k: citation[k] for k in (
                          "rank", "score", "source_type", "source_id", "version",
                          "semantic_chunk_id", "semantic_excerpt_hash", "c04_lookup",
                          "c04_excerpt_hash",
                      )}, "server_exit_codes": report["server_exit_codes"]}, indent=2))


if __name__ == "__main__":
    main()
