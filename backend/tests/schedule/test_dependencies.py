"""D10-BE-02 Task dependency와 cycle 검증 시험."""

import pytest

from backend.app.services.task_dependencies import (
    DependencyEdge,
    DependencyValidationCode,
    add_dependency,
    validate_dependency_graph,
)


TASK_IDS = {"A", "B", "C", "D"}


def test_dependency_free_graph_is_valid() -> None:
    result = validate_dependency_graph(
        task_ids=TASK_IDS,
        edges=(),
    )

    assert result.valid is True
    assert result.code == DependencyValidationCode.DEPENDENCY_FREE
    assert result.graph == ()


def test_valid_dependency_graph_preserves_lag() -> None:
    edges = (
        DependencyEdge("A", "B", lag_hours=4),
        DependencyEdge("B", "C", lag_hours=8),
    )

    result = validate_dependency_graph(
        task_ids=TASK_IDS,
        edges=edges,
    )

    assert result.valid is True
    assert result.code == DependencyValidationCode.VALID

    by_pair = {
        (edge.predecessor_id, edge.successor_id): edge
        for edge in result.graph
    }

    assert by_pair[("A", "B")].lag_hours == 4
    assert by_pair[("B", "C")].lag_hours == 8


def test_missing_predecessor_is_distinguished() -> None:
    edge = DependencyEdge("MISSING", "B")

    result = add_dependency(
        task_ids=TASK_IDS,
        existing_edges=(),
        new_edge=edge,
    )

    assert result.valid is False
    assert (
        result.code
        == DependencyValidationCode.MISSING_PREDECESSOR
    )
    assert result.rejected_edge == edge
    assert result.graph == ()


def test_missing_successor_is_distinguished() -> None:
    edge = DependencyEdge("A", "MISSING")

    result = add_dependency(
        task_ids=TASK_IDS,
        existing_edges=(),
        new_edge=edge,
    )

    assert result.valid is False
    assert (
        result.code
        == DependencyValidationCode.MISSING_SUCCESSOR
    )
    assert result.rejected_edge == edge
    assert result.graph == ()


def test_duplicate_edge_is_rejected() -> None:
    original = (
        DependencyEdge("A", "B", lag_hours=4),
    )

    result = add_dependency(
        task_ids=TASK_IDS,
        existing_edges=original,
        new_edge=DependencyEdge("A", "B", lag_hours=12),
    )

    assert result.valid is False
    assert result.code == DependencyValidationCode.DUPLICATE_EDGE

    # 실패해도 원본 graph는 그대로다.
    assert result.graph == original
    assert result.graph[0].lag_hours == 4


def test_self_cycle_is_rejected_without_graph_mutation() -> None:
    original = (
        DependencyEdge("A", "B"),
    )

    result = add_dependency(
        task_ids=TASK_IDS,
        existing_edges=original,
        new_edge=DependencyEdge("C", "C"),
    )

    assert result.valid is False
    assert result.code == DependencyValidationCode.SELF_CYCLE
    assert result.graph == original


def test_multi_node_cycle_is_rejected_without_graph_mutation() -> None:
    original = (
        DependencyEdge("A", "B"),
        DependencyEdge("B", "C"),
    )

    result = add_dependency(
        task_ids=TASK_IDS,
        existing_edges=original,
        new_edge=DependencyEdge("C", "A"),
    )

    assert result.valid is False
    assert result.code == DependencyValidationCode.CYCLE

    # C -> A가 반환 graph에 들어가면 안 된다.
    assert result.graph == original

    assert DependencyEdge("C", "A") not in result.graph


def test_longer_multi_node_cycle_is_rejected() -> None:
    original = (
        DependencyEdge("A", "B"),
        DependencyEdge("B", "C"),
        DependencyEdge("C", "D"),
    )

    result = add_dependency(
        task_ids=TASK_IDS,
        existing_edges=original,
        new_edge=DependencyEdge("D", "A"),
    )

    assert result.valid is False
    assert result.code == DependencyValidationCode.CYCLE
    assert result.graph == original


def test_non_cycle_branch_is_accepted() -> None:
    original = (
        DependencyEdge("A", "B"),
        DependencyEdge("A", "C"),
    )

    result = add_dependency(
        task_ids=TASK_IDS,
        existing_edges=original,
        new_edge=DependencyEdge("C", "D", lag_hours=6),
    )

    assert result.valid is True
    assert result.code == DependencyValidationCode.VALID
    assert DependencyEdge("C", "D", lag_hours=6) in result.graph


def test_negative_lag_is_rejected() -> None:
    with pytest.raises(ValueError, match="lag_hours"):
        DependencyEdge(
            predecessor_id="A",
            successor_id="B",
            lag_hours=-1,
        )


def test_same_input_produces_same_canonical_graph() -> None:
    first = validate_dependency_graph(
        task_ids=TASK_IDS,
        edges=(
            DependencyEdge("B", "C", 8),
            DependencyEdge("A", "B", 4),
        ),
    )

    second = validate_dependency_graph(
        task_ids=TASK_IDS,
        edges=(
            DependencyEdge("B", "C", 8),
            DependencyEdge("A", "B", 4),
        ),
    )

    assert first == second


def test_validation_does_not_mutate_caller_edge_collection() -> None:
    original = [
        DependencyEdge("A", "B"),
        DependencyEdge("B", "C"),
    ]
    before = list(original)

    result = add_dependency(
        task_ids=TASK_IDS,
        existing_edges=original,
        new_edge=DependencyEdge("C", "A"),
    )

    assert result.valid is False
    assert original == before