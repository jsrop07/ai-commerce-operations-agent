"""D10-BE-01 출시 일정 템플릿 시험."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from backend.app.domain.schedule_templates import (
    FLOW_A_TEMPLATE,
    FLOW_B_TEMPLATE,
    FlowType,
    build_launch_tasks,
    get_schedule_template,
)


SEOUL = ZoneInfo("Asia/Seoul")


def test_flow_a_template_has_required_metadata_and_tasks() -> None:
    template = get_schedule_template(FlowType.FLOW_A)

    assert template.template_id == "launch-flow-a"
    assert template.version == "1.0"
    assert template.timezone == "Asia/Seoul"

    task_keys = [task.task_key for task in template.tasks]

    assert task_keys == [
        "INCOMING",
        "INSPECTION",
        "PRODUCT_PAGE",
        "CAFE24_PREP",
        "POS_PREP",
        "PROMOTION",
        "SALE_START",
    ]

    for task in template.tasks:
        assert task.duration_hours >= 0
        assert task.lead_time_hours >= 0
        assert task.owner_role


def test_flow_a_and_b_difference_is_defined_as_template_data() -> None:
    assert FLOW_A_TEMPLATE.flow_type == FlowType.FLOW_A
    assert FLOW_B_TEMPLATE.flow_type == FlowType.FLOW_B

    flow_a = {
        task.task_key: (task.duration_hours, task.lead_time_hours)
        for task in FLOW_A_TEMPLATE.tasks
    }
    flow_b = {
        task.task_key: (task.duration_hours, task.lead_time_hours)
        for task in FLOW_B_TEMPLATE.tasks
    }

    assert flow_a.keys() == flow_b.keys()
    assert flow_a != flow_b

    assert flow_a["INCOMING"] == (24, 168)
    assert flow_b["INCOMING"] == (12, 72)


def test_flow_a_deadlines_are_reverse_calculated_from_launch_at() -> None:
    launch_at = datetime(2026, 10, 20, 10, 0, tzinfo=SEOUL)

    tasks = build_launch_tasks(FlowType.FLOW_A, launch_at)
    by_key = {task.task_key: task for task in tasks}

    assert by_key["INCOMING"].deadline == launch_at - timedelta(hours=168)
    assert by_key["INSPECTION"].deadline == launch_at - timedelta(hours=120)
    assert by_key["PRODUCT_PAGE"].deadline == launch_at - timedelta(hours=96)
    assert by_key["CAFE24_PREP"].deadline == launch_at - timedelta(hours=48)
    assert by_key["POS_PREP"].deadline == launch_at - timedelta(hours=48)
    assert by_key["PROMOTION"].deadline == launch_at - timedelta(hours=24)
    assert by_key["SALE_START"].deadline == launch_at

    assert by_key["INSPECTION"].scheduled_start == (
        by_key["INSPECTION"].deadline - timedelta(hours=8)
    )


def test_flow_b_deadlines_are_reverse_calculated_from_launch_at() -> None:
    launch_at = datetime(2026, 10, 20, 10, 0, tzinfo=SEOUL)

    tasks = build_launch_tasks(FlowType.FLOW_B, launch_at)
    by_key = {task.task_key: task for task in tasks}

    assert by_key["INCOMING"].deadline == launch_at - timedelta(hours=72)
    assert by_key["INSPECTION"].deadline == launch_at - timedelta(hours=48)
    assert by_key["PRODUCT_PAGE"].deadline == launch_at - timedelta(hours=36)
    assert by_key["CAFE24_PREP"].deadline == launch_at - timedelta(hours=18)
    assert by_key["POS_PREP"].deadline == launch_at - timedelta(hours=18)
    assert by_key["PROMOTION"].deadline == launch_at - timedelta(hours=6)
    assert by_key["SALE_START"].deadline == launch_at


def test_same_input_produces_same_result() -> None:
    launch_at = datetime(2026, 10, 20, 10, 0, tzinfo=SEOUL)

    first = build_launch_tasks(FlowType.FLOW_A, launch_at)
    second = build_launch_tasks(FlowType.FLOW_A, launch_at)

    assert first == second


def test_template_preserves_predecessors() -> None:
    launch_at = datetime(2026, 10, 20, 10, 0, tzinfo=SEOUL)

    tasks = build_launch_tasks(FlowType.FLOW_A, launch_at)
    by_key = {task.task_key: task for task in tasks}

    assert [
        dependency.predecessor_key
        for dependency in by_key["PROMOTION"].predecessors
    ] == ["CAFE24_PREP", "POS_PREP"]

    assert [
        dependency.predecessor_key
        for dependency in by_key["SALE_START"].predecessors
    ] == ["PROMOTION"]


def test_naive_launch_at_is_rejected() -> None:
    launch_at = datetime(2026, 10, 20, 10, 0)

    with pytest.raises(ValueError, match="timezone-aware"):
        build_launch_tasks(FlowType.FLOW_A, launch_at)