"""D10-BE-02 Task dependency 검증과 cycle 탐지."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable


class DependencyValidationCode(StrEnum):
    """Dependency 검증 결과 코드."""

    VALID = "VALID"
    DEPENDENCY_FREE = "DEPENDENCY_FREE"
    MISSING_PREDECESSOR = "MISSING_PREDECESSOR"
    MISSING_SUCCESSOR = "MISSING_SUCCESSOR"
    DUPLICATE_EDGE = "DUPLICATE_EDGE"
    SELF_CYCLE = "SELF_CYCLE"
    CYCLE = "CYCLE"


@dataclass(frozen=True, order=True)
class DependencyEdge:
    """Task 간 선행/후행 관계."""

    predecessor_id: str
    successor_id: str
    lag_hours: int = 0

    def __post_init__(self) -> None:
        if self.lag_hours < 0:
            raise ValueError("lag_hours must be >= 0")


@dataclass(frozen=True)
class DependencyValidationResult:
    """Dependency graph 검증 결과."""

    valid: bool
    code: DependencyValidationCode
    message: str
    graph: tuple[DependencyEdge, ...]
    rejected_edge: DependencyEdge | None = None


def _canonical_graph(
    edges: Iterable[DependencyEdge],
) -> tuple[DependencyEdge, ...]:
    """비교와 재현성을 위해 edge 순서를 고정한다."""

    return tuple(
        sorted(
            edges,
            key=lambda edge: (
                edge.predecessor_id,
                edge.successor_id,
                edge.lag_hours,
            ),
        )
    )


def _contains_cycle(edges: Iterable[DependencyEdge]) -> bool:
    """Directed graph의 cycle 존재 여부를 검사한다."""

    adjacency: dict[str, set[str]] = {}

    for edge in edges:
        adjacency.setdefault(edge.predecessor_id, set()).add(
            edge.successor_id
        )
        adjacency.setdefault(edge.successor_id, set())

    # 0 = 미방문, 1 = 방문 중, 2 = 완료
    state: dict[str, int] = {node_id: 0 for node_id in adjacency}

    def visit(node_id: str) -> bool:
        node_state = state[node_id]

        if node_state == 1:
            return True

        if node_state == 2:
            return False

        state[node_id] = 1

        for successor_id in sorted(adjacency[node_id]):
            if visit(successor_id):
                return True

        state[node_id] = 2
        return False

    for node_id in sorted(adjacency):
        if state[node_id] == 0 and visit(node_id):
            return True

    return False


def validate_dependency_graph(
    *,
    task_ids: Iterable[str],
    edges: Iterable[DependencyEdge],
) -> DependencyValidationResult:
    """현재 graph 전체를 검증한다."""

    known_tasks = frozenset(task_ids)
    original_graph = _canonical_graph(edges)

    if not original_graph:
        return DependencyValidationResult(
            valid=True,
            code=DependencyValidationCode.DEPENDENCY_FREE,
            message="dependency가 없는 Task graph입니다.",
            graph=original_graph,
        )

    seen_pairs: set[tuple[str, str]] = set()

    for edge in original_graph:
        if edge.predecessor_id not in known_tasks:
            return DependencyValidationResult(
                valid=False,
                code=DependencyValidationCode.MISSING_PREDECESSOR,
                message=(
                    f"존재하지 않는 predecessor입니다: "
                    f"{edge.predecessor_id}"
                ),
                graph=original_graph,
                rejected_edge=edge,
            )

        if edge.successor_id not in known_tasks:
            return DependencyValidationResult(
                valid=False,
                code=DependencyValidationCode.MISSING_SUCCESSOR,
                message=(
                    f"존재하지 않는 successor입니다: "
                    f"{edge.successor_id}"
                ),
                graph=original_graph,
                rejected_edge=edge,
            )

        if edge.predecessor_id == edge.successor_id:
            return DependencyValidationResult(
                valid=False,
                code=DependencyValidationCode.SELF_CYCLE,
                message="Task는 자기 자신을 predecessor로 가질 수 없습니다.",
                graph=original_graph,
                rejected_edge=edge,
            )

        pair = (edge.predecessor_id, edge.successor_id)

        if pair in seen_pairs:
            return DependencyValidationResult(
                valid=False,
                code=DependencyValidationCode.DUPLICATE_EDGE,
                message=(
                    "동일 predecessor/successor dependency가 "
                    "중복되었습니다."
                ),
                graph=original_graph,
                rejected_edge=edge,
            )

        seen_pairs.add(pair)

    if _contains_cycle(original_graph):
        return DependencyValidationResult(
            valid=False,
            code=DependencyValidationCode.CYCLE,
            message="Task dependency graph에 cycle이 존재합니다.",
            graph=original_graph,
        )

    return DependencyValidationResult(
        valid=True,
        code=DependencyValidationCode.VALID,
        message="Task dependency graph가 유효합니다.",
        graph=original_graph,
    )


def add_dependency(
    *,
    task_ids: Iterable[str],
    existing_edges: Iterable[DependencyEdge],
    new_edge: DependencyEdge,
) -> DependencyValidationResult:
    """
    기존 graph에 edge 하나를 추가할 수 있는지 검증한다.

    검증 실패 시 반환 graph는 기존 graph 그대로이며,
    partial mutation을 발생시키지 않는다.
    """

    known_tasks = frozenset(task_ids)
    original_graph = _canonical_graph(existing_edges)

    if new_edge.predecessor_id not in known_tasks:
        return DependencyValidationResult(
            valid=False,
            code=DependencyValidationCode.MISSING_PREDECESSOR,
            message=(
                f"존재하지 않는 predecessor입니다: "
                f"{new_edge.predecessor_id}"
            ),
            graph=original_graph,
            rejected_edge=new_edge,
        )

    if new_edge.successor_id not in known_tasks:
        return DependencyValidationResult(
            valid=False,
            code=DependencyValidationCode.MISSING_SUCCESSOR,
            message=(
                f"존재하지 않는 successor입니다: "
                f"{new_edge.successor_id}"
            ),
            graph=original_graph,
            rejected_edge=new_edge,
        )

    if new_edge.predecessor_id == new_edge.successor_id:
        return DependencyValidationResult(
            valid=False,
            code=DependencyValidationCode.SELF_CYCLE,
            message="Task는 자기 자신을 predecessor로 가질 수 없습니다.",
            graph=original_graph,
            rejected_edge=new_edge,
        )

    existing_pairs = {
        (edge.predecessor_id, edge.successor_id)
        for edge in original_graph
    }
    new_pair = (
        new_edge.predecessor_id,
        new_edge.successor_id,
    )

    if new_pair in existing_pairs:
        return DependencyValidationResult(
            valid=False,
            code=DependencyValidationCode.DUPLICATE_EDGE,
            message=(
                "동일 predecessor/successor dependency가 "
                "이미 존재합니다."
            ),
            graph=original_graph,
            rejected_edge=new_edge,
        )

    candidate_graph = _canonical_graph(
        (*original_graph, new_edge)
    )

    if _contains_cycle(candidate_graph):
        return DependencyValidationResult(
            valid=False,
            code=DependencyValidationCode.CYCLE,
            message="추가한 dependency가 cycle을 생성합니다.",
            graph=original_graph,
            rejected_edge=new_edge,
        )

    return DependencyValidationResult(
        valid=True,
        code=DependencyValidationCode.VALID,
        message="dependency를 추가할 수 있습니다.",
        graph=candidate_graph,
    )