"""Hash-pinned, aggregate-only projection of the four public R07 artifacts."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ROOT = Path(__file__).resolve().parents[3]
ARTIFACT_DIR = ROOT / "artifacts/experiments/OPS-RAG-02"
SAFE_HASHES = {
    "r07_reranker_config.json": "e2970b62ab699f091bb5be92b4dc79e9a0c5d8ea02e8e8052517e58ce4ad5ceb",
    "r07_reranker_summary.json": "b94ae29aa02b34b93ec4b2cd070f90d91e00f060f5ee6a76fe48e93285f81588",
    "r07_context_compression_config.json": (
        "5ec12de7bc748d17010e9b3d405c3127ce780553709c15a37d52324c739336b0"
    ),
    "r07_context_compression_summary.json": (
        "3c0c4f246f455ab80f7308721b1c4604896d96d544a8a9abe7e930903455ae56"
    ),
}
PRODUCT_HASH = "6438ad2ca5a21d4d30b1bf5bacbeb186679df1c16369fbc8eacc9cca3f1a9892"
DEV24_HASH = "c434e0a6c784861962dc09d5472380e5d775f4286590b8bc8de564b4552b879a"


class R07EvaluationFailure(Exception):
    pass


class SafeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class InputHashes(SafeModel):
    product_snapshot_sha256: str
    dev24_sha256: str
    final12_used: Literal[False] = False


class Metrics(SafeModel):
    recall_at_5: float = Field(ge=0, le=1)
    mrr_at_5: float = Field(ge=0, le=1)
    full_evidence_count: int = Field(ge=0)
    full_evidence_rate: float = Field(ge=0, le=1)


class Measurement(SafeModel):
    kind: Literal["RERANK_ONLY", "SEARCH_PLUS_RERANK_E2E", "SYNTHETIC_COMPRESSION"]
    unit: Literal["ms"] = "ms"
    count: int = Field(ge=0)
    mean_ms: float = Field(ge=0)
    p95_ms: float | None = Field(default=None, ge=0)
    http_round_trip: Literal[False] = False


class ObservedEvents(SafeModel):
    timeout_count: int = Field(ge=0)
    retry_count: int = Field(ge=0)
    fallback_count: int = Field(ge=0)


class Reranker(SafeModel):
    evaluation_status: Literal["PASS_WITH_FINDING"]
    baseline: Literal["BM25"]
    always_on_selected: Literal[False]
    conditional_candidate: Literal[True]
    conditional_routing_validated: Literal[False]
    runtime_enabled: Literal[False]
    fallback_target: Literal["BM25"]
    before: Metrics
    after: Metrics
    candidate_miss_count: int = Field(ge=0)
    candidate_miss_category: Literal["RETRIEVAL_CANDIDATE_MISS"]
    latency: list[Measurement]
    observed_events: ObservedEvents
    timeout_seconds: float = Field(gt=0)
    max_retries: int = Field(ge=0)
    model: str
    revision: str
    device: Literal["cpu"]


class Compression(SafeModel):
    evaluation_status: Literal["PASS_WITH_LIMITATION"]
    scope: Literal["SYNTHETIC_POLICY_COMPRESSION_ONLY"]
    case_count: int = Field(ge=0)
    before_tokens: int = Field(ge=0)
    after_tokens: int = Field(ge=0)
    reduction_ratio: float = Field(ge=0, le=1)
    evidence_preserved_count: int = Field(ge=0)
    citation_preserved_count: int = Field(ge=0)
    fallback_count: int = Field(ge=0)
    latency: Measurement
    actual_context_validated: Literal[False]
    runtime_enabled: Literal[False]


class R07Evaluation(SafeModel):
    status: Literal["COMPLETE_WITH_LIMITS"]
    experiment_id: Literal["OPS-RAG-02"]
    run_id: None
    input_hashes: InputHashes
    validated_baseline: Literal["BM25"]
    reranker: Reranker
    compression: Compression


def _require(condition: bool) -> None:
    if not condition:
        raise R07EvaluationFailure("R07_EVALUATION_INVALID")


def _load_safe(name: str) -> dict:
    try:
        raw = (ARTIFACT_DIR / name).read_bytes()
    except OSError:
        raise R07EvaluationFailure("R07_EVALUATION_UNAVAILABLE") from None
    _require(hashlib.sha256(raw).hexdigest() == SAFE_HASHES[name])
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeError):
        raise R07EvaluationFailure("R07_EVALUATION_INVALID") from None
    _require(isinstance(value, dict))
    return value


def _number(value: object) -> float:
    _require(type(value) in (int, float) and math.isfinite(value) and value >= 0)
    return float(value)


def _count(value: object) -> int:
    _require(type(value) is int and value >= 0)
    return value


def _measurement(kind: str, value: dict) -> Measurement:
    return Measurement(kind=kind, count=_count(value["count"]),
                       mean_ms=_number(value["mean_ms"]), p95_ms=_number(value["p95_ms"]))


def _project(rc: dict, rs: dict, cc: dict, cs: dict) -> R07Evaluation:
    _require(rc["task_id"] == rs["task_id"] == cc["task_id"] == cs["task_id"] == "R07-AI-01")
    _require(rc["experiment_id"] == rs["experiment_id"] == "OPS-RAG-02")
    _require(cc["experiment_id"] == cs["experiment_id"] == "OPS-RAG-02-COMPRESSION")
    _require(rc["scope"] == "PRODUCT_ONLY")
    _require(cc["scope"] == "SYNTHETIC_POLICY_COMPRESSION_ONLY")
    _require(cc["source_classification"] == cs["source_classification"] == "LOCAL_EVAL_SYNTHETIC")
    _require(
        rc["input"]["product_snapshot_sha256"]
        == rs["input_hashes"]["product_snapshot_sha256"]
        == PRODUCT_HASH
    )
    _require(rc["input"]["dev24_sha256"] == rs["input_hashes"]["dev24_sha256"] == DEV24_HASH)
    _require(rc["input"]["final12_used"] is rs["final12_used"] is cc["final12_used"] is False)
    _require(cc["actual_policy_used"] is False)
    _require(cc["retrieval_run_used"] is cc["reranker_run_used"] is False)
    _require(rc["retrieval"]["baseline"] == "bm25")
    _require(rc["reranker"]["model"] == rs["model"]["model"] == "BAAI/bge-reranker-v2-m3")
    _require(
        rc["reranker"]["revision"] == rs["model"]["revision"]
        == "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"
    )
    _require(rc["reranker"]["device"] == rs["model"]["device"] == "cpu")
    _require(rc["reranker"]["timeout_seconds"] == rs["model"]["timeout_seconds"] == 120.0)
    _require(rc["reranker"]["max_retries"] == rs["model"]["max_retries"] == 1)
    _require(_count(rs["candidate_miss"]["count"]) == 4)
    _require(_count(cc["case_count"]) == _count(cs["case_count"]) == 3)
    _require(cs["evidence_preserved_all"] is cs["citation_preserved_all"] is True)
    _require(_count(cs["preserved_case_count"]) == 3)
    before = Metrics(**{key: rs["before"][key] for key in Metrics.model_fields})
    after = Metrics(**{key: rs["after"][key] for key in Metrics.model_fields})
    events = ObservedEvents(**{
        key: _count(rs["reranker_events"][key]) for key in ObservedEvents.model_fields
    })
    latency = rs["latency"]
    return R07Evaluation(
        status="COMPLETE_WITH_LIMITS", experiment_id="OPS-RAG-02", run_id=None,
        input_hashes=InputHashes(product_snapshot_sha256=PRODUCT_HASH, dev24_sha256=DEV24_HASH),
        validated_baseline="BM25",
        reranker=Reranker(
            evaluation_status="PASS_WITH_FINDING", baseline="BM25", always_on_selected=False,
            conditional_candidate=True, conditional_routing_validated=False, runtime_enabled=False,
            fallback_target="BM25", before=before, after=after,
            candidate_miss_count=4, candidate_miss_category="RETRIEVAL_CANDIDATE_MISS",
            latency=[_measurement("RERANK_ONLY", latency["reranker"]),
                     _measurement("SEARCH_PLUS_RERANK_E2E", latency["e2e_search_plus_rerank"])],
            observed_events=events, timeout_seconds=_number(rs["model"]["timeout_seconds"]),
            max_retries=_count(rs["model"]["max_retries"]), model=rs["model"]["model"],
            revision=rs["model"]["revision"], device=rs["model"]["device"],
        ),
        compression=Compression(
            evaluation_status="PASS_WITH_LIMITATION", scope="SYNTHETIC_POLICY_COMPRESSION_ONLY",
            case_count=3, before_tokens=_count(cs["total_before_tokens"]),
            after_tokens=_count(cs["total_after_tokens"]),
            reduction_ratio=_number(cs["token_reduction_ratio"]),
            evidence_preserved_count=3, citation_preserved_count=3,
            fallback_count=_count(cs["fallback_count"]),
            latency=Measurement(kind="SYNTHETIC_COMPRESSION", count=3,
                                mean_ms=_number(cs["compression_latency_ms"]["mean"])),
            actual_context_validated=False, runtime_enabled=False,
        ),
    )


def load_r07_evaluation() -> R07Evaluation:
    """Read the four named public-safe artifacts, verify bytes, then expose aggregates only."""
    try:
        return _project(*(_load_safe(name) for name in SAFE_HASHES))
    except R07EvaluationFailure:
        raise
    except (KeyError, TypeError, ValueError, AttributeError):
        raise R07EvaluationFailure("R07_EVALUATION_INVALID") from None
