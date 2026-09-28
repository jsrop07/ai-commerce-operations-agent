"""Allowlisted historical DEV aggregates. Never imports/calls a retriever."""

import json
import math
import re
from collections import defaultdict
from hashlib import sha256
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict

from backend.app.services import corpus_restore as cr

RESULT_PATH = cr.ROOT / "artifacts/experiments/OPS-RAG-01/r05_retrieval_result.json"
EXPERIMENT_MANIFEST_PATH = cr.ROOT / (
    "artifacts/experiments/OPS-RAG-01/r05_grounded_snapshot_manifest_v2.json"
)
EXPERIMENT_SNAPSHOT_PATH = cr.ROOT / cr.BASE_SNAPSHOT_REL
METHODS = {"bm25", "dense", "rrf_hybrid"}
METRICS = ("mean_recall_at_5", "mean_mrr_at_5", "mean_latency_ms", "p95_latency_ms")


class SummaryModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Selection(SummaryModel):
    method: str
    status: str


class SnapshotSummary(SummaryModel):
    version: str
    canonical_hash: str
    file_sha256: str


class MethodSummary(SummaryModel):
    method: str
    executed: bool | None
    execution_status: Literal["EXECUTED", "PARTIAL", "NOT_EXECUTED", "UNKNOWN"]
    source_status: str | None
    mean_recall_at_5: float | None
    mean_mrr_at_5: float | None
    full_evidence_numerator: int | None
    full_evidence_denominator: int | None
    mean_latency_ms: float | None
    p95_latency_ms: float | None
    metric_status: dict[str, str]


class DevSummary(SummaryModel):
    experiment_id: str
    handoff_id: str
    evaluation_as_of: AwareDatetime
    selection: Selection
    corpus_version: str | None
    corpus_version_status: Literal["PROVIDED", "NOT_PROVIDED"]
    corpus_sha256: str
    corpus_documents: int
    experiment_snapshot: SnapshotSummary
    runtime_snapshot: SnapshotSummary
    query_count: int
    execution_count: int
    all_executed: bool | None
    error_count: int
    external_embedding_api_calls: int | None
    actual_retrieval_executed_in_experiment: bool | None
    runtime_search_available: bool
    data_mode: Literal["SYNTHETIC_DEMO"]
    actual_scale_retrieval_validation_required: bool
    hold_behavior_evaluated: bool
    methods: list[MethodSummary]
    latency_scope: Literal["historical DEV retrieval; milliseconds; not API latency"]


class SummaryFailure(Exception):
    pass


def require(condition, code="RETRIEVAL_SUMMARY_INVALID"):
    if not condition:
        raise SummaryFailure(code)


def count(value):
    require(type(value) is int and value >= 0)
    return value


def digest(value):
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value))
    return value


def read(path):
    try:
        return path.read_bytes()
    except OSError:
        raise SummaryFailure("RETRIEVAL_SUMMARY_UNAVAILABLE") from None


def execution_state(rows):
    flags = [row.get("executed") for row in rows]
    require(all(flag is None or type(flag) is bool for flag in flags))
    if flags and all(flag is True for flag in flags):
        return True, "EXECUTED"
    if any(flag is True for flag in flags):
        return True, "PARTIAL"
    if flags and all(flag is False for flag in flags):
        return False, "NOT_EXECUTED"
    return None, "UNKNOWN"


def load_summary(*, tenant_id: str, runtime_search_available: bool) -> DevSummary:
    try:
        return _load(tenant_id=tenant_id, runtime_search_available=runtime_search_available)
    except SummaryFailure:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, cr.LookupFailure):
        raise SummaryFailure("RETRIEVAL_SUMMARY_INVALID") from None


def _load(*, tenant_id, runtime_search_available):
    result = cr._json(read(RESULT_PATH))
    handoff = cr._json(read(cr.HANDOFF_PATH))
    old_manifest = cr._json(read(EXPERIMENT_MANIFEST_PATH))
    current_manifest = cr._json(read(cr.MANIFEST_PATH))
    require(result["experiment_id"] == handoff["experiment_id"] == "OPS-RAG-01-R05"
            and handoff["handoff_id"] == "C05-R05-RETRIEVAL",
            "RETRIEVAL_SUMMARY_IDENTITY_MISMATCH")
    selection = handoff["selection"]
    require(selection["method"] in METHODS and isinstance(selection["status"], str)
            and re.fullmatch(r"[A-Z][A-Z0-9_]{0,79}", selection["status"]))
    require(result["dev_selection"]["selected_method"] == selection["method"]
            and result["dev_selection"]["selection_status"] == selection["status"],
            "RETRIEVAL_SUMMARY_SELECTION_MISMATCH")
    dataset = handoff["dataset"]
    require(dataset["final_set_used"] is False)
    require(old_manifest["schema_version"] == "retrieval-snapshot-manifest.v1"
            and old_manifest["snapshot_version"] == "r05-grounded-semantic-v2"
            == current_manifest["metadata_enrichment"]["base_snapshot_version"],
            "RETRIEVAL_SUMMARY_VERSION_MISMATCH")
    require(old_manifest["corpus"] == current_manifest["corpus"],
            "RETRIEVAL_SUMMARY_CORPUS_MISMATCH")
    old_bytes = read(EXPERIMENT_SNAPSHOT_PATH)
    require(sha256(old_bytes).hexdigest() == digest(dataset["snapshot_sha256"]),
            "RETRIEVAL_SUMMARY_HASH_MISMATCH")
    # Use the same canonical serialization as the snapshot producer.
    old_rows = cr._rows(old_bytes)
    normalized = "\n".join(
        json.dumps(r, ensure_ascii=False, sort_keys=True) for r in old_rows
    ) + "\n"
    require(sha256(normalized.encode()).hexdigest() == digest(old_manifest["snapshot_hash"]),
            "RETRIEVAL_SUMMARY_HASH_MISMATCH")
    corpus = cr._validate_bundle(
        handoff=handoff, manifest=current_manifest, snapshot_bytes=read(cr.SNAPSHOT_PATH),
        corpus_bytes=read(cr.CORPUS_PATH), tenant_id=tenant_id,
    )
    # v3 only enriches provenance; never label the old experiment as a v3 rerun.
    require(old_rows == [{k: v for k, v in row.items()
                          if k not in {"tenant_id", "data_mode", "as_of"}}
                         for row in corpus.search_rows], "RETRIEVAL_SUMMARY_CORPUS_MISMATCH")
    rows = result["rows"]
    require(isinstance(rows, list) and bool(rows) and all(isinstance(r, dict) for r in rows))
    grouped = defaultdict(list)
    identities = set()
    for row in rows:
        require(row["method"] in METHODS and isinstance(row["case_id"], str)
                and re.fullmatch(r"GE-D-\d{3}", row["case_id"]))
        identity = (row["method"], row["case_id"])
        require(identity not in identities)
        identities.add(identity)
        require("error" in row)
        grouped[row["method"]].append(row)
    executions = handoff["execution"]
    require(count(result["execution_count"]) == count(executions["execution_count"]) == len(rows))
    require(count(result["query_count"]) == count(dataset["dev_cases"])
            == len({row["case_id"] for row in rows}))
    require(count(executions["error_count"]) == sum(row["error"] is not None for row in rows))
    actual, _ = execution_state(rows)
    all_executed = (False if any(r.get("executed") is False for r in rows) else
                    True if all(r.get("executed") is True for r in rows) else None)
    require(executions.get("all_executed") is all_executed)
    external_calls = executions.get("external_embedding_api_calls")
    if external_calls is not None:
        count(external_calls)
    require(isinstance(result["summaries"], dict)
            and set(result["summaries"]) == set(handoff["results"])
            and set(grouped) <= set(result["summaries"]) <= METHODS)
    require(selection["method"] in result["summaries"])
    methods = []
    for method, summary in result["summaries"].items():
        require(isinstance(summary, dict) and summary == handoff["results"][method],
                "RETRIEVAL_SUMMARY_METRIC_MISMATCH")
        executed, status = execution_state(grouped[method])
        source_status = summary.get("status")
        require(source_status in {None, "EXECUTED", "NOT_EXECUTED", "UNMEASURED", "HOLD",
                                  "NOT_APPLICABLE", "PARTIAL"})
        if source_status == "NOT_EXECUTED":
            require(executed is not True)
            executed, status = False, "NOT_EXECUTED"
        values, statuses = {}, {}
        for field in (*METRICS, "full_evidence_cases", "answerable_cases"):
            value = summary.get(field)
            if value is not None:
                require(type(value) in {int, float} and math.isfinite(value) and value >= 0)
                require(executed is not False and source_status not in {
                    "NOT_EXECUTED", "UNMEASURED", "HOLD", "NOT_APPLICABLE",
                })
                if field in {"mean_recall_at_5", "mean_mrr_at_5"}:
                    require(value <= 1)
                if field in {"full_evidence_cases", "answerable_cases"}:
                    count(value)
            values[field] = value
            statuses[field] = ("MEASURED" if value is not None else
                               source_status if source_status in {
                                   "NOT_EXECUTED", "UNMEASURED", "HOLD", "NOT_APPLICABLE",
                               } else "NOT_EXECUTED" if executed is False else "UNMEASURED")
        numerator, denominator = values.pop("full_evidence_cases"), values.pop("answerable_cases")
        require(numerator is None or (denominator is not None and numerator <= denominator))
        methods.append(MethodSummary(
            method=method, executed=executed, execution_status=status, source_status=source_status,
            **values, full_evidence_numerator=numerator, full_evidence_denominator=denominator,
            metric_status=statuses,
        ))
    corpus_version = current_manifest["corpus"].get("version")
    require(corpus_version is None or (isinstance(corpus_version, str)
                                     and re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", corpus_version)))
    required_scale = handoff["schedule_followup"]["actual_scale_retrieval_validation_required"]
    require(type(required_scale) is bool and type(result["hold_behavior_evaluated"]) is bool)
    return DevSummary(
        experiment_id=result["experiment_id"], handoff_id=handoff["handoff_id"],
        evaluation_as_of=result["evaluation_as_of"],
        selection=Selection(method=selection["method"], status=selection["status"]),
        corpus_version=corpus_version,
        corpus_version_status="PROVIDED" if corpus_version else "NOT_PROVIDED",
        corpus_sha256=digest(dataset["corpus_sha256"]), corpus_documents=dataset["corpus_records"],
        experiment_snapshot=SnapshotSummary(version=old_manifest["snapshot_version"],
            canonical_hash=old_manifest["snapshot_hash"], file_sha256=dataset["snapshot_sha256"]),
        runtime_snapshot=SnapshotSummary(version=current_manifest["snapshot_version"],
            canonical_hash=current_manifest["snapshot_hash"],
            file_sha256=digest(current_manifest["snapshot_file_sha256"])),
        query_count=result["query_count"], execution_count=result["execution_count"],
        all_executed=all_executed, error_count=executions["error_count"],
        external_embedding_api_calls=external_calls,
        actual_retrieval_executed_in_experiment=actual,
        runtime_search_available=runtime_search_available, data_mode="SYNTHETIC_DEMO",
        actual_scale_retrieval_validation_required=required_scale,
        hold_behavior_evaluated=result["hold_behavior_evaluated"], methods=methods,
        latency_scope="historical DEV retrieval; milliseconds; not API latency",
    )
