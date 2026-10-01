"""Allowlisted C07 E08 aggregates. Reads no query, gold, evidence or provider data."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.app.services.r07_retrieval_evaluation import (
    R07Evaluation,
    R07EvaluationFailure,
    load_r07_evaluation,
)

ROOT = Path(__file__).resolve().parents[3]
SUMMARY_PATH = ROOT / "artifacts/experiments/OPS-RAG-SCALE-01/r07_pre_summary.json"
CONFIG_PATH = ROOT / "artifacts/experiments/OPS-RAG-SCALE-01/r07_pre_run_config.json"
SOURCE_SUPPORT = {
    "PRODUCT": "SUPPORTED", "POLICY": "MISSING",
    "INVENTORY_SNAPSHOT": "BLOCKED", "INCOMING_STOCK": "MISSING",
    "C02": "BLOCKED",
}
METHOD_KEYS = ("bm25", "dense", "rrf_hybrid")


class C07Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class SourceSupport(C07Model):
    PRODUCT: Literal["SUPPORTED"]
    POLICY: Literal["MISSING"]
    INVENTORY_SNAPSHOT: Literal["BLOCKED"]
    INCOMING_STOCK: Literal["MISSING"]
    C02: Literal["BLOCKED"]


class Counts(C07Model):
    document_count: int = Field(ge=0)
    chunk_count: int = Field(ge=0)
    question_count: int = Field(ge=0)
    answerable_count: int = Field(ge=0)
    hold_count: int = Field(ge=0)
    review_completed_count: int = Field(ge=0)


class Execution(C07Model):
    planned_count: int = Field(ge=0)
    executed_count: int = Field(ge=0)
    succeeded_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    blocked_count: int = Field(ge=0)
    not_run_count: int = Field(ge=0)


class EvidenceCoverage(C07Model):
    full_evidence_count: int = Field(ge=0)
    full_evidence_denominator: int = Field(ge=0)


class Latency(C07Model):
    kind: Literal["SEARCH", "SERIAL_SEARCH_E2E"]
    unit: Literal["ms"] = "ms"
    avg_ms: float = Field(ge=0)
    warm_p95_ms: float = Field(ge=0)
    http_round_trip: Literal[False] = False


class PreparationCost(C07Model):
    status: Literal["MEASURED", "UNMEASURED", "NOT_APPLICABLE"]
    model_load_seconds: float | None
    document_embedding_seconds: float | None


class Method(C07Model):
    method: Literal["BM25", "DENSE", "RRF_HYBRID"]
    execution_status: Literal["SUCCEEDED", "NOT_RUN", "FAILED", "BLOCKED"]
    executed_count: int = Field(ge=0)
    metric_status: Literal["MEASURED", "UNMEASURED"]
    recall_at_5: float | None = Field(ge=0, le=1)
    mrr_at_5: float | None = Field(ge=0, le=1)
    full_evidence: EvidenceCoverage
    latency: Latency
    preparation: PreparationCost


class Selection(C07Model):
    selected_method: Literal["BM25"]
    status: Literal["PROVISIONAL_PRODUCT_ONLY"]
    selection_scope: Literal["PRODUCT-only mixed actual-scale DEV24"]
    reasons: list[str]
    final_natural_language_retriever: Literal[False] = False


class ActualSummary(C07Model):
    status: Literal["COMPLETE_WITH_LIMITS"]
    data_mode: Literal["PRIVATE_ACTUAL_EVAL"]
    validation_scope: Literal["PRODUCT-only actual-scale mixed DEV24 retrieval baseline"]
    experiment_id: Literal["OPS-RAG-SCALE-01"]
    experiment: Literal["E08"]
    task_id: Literal["R07-PRE-AI-01"]
    run_group: Literal["OPS-RAG-SCALE-01 / E08"]
    run_id: None
    corpus_alias: Literal["PRODUCT-SAFE-SNAPSHOT"]
    question_set_alias: Literal["R07-PRE-ACTUAL-DEV24"]
    source_support: SourceSupport
    counts: Counts
    execution: Execution
    methods: list[Method]
    selection: Selection
    r07: R07Evaluation


class ActualSummaryFailure(Exception):
    pass


def _require(condition: bool) -> None:
    if not condition:
        raise ActualSummaryFailure("ACTUAL_SUMMARY_INVALID")


def _count(value: object) -> int:
    _require(type(value) is int and value >= 0)
    return value


def _number(value: object, *, maximum: float | None = None) -> float:
    _require(type(value) in (int, float) and math.isfinite(value) and value >= 0)
    if maximum is not None:
        _require(value <= maximum)
    return float(value)


def _load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_bytes())
    except OSError:
        raise ActualSummaryFailure("ACTUAL_SUMMARY_UNAVAILABLE") from None
    except (ValueError, UnicodeError):
        raise ActualSummaryFailure("ACTUAL_SUMMARY_INVALID") from None
    _require(isinstance(value, dict))
    return value


def _mean_with_cold(search: dict) -> float:
    total = _count(search["count"])
    warm = _count(search["warm_count"])
    _require(total == 24 and warm == 23)
    return (_number(search["cold_first_ms"]) + warm * _number(search["warm_mean_ms"])) / total


def load_actual_summary() -> ActualSummary:
    """Read curated E08 aggregates and hash-pinned R07 safe aggregates."""
    try:
        return _project(_load_json(SUMMARY_PATH), _load_json(CONFIG_PATH), load_r07_evaluation())
    except ActualSummaryFailure:
        raise
    except R07EvaluationFailure as exc:
        raise ActualSummaryFailure(str(exc)) from None
    except (KeyError, TypeError, ValueError, AttributeError):
        raise ActualSummaryFailure("ACTUAL_SUMMARY_INVALID") from None


def _project(summary: dict, config: dict, r07: R07Evaluation) -> ActualSummary:
    for item in (summary, config):
        _require(item["experiment_id"] == "OPS-RAG-SCALE-01")
        _require(item["experiment"] == "E08")
        _require(item["task_id"] == "R07-PRE-AI-01")
        _require(item["scope"] == "PRODUCT_ONLY")
        _require(item["source_support"] == SOURCE_SUPPORT)
        if "data_mode" in item:
            _require(item["data_mode"] == "PRIVATE_ACTUAL_EVAL")
        if "status" in item:
            _require(item["status"] == "COMPLETE_WITH_LIMITS")
        if "run_id" in item:
            _require(item["run_id"] is None)
    _require(summary["final12_used"] is False)
    _require(summary["raw_private_source_used"] is False)
    _require(config["input"]["final12_used"] is False)
    _require(config["document_projection"]["one_product_one_document"] is True)
    _require(config["retrieval"]["methods"] == list(METHOD_KEYS))
    _require(summary["retrieval_config"]["methods"] == list(METHOD_KEYS))
    docs = _count(summary["retrieval_documents"])
    _require(docs == _count(summary["product_records"]) == _count(config["input"]["retrieval_documents"]) == 2167)
    dev = summary["dev24"]
    questions = _count(dev["count"])
    answerable = _count(dev["answerable"])
    hold = _count(dev["hold"])
    _require(questions == answerable + hold == _count(config["input"]["dev24_count"]) == 24)
    _require(dev["human_reviewed"] is True and config["input"]["human_reviewed"] is True)
    _require(dev["sha256"] == config["input"]["dev24_sha256"])
    execution = summary["execution"]
    planned = _count(execution["planned_cases"])
    executed = _count(execution["attempted"])
    succeeded = _count(execution["succeeded"])
    failed = _count(execution["error"])
    blocked = _count(execution["blocked"])
    not_run = _count(execution["not_run"])
    _require(planned == 72 and executed == _count(execution["rows_recorded"]) == 72)
    _require(executed == succeeded + failed + blocked and planned == executed + not_run)
    _require((succeeded, failed, blocked, not_run) == (72, 0, 0, 0))
    source_methods = summary["methods"]
    _require(isinstance(source_methods, dict) and set(source_methods) == set(METHOD_KEYS))
    search = summary["latency"]["search"]
    build = summary["latency"]["build"]
    methods: list[Method] = []
    for key, label, latency_key, kind in (
        ("bm25", "BM25", "bm25", "SEARCH"),
        ("dense", "DENSE", "dense", "SEARCH"),
        ("rrf_hybrid", "RRF_HYBRID", "rrf_end_to_end_serial", "SERIAL_SEARCH_E2E"),
    ):
        item = source_methods[key]
        _require(_count(item["attempted"]) == _count(item["succeeded"]) == 24)
        _require((_count(item["error"]), _count(item["blocked"]), _count(item["not_run"])) == (0, 0, 0))
        denominator = _count(item["answerable_denominator"])
        numerator = _count(item["full_evidence_count"])
        _require(denominator == answerable and numerator <= denominator)
        recall = _number(item["recall_at_5"], maximum=1)
        mrr = _number(item["mrr_at_5"], maximum=1)
        latency = search[latency_key]
        _require(_count(latency["count"]) == 24)
        if key == "dense":
            preparation = PreparationCost(
                status="MEASURED",
                model_load_seconds=_number(build["dense_model_load_ms"]) / 1000,
                document_embedding_seconds=_number(build["dense_document_embedding_ms"]) / 1000,
            )
        else:
            preparation = PreparationCost(
                status="NOT_APPLICABLE", model_load_seconds=None,
                document_embedding_seconds=None,
            )
        methods.append(Method(
            method=label, execution_status="SUCCEEDED", executed_count=24,
            metric_status="MEASURED", recall_at_5=recall, mrr_at_5=mrr,
            full_evidence=EvidenceCoverage(
                full_evidence_count=numerator, full_evidence_denominator=denominator,
            ),
            latency=Latency(
                kind=kind, avg_ms=_mean_with_cold(latency),
                warm_p95_ms=_number(latency["warm_p95_ms"]),
            ),
            preparation=preparation,
        ))
    bm25, dense, hybrid = methods
    _require(hybrid.recall_at_5 == bm25.recall_at_5)
    _require(hybrid.mrr_at_5 < bm25.mrr_at_5)
    _require(hybrid.latency.avg_ms > bm25.latency.avg_ms)
    _require(dense.recall_at_5 < bm25.recall_at_5 and dense.mrr_at_5 < bm25.mrr_at_5)
    return ActualSummary(
        status="COMPLETE_WITH_LIMITS", data_mode="PRIVATE_ACTUAL_EVAL",
        validation_scope="PRODUCT-only actual-scale mixed DEV24 retrieval baseline",
        experiment_id=summary["experiment_id"], experiment=summary["experiment"],
        task_id=summary["task_id"], run_group="OPS-RAG-SCALE-01 / E08",
        run_id=None, corpus_alias="PRODUCT-SAFE-SNAPSHOT",
        question_set_alias="R07-PRE-ACTUAL-DEV24",
        source_support=SourceSupport(**SOURCE_SUPPORT),
        counts=Counts(
            document_count=docs, chunk_count=docs, question_count=questions,
            answerable_count=answerable, hold_count=hold,
            review_completed_count=questions,
        ),
        execution=Execution(
            planned_count=planned, executed_count=executed, succeeded_count=succeeded,
            failed_count=failed, blocked_count=blocked, not_run_count=not_run,
        ),
        methods=methods,
        selection=Selection(
            selected_method="BM25", status="PROVISIONAL_PRODUCT_ONLY",
            selection_scope="PRODUCT-only mixed actual-scale DEV24",
            reasons=[
                "Hybrid Recall@5 did not improve over BM25.",
                "Hybrid MRR@5 decreased and serial search latency increased.",
                "Dense actual-scale retrieval metrics were lower than BM25.",
                "Three semantic cases failed for all three methods (task handoff).",
                "DEV24 is lexical-heavy; do not generalize to all natural-language product search.",
            ],
        ),
        r07=r07,
    )
