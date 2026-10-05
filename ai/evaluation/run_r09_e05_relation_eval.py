from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import time
from dataclasses import asdict
from inspect import signature
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from sentence_transformers import SentenceTransformer

from ai.evaluation.r09_graph_eval_contract import (
    R09_EMBEDDING_CONFIG,
    GraphEvalPrediction,
    R09GraphMethod,
    load_gold_cases,
    score_prediction,
    validate_gold_contract,
)
from ai.retrieval.bm25 import BM25Config, BM25Document, BM25Index
from ai.retrieval.dense import DenseDocument, DenseIndex
from ai.retrieval.hybrid import reciprocal_rank_fusion


SNAPSHOT_PATH = Path(
    "ai/evaluation/datasets/golden_graph/r08_c08_relation_snapshot.json"
)
GOLD_PATH = Path(
    "ai/evaluation/datasets/golden_graph/r08_gold_cases.json"
)
OUTPUT_DIR = Path("artifacts/experiments/R09/E05")

EXPECTED_SNAPSHOT_ID = "c08-r08-synthetic-v1"
EXPECTED_SNAPSHOT_SHA256 = (
    "aefc694a5c3364752934f2a33616500b464f3e1e21a27413b6f7420a56b45d40"
)

CANDIDATE_TOP_K = 8
RRF_K = 60

TYPE_LABELS = {
    "INCOMING_STOCK": ("입고", "incoming", "incoming stock"),
    "TASK": ("task", "업무", "작업", "검수", "상품 페이지", "product page"),
    "RESERVATION": ("예약", "reservation"),
    "LAUNCH_EVENT": ("출시", "launch", "출시 이벤트"),
}
RELATION_LABELS = {
    "IMPACTS": ("영향", "impacts"),
    "PRECEDES": ("선행", "precedes"),
}

QUESTION_ALIASES = {
    "상품 페이지": "product page",
    "상품페이지": "product page",
    "검수": "inspection",
    "예약": "reservation",
    "출시 이벤트": "launch event",
    "출시": "launch",
    "입고": "incoming",
    "영향": "impacts",
    "선행": "precedes",
}


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fp:
        payload = json.load(fp)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _node_key(node_type: str, node_id: str) -> str:
    return f"{node_type}:{node_id}"


def _edge_key(edge: dict[str, Any]) -> str:
    return (
        f"edge:{edge['from_type']}:{edge['from_id']}"
        f"->{edge['relation_type']}->"
        f"{edge['to_type']}:{edge['to_id']}"
    )


def _validate_snapshot(snapshot: dict[str, Any]) -> None:
    if snapshot.get("source_snapshot_id") != EXPECTED_SNAPSHOT_ID:
        raise ValueError("unexpected R08 source_snapshot_id")
    if snapshot.get("source_snapshot_sha256") != EXPECTED_SNAPSHOT_SHA256:
        raise ValueError("unexpected R08 source_snapshot_sha256")
    if snapshot.get("data_mode") != "SYNTHETIC_DEMO":
        raise ValueError("R09 E05 must use SYNTHETIC_DEMO snapshot")
    if not isinstance(snapshot.get("nodes"), list):
        raise ValueError("snapshot nodes must be a list")
    if not isinstance(snapshot.get("edges"), list):
        raise ValueError("snapshot edges must be a list")


def _edge_text(edge: dict[str, Any]) -> str:
    from_type = str(edge["from_type"])
    to_type = str(edge["to_type"])
    relation = str(edge["relation_type"])
    from_labels = " ".join(TYPE_LABELS.get(from_type, (from_type,)))
    to_labels = " ".join(TYPE_LABELS.get(to_type, (to_type,)))
    relation_labels = " ".join(RELATION_LABELS.get(relation, (relation,)))
    return (
        f"{from_type} {edge['from_id']} {from_labels} "
        f"{relation} {relation_labels} "
        f"{to_type} {edge['to_id']} {to_labels}. "
        f"incoming_id={edge.get('incoming_id')} "
        f"source={edge.get('source_classification')} "
        f"source_id={edge.get('source_id')} "
        f"provenance={edge.get('provenance_scope')} "
        f"as_of={edge.get('as_of')} "
        f"quality={edge.get('quality')} "
        f"missing_status={edge.get('missing_status')}"
    )


def _document_kwargs(edge: dict[str, Any]) -> dict[str, Any]:
    return {
        "chunk_id": _edge_key(edge),
        "source_id": _edge_key(edge),
        "source_type": "RELATION_EDGE",
        "version": str(edge.get("version") or EXPECTED_SNAPSHOT_ID),
        "text": _edge_text(edge),
        "metadata": {
            "title": _edge_key(edge),
            "name": f"{edge['from_id']} {edge['to_id']}",
            "brand": "",
            "sku": str(edge.get("incoming_id") or ""),
            "category": str(edge["relation_type"]),
            "language": "ko-en",
            "from_type": str(edge["from_type"]),
            "from_id": str(edge["from_id"]),
            "to_type": str(edge["to_type"]),
            "to_id": str(edge["to_id"]),
            "relation_type": str(edge["relation_type"]),
            "source_classification": str(edge.get("source_classification") or ""),
            "source_id_authoritative": str(edge.get("source_id") or ""),
            "provenance_scope": str(edge.get("provenance_scope") or ""),
            "as_of": str(edge.get("as_of") or ""),
        },
    }


def _construct_dense_document(kwargs: dict[str, Any]) -> DenseDocument:
    allowed = set(signature(DenseDocument).parameters)
    filtered = {key: value for key, value in kwargs.items() if key in allowed}
    return DenseDocument(**filtered)


def _build_documents(
    edges: list[dict[str, Any]],
) -> tuple[list[BM25Document], list[DenseDocument]]:
    bm25_docs: list[BM25Document] = []
    dense_docs: list[DenseDocument] = []
    for edge in edges:
        kwargs = _document_kwargs(edge)
        bm25_docs.append(BM25Document(**kwargs))
        dense_docs.append(_construct_dense_document(kwargs))
    return bm25_docs, dense_docs


def _normalize_query(question: str) -> str:
    normalized = question.lower()
    for source, target in QUESTION_ALIASES.items():
        normalized = normalized.replace(source, f" {target} ")
    return re.sub(r"\s+", " ", normalized).strip()


def _question_node_ids(
    question: str,
    nodes: list[dict[str, Any]],
) -> list[str]:
    q = question.lower()
    found: list[str] = []
    for node in nodes:
        node_id = str(node["id"])
        if node_id.lower() in q:
            found.append(_node_key(str(node["type"]), node_id))
    return found


def _infer_target_types(question: str) -> list[str]:
    q = question.lower()
    result: list[str] = []
    if "예약" in q or "reservation" in q:
        result.append("RESERVATION")
    if "출시" in q or "launch" in q:
        result.append("LAUNCH_EVENT")
    if (
        "task" in q
        or "업무" in q
        or "작업" in q
        or "검수" in q
        or "상품 페이지" in q
        or "상품페이지" in q
    ):
        result.append("TASK")
    return result


def _is_hold_question(question: str) -> bool:
    q = question.lower()
    hold_tokens = (
        "blocked",
        "unknown",
        "authoritative source가 없",
        "authoritative source 없",
        "근거부족",
        "근거 부족",
        "날짜나",
    )
    return any(token in q for token in hold_tokens)


def _build_adjacency(
    edges: Iterable[dict[str, Any]],
) -> dict[str, list[tuple[str, str, dict[str, Any]]]]:
    adjacency: dict[str, list[tuple[str, str, dict[str, Any]]]] = {}
    for edge in edges:
        source = _node_key(str(edge["from_type"]), str(edge["from_id"]))
        target = _node_key(str(edge["to_type"]), str(edge["to_id"]))
        adjacency.setdefault(source, []).append(
            (target, str(edge["relation_type"]), edge)
        )
    for values in adjacency.values():
        values.sort(key=lambda item: (item[0], item[1]))
    return adjacency


def _all_paths(
    adjacency: dict[str, list[tuple[str, str, dict[str, Any]]]],
    start: str,
    *,
    max_depth: int = 4,
) -> list[tuple[list[str], list[str], list[dict[str, Any]]]]:
    paths: list[tuple[list[str], list[str], list[dict[str, Any]]]] = []

    def visit(
        current: str,
        nodes: list[str],
        relations: list[str],
        edge_rows: list[dict[str, Any]],
        seen: set[str],
    ) -> None:
        if len(relations) >= max_depth:
            return
        for target, relation, edge in adjacency.get(current, []):
            if target in seen:
                continue
            new_nodes = [*nodes, target]
            new_relations = [*relations, relation]
            new_edges = [*edge_rows, edge]
            paths.append((new_nodes, new_relations, new_edges))
            visit(
                target,
                new_nodes,
                new_relations,
                new_edges,
                {*seen, target},
            )

    visit(start, [start], [], [], {start})
    return paths


def _terminal_type(node_key: str) -> str:
    return node_key.split(":", 1)[0]


def _path_relevance(question: str, path_nodes: list[str]) -> tuple[int, int, str]:
    q = _normalize_query(question)
    terminal = path_nodes[-1].lower().replace("_", " ").replace("-", " ")
    overlap = sum(
        1
        for token in re.findall(r"[a-z0-9가-힣]+", terminal)
        if len(token) >= 3 and token in q
    )
    return (overlap, len(path_nodes), path_nodes[-1])


def _resolve_authoritative_path(
    question: str,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> tuple[str, tuple[str, ...], tuple[str, ...], list[dict[str, Any]]]:
    if _is_hold_question(question):
        return "HOLD", (), (), []

    explicit_nodes = _question_node_ids(question, nodes)
    incoming_nodes = [
        key for key in explicit_nodes if key.startswith("INCOMING_STOCK:")
    ]
    start = incoming_nodes[0] if incoming_nodes else None

    if start is None:
        return "HOLD", (), (), []

    adjacency = _build_adjacency(edges)
    paths = _all_paths(adjacency, start)

    explicit_targets = [
        key
        for key in explicit_nodes
        if key != start
    ]
    if explicit_targets:
        target_set = set(explicit_targets)
        matching = [path for path in paths if path[0][-1] in target_set]
        if not matching:
            return "NO_EDGE", (), (), []
        matching.sort(
            key=lambda p: _path_relevance(question, p[0]),
            reverse=True,
        )
        nodes_path, relations, edge_rows = matching[0]
        return (
            "ANSWER",
            tuple(nodes_path),
            tuple(relations),
            edge_rows,
        )

    target_types = _infer_target_types(question)
    if not target_types:
        return "HOLD", (), (), []

    matching = [
        path
        for path in paths
        if _terminal_type(path[0][-1]) in target_types
    ]
    if not matching:
        return "NO_EDGE", (), (), []

    matching.sort(
        key=lambda p: _path_relevance(question, p[0]),
        reverse=True,
    )
    nodes_path, relations, edge_rows = matching[0]
    return "ANSWER", tuple(nodes_path), tuple(relations), edge_rows


def _availability(
    status: str,
    used_edges: list[dict[str, Any]],
    snapshot: dict[str, Any],
) -> tuple[bool | None, bool | None, bool | None, bool | None]:
    if status == "HOLD":
        return False, False, False, False

    scope = used_edges if used_edges else list(snapshot["edges"])
    if not scope:
        return False, False, False, False

    evidence = all(bool(edge.get("source_id")) for edge in scope)
    provenance = all(bool(edge.get("provenance_scope")) for edge in scope)
    source = all(bool(edge.get("source_classification")) for edge in scope)
    valid_time = all(bool(edge.get("as_of")) for edge in scope)
    return evidence, provenance, source, valid_time


def _prediction_from_edges(
    *,
    question: str,
    method: R09GraphMethod,
    snapshot: dict[str, Any],
    candidate_edges: list[dict[str, Any]],
    latency_ms: float,
    evidence_ids: tuple[str, ...] = (),
) -> GraphEvalPrediction:
    status, nodes, relations, used_edges = _resolve_authoritative_path(
        question,
        list(snapshot["nodes"]),
        candidate_edges,
    )
    evidence, provenance, source, valid_time = _availability(
        status, used_edges, snapshot
    )
    if not evidence_ids and used_edges:
        evidence_ids = tuple(
            str(edge.get("source_id") or _edge_key(edge))
            for edge in used_edges
        )
    return GraphEvalPrediction(
        case_id="",
        method=method,
        predicted_status=status,
        predicted_nodes=nodes,
        predicted_relations=relations,
        evidence_ids=evidence_ids,
        evidence_available=evidence,
        provenance_available=provenance,
        source_available=source,
        valid_time_available=valid_time,
        latency_ms=latency_ms,
        error=None,
    )


class R09E05Runner:
    def __init__(self, snapshot: dict[str, Any]) -> None:
        self.snapshot = snapshot
        self.edges = list(snapshot["edges"])
        self.edge_by_doc_id = {
            _edge_key(edge): edge for edge in self.edges
        }

        bm25_docs, dense_docs = _build_documents(self.edges)
        self.bm25_index = BM25Index(bm25_docs, config=BM25Config())

        self.model = SentenceTransformer(
            R09_EMBEDDING_CONFIG.model,
            revision=R09_EMBEDDING_CONFIG.revision,
            device="cpu",
        )

        def embed_texts(texts: list[str]) -> np.ndarray:
            return np.asarray(
                self.model.encode(
                    texts,
                    convert_to_numpy=True,
                    normalize_embeddings=R09_EMBEDDING_CONFIG.normalized,
                    show_progress_bar=False,
                ),
                dtype=np.float32,
            )

        self.dense_index = DenseIndex(
            dense_docs,
            embed_texts=embed_texts,
        )

        if self.dense_index.vector_dimension != R09_EMBEDDING_CONFIG.dimension:
            raise RuntimeError(
                "dense dimension mismatch: "
                f"{self.dense_index.vector_dimension} "
                f"!= {R09_EMBEDDING_CONFIG.dimension}"
            )

    def deterministic(self, question: str) -> GraphEvalPrediction:
        started = time.perf_counter()
        status, nodes, relations, used_edges = _resolve_authoritative_path(
            question,
            list(self.snapshot["nodes"]),
            self.edges,
        )
        latency_ms = (time.perf_counter() - started) * 1000.0
        evidence, provenance, source, valid_time = _availability(
            status, used_edges, self.snapshot
        )
        return GraphEvalPrediction(
            case_id="",
            method=R09GraphMethod.DETERMINISTIC,
            predicted_status=status,
            predicted_nodes=nodes,
            predicted_relations=relations,
            evidence_ids=tuple(
                str(edge.get("source_id") or _edge_key(edge))
                for edge in used_edges
            ),
            evidence_available=evidence,
            provenance_available=provenance,
            source_available=source,
            valid_time_available=valid_time,
            latency_ms=latency_ms,
        )

    def hybrid(self, question: str) -> GraphEvalPrediction:
        started = time.perf_counter()
        bm25 = self.bm25_index.search(
            question,
            top_k=min(CANDIDATE_TOP_K, self.bm25_index.document_count),
        )
        dense = self.dense_index.search(
            question,
            top_k=min(CANDIDATE_TOP_K, self.dense_index.document_count),
        )
        fused = reciprocal_rank_fusion(
            bm25,
            dense,
            candidate_top_k=CANDIDATE_TOP_K,
            rrf_k=RRF_K,
        )

        # 검색 유사도만으로 edge를 확정하지 않는다.
        # 검색된 문서는 authoritative snapshot edge로 다시 resolve한다.
        candidate_edges = [
            self.edge_by_doc_id[item.source_id]
            for item in fused
            if item.source_id in self.edge_by_doc_id
        ]
        latency_ms = (time.perf_counter() - started) * 1000.0

        status, nodes, relations, used_edges = _resolve_authoritative_path(
            question,
            list(self.snapshot["nodes"]),
            candidate_edges,
        )
        evidence, provenance, source, valid_time = _availability(
            status, used_edges, self.snapshot
        )

        return GraphEvalPrediction(
            case_id="",
            method=R09GraphMethod.HYBRID,
            predicted_status=status,
            predicted_nodes=nodes,
            predicted_relations=relations,
            evidence_ids=tuple(item.source_id for item in fused),
            evidence_available=evidence,
            provenance_available=provenance,
            source_available=source,
            valid_time_available=valid_time,
            latency_ms=latency_ms,
        )

    def relation_document(self, question: str) -> GraphEvalPrediction:
        started = time.perf_counter()

        # 권위 graph path를 먼저 확정하고, 해당 path edge의 source/provenance를
        # evidence로 함께 반환한다. 문서 검색 결과만으로 새 edge를 만들지 않는다.
        status, nodes, relations, used_edges = _resolve_authoritative_path(
            question,
            list(self.snapshot["nodes"]),
            self.edges,
        )

        evidence_ids = tuple(
            f"{edge.get('source_id')}|{edge.get('provenance_scope')}"
            for edge in used_edges
        )
        latency_ms = (time.perf_counter() - started) * 1000.0
        evidence, provenance, source, valid_time = _availability(
            status, used_edges, self.snapshot
        )

        return GraphEvalPrediction(
            case_id="",
            method=R09GraphMethod.RELATION_DOCUMENT,
            predicted_status=status,
            predicted_nodes=nodes,
            predicted_relations=relations,
            evidence_ids=evidence_ids,
            evidence_available=evidence,
            provenance_available=provenance,
            source_available=source,
            valid_time_available=valid_time,
            latency_ms=latency_ms,
        )


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _method_summary(rows: list[dict[str, Any]], method: str) -> dict[str, Any]:
    selected = [row for row in rows if row["method"] == method]
    latencies = [
        float(row["latency_ms"])
        for row in selected
        if row.get("latency_ms") is not None
    ]
    status_counts: dict[str, int] = {}
    for row in selected:
        status_counts[row["predicted_status"]] = (
            status_counts.get(row["predicted_status"], 0) + 1
        )

    return {
        "planned_units": 6,
        "executed_units": len(selected),
        "passed": sum(bool(row["passed"]) for row in selected),
        "failed": sum(not bool(row["passed"]) for row in selected),
        "pass_rate": (
            sum(bool(row["passed"]) for row in selected) / len(selected)
            if selected
            else 0.0
        ),
        "false_edge_count": sum(int(row["false_edge_count"]) for row in selected),
        "predicted_status_counts": status_counts,
        "latency_ms": {
            "mean": statistics.fmean(latencies) if latencies else None,
            "p95": _percentile(latencies, 0.95),
        },
    }


def run() -> dict[str, Any]:
    snapshot = _load_json(SNAPSHOT_PATH)
    _validate_snapshot(snapshot)

    cases = load_gold_cases(GOLD_PATH)
    expected_status_counts = validate_gold_contract(cases)

    runner = R09E05Runner(snapshot)
    rows: list[dict[str, Any]] = []

    predictors = (
        (R09GraphMethod.DETERMINISTIC, runner.deterministic),
        (R09GraphMethod.HYBRID, runner.hybrid),
        (R09GraphMethod.RELATION_DOCUMENT, runner.relation_document),
    )

    for method, predictor in predictors:
        for case in cases:
            # IMPORTANT:
            # predictor receives question only. expected/path/status stay evaluator-only.
            prediction = predictor(str(case["question"]))
            prediction = GraphEvalPrediction(
                **{
                    **asdict(prediction),
                    "case_id": str(case["case_id"]),
                    "method": method,
                }
            )
            score = score_prediction(case, prediction)
            row = asdict(score)
            row["method"] = method.value
            row["latency_ms"] = prediction.latency_ms
            row["evidence_ids"] = list(prediction.evidence_ids)
            row["predicted_nodes"] = list(prediction.predicted_nodes)
            row["predicted_relations"] = list(prediction.predicted_relations)
            rows.append(row)

    summary = {
        "experiment_id": "E05",
        "task_id": "R09-AI-01",
        "schema_version": "r09-e05-relation-eval.v1",
        "source_snapshot_id": snapshot["source_snapshot_id"],
        "source_snapshot_sha256": snapshot["source_snapshot_sha256"],
        "gold_version": "v0.1",
        "data_mode": snapshot["data_mode"],
        "quality": snapshot.get("quality"),
        "planned_evaluation_units": 18,
        "executed_evaluation_units": len(rows),
        "external_llm_calls": 0,
        "external_embedding_api_calls": 0,
        "embedding": asdict(R09_EMBEDDING_CONFIG),
        "retrieval": {
            "candidate_top_k": CANDIDATE_TOP_K,
            "rrf_k": RRF_K,
            "dense_device": "cpu",
            "vector_persistence": "DEFER_VECTOR_PERSISTENCE",
        },
        "gold_status_counts": expected_status_counts,
        "methods": {
            method.value: _method_summary(rows, method.value)
            for method in R09GraphMethod
        },
        "all_passed": all(bool(row["passed"]) for row in rows),
        "limitations": [
            "SYNTHETIC_DEMO fixed relation snapshot only; not actual inventory/incoming/task runtime.",
            "The snapshot contains four authoritative edges, so retrieval candidate space is very small.",
            "Hybrid similarity is used only to retrieve candidate authoritative edges; similarity never creates an edge.",
            "No LLM generation is executed in E05.",
            "No pgvector/vector writer is introduced; DenseIndex remains in-memory.",
            "FINAL12 is not used.",
        ],
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    result_path = OUTPUT_DIR / "r09_e05_relation_eval_result.json"
    summary_path = OUTPUT_DIR / "r09_e05_relation_eval_summary.json"

    with result_path.open("w", encoding="utf-8") as fp:
        json.dump(
            {
                "summary": summary,
                "rows": rows,
            },
            fp,
            ensure_ascii=False,
            indent=2,
        )

    with summary_path.open("w", encoding="utf-8") as fp:
        json.dump(summary, fp, ensure_ascii=False, indent=2)

    print("R09_E05_RELATION_EVAL_OK")
    print(f"PLANNED_UNITS={summary['planned_evaluation_units']}")
    print(f"EXECUTED_UNITS={summary['executed_evaluation_units']}")
    print(f"EXTERNAL_LLM_CALLS={summary['external_llm_calls']}")
    for method, data in summary["methods"].items():
        print(
            f"{method}: passed={data['passed']}/{data['executed_units']} "
            f"false_edges={data['false_edge_count']} "
            f"mean_ms={data['latency_ms']['mean']} "
            f"p95_ms={data['latency_ms']['p95']}"
        )
    print(f"ALL_PASSED={summary['all_passed']}")
    print(f"RESULT={result_path}")
    print(f"SUMMARY={summary_path}")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run R09 E05 relation evaluation.")
    parser.parse_args()
    run()


if __name__ == "__main__":
    main()
