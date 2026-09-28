"""D10-BE-01 출시 Flow A/B Task 템플릿과 deadline 역산 로직."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo


DEFAULT_SCHEDULE_TIMEZONE = "Asia/Seoul"


class FlowType(StrEnum):
    """출시 운영 Flow 종류."""

    FLOW_A = "FLOW_A"
    FLOW_B = "FLOW_B"


@dataclass(frozen=True)
class TemplateDependency:
    """템플릿 내부 선행 Task 관계."""

    predecessor_key: str
    lag_hours: int = 0


@dataclass(frozen=True)
class TemplateTaskSpec:
    """출시 Flow를 구성하는 Task 정의."""

    task_key: str
    task_type: str
    title: str
    duration_hours: int
    lead_time_hours: int
    owner_role: str
    predecessors: tuple[TemplateDependency, ...] = ()


@dataclass(frozen=True)
class ScheduleTemplate:
    """버전 관리되는 출시 일정 템플릿."""

    template_id: str
    version: str
    flow_type: FlowType
    timezone: str
    tasks: tuple[TemplateTaskSpec, ...]


@dataclass(frozen=True)
class GeneratedTask:
    """출시일을 기준으로 역산된 Task."""

    template_id: str
    template_version: str
    flow_type: FlowType
    task_key: str
    task_type: str
    title: str
    owner_role: str
    scheduled_start: datetime
    deadline: datetime
    predecessors: tuple[TemplateDependency, ...]


FLOW_A_TEMPLATE = ScheduleTemplate(
    template_id="launch-flow-a",
    version="1.0",
    flow_type=FlowType.FLOW_A,
    timezone=DEFAULT_SCHEDULE_TIMEZONE,
    tasks=(
        TemplateTaskSpec(
            task_key="INCOMING",
            task_type="INCOMING",
            title="입고 확인",
            duration_hours=24,
            lead_time_hours=168,
            owner_role="OPERATIONS",
        ),
        TemplateTaskSpec(
            task_key="INSPECTION",
            task_type="INSPECTION",
            title="입고 상품 검수",
            duration_hours=8,
            lead_time_hours=120,
            owner_role="OPERATIONS",
            predecessors=(TemplateDependency("INCOMING"),),
        ),
        TemplateTaskSpec(
            task_key="PRODUCT_PAGE",
            task_type="PRODUCT_PAGE",
            title="상품페이지 준비",
            duration_hours=8,
            lead_time_hours=96,
            owner_role="ECOMMERCE",
            predecessors=(TemplateDependency("INSPECTION"),),
        ),
        TemplateTaskSpec(
            task_key="CAFE24_PREP",
            task_type="CAFE24_PREP",
            title="Cafe24 판매 준비",
            duration_hours=4,
            lead_time_hours=48,
            owner_role="ECOMMERCE",
            predecessors=(TemplateDependency("PRODUCT_PAGE"),),
        ),
        TemplateTaskSpec(
            task_key="POS_PREP",
            task_type="POS_PREP",
            title="POS 판매 준비",
            duration_hours=4,
            lead_time_hours=48,
            owner_role="STORE",
            predecessors=(TemplateDependency("PRODUCT_PAGE"),),
        ),
        TemplateTaskSpec(
            task_key="PROMOTION",
            task_type="PROMOTION",
            title="출시 홍보 준비",
            duration_hours=4,
            lead_time_hours=24,
            owner_role="MARKETING",
            predecessors=(
                TemplateDependency("CAFE24_PREP"),
                TemplateDependency("POS_PREP"),
            ),
        ),
        TemplateTaskSpec(
            task_key="SALE_START",
            task_type="SALE_START",
            title="판매 시작",
            duration_hours=0,
            lead_time_hours=0,
            owner_role="OPERATIONS",
            predecessors=(TemplateDependency("PROMOTION"),),
        ),
    ),
)


FLOW_B_TEMPLATE = ScheduleTemplate(
    template_id="launch-flow-b",
    version="1.0",
    flow_type=FlowType.FLOW_B,
    timezone=DEFAULT_SCHEDULE_TIMEZONE,
    tasks=(
        TemplateTaskSpec(
            task_key="INCOMING",
            task_type="INCOMING",
            title="입고 확인",
            duration_hours=12,
            lead_time_hours=72,
            owner_role="OPERATIONS",
        ),
        TemplateTaskSpec(
            task_key="INSPECTION",
            task_type="INSPECTION",
            title="입고 상품 검수",
            duration_hours=4,
            lead_time_hours=48,
            owner_role="OPERATIONS",
            predecessors=(TemplateDependency("INCOMING"),),
        ),
        TemplateTaskSpec(
            task_key="PRODUCT_PAGE",
            task_type="PRODUCT_PAGE",
            title="상품페이지 준비",
            duration_hours=6,
            lead_time_hours=36,
            owner_role="ECOMMERCE",
            predecessors=(TemplateDependency("INSPECTION"),),
        ),
        TemplateTaskSpec(
            task_key="CAFE24_PREP",
            task_type="CAFE24_PREP",
            title="Cafe24 판매 준비",
            duration_hours=3,
            lead_time_hours=18,
            owner_role="ECOMMERCE",
            predecessors=(TemplateDependency("PRODUCT_PAGE"),),
        ),
        TemplateTaskSpec(
            task_key="POS_PREP",
            task_type="POS_PREP",
            title="POS 판매 준비",
            duration_hours=3,
            lead_time_hours=18,
            owner_role="STORE",
            predecessors=(TemplateDependency("PRODUCT_PAGE"),),
        ),
        TemplateTaskSpec(
            task_key="PROMOTION",
            task_type="PROMOTION",
            title="출시 홍보 준비",
            duration_hours=2,
            lead_time_hours=6,
            owner_role="MARKETING",
            predecessors=(
                TemplateDependency("CAFE24_PREP"),
                TemplateDependency("POS_PREP"),
            ),
        ),
        TemplateTaskSpec(
            task_key="SALE_START",
            task_type="SALE_START",
            title="판매 시작",
            duration_hours=0,
            lead_time_hours=0,
            owner_role="OPERATIONS",
            predecessors=(TemplateDependency("PROMOTION"),),
        ),
    ),
)


TEMPLATES: dict[FlowType, ScheduleTemplate] = {
    FlowType.FLOW_A: FLOW_A_TEMPLATE,
    FlowType.FLOW_B: FLOW_B_TEMPLATE,
}


def get_schedule_template(flow_type: FlowType | str) -> ScheduleTemplate:
    """Flow에 대응하는 일정 템플릿을 반환한다."""

    flow = FlowType(flow_type)
    return TEMPLATES[flow]


def build_launch_tasks(
    flow_type: FlowType | str,
    launch_at: datetime,
) -> tuple[GeneratedTask, ...]:
    """출시 시각에서 각 Task의 deadline과 시작 시각을 역산한다."""

    if launch_at.tzinfo is None or launch_at.utcoffset() is None:
        raise ValueError("launch_at must be timezone-aware")

    template = get_schedule_template(flow_type)
    timezone = ZoneInfo(template.timezone)
    localized_launch_at = launch_at.astimezone(timezone)

    generated: list[GeneratedTask] = []

    for spec in template.tasks:
        deadline = localized_launch_at - timedelta(hours=spec.lead_time_hours)
        scheduled_start = deadline - timedelta(hours=spec.duration_hours)

        generated.append(
            GeneratedTask(
                template_id=template.template_id,
                template_version=template.version,
                flow_type=template.flow_type,
                task_key=spec.task_key,
                task_type=spec.task_type,
                title=spec.title,
                owner_role=spec.owner_role,
                scheduled_start=scheduled_start,
                deadline=deadline,
                predecessors=spec.predecessors,
            )
        )

    return tuple(generated)