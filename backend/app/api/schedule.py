"""D10-BE-05 출시·일정·Task Read API와 내부 Replan Draft API."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.catalog_v2 import _require_catalog_tenant, _require_v2_runtime
from backend.app.core.config import Environment
from backend.app.models_v2.operations import IncomingShipmentV2, TaskIncomingDependencyV2, TaskV2
from backend.app.services.delay_impact import (
    DelayImpactResult,
    FreshnessStatus,
    ImpactPathItem,
    ImpactStatus,
    SourceClassification,
    SourceQuality,
)
from backend.app.services.demo_session import COOKIE_NAME, resolve_demo_session
from backend.app.services.schedule_replan import (
    ScheduleItem,
    build_replan_proposal,
)
from backend.app.services.task_feedback import (
    FeedbackIdempotencyConflict,
    FeedbackVersionConflict,
    append_task_feedback,
    list_task_feedback,
)
from backend.app.services.task_priority import (
    score_task_priority,
)
from contracts.api import ApiEnvelope

router = APIRouter(
    prefix="/api/v1",
    tags=["schedule"],
)


class IncomingRelatedTaskData(BaseModel):
    id: str
    task_type: Literal["RESERVATION_SHORTAGE"]
    title: str
    status: str
    due_at: datetime | None
    priority: str | None
    dependency_type: str


class IncomingScheduleData(BaseModel):
    id: str
    external_reference: str | None
    expected_arrival_at: datetime | None
    incoming_status: str
    confidence_status: str
    source_system: Literal["SYNTHETIC_DEMO"]
    source_as_of: None
    product_id: str
    product_variant_id: str | None
    related_tasks: list[IncomingRelatedTaskData]


class IncomingSchedulesData(BaseModel):
    items: list[IncomingScheduleData]
    total: int


@router.get(
    "/schedule/incoming-shipments",
    response_model=ApiEnvelope[IncomingSchedulesData],
)
def synthetic_incoming_schedules(request: Request) -> ApiEnvelope[IncomingSchedulesData]:
    """Read stored Demo incoming dates and their explicit shortage-task links."""
    if request.app.state.settings.environment != Environment.DEMO:
        raise HTTPException(status_code=403, detail="SCHEDULE_DEMO_ONLY")
    if request.query_params:
        raise HTTPException(status_code=422, detail="SCHEDULE_FILTER_UNSUPPORTED")
    factory, tenant_id, environment = _require_v2_runtime(request)
    with factory() as db:
        _require_catalog_tenant(db, tenant_id, environment)
        if resolve_demo_session(
            db, tenant_id=tenant_id, token=request.cookies.get(COOKIE_NAME), touch=False,
        ) is None:
            raise HTTPException(status_code=401, detail="DEMO_SESSION_REQUIRED")

        incoming = db.scalars(
            select(IncomingShipmentV2)
            .where(
                IncomingShipmentV2.tenant_id == tenant_id,
                IncomingShipmentV2.source_system == "SYNTHETIC_DEMO",
            )
            .order_by(
                IncomingShipmentV2.expected_arrival_at.asc().nulls_last(),
                IncomingShipmentV2.id.asc(),
            )
        ).all()
        linked: dict[str, list[IncomingRelatedTaskData]] = {
            str(row.id): [] for row in incoming
        }
        if incoming:
            relations = db.execute(
                select(TaskIncomingDependencyV2, TaskV2)
                .join(
                    TaskV2,
                    (TaskV2.tenant_id == TaskIncomingDependencyV2.tenant_id)
                    & (TaskV2.id == TaskIncomingDependencyV2.task_id),
                )
                .where(
                    TaskIncomingDependencyV2.tenant_id == tenant_id,
                    TaskIncomingDependencyV2.incoming_shipment_id.in_(
                        [row.id for row in incoming]
                    ),
                    TaskV2.task_type == "RESERVATION_SHORTAGE",
                )
                .order_by(TaskIncomingDependencyV2.incoming_shipment_id, TaskV2.id)
            ).all()
            for relation, task in relations:
                linked[str(relation.incoming_shipment_id)].append(
                    IncomingRelatedTaskData(
                        id=str(task.id),
                        task_type="RESERVATION_SHORTAGE",
                        title=task.task_title,
                        status=task.task_status,
                        due_at=task.due_at,
                        priority=str(task.priority) if task.priority is not None else None,
                        dependency_type=relation.dependency_type,
                    )
                )
        items = [
            IncomingScheduleData(
                id=str(row.id),
                external_reference=row.external_reference,
                expected_arrival_at=row.expected_arrival_at,
                incoming_status=row.incoming_status,
                confidence_status=row.confidence_status,
                source_system="SYNTHETIC_DEMO",
                source_as_of=None,
                product_id=str(row.product_id),
                product_variant_id=(
                    str(row.product_variant_id) if row.product_variant_id is not None else None
                ),
                related_tasks=linked[str(row.id)],
            )
            for row in incoming
        ]

    return _envelope(
        request=request,
        data=IncomingSchedulesData(items=items, total=len(items)),
        evidence_ids=[],
        warnings=[] if items else ["SYNTHETIC_INCOMING_EMPTY"],
    )


class ScheduleItemInput(BaseModel):
    """내부 Replan Draft용 현재 일정 입력."""

    item_type: str
    item_id: str
    scheduled_at: datetime


class ImpactPathInput(BaseModel):
    """내부 Replan Draft용 영향 경로 입력."""

    target_type: str
    target_id: str
    source_id: str
    before: datetime | None = None
    after: datetime | None = None
    lag_hours: int = Field(default=0, ge=0)
    reason: str
    evidence_ids: list[str] = Field(default_factory=list)


class DelayImpactInput(BaseModel):
    """내부 Replan Draft용 DelayImpact 계약."""

    status: ImpactStatus
    actual_delay_confirmed: bool
    incoming_id: str
    delay_hours: int | None

    source_id: str
    source_classification: SourceClassification
    as_of: datetime | None
    freshness: FreshnessStatus
    quality: SourceQuality
    evidence_ids: list[str] = Field(default_factory=list)

    impacted_task_ids: list[str] = Field(default_factory=list)
    impacted_reservation_ids: list[str] = Field(default_factory=list)
    impacted_launch_event_ids: list[str] = Field(default_factory=list)

    critical_path: list[str] = Field(default_factory=list)
    impact_path: list[ImpactPathInput] = Field(default_factory=list)

    reason: str


class ReplanDraftRequest(BaseModel):
    """내부/Demo 전용 Replan Proposal 생성 요청."""

    current_schedule: list[ScheduleItemInput]
    impact: DelayImpactInput
    created_at: datetime
    confidence: float = Field(ge=0.0, le=1.0)

class TaskFeedbackRequest(BaseModel):
    decision: Literal[
        "EDIT",
        "REJECT",
    ]

    target_field: str | None = None
    after_value: Any | None = None

    reason: str = Field(
        min_length=1,
        max_length=500,
        pattern=r"\S",
    )

    idempotency_key: str = Field(
        min_length=1,
        max_length=100,
    )

    expected_version: int = Field(
        ge=0,
    )

TASK_FEEDBACK_EDITABLE_FIELDS = {
    "title",
    "deadline",
}


def _find_task_projection(
    request: Request,
    *,
    task_id: str,
) -> dict[str, Any] | None:
    tenant_id = (
        request.app.state.settings.tenant_id
    )

    for item in (
        request.app.state
        .schedule_task_projections
    ):
        data = _serialize(item)

        item_id = str(
            data.get("id")
            or data.get("task_id")
            or ""
        )

        if item_id != task_id:
            continue

        item_tenant = data.get(
            "tenant_id"
        )

        if (
            item_tenant is not None
            and item_tenant != tenant_id
        ):
            continue

        return data

    return None


def _feedback_to_dict(
    row: Any,
) -> dict[str, Any]:
    return {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "task_id": row.task_id,
        "decision": row.decision,
        "target_field": row.target_field,
        "before_value": row.before_value,
        "after_value": row.after_value,
        "reason": row.reason,
        "actor": row.actor,
        "idempotency_key": (
            row.idempotency_key
        ),
        "feedback_version": (
            row.feedback_version
        ),
        "schema_version": (
            row.schema_version
        ),
        "created_at": row.created_at,
    }

def _request_context(
    request: Request,
) -> tuple[str, str]:
    request_id = request.headers.get(
        "x-request-id",
        f"req_{uuid4().hex}",
    )
    trace_id = request.headers.get(
        "x-trace-id",
        f"tr_{uuid4().hex}",
    )

    return request_id, trace_id


def _serialize(item: Any) -> dict[str, Any]:
    """Dataclass와 dict Projection을 공통 직렬화한다."""

    if isinstance(item, dict):
        return dict(item)

    if is_dataclass(item):
        return asdict(item)

    raise TypeError(
        f"unsupported schedule projection type: "
        f"{type(item).__name__}"
    )

def _task_priority_projection(
    item: Any,
    *,
    tenant_id: str,
    as_of: datetime,
) -> dict[str, Any]:
    data = _serialize(item)

    task_id = str(
        data.get("id")
        or data.get("task_id")
        or ""
    )

    if not task_id:
        return data

    deadline = data.get("deadline")
    risk_level = data.get(
        "risk_level",
        data.get("delivery_risk"),
    )

    affected_count = data.get(
        "affected_count"
    )

    if affected_count is None:
        affected_order_ids = data.get(
            "affected_order_ids"
        )

        if affected_order_ids is not None:
            affected_count = len(
                affected_order_ids
            )

    aging_hours = data.get(
        "aging_hours"
    )

    source_classification = str(
        data.get(
            "source_classification",
            "UNKNOWN",
        )
    )

    priority_result = score_task_priority(
        tenant_id=tenant_id,
        task_id=task_id,
        deadline=deadline,
        risk_level=risk_level,
        affected_count=affected_count,
        aging_hours=aging_hours,
        as_of=as_of,
        source_classification=(
            source_classification
        ),
    )

    rule_score = priority_result.total_score
    coverage_weight = priority_result.coverage_weight

    data["priority_rule_score"] = rule_score

    if coverage_weight > 0:
        data["priority"] = rule_score
    else:
        data["priority"] = data.get("priority")

    data["priority_breakdown"] = {
        "deadline": asdict(
            priority_result.deadline
        ),
        "risk": asdict(
            priority_result.risk
        ),
        "business_impact": asdict(
            priority_result.business_impact
        ),
        "aging": asdict(
            priority_result.aging
        ),
    }

    data["priority_rule_version"] = (
        priority_result.rule_version
    )

    data["priority_provenance"] = (
        priority_result.provenance
    )

    data["priority_calibration_status"] = (
        priority_result
        .calibration_status
    )

    data["priority_missing_features"] = list(
        priority_result.missing_features
    )

    data["priority_coverage_weight"] = (
        priority_result.coverage_weight
    )

    data["priority_as_of"] = (
        priority_result.as_of
    )

    return data

def _task_sort_tuple(
    data: dict[str, Any],
) -> tuple[float, float, str]:
    priority = data.get("priority")

    if isinstance(
        priority,
        (int, float),
    ):
        priority_value = float(
            priority
        )
    else:
        priority_value = 0.0

    coverage = data.get(
        "priority_coverage_weight"
    )

    if isinstance(
        coverage,
        (int, float),
    ):
        coverage_value = float(
            coverage
        )
    else:
        coverage_value = 0.0

    task_id = str(
        data.get("id")
        or data.get("task_id")
        or ""
    )

    return (
        -priority_value,
        -coverage_value,
        task_id,
    )
def _projection_evidence_ids(
    items: list[Any],
) -> list[str]:
    """Projection에서 evidence id를 중복 없이 수집한다."""

    collected: list[str] = []

    for item in items:
        data = _serialize(item)

        evidence = (
            data.get("evidence_ids")
            or data.get("evidence")
            or []
        )

        for evidence_id in evidence:
            if evidence_id not in collected:
                collected.append(evidence_id)

    return collected


def _envelope(
    *,
    request: Request,
    data: Any,
    evidence_ids: list[str],
    warnings: list[str],
) -> ApiEnvelope[Any]:
    request_id, trace_id = _request_context(request)

    return ApiEnvelope(
        tenant_id=request.app.state.settings.tenant_id,
        request_id=request_id,
        trace_id=trace_id,
        data=data,
        evidence_ids=evidence_ids,
        warnings=warnings,
        as_of=datetime.now(UTC),
    )


def _is_production_read(request: Request) -> bool:
    environment = request.app.state.settings.environment

    environment_value = getattr(
        environment,
        "value",
        str(environment),
    )

    return environment_value == "PRODUCTION_READ"


@router.get(
    "/launch-events",
    response_model=ApiEnvelope[list[dict[str, Any]]],
)
def launch_events(
    request: Request,
) -> ApiEnvelope[list[dict[str, Any]]]:
    projections = list(
        request.app.state.schedule_launch_event_projections
    )

    data = [_serialize(item) for item in projections]

    warnings: list[str] = []

    if not data:
        warnings.append(
            "LAUNCH_EVENTS_EMPTY:"
            " no usable launch event projection available"
        )

    return _envelope(
        request=request,
        data=data,
        evidence_ids=_projection_evidence_ids(projections),
        warnings=warnings,
    )

@router.post(
    "/tasks/{task_id}/feedback",
    response_model=ApiEnvelope[
        dict[str, Any]
    ],
)
def create_task_feedback(
    task_id: str,
    payload: TaskFeedbackRequest,
    request: Request,
) -> ApiEnvelope[dict[str, Any]]:
    if (_is_production_read(request) or
            (request.app.state.settings.environment == "DEMO"
             and request.app.state.db_engine is None)):
        raise HTTPException(
            status_code=(
                status.HTTP_403_FORBIDDEN
            ),
            detail={
                "code": "POLICY_DENIED",
                "reason": (
                    "task feedback POST "
                    "is disabled in "
                    "PRODUCTION_READ"
                ),
            },
        )

    task = _find_task_projection(
        request,
        task_id=task_id,
    )

    if task is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail={
                "code": "TASK_NOT_FOUND",
                "task_id": task_id,
            },
        )

    if payload.decision == "EDIT":
        if (
            payload.target_field
            not in TASK_FEEDBACK_EDITABLE_FIELDS
        ):
            raise HTTPException(
                status_code=(
                    status.HTTP_422_UNPROCESSABLE_ENTITY
                ),
                detail={
                    "code": (
                        "FIELD_NOT_EDITABLE"
                    ),
                    "allowed_fields": sorted(
                        TASK_FEEDBACK_EDITABLE_FIELDS
                    ),
                },
            )

        before_value = task.get(
            payload.target_field
        )

        after_value = (
            payload.after_value
        )

    else:
        if payload.target_field is not None:
            raise HTTPException(
                status_code=(
                    status.HTTP_422_UNPROCESSABLE_ENTITY
                ),
                detail={
                    "code": (
                        "REJECT_TARGET_FIELD_FORBIDDEN"
                    ),
                },
            )

        before_value = {
            "status": task.get(
                "status"
            ),
        }

        after_value = {
            "status": "DISMISSED",
        }

    tenant_id = (
        request.app.state.settings.tenant_id
    )

    try:
        with Session(
            request.app.state.db_engine
        ) as session:
            row = append_task_feedback(
                session,
                tenant_id=tenant_id,
                task_id=task_id,
                decision=payload.decision,
                target_field=(
                    payload.target_field
                ),
                before_value=before_value,
                after_value=after_value,
                reason=payload.reason,
                idempotency_key=(
                    payload.idempotency_key
                ),
                expected_version=(
                    payload.expected_version
                ),
            )

    except FeedbackVersionConflict as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail={
                "code": (
                    "FEEDBACK_VERSION_CONFLICT"
                ),
                "reason": str(exc),
            },
        ) from exc

    except FeedbackIdempotencyConflict as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail={
                "code": (
                    "IDEMPOTENCY_CONFLICT"
                ),
                "reason": str(exc),
            },
        ) from exc

    return _envelope(
        request=request,
        data=_feedback_to_dict(row),
        evidence_ids=[],
        warnings=[],
    )

@router.get(
    "/tasks/{task_id}/feedback",
    response_model=ApiEnvelope[
        list[dict[str, Any]]
    ],
)
def task_feedback_history(
    task_id: str,
    request: Request,
) -> ApiEnvelope[
    list[dict[str, Any]]
]:
    if request.app.state.settings.environment == "DEMO" and request.app.state.db_engine is None:
        raise HTTPException(status_code=403, detail={"code": "POLICY_DENIED"})
    task = _find_task_projection(
        request,
        task_id=task_id,
    )

    if task is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail={
                "code": "TASK_NOT_FOUND",
                "task_id": task_id,
            },
        )

    tenant_id = (
        request.app.state.settings.tenant_id
    )

    with Session(
        request.app.state.db_engine
    ) as session:
        rows = list_task_feedback(
            session,
            tenant_id=tenant_id,
            task_id=task_id,
        )

        data = [
            _feedback_to_dict(row)
            for row in rows
        ]

    return _envelope(
        request=request,
        data=data,
        evidence_ids=[],
        warnings=[],
    )

@router.get(
    "/tasks",
    response_model=ApiEnvelope[list[dict[str, Any]]],
)

def tasks(
    request: Request,
) -> ApiEnvelope[list[dict[str, Any]]]:
    projections = list(
        request.app.state.schedule_task_projections
    )

    tenant_id = (
        request
        .app
        .state
        .settings
        .tenant_id
    )

    calculated_at = datetime.now(UTC)

    data = [
        _task_priority_projection(
            item,
            tenant_id=tenant_id,
            as_of=calculated_at,
        )
        for item in projections
    ]

    data.sort(
        key=_task_sort_tuple
    )

    warnings: list[str] = []

    if not data:
        warnings.append(
            "TASKS_EMPTY:"
            " no usable task projection available"
        )

    return _envelope(
        request=request,
        data=data,
        evidence_ids=_projection_evidence_ids(projections),
        warnings=warnings,
    )


@router.get(
    "/schedule/dependencies",
    response_model=ApiEnvelope[list[dict[str, Any]]],
)
def schedule_dependencies(
    request: Request,
) -> ApiEnvelope[list[dict[str, Any]]]:
    projections = list(
        request.app.state.schedule_dependency_projections
    )

    data = [_serialize(item) for item in projections]

    warnings: list[str] = []

    if not data:
        warnings.append(
            "SCHEDULE_DEPENDENCIES_EMPTY:"
            " no dependency projection available"
        )

    return _envelope(
        request=request,
        data=data,
        evidence_ids=_projection_evidence_ids(projections),
        warnings=warnings,
    )


@router.get(
    "/schedule/delay-impacts",
    response_model=ApiEnvelope[list[dict[str, Any]]],
)
def delay_impacts(
    request: Request,
) -> ApiEnvelope[list[dict[str, Any]]]:
    projections = list(
        request.app.state.schedule_delay_impact_projections
    )

    data = [_serialize(item) for item in projections]

    warnings: list[str] = []

    if not data:
        warnings.append(
            "DELAY_IMPACTS_EMPTY:"
            " no delay impact projection available"
        )

    return _envelope(
        request=request,
        data=data,
        evidence_ids=_projection_evidence_ids(projections),
        warnings=warnings,
    )


@router.get(
    "/schedule/delay-impacts/{incoming_id}",
    response_model=ApiEnvelope[dict[str, Any]],
)
def delay_impact(
    incoming_id: str,
    request: Request,
) -> ApiEnvelope[dict[str, Any]]:
    projections = list(
        request.app.state.schedule_delay_impact_projections
    )

    matched = None

    for item in projections:
        data = _serialize(item)

        if data.get("incoming_id") == incoming_id:
            matched = item
            break

    if matched is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "DELAY_IMPACT_NOT_FOUND",
                "incoming_id": incoming_id,
            },
        )

    data = _serialize(matched)

    return _envelope(
        request=request,
        data=data,
        evidence_ids=_projection_evidence_ids([matched]),
        warnings=[],
    )


@router.get(
    "/schedule/replan-proposals",
    response_model=ApiEnvelope[list[dict[str, Any]]],
)
def replan_proposals(
    request: Request,
) -> ApiEnvelope[list[dict[str, Any]]]:
    projections = list(
        request.app.state.schedule_replan_proposals
    )

    data = [_serialize(item) for item in projections]

    warnings: list[str] = []

    if not data:
        warnings.append(
            "REPLAN_PROPOSALS_EMPTY:"
            " no replan proposal available"
        )

    return _envelope(
        request=request,
        data=data,
        evidence_ids=_projection_evidence_ids(projections),
        warnings=warnings,
    )


@router.get(
    "/schedule/replan-proposals/{proposal_id}",
    response_model=ApiEnvelope[dict[str, Any]],
)
def replan_proposal(
    proposal_id: str,
    request: Request,
) -> ApiEnvelope[dict[str, Any]]:
    projections = list(
        request.app.state.schedule_replan_proposals
    )

    matched = None

    for item in projections:
        data = _serialize(item)

        if data.get("proposal_id") == proposal_id:
            matched = item
            break

    if matched is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "REPLAN_PROPOSAL_NOT_FOUND",
                "proposal_id": proposal_id,
            },
        )

    return _envelope(
        request=request,
        data=_serialize(matched),
        evidence_ids=_projection_evidence_ids([matched]),
        warnings=[],
    )


@router.post(
    "/demo/schedule/replan-proposals/draft",
    response_model=ApiEnvelope[dict[str, Any]],
    status_code=status.HTTP_200_OK,
)
def draft_replan_proposal(
    payload: ReplanDraftRequest,
    request: Request,
) -> ApiEnvelope[dict[str, Any]]:
    """
    LOCAL/DEMO 내부 Proposal 생성.

    원본 Schedule 및 외부 Provider는 수정하지 않는다.
    """

    if _is_production_read(request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "POLICY_DENIED",
                "reason": (
                    "replan draft POST is disabled "
                    "in PRODUCTION_READ"
                ),
            },
        )

    impact_input = payload.impact

    impact = DelayImpactResult(
        status=impact_input.status,
        actual_delay_confirmed=(
            impact_input.actual_delay_confirmed
        ),
        incoming_id=impact_input.incoming_id,
        delay_hours=impact_input.delay_hours,
        source_id=impact_input.source_id,
        source_classification=(
            impact_input.source_classification
        ),
        as_of=impact_input.as_of,
        freshness=impact_input.freshness,
        quality=impact_input.quality,
        evidence_ids=tuple(impact_input.evidence_ids),
        impacted_task_ids=tuple(
            impact_input.impacted_task_ids
        ),
        impacted_reservation_ids=tuple(
            impact_input.impacted_reservation_ids
        ),
        impacted_launch_event_ids=tuple(
            impact_input.impacted_launch_event_ids
        ),
        critical_path=tuple(
            impact_input.critical_path
        ),
        impact_path=tuple(
            ImpactPathItem(
                target_type=item.target_type,
                target_id=item.target_id,
                source_id=item.source_id,
                before=item.before,
                after=item.after,
                lag_hours=item.lag_hours,
                reason=item.reason,
                evidence_ids=tuple(
                    item.evidence_ids
                ),
            )
            for item in impact_input.impact_path
        ),
        reason=impact_input.reason,
    )

    current_schedule = tuple(
        ScheduleItem(
            item_type=item.item_type,
            item_id=item.item_id,
            scheduled_at=item.scheduled_at,
        )
        for item in payload.current_schedule
    )

    proposal = build_replan_proposal(
        current_schedule=current_schedule,
        impact=impact,
        created_at=payload.created_at,
        confidence=payload.confidence,
    )

    existing = {
        _serialize(item).get("proposal_id")
        for item in request.app.state.schedule_replan_proposals
    }

    # 동일 replay는 동일 proposal_id를 가지므로 중복 effect를 만들지 않는다.
    if proposal.proposal_id not in existing:
        request.app.state.schedule_replan_proposals.append(
            proposal
        )

    return _envelope(
        request=request,
        data=_serialize(proposal),
        evidence_ids=list(proposal.evidence_ids),
        warnings=[
            "DEMO_INTERNAL_DRAFT_ONLY:"
            " original schedule unchanged;"
            " external provider write disabled"
        ],
    )
