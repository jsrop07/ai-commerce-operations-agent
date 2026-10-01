"""C07 aggregate-only API checks; never run retrieval, Provider or LLM."""

import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.api.retrieval import router as retrieval_router
from backend.app.core.config import Settings
from backend.app.main import create_app
from backend.app.services import actual_retrieval_summary as actual
from backend.app.services import r07_retrieval_evaluation as r07

PATH = "/api/v1/retrieval/actual-summary"
SYNTHETIC_PATH = "/api/v1/retrieval/summary"


def _client(environment="TEST"):
    return TestClient(create_app(Settings(
        _env_file=None, environment=environment, database_url="sqlite://",
    )))


class ActualRetrievalSummaryTests(unittest.TestCase):
    def test_actual_response_has_only_validated_aggregates(self):
        with _client() as client:
            response = client.get(PATH)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "COMPLETE_WITH_LIMITS")
        self.assertEqual(data["data_mode"], "PRIVATE_ACTUAL_EVAL")
        self.assertEqual(data["validation_scope"], "PRODUCT-only actual-scale mixed DEV24 retrieval baseline")
        self.assertIsNone(data["run_id"])
        self.assertEqual(data["source_support"], actual.SOURCE_SUPPORT)
        self.assertEqual(data["counts"], {
            "document_count": 2167, "chunk_count": 2167, "question_count": 24,
            "answerable_count": 24, "hold_count": 0,
            "review_completed_count": 24,
        })
        self.assertEqual(data["execution"], {
            "planned_count": 72, "executed_count": 72, "succeeded_count": 72,
            "failed_count": 0, "blocked_count": 0, "not_run_count": 0,
        })
        methods = {item["method"]: item for item in data["methods"]}
        self.assertEqual(set(methods), {"BM25", "DENSE", "RRF_HYBRID"})
        expected = {
            "BM25": (0.8333333333333334, 0.7916666666666666, 20, 27.84, 38.96, "SEARCH"),
            "DENSE": (0.4166666666666667, 0.2861111111111111, 10, 59.31, 76.47, "SEARCH"),
            "RRF_HYBRID": (0.8333333333333334, 0.7291666666666666, 20, 87.36, 117.92, "SERIAL_SEARCH_E2E"),
        }
        for name, (recall, mrr, full, avg, p95, kind) in expected.items():
            item = methods[name]
            self.assertEqual(item["executed_count"], 24)
            self.assertEqual(item["execution_status"], "SUCCEEDED")
            self.assertEqual(item["metric_status"], "MEASURED")
            self.assertTrue(math.isclose(item["recall_at_5"], recall))
            self.assertTrue(math.isclose(item["mrr_at_5"], mrr))
            self.assertEqual(item["full_evidence"], {
                "full_evidence_count": full, "full_evidence_denominator": 24,
            })
            self.assertAlmostEqual(item["latency"]["avg_ms"], avg, places=2)
            self.assertAlmostEqual(item["latency"]["warm_p95_ms"], p95, places=2)
            self.assertEqual(item["latency"]["kind"], kind)
            self.assertEqual(item["latency"]["unit"], "ms")
            self.assertFalse(item["latency"]["http_round_trip"])
        dense = methods["DENSE"]["preparation"]
        self.assertEqual(dense["status"], "MEASURED")
        self.assertAlmostEqual(dense["model_load_seconds"], 3.03, places=2)
        self.assertAlmostEqual(dense["document_embedding_seconds"], 30.07, places=2)
        self.assertIsNone(methods["BM25"]["preparation"]["model_load_seconds"])
        self.assertEqual(methods["BM25"]["preparation"]["status"], "NOT_APPLICABLE")
        self.assertEqual(data["selection"]["selected_method"], "BM25")
        self.assertFalse(data["selection"]["final_natural_language_retriever"])
        self.assertEqual(data["r07"]["validated_baseline"], "BM25")
        self.assertIsNone(data["r07"]["run_id"])
        self.assertEqual(data["r07"]["input_hashes"], {
            "product_snapshot_sha256": r07.PRODUCT_HASH,
            "dev24_sha256": r07.DEV24_HASH, "final12_used": False,
        })
        reranker = data["r07"]["reranker"]
        self.assertEqual(reranker["evaluation_status"], "PASS_WITH_FINDING")
        self.assertFalse(reranker["always_on_selected"])
        self.assertTrue(reranker["conditional_candidate"])
        self.assertFalse(reranker["conditional_routing_validated"])
        self.assertFalse(reranker["runtime_enabled"])
        self.assertEqual(reranker["fallback_target"], "BM25")
        self.assertEqual(reranker["candidate_miss_count"], 4)
        self.assertEqual(reranker["candidate_miss_category"], "RETRIEVAL_CANDIDATE_MISS")
        self.assertEqual(reranker["observed_events"], {
            "timeout_count": 0, "retry_count": 0, "fallback_count": 0,
        })
        self.assertEqual((reranker["timeout_seconds"], reranker["max_retries"]), (120, 1))
        self.assertEqual((reranker["before"]["full_evidence_count"],
                          reranker["after"]["full_evidence_count"]), (20, 20))
        self.assertEqual([item["kind"] for item in reranker["latency"]],
                         ["RERANK_ONLY", "SEARCH_PLUS_RERANK_E2E"])
        self.assertAlmostEqual(reranker["latency"][0]["mean_ms"], 1687.33, places=2)
        self.assertAlmostEqual(reranker["latency"][1]["mean_ms"], 1706.92, places=2)
        self.assertTrue(all(not item["http_round_trip"] for item in reranker["latency"]))
        compression = data["r07"]["compression"]
        self.assertEqual(compression["evaluation_status"], "PASS_WITH_LIMITATION")
        self.assertEqual(compression["scope"], "SYNTHETIC_POLICY_COMPRESSION_ONLY")
        self.assertEqual((compression["case_count"], compression["before_tokens"],
                          compression["after_tokens"]), (3, 903, 445))
        self.assertEqual((compression["evidence_preserved_count"],
                          compression["citation_preserved_count"],
                          compression["fallback_count"]), (3, 3, 0))
        self.assertFalse(compression["actual_context_validated"])
        self.assertFalse(compression["runtime_enabled"])

    def test_synthetic_summary_is_still_separate(self):
        with _client() as client:
            actual_response = client.get(PATH)
            synthetic_response = client.get(SYNTHETIC_PATH)
        self.assertEqual(actual_response.status_code, 200)
        self.assertEqual(synthetic_response.status_code, 200)
        synthetic = synthetic_response.json()["data"]
        self.assertEqual(synthetic["data_mode"], "SYNTHETIC_DEMO")
        self.assertEqual(synthetic["corpus_documents"], 8)
        self.assertEqual(synthetic["query_count"], 24)
        self.assertEqual(actual_response.json()["data_mode"], "PRIVATE_ACTUAL_EVAL")

    def test_no_sensitive_fields_or_paths(self):
        with _client() as client:
            response = client.get(PATH)
        self.assertEqual(response.status_code, 200)
        text = response.text.lower()
        for forbidden in (
            '"request_id"', '"query"', '"gold_answer"', '"gold_evidence"',
            '"required_evidence"', '"evidence_text"', '"raw_prompt"',
            '"provider_receipt"', '"final12"', '"private_path"',
            "c:\\\\", ".jsonl", "artifacts/", "artifacts\\\\",
        ):
            self.assertNotIn(forbidden, text)

    def test_schema_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            summary_path = Path(temp) / "summary.json"
            config_path = Path(temp) / "config.json"
            summary = json.loads(actual.SUMMARY_PATH.read_bytes())
            config = json.loads(actual.CONFIG_PATH.read_bytes())
            summary["dev24"].pop("answerable")
            summary_path.write_text(json.dumps(summary), encoding="utf-8")
            config_path.write_text(json.dumps(config), encoding="utf-8")
            with patch.object(actual, "SUMMARY_PATH", summary_path), patch.object(actual, "CONFIG_PATH", config_path):
                with _client() as client:
                    response = client.get(PATH)
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json(), {"detail": "ACTUAL_SUMMARY_INVALID"})

    def test_identity_and_mode_mismatch_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "summary.json"
            value = json.loads(actual.SUMMARY_PATH.read_bytes())
            value["data_mode"] = "SYNTHETIC_DEMO"
            path.write_text(json.dumps(value), encoding="utf-8")
            with patch.object(actual, "SUMMARY_PATH", path):
                with _client() as client:
                    self.assertEqual(client.get(PATH).status_code, 503)
            value["data_mode"] = "PRIVATE_ACTUAL_EVAL"
            value["task_id"] = "WRONG"
            path.write_text(json.dumps(value), encoding="utf-8")
            with patch.object(actual, "SUMMARY_PATH", path):
                with _client() as client:
                    self.assertEqual(client.get(PATH).status_code, 503)

    def test_missing_or_null_metric_is_not_converted_to_zero(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "summary.json"
            original = json.loads(actual.SUMMARY_PATH.read_bytes())
            for replacement in (None, "REMOVE"):
                value = json.loads(json.dumps(original))
                if replacement == "REMOVE":
                    value["methods"]["bm25"].pop("recall_at_5")
                else:
                    value["methods"]["bm25"]["recall_at_5"] = replacement
                path.write_text(json.dumps(value), encoding="utf-8")
                with patch.object(actual, "SUMMARY_PATH", path):
                    with _client() as client:
                        response = client.get(PATH)
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json(), {"detail": "ACTUAL_SUMMARY_INVALID"})

    def test_private_route_and_openapi_are_distinct(self):
        actual_routes = [
            route for route in retrieval_router.routes
            if getattr(route, "path", None) == PATH and "GET" in getattr(route, "methods", set())
        ]
        with _client() as client:
            self.assertEqual(client.get(PATH, params={"path": "ignored"}).status_code, 422)
            self.assertEqual(client.request("GET", PATH, json={}).status_code, 422)
            self.assertEqual(client.post(PATH).status_code, 405)
            schema = client.get("/openapi.json").json()
        self.assertEqual(len(actual_routes), 1)
        self.assertEqual(set(schema["paths"][PATH]), {"get"})
        self.assertEqual(set(schema["paths"][SYNTHETIC_PATH]), {"get"})
        self.assertNotEqual(
            schema["paths"][PATH]["get"]["responses"]["200"],
            schema["paths"][SYNTHETIC_PATH]["get"]["responses"]["200"],
        )
        self.assertNotIn("request_id", schema["components"]["schemas"]["ActualSummary"]["properties"])
        with _client(environment="DEMO") as client:
            self.assertEqual(client.get(PATH).status_code, 403)

    def test_r07_reads_only_four_hash_pinned_safe_files(self):
        seen = []
        original = Path.read_bytes

        def recording_read(path):
            seen.append(path.name)
            return original(path)

        with patch.object(Path, "read_bytes", recording_read):
            result = r07.load_r07_evaluation()
        self.assertEqual(set(seen), set(r07.SAFE_HASHES))
        self.assertEqual(len(seen), 4)
        self.assertEqual(result.reranker.candidate_miss_count, 4)
        for name, expected in r07.SAFE_HASHES.items():
            import hashlib
            self.assertEqual(hashlib.sha256((r07.ARTIFACT_DIR / name).read_bytes()).hexdigest(),
                             expected)

    def test_each_r07_hash_mismatch_fails_closed(self):
        for name in r07.SAFE_HASHES:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                for safe_name in r07.SAFE_HASHES:
                    raw = (r07.ARTIFACT_DIR / safe_name).read_bytes()
                    (root / safe_name).write_bytes(raw + (b" " if safe_name == name else b""))
                with patch.object(r07, "ARTIFACT_DIR", root), _client() as client:
                    response = client.get(PATH)
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json(), {"detail": "R07_EVALUATION_INVALID"})

    def test_r07_input_identity_and_final12_fail_closed(self):
        source = [json.loads((r07.ARTIFACT_DIR / name).read_bytes()) for name in r07.SAFE_HASHES]
        changes = [
            (0, ("input", "product_snapshot_sha256"), "wrong"),
            (0, ("input", "dev24_sha256"), "wrong"),
            (1, ("input_hashes", "product_snapshot_sha256"), "wrong"),
            (1, ("input_hashes", "dev24_sha256"), "wrong"),
            (0, ("input", "final12_used"), True),
            (1, ("final12_used",), True),
            (2, ("final12_used",), True),
        ]
        for index, keys, value in changes:
            with self.subTest(index=index, keys=keys):
                items = json.loads(json.dumps(source))
                target = items[index]
                for key in keys[:-1]:
                    target = target[key]
                target[keys[-1]] = value
                with self.assertRaises(r07.R07EvaluationFailure):
                    r07._project(*items)

    def test_local_actual_summary_remains_available(self):
        with _client(environment="LOCAL") as client:
            response = client.get(PATH)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["source_support"]["C02"], "BLOCKED")
