from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


# R08에서 사람 검수까지 끝난 고정 gold.
DEFAULT_GOLD_PATH = Path(
    "ai/evaluation/datasets/golden_graph/r08_gold_cases.json"
)

EXPECTED_STATUS_COUNTS = {
    "ANSWER": 3,
    "NO_EDGE": 2,
    "HOLD": 1,
}

EXPECTED_TOTAL_CASES = 6


class R09GraphMethod(str, Enum):
    """R09 E05에서 비교할 세 가지 고정 방법."""

    DETERMINISTIC = "DETERMINISTIC"
    HYBRID = "HYBRID"
    RELATION_DOCUMENT = "RELATION_DOCUMENT"


@dataclass(frozen=True)
class EmbeddingConfig:
    model: str
    revision: str
    dimension: int
    normalized: bool


# R07-PRE 실제 평가에서 이미 사용하고 재현값이 확인된 embedding 설정.
R09_EMBEDDING_CONFIG = EmbeddingConfig(
    model="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    revision="e8f8c211226b894fcb81acc59f3b34ba3efd5f42",
    dimension=384,
    normalized=True,
)

@dataclass(frozen=True)
class GraphEvalScore:
    case_id: str
    method: R09GraphMethod
    expected_status: str
    predicted_status: str

    status_match: bool
    path_match: bool | None
    relation_match: bool | None
    false_edge_count: int
    hold_correct: bool | None

    evidence_available: bool | None
    provenance_available: bool | None
    source_available: bool | None
    valid_time_available: bool | None

    failure_reason: str | None

    passed: bool

@dataclass(frozen=True)
class GraphEvalPrediction:
    case_id: str
    method: R09GraphMethod
    predicted_status: str

    predicted_nodes: tuple[str, ...] = ()
    predicted_relations: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()

    evidence_available: bool | None = None
    provenance_available: bool | None = None
    source_available: bool | None = None
    valid_time_available: bool | None = None

    latency_ms: float | None = None
    error: str | None = None
    
def load_gold_cases(
    path: Path = DEFAULT_GOLD_PATH,
) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as fp:
        payload = json.load(fp)

    cases = payload.get("cases")
    if not isinstance(cases, list):
        raise ValueError("gold payload must contain a cases list")

    return cases


def validate_gold_contract(
    cases: list[dict[str, Any]],
) -> dict[str, int]:
    """R08 gold를 R09 튜닝 때문에 바꾸지 않았는지 최소 계약을 검사한다."""

    if len(cases) != EXPECTED_TOTAL_CASES:
        raise ValueError(
            f"expected {EXPECTED_TOTAL_CASES} cases, got {len(cases)}"
        )

    required_fields = {
        "case_id",
        "question",
        "start_node",
        "intermediate_nodes",
        "end_nodes",
        "required_relations",
        "expected",
        "expected_status",
        "query_sha256",
        "gold_sha256",
    }

    status_counts = {
        "ANSWER": 0,
        "NO_EDGE": 0,
        "HOLD": 0,
    }

    seen_case_ids: set[str] = set()

    for case in cases:
        missing = required_fields - set(case)
        if missing:
            raise ValueError(
                f"{case.get('case_id', '<unknown>')} missing fields: "
                f"{sorted(missing)}"
            )

        case_id = case["case_id"]
        if case_id in seen_case_ids:
            raise ValueError(f"duplicate case_id: {case_id}")
        seen_case_ids.add(case_id)

        status = case["expected_status"]
        if status not in status_counts:
            raise ValueError(
                f"{case_id} has unsupported expected_status: {status}"
            )

        status_counts[status] += 1

    if status_counts != EXPECTED_STATUS_COUNTS:
        raise ValueError(
            "unexpected status distribution: "
            f"{status_counts}, expected {EXPECTED_STATUS_COUNTS}"
        )

    return status_counts


def _expected_nodes(case: dict[str, Any]) -> tuple[str, ...]:
    return (
        case["start_node"],
        *case["intermediate_nodes"],
        *case["end_nodes"],
    )


def score_prediction(
    case: dict[str, Any],
    prediction: GraphEvalPrediction,
) -> GraphEvalScore:
    """
    R09 E05 공통 판정.

    ANSWER:
      - 상태 일치
      - 필요한 node/path 정확 일치
      - required relation 정확 일치
      - 불필요 edge/node 0

    NO_EDGE:
      - NO_EDGE를 유지
      - target으로의 fabricated edge/node가 없어야 함

    HOLD:
      - HOLD 유지
      - 관계/node를 만들어내지 않아야 함
    """

    expected_status = case["expected_status"]
    status_match = prediction.predicted_status == expected_status

    expected_nodes = _expected_nodes(case)
    expected_relations = tuple(case["required_relations"])

    predicted_nodes = tuple(prediction.predicted_nodes)
    predicted_relations = tuple(prediction.predicted_relations)

    if expected_status == "ANSWER":
        path_match = predicted_nodes == expected_nodes
        relation_match = predicted_relations == expected_relations

        expected_node_set = set(expected_nodes)
        expected_relation_set = set(expected_relations)

        unexpected_nodes = [
            node
            for node in predicted_nodes
            if node not in expected_node_set
        ]
        unexpected_relations = [
            relation
            for relation in predicted_relations
            if relation not in expected_relation_set
        ]

        false_edge_count = (
            len(unexpected_nodes)
            + len(unexpected_relations)
        )

        hold_correct = None

        passed = (
            status_match
            and path_match
            and relation_match
            and false_edge_count == 0
            and prediction.error is None
        )

    elif expected_status == "NO_EDGE":
        path_match = None
        relation_match = None

        # NO_EDGE case에서는 관계를 만들어내는 순간 실패.
        false_edge_count = (
            len(predicted_nodes)
            + len(predicted_relations)
        )

        hold_correct = None

        passed = (
            status_match
            and false_edge_count == 0
            and prediction.error is None
        )

    elif expected_status == "HOLD":
        path_match = None
        relation_match = None

        false_edge_count = (
            len(predicted_nodes)
            + len(predicted_relations)
        )

        hold_correct = (
            prediction.predicted_status == "HOLD"
            and false_edge_count == 0
        )

        passed = (
            status_match
            and hold_correct
            and prediction.error is None
        )

    else:
        raise ValueError(
            f"unsupported expected_status: {expected_status}"
        )

    return GraphEvalScore(
        case_id=case["case_id"],
        method=prediction.method,
        expected_status=expected_status,
        predicted_status=prediction.predicted_status,
        status_match=status_match,
        path_match=path_match,
        relation_match=relation_match,
        false_edge_count=false_edge_count,
        hold_correct=hold_correct,
        passed=passed,
        evidence_available=prediction.evidence_available,
        provenance_available=prediction.provenance_available,
        source_available=prediction.source_available,
        valid_time_available=prediction.valid_time_available,
        failure_reason=prediction.error,
    )