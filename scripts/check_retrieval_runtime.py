"""One real DEV runtime/readback smoke with model imports and outbound sockets denied.

Run: ai_venv\Scripts\python.exe -m scripts.check_retrieval_runtime
No experiment summary, expected-answer scoring, or FINAL data is used.
"""

import importlib.abc
import json
import socket
import sys
from pathlib import Path
from unittest.mock import patch


class NoModels(importlib.abc.MetaPathFinder):
    attempts = []

    def find_spec(self, fullname, path=None, target=None):
        if fullname == "ai.retrieval.dense" or fullname.split(".")[0] in {
            "sentence_transformers", "transformers", "torch", "numpy",
        }:
            self.attempts.append(fullname)
            raise AssertionError(f"Forbidden model import: {fullname}")


def main():
    guard = NoModels()
    sys.meta_path.insert(0, guard)
    calls = {"RetrievalService.search": 0, "BM25Index.search": 0, "external_network": 0}
    original_connect = socket.socket.connect

    def connect(sock, address):
        if isinstance(address, tuple) and address[0] not in {"127.0.0.1", "::1", "localhost"}:
            calls["external_network"] += 1
            raise AssertionError("Outbound network denied during smoke")
        return original_connect(sock, address)

    with patch.object(socket.socket, "connect", connect):
        from fastapi.testclient import TestClient

        from ai.retrieval.bm25 import BM25Index
        from ai.services.retrieval_service import RetrievalService
        from backend.app.core.config import Settings
        from backend.app.main import create_app

        original_service, original_index = RetrievalService.search, BM25Index.search

        def service(self, request):
            calls["RetrievalService.search"] += 1
            assert self._dense_index is None
            return original_service(self, request)

        def index(self, query, **kwargs):
            calls["BM25Index.search"] += 1
            return original_index(self, query, **kwargs)

        root = Path(__file__).resolve().parents[1]
        with (root / "ai/evaluation/datasets/grounded_eval_dev.jsonl").open(encoding="utf-8") as f:
            for line in f:
                case = json.loads(line)
                if case["case_id"] == "GE-D-004":
                    break
            else:
                raise AssertionError("DEV case unavailable")
        assert case["split"] == "DEV"
        with (
            patch.object(RetrievalService, "search", service),
            patch.object(BM25Index, "search", index),
        ):
            app = create_app(Settings(_env_file=None, environment="TEST", database_url="sqlite://"))
            with TestClient(app) as client:
                response = client.post("/api/v1/retrieval/search", json={"query": case["query"]})
                assert response.status_code == 200, response.text
                body = response.json()
                citation = next(c for c in body["data"]["citations"]
                                if c["source_id"] == "product_demo_long_003")
                exact = client.get("/api/v1/c04/lookup", params=citation["c04_lookup"])
                assert exact.status_code == 200
                assert exact.json()["data"]["excerpt_hash"] == citation["c04_excerpt_hash"]
        assert calls == {"RetrievalService.search": 1, "BM25Index.search": 1, "external_network": 0}
        assert guard.attempts == []
        assert "ai.retrieval.dense" not in sys.modules
        report = {
            "case_id": case["case_id"], "query": case["query"],
            "search_http_status": response.status_code, "response": body,
            "readback_http_status": exact.status_code, "readback": exact.json(),
            "real_call_counts": calls, "forbidden_import_attempts": guard.attempts,
            "dense_loaded": False, "llm_executed": False, "external_embedding_calls": 0,
            "timeout_canary_is_performance_measurement": False,
        }
        print(json.dumps(report, ensure_ascii=True, indent=2))
    sys.meta_path.remove(guard)


if __name__ == "__main__":
    main()
