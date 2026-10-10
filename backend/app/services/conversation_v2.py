"""C09 conversation storage and provider-free analysis dispatch boundary."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.config import Settings
from backend.app.services.c24_grounded_operations import (
    run_product_grounded_explanation,
    run_reservation_grounded_explanation,
)
from backend.app.services.demo_provider_quota import (
    DemoQuotaDenied,
)
from ai.services.grounded_explanation_output import (
    ExplanationStatus,
)
from ai.services.grounded_explanation_provider import (
    GroundedProviderError,
    GroundedProviderTimeout,
)

from ai.evaluation.r09_conversation_contract import (
    AiAnswerContract,
    ConversationStatus,
    validate_answer_contract,
)
from backend.app.core.c09_actor import valid_c09_actor_id
from backend.app.models_v2.ai import AgentRunV2, ConversationV2, MessageContextV2, MessageV2
from backend.app.models_v2.catalog import CategoryV2, ProductV2
from backend.app.models_v2.operations import IncomingShipmentV2, TaskIncomingDependencyV2, TaskV2
from backend.app.services.c09_order_aggregate import (
    SafeProductDemandAggregate,
    safe_product_demand_aggregate,
)
from backend.app.services.c09_view_context import VIEW_SNAPSHOT_KEY, ViewContextInput
from backend.app.services.c18_product_evidence import retrieve_frozen_product_evidence
from backend.app.services.product_demand_projection import (
    project_product_demand,
)
from backend.app.services.retrieval_runtime import RetrievalFailure, validate_query
from backend.app.worker.privacy.text_redaction import EMAIL_PATTERN, ORDER_ID_PATTERN, PHONE_PATTERN
from backend.app.services.reservation_projection import (
    ReservationRiskProjection,
)
from backend.app.services.c17_graph_runtime import (
    analyze_product_graph,
)
from backend.app.services.reservation_chat_read import (
    read_product_reservation_facts,
)

TargetType = Literal["PRODUCT", "INCOMING", "TASK"]
Intent = Literal["INSPECT_TARGET", "FOLLOW_RELATED_TARGET"]
AnalysisKind = Literal["NONE", "DETERMINISTIC", "HYBRID", "RELATION_DOCUMENT"]
MessageResponseStatus = Literal["ANSWER", "NO_EDGE", "HOLD"]
ContractErrorStatus = Literal["HOLD", "MISSING", "STALE", "ERROR", "CONFLICT"]

AI_TO_MESSAGE_STATUS: dict[ConversationStatus, MessageResponseStatus] = {
    ConversationStatus.ANSWER: "ANSWER",
    ConversationStatus.NO_EDGE: "NO_EDGE",
    ConversationStatus.HOLD: "HOLD",
}


def message_status_for_ai(status: ConversationStatus) -> MessageResponseStatus:
    try:
        return AI_TO_MESSAGE_STATUS[status]
    except KeyError as exc:
        raise C09ContractError("ERROR", "UNSUPPORTED_AI_STATUS") from exc


@dataclass(frozen=True)
class TargetInput:
    target_type: TargetType
    target_id: str
    target_label: str
    source: str
    as_of: datetime | None


ContextInput = TargetInput | ViewContextInput


@dataclass(frozen=True)
class ResolvedTarget:
    target_type: str
    target_id: str
    target_label: str
    source: str
    as_of: datetime | None
    data_mode: str
    entity_id: UUID | None
    product_id: UUID | None
    view_snapshot: dict | None = None


@dataclass(frozen=True)
class AnalysisRuntimeResult:
    answer: AiAnswerContract
    retrieval_evidence: tuple[dict, ...] = ()


class C09ContractError(Exception):
    def __init__(self, status: ContractErrorStatus, code: str):
        super().__init__(code)
        self.status = status
        self.code = code


class ProductSearchService(Protocol):
    """Injected, provider-free Product candidate resolver; no conversation writes."""

    def resolve_product_ids(
        self, *, session: Session, tenant_id: UUID, query: str,
    ) -> Sequence[UUID]: ...


_SOURCE_BY_TYPE = {
    "PRODUCT": "CAFE24_CATALOG",
    "INCOMING": "OPERATIONS_INCOMING",
    "TASK": "OPERATIONS_TASK",
}
_PRODUCT_NUMBER = re.compile(r"^[0-9]{1,18}$")
_PRODUCT_CODE = re.compile(r"^[A-Za-z0-9_.-]{1,120}$")
_PRODUCT_SEARCH_SENSITIVE = re.compile(
    r"\b(?:customer|order|payment|address|inquiry|recipient|shipping)\b|"
    r"고객|주문|결제|주소|문의|배송",
    re.IGNORECASE,
)
_FORBIDDEN_HINT = re.compile(
    r"(?:고객\s*(?:이름|성명|전화|주소|메일)|문의\s*원문|배송\s*(?:주소|번호)|"
    r"결제\s*(?:번호|정보)|customer[_ -]?id|order[_ -]?id|inquiry[_ -]?(?:body|text))",
    re.IGNORECASE,
)


def validate_pre_storage(actor_id: str, target: ContextInput, intent: Intent) -> None:
    """Run before any conversation, message, context, log, or checkpoint write."""
    if not valid_c09_actor_id(actor_id):
        raise C09ContractError("HOLD", "TRUSTED_ACTOR_REQUIRED")
    if intent not in {"INSPECT_TARGET", "FOLLOW_RELATED_TARGET"}:
        raise C09ContractError("HOLD", "UNSUPPORTED_INTENT")
    if isinstance(target, ViewContextInput):
        for value in (target.search, target.filters.major_category):
            if value and (
                EMAIL_PATTERN.search(value)
                or PHONE_PATTERN.search(value)
                or ORDER_ID_PATTERN.search(value)
                or _FORBIDDEN_HINT.search(value)
            ):
                raise C09ContractError("HOLD", "FORBIDDEN_INPUT")
        return
    if (
        target.target_type not in _SOURCE_BY_TYPE
        or target.source != _SOURCE_BY_TYPE[target.target_type]
    ):
        raise C09ContractError("HOLD", "UNSUPPORTED_CONTEXT_SOURCE")
    if (
        not isinstance(target.target_label, str)
        or not target.target_label
        or len(target.target_label) > 255
    ):
        raise C09ContractError("HOLD", "INVALID_TARGET_LABEL")
    for value in (target.target_id, target.target_label):
        if (
            EMAIL_PATTERN.search(value)
            or PHONE_PATTERN.search(value)
            or ORDER_ID_PATTERN.search(value)
            or _FORBIDDEN_HINT.search(value)
        ):
            raise C09ContractError("HOLD", "FORBIDDEN_INPUT")
    if target.as_of is not None and (
        target.as_of.tzinfo is None or target.as_of.utcoffset() is None
    ):
        raise C09ContractError("HOLD", "INVALID_SOURCE_TIME")
    if target.target_type == "PRODUCT":
        if not _PRODUCT_NUMBER.fullmatch(target.target_id):
            raise C09ContractError("HOLD", "INVALID_PRODUCT_NUMBER")
    else:
        try:
            UUID(target.target_id)
        except (ValueError, AttributeError) as exc:
            raise C09ContractError("HOLD", "INVALID_TARGET_ID") from exc

def classify_operational_question(question: str) -> tuple[AnalysisKind, str]:
    """운영 질문을 기존 검증 가능한 분석 경로로 분류한다."""
    if not isinstance(question, str):
        raise C09ContractError("HOLD", "INVALID_QUESTION")

    text = unicodedata.normalize("NFKC", question).strip()

    if (
        not text
        or len(text) > 500
        or any(unicodedata.category(ch).startswith("C") for ch in text)
        or EMAIL_PATTERN.search(text)
        or PHONE_PATTERN.search(text)
        or ORDER_ID_PATTERN.search(text)
        or _FORBIDDEN_HINT.search(text)
    ):
        raise C09ContractError("HOLD", "FORBIDDEN_QUESTION_INPUT")

    # 예약 수량은 일반 주문 추세 및 재고 Snapshot과 구분한다.
    if any(word in text for word in (
        "예약", "미확보", "확보 수량", "선주문",
        "preorder", "pre-order",
    )):
        return "DETERMINISTIC", "RESERVATION"

    # 입고 예정 및 실제 입고는 서로 다른 업무 상태다.
    if any(word in text for word in (
        "입고", "납품", "입고 예정", "도착 예정",
    )):
        return "DETERMINISTIC", "INCOMING"

    if any(word in text for word in (
        "재고", "품절", "가용수량", "가용 수량",
    )):
        return "DETERMINISTIC", "INVENTORY_UNAVAILABLE"

    if any(word in text for word in (
        "관계", "연결된", "연관", "영향", "의존",
    )):
        return "RELATION_DOCUMENT", "RELATION"

    if any(word in text for word in (
        "주문", "판매량", "판매 추세", "수요", "매출",
    )):
        return "DETERMINISTIC", "DEMAND"

    if any(word in text for word in (
        "상품 설명", "제품 설명", "상품 정보",
        "제품 정보", "특징", "소개",
    )):
        return "HYBRID", "PRODUCT_INFO"

    return "DETERMINISTIC", "UNSUPPORTED"

def resolve_target(session: Session, *, tenant_id: UUID, target: ContextInput) -> ResolvedTarget:
    """Resolve external PRODUCT number or scoped UUID to a same-tenant V2 FK."""
    if isinstance(target, ViewContextInput):
        category = target.filters.major_category
        if category is not None and session.scalar(
            select(CategoryV2.id).where(
                CategoryV2.tenant_id == tenant_id,
                CategoryV2.category_depth == 1,
                CategoryV2.category_name == category,
            )
        ) is None:
            raise C09ContractError("HOLD", "UNKNOWN_VIEW_CATEGORY")
        return ResolvedTarget(
            target.page, "", target.page, "C09_VIEW", None,
            "LOCAL_V2_VIEW_SCOPE", None, None, target.snapshot(),
        )
    if target.target_type == "PRODUCT":
        row = session.scalar(
            select(ProductV2).where(
                ProductV2.tenant_id == tenant_id,
                ProductV2.cafe24_product_no == int(target.target_id),
            )
        )
        if row is None:
            raise C09ContractError("MISSING", "TARGET_NOT_FOUND")
        label, as_of, product_id = row.product_name, row.source_as_of, row.id
        data_mode = "LOCAL_V2_CATALOG_MASTER"
    else:
        model = IncomingShipmentV2 if target.target_type == "INCOMING" else TaskV2
        row = session.scalar(
            select(model).where(model.tenant_id == tenant_id, model.id == UUID(target.target_id))
        )
        if row is None:
            raise C09ContractError("MISSING", "TARGET_NOT_FOUND")
        label = f"{target.target_type} {row.id}"
        as_of = None  # operations incoming/task models have no source_as_of field
        product_id = row.product_id
        data_mode = "LOCAL_V2_OPERATIONS"
    if target.target_label != label:
        raise C09ContractError("CONFLICT", "TARGET_LABEL_MISMATCH")
    if target.as_of != as_of:
        raise C09ContractError("STALE", "SOURCE_TIME_MISMATCH")
    return ResolvedTarget(
        target.target_type,
        target.target_id,
        label,
        target.source,
        as_of,
        data_mode,
        row.id,
        product_id,
    )


def _context_entity(context: MessageContextV2) -> UUID | None:
    return context.product_id or context.incoming_shipment_id or context.task_id


def _view_metadata(target: ResolvedTarget) -> dict | None:
    return {VIEW_SNAPSHOT_KEY: target.view_snapshot} if target.view_snapshot is not None else None


def _same_context(prior: MessageContextV2, target: ResolvedTarget) -> bool:
    return (
        prior.page_type == target.target_type
        and _context_entity(prior) == target.entity_id
        and prior.source == target.source
        and prior.data_as_of == target.as_of
        and prior.source_versions == _view_metadata(target)
    )


def _related(
    session: Session, tenant_id: UUID, prior: MessageContextV2, target: ResolvedTarget
) -> bool:
    if target.view_snapshot is not None:
        return prior.page_type == target.target_type and prior.product_id is None
    if prior.source == "C09_VIEW":
        return False
    if prior.page_type == target.target_type and _context_entity(prior) == target.entity_id:
        return True
    previous_product = prior.product_id
    if previous_product is None and prior.incoming_shipment_id is not None:
        previous_product = session.scalar(
            select(IncomingShipmentV2.product_id).where(
                IncomingShipmentV2.tenant_id == tenant_id,
                IncomingShipmentV2.id == prior.incoming_shipment_id,
            )
        )
    if previous_product is None and prior.task_id is not None:
        previous_product = session.scalar(
            select(TaskV2.product_id).where(
                TaskV2.tenant_id == tenant_id,
                TaskV2.id == prior.task_id,
            )
        )
    pair = {prior.page_type, target.target_type}
    if pair == {"INCOMING", "TASK"}:
        incoming_id = prior.incoming_shipment_id or target.entity_id
        task_id = prior.task_id or target.entity_id
        return (
            session.scalar(
                select(TaskIncomingDependencyV2.task_id).where(
                    TaskIncomingDependencyV2.tenant_id == tenant_id,
                    TaskIncomingDependencyV2.task_id == task_id,
                    TaskIncomingDependencyV2.incoming_shipment_id == incoming_id,
                )
            )
            is not None
        )
    if previous_product is not None and target.product_id == previous_product:
        return True
    return False


def _append(
    session: Session,
    *,
    conversation: ConversationV2,
    target: ResolvedTarget,
    intent: Intent,
    order: int,
    revision: int,
    analysis_kind: AnalysisKind = "NONE",
    question: str | None = None,
) -> MessageV2:
    message = MessageV2(
        tenant_id=conversation.tenant_id,
        conversation_id=conversation.id,
        message_order=order,
        role="USER",
        content=question if question is not None else "선택 대상 확인 요청",
        intent=intent,
        analysis_kind=analysis_kind,
        response_status="HOLD",
    )
    session.add(message)
    session.flush()
    context = MessageContextV2(
        tenant_id=conversation.tenant_id,
        message_id=message.id,
        page_type=target.target_type,
        target_label=target.target_label,
        source=target.source,
        product_id=target.entity_id if target.target_type == "PRODUCT" else None,
        incoming_shipment_id=target.entity_id if target.target_type == "INCOMING" else None,
        task_id=target.entity_id if target.target_type == "TASK" else None,
        data_mode=target.data_mode,
        data_as_of=target.as_of,
        context_revision=revision,
        source_versions=(
            {VIEW_SNAPSHOT_KEY: target.view_snapshot} if target.view_snapshot is not None else None
        ),
        evidence_ids=[],
    )
    session.add(context)
    return message


def create_conversation(
    session: Session, *, tenant_id: UUID, actor_id: str, target: ContextInput
) -> ConversationV2:
    validate_pre_storage(actor_id, target, "INSPECT_TARGET")
    resolved = resolve_target(session, tenant_id=tenant_id, target=target)
    row = ConversationV2(
        tenant_id=tenant_id, owner_actor_id=actor_id, title=None, conversation_status="ACTIVE"
    )
    try:
        session.add(row)
        session.flush()
        _append(
            session, conversation=row, target=resolved, intent="INSPECT_TARGET", order=0, revision=1
        )
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise C09ContractError("CONFLICT", "CONVERSATION_WRITE_CONFLICT") from exc
    return row


def _owned(
    session: Session, tenant_id: UUID, actor_id: str, conversation_id: UUID, *, lock: bool = False
) -> ConversationV2:
    if not valid_c09_actor_id(actor_id):
        raise C09ContractError("HOLD", "TRUSTED_ACTOR_REQUIRED")
    statement = select(ConversationV2).where(
        ConversationV2.id == conversation_id,
        ConversationV2.tenant_id == tenant_id,
        ConversationV2.owner_actor_id == actor_id,
    )
    if lock:
        statement = statement.with_for_update()
    row = session.scalar(statement)
    if row is None:
        raise C09ContractError("MISSING", "CONVERSATION_NOT_FOUND")
    return row


def resolve_product_search_target(
    session: Session,
    *,
    tenant_id: UUID,
    query: str,
    search_service: ProductSearchService | None,
) -> TargetInput:
    """Resolve validated text to one same-tenant Product before C09 context freeze."""
    normalized = unicodedata.normalize("NFKC", query).strip()
    if (
        not normalized or len(normalized) > 200
        or any(unicodedata.category(char).startswith("C") for char in normalized)
        or _PRODUCT_SEARCH_SENSITIVE.search(normalized)
    ):
        raise C09ContractError("HOLD", "PRODUCT_SEARCH_INPUT_FORBIDDEN")
    try:
        validate_query(normalized)
    except RetrievalFailure as exc:
        raise C09ContractError("HOLD", "PRODUCT_SEARCH_INPUT_FORBIDDEN") from exc

    product = None
    if normalized.lower().startswith("product_id:"):
        try:
            product_id = UUID(normalized.split(":", 1)[1])
        except ValueError as exc:
            raise C09ContractError("HOLD", "PRODUCT_SEARCH_INVALID_ID") from exc
        product = session.scalar(select(ProductV2).where(
            ProductV2.tenant_id == tenant_id, ProductV2.id == product_id,
        ))
    else:
        code = (
            normalized.split(":", 1)[1]
            if normalized.lower().startswith("product_code:") else normalized
        )
        if _PRODUCT_CODE.fullmatch(code):
            matches = session.scalars(select(ProductV2).where(
                ProductV2.tenant_id == tenant_id, ProductV2.product_code == code,
            ).limit(2)).all()
            if len(matches) > 1:
                raise C09ContractError("CONFLICT", "PRODUCT_SEARCH_AMBIGUOUS")
            product = matches[0] if matches else None
        if product is None and normalized.lower().startswith("product_code:"):
            raise C09ContractError("MISSING", "PRODUCT_SEARCH_NOT_FOUND")
        if product is None:
            if search_service is None:
                raise C09ContractError("HOLD", "PRODUCT_SEARCH_UNAVAILABLE")
            try:
                candidates = search_service.resolve_product_ids(
                    session=session, tenant_id=tenant_id, query=normalized,
                )
            except Exception as exc:
                raise C09ContractError("HOLD", "PRODUCT_SEARCH_UNAVAILABLE") from exc
            if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes)):
                raise C09ContractError("HOLD", "PRODUCT_SEARCH_INVALID_RESULT")
            if len(candidates) > 1:
                raise C09ContractError("CONFLICT", "PRODUCT_SEARCH_AMBIGUOUS")
            if not candidates:
                raise C09ContractError("MISSING", "PRODUCT_SEARCH_NOT_FOUND")
            if not isinstance(candidates[0], UUID):
                raise C09ContractError("HOLD", "PRODUCT_SEARCH_INVALID_RESULT")
            product = session.scalar(select(ProductV2).where(
                ProductV2.tenant_id == tenant_id, ProductV2.id == candidates[0],
            ))
    if product is None:
        raise C09ContractError("MISSING", "PRODUCT_SEARCH_NOT_FOUND")
    return TargetInput(
        "PRODUCT", str(product.cafe24_product_no), product.product_name,
        "CAFE24_CATALOG", product.source_as_of,
    )


def append_turn(
    session: Session,
    *,
    tenant_id: UUID,
    actor_id: str,
    conversation_id: UUID,
    target: ContextInput,
    intent: Intent,
) -> ConversationV2:
    validate_pre_storage(actor_id, target, intent)
    row = _owned(session, tenant_id, actor_id, conversation_id, lock=True)
    if row.conversation_status != "ACTIVE":
        raise C09ContractError("CONFLICT", "CONVERSATION_NOT_ACTIVE")
    resolved = resolve_target(session, tenant_id=tenant_id, target=target)
    previous = session.execute(
        select(MessageV2, MessageContextV2)
        .join(
            MessageContextV2,
            (MessageContextV2.tenant_id == MessageV2.tenant_id)
            & (MessageContextV2.message_id == MessageV2.id),
        )
        .where(
            MessageV2.tenant_id == tenant_id,
            MessageV2.conversation_id == conversation_id,
            MessageV2.role == "USER",
        )
        .order_by(MessageV2.message_order.desc())
        .limit(1)
    ).first()
    if previous is None:
        raise C09ContractError("ERROR", "CONVERSATION_CONTEXT_MISSING")
    _, last_context = previous
    if not _related(session, tenant_id, last_context, resolved):
        raise C09ContractError("CONFLICT", "UNRELATED_TARGET_NEW_CONVERSATION_REQUIRED")
    same_target = _same_context(last_context, resolved)
    revision = last_context.context_revision if same_target else last_context.context_revision + 1
    last_order = session.scalar(
        select(func.max(MessageV2.message_order)).where(
            MessageV2.tenant_id == tenant_id, MessageV2.conversation_id == conversation_id
        )
    )
    try:
        _append(
            session,
            conversation=row,
            target=resolved,
            intent=intent,
            order=last_order + 1,
            revision=revision,
        )
        row.updated_at = func.now()
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise C09ContractError("CONFLICT", "CONVERSATION_WRITE_CONFLICT") from exc
    return row

def _product_demand_answer(
    aggregate: SafeProductDemandAggregate,
) -> AiAnswerContract:
    """Create a safe product-level demand answer."""

    aggregate_evidence_id = (
        "product-demand:"
        f"{aggregate.data_mode}:"
        f"{aggregate.product_no}:"
        f"{aggregate.as_of.date().isoformat()}"
    )

    if aggregate.order_count == 0:
        answer = AiAnswerContract(
            conclusion=(
                "현재 synthetic 주문 데이터에서 "
                "이 상품의 주문 이력이 확인되지 않습니다."
            ),
            key_facts=(
                f"상품번호: {aggregate.product_no}",
                f"데이터 모드: {aggregate.data_mode}",
                f"기준시각: {aggregate.as_of.isoformat()}",
            ),
            evidence_ids=(),
            next_checks=(
                "주문 데이터 범위와 기준시각을 확인하세요.",
            ),
            status=ConversationStatus.HOLD,
        )
        validate_answer_contract(answer)
        return answer

    if aggregate.quality_status == "LOW_SAMPLE":
        sample_note = (
            "표본이 적어 추세를 강하게 해석하면 안 됩니다."
        )
    else:
        sample_note = (
            "현재 표본은 최소 분석 기준을 충족합니다."
        )

    if aggregate.trend_direction == "SURGE":
        trend_text = (
            "직전 10일의 유효수요가 0이어서 "
            "최근 구간에 새 수요가 발생했습니다."
        )
    elif aggregate.trend_direction == "UP":
        trend_text = (
            "최근 10일 유효수요가 직전 10일보다 증가했습니다."
        )
    elif aggregate.trend_direction == "DOWN":
        trend_text = (
            "최근 10일 유효수요가 직전 10일보다 감소했습니다."
        )
    else:
        trend_text = (
            "최근 10일 유효수요가 직전 10일과 비슷합니다."
        )

    ratio_text = (
        "비율 계산 불가"
        if aggregate.trend_ratio is None
        else f"{aggregate.trend_ratio:.2f}배"
    )
    aggregate_evidence_id = (
        "product-demand:"
        f"{aggregate.data_mode}:"
        f"{aggregate.product_no}:"
        f"{aggregate.as_of.date().isoformat()}"
    )
    answer = AiAnswerContract(
        conclusion=trend_text,
        key_facts=(
            f"상품번호: {aggregate.product_no}",
            f"상품명: {aggregate.product_name}",
            f"전체 주문건수: {aggregate.order_count}",
            f"전체 주문수량: {aggregate.ordered_quantity}",
            (
                "유효 주문건수: "
                f"{aggregate.effective_order_count}"
            ),
            (
                "유효 주문수량: "
                f"{aggregate.effective_quantity}"
            ),
            (
                "최근 10일 유효수량: "
                f"{aggregate.recent_10d_effective_quantity}"
            ),
            (
                "직전 10일 유효수량: "
                f"{aggregate.previous_10d_effective_quantity}"
            ),
            (
                (
                    f"최근 10일 주문 수량: "
                    f"{aggregate.recent_10d_effective_quantity}개"
                ),
                (
                    f"직전 10일 주문 수량: "
                    f"{aggregate.previous_10d_effective_quantity}개"
                ),
                (
                    f"직전 기간 대비 주문 수량 변화: "
                    f"{aggregate.trend_delta:+d}개"
                ),
            ),
            (
                "취소/불확실/미결제 수량: "
                f"{aggregate.canceled_quantity}/"
                f"{aggregate.uncertain_quantity}/"
                f"{aggregate.unpaid_quantity}"
            ),
            (
                "배송대기/부분/완료 주문건수: "
                f"{aggregate.shipping_pending_count}/"
                f"{aggregate.shipping_partial_count}/"
                f"{aggregate.shipping_complete_count}"
            ),
            f"품질상태: {aggregate.quality_status}",
            f"데이터 모드: {aggregate.data_mode}",
            f"기준시각: {aggregate.as_of.isoformat()}",
        ),
        evidence_ids=(
            aggregate_evidence_id,
        ),
        next_checks=(
            sample_note,
            (
                "재고 부족 여부는 실제 재고 source가 연결되지 않아 "
                "현재 판단하지 않습니다."
            ),
            (
                "SKU/variant 단위 분석은 variant master가 "
                "준비된 뒤 수행하세요."
            ),
        ),
        status=ConversationStatus.ANSWER,
    )

    validate_answer_contract(answer)
    return answer

def _safe_analysis(
    session: Session,
    *,
    tenant_id: UUID,
    target: ResolvedTarget,
    analysis_kind: AnalysisKind,
) -> AiAnswerContract:
    """Run only currently supported safe operational analysis."""

    if analysis_kind != "DETERMINISTIC":
        raise C09ContractError(
            "HOLD",
            "UNSUPPORTED_ANALYSIS_KIND",
        )

    if (
        target.target_type == "PRODUCT"
        and target.product_id is not None
    ):
        try:
            projection = project_product_demand(
                session,
                tenant_id=tenant_id,
                product_id=target.product_id,
            )

            aggregate = (
                safe_product_demand_aggregate(
                    projection
                )
            )

        except ValueError as exc:
            if str(exc) == (
                "SYNTHETIC_DEMO_ORDER_SOURCE_MISSING"
            ):
                answer = AiAnswerContract(
                    conclusion=(
                        "상품 주문수요를 판단할 "
                        "안전한 주문 데이터가 없습니다."
                    ),
                    key_facts=(
                        "지원 대상: PRODUCT",
                        (
                            "필요 데이터 모드: "
                            "SYNTHETIC_DEMO"
                        ),
                    ),
                    evidence_ids=(),
                    next_checks=(
                        "Synthetic 주문 source를 확인하세요.",
                    ),
                    status=ConversationStatus.HOLD,
                )
                validate_answer_contract(answer)
                return answer

            raise C09ContractError(
                "ERROR",
                "PRODUCT_DEMAND_PROJECTION_FAILED",
            ) from exc

        return _product_demand_answer(
            aggregate
        )

    answer = AiAnswerContract(
        conclusion=(
            "현재 대상의 운영 관계를 판단할 "
            "권위 자료가 부족합니다."
        ),
        key_facts=(
            f"확인된 대상 유형: {target.target_type}",
            f"확인된 출처: {target.source}",
        ),
        evidence_ids=(),
        next_checks=(
            (
                "현재 재고·입고·업무의 "
                "권위 자료를 확인하세요."
            ),
        ),
        status=ConversationStatus.HOLD,
    )

    validate_answer_contract(answer)
    return answer


def dispatch_analysis_request(
    session: Session,
    *,
    tenant_id: UUID,
    request_message: MessageV2,
    frozen_target: ResolvedTarget,
    session_factory: sessionmaker | None = None,
    demo_session_id: UUID | None = None,
    settings: Settings | None = None,
    reservation_projection: (
        ReservationRiskProjection | None
    ) = None,
    neo4j_driver=None,
) -> AnalysisRuntimeResult:
    """Route a persisted C09 request without changing its frozen context."""
    if request_message.content != "선택 대상 확인 요청" and frozen_target.target_type != "PRODUCT":
        answer = AiAnswerContract(
            conclusion="이 대상의 자연어 분석은 아직 지원되지 않아 판단을 보류합니다.",
            key_facts=("현재 질문과 업무 대상은 대화 이력에 보존했습니다.",),
            evidence_ids=(),
            next_checks=("운영 일정의 확인된 입고·업무 정보를 직접 확인하세요.",),
            status=ConversationStatus.HOLD,
        )
        validate_answer_contract(answer)
        return AnalysisRuntimeResult(answer)
    if request_message.content != "선택 대상 확인 요청":
        _, question_type = classify_operational_question(
            request_message.content
        )
        if question_type in {"RESERVATION", "INCOMING"}:
            facts = read_product_reservation_facts(
                session,
                tenant_id=tenant_id,
                product_id=frozen_target.product_id,
            )

            if facts["status"] == "HOLD":
                answer = AiAnswerContract(
                    conclusion=(
                        "이 상품의 예약 수량을 판단할 "
                        "충분한 자료가 확인되지 않았습니다."
                    ),
                    key_facts=(),
                    evidence_ids=(),
                    next_checks=(
                        f"확인 필요: {facts['reason']}",
                    ),
                    status=ConversationStatus.HOLD,
                )
            else:
                baseline = facts["baseline_unsecured_quantity"]
                conditional = facts["conditional_shortage_quantity"]

                conclusion = (
                    f"현재 확보된 수량만 기준으로 보면 "
                    f"예약 물량 {baseline}개가 미확보 상태입니다."
                )

                details = [
                    f"예약 필요 수량: {facts['required_quantity']}개",
                    f"현재 확보 수량: {facts['secured_quantity']}개",
                    f"현재 미확보 수량: {baseline}개",
                ]

                if conditional is not None:
                    conclusion += (
                        f" 예정 입고 {facts['conditional_incoming_quantity']}개를 "
                        f"예약에 사용할 수 있다고 가정하면 "
                        f"잔여 미확보 수량은 {conditional}개입니다."
                    )
                    details.append(
                        f"예정 입고 반영 시 조건부 미확보 수량: {conditional}개"
                    )

                answer = AiAnswerContract(
                    conclusion=conclusion,
                    key_facts=tuple(details),
                    evidence_ids=(
                        f"reservation-risk:{facts['reservation_id']}",
                    ),
                    next_checks=(
                        "예정 입고의 실제 수령 여부와 "
                        "해당 예약에 배분할 수 있는지 확인하세요.",
                    ),
                    status=ConversationStatus.ANSWER,
                )

            validate_answer_contract(answer)
            return AnalysisRuntimeResult(answer)
        if question_type in {
            "INVENTORY_UNAVAILABLE",
            "RESERVATION",
            "INCOMING",
            "UNSUPPORTED",
        }:
            if question_type == "RESERVATION":
                conclusion = (
                    "예약 수량은 일반 주문 추세와 별도로 계산해야 합니다. "
                    "현재 대화 경로에는 검증된 예약 수량 결과가 "
                    "연결되지 않아 충분 여부를 판단할 수 없습니다."
                )
                next_check = (
                    "예약 필요 수량, 확보 수량 및 사용 가능한 "
                    "예정 입고를 확인해야 합니다."
                )
            elif question_type == "INCOMING":
                conclusion = (
                    "예정된 입고가 있는지와 예약에 사용할 수 있는지는 "
                    "서로 다른 문제입니다. 현재 질문에 대한 "
                    "입고 배분 근거가 연결되지 않았습니다."
                )
                next_check = (
                    "입고 예정 수량, 상태, SKU 및 예약 배분 가능성을 "
                    "확인해야 합니다."
                )
            if question_type == "INVENTORY_UNAVAILABLE":
                conclusion = (
                    "현재 상품은 확인했지만 실제 재고 Snapshot이 "
                    "연결되지 않아 정확한 재고 수량과 부족 여부를 "
                    "판단할 수 없습니다."
                )
                next_check = "검증된 SKU/variant 재고 근거를 연결한 뒤 확인하세요."
            else:
                conclusion = (
                    "현재 질문은 지원되는 운영 분석 범위에 "
                    "해당하지 않아 판단을 보류합니다."
                )
                next_check = (
                    "상품 주문량·주문 추세·상품 설명·상품 관계를 "
                    "질문할 수 있습니다."
                )

            answer = AiAnswerContract(
                conclusion=conclusion,
                key_facts=(
                    f"확인 상품: {frozen_target.target_label}",
                    f"질문: {request_message.content}",
                ),
                evidence_ids=(),
                next_checks=(next_check,),
                status=ConversationStatus.HOLD,
            )
            validate_answer_contract(answer)
            return AnalysisRuntimeResult(answer)
    if request_message.analysis_kind == "DETERMINISTIC":
        return AnalysisRuntimeResult(_safe_analysis(
            session, tenant_id=tenant_id, target=frozen_target,
            analysis_kind="DETERMINISTIC",
        ))
    if request_message.analysis_kind == "HYBRID":
        evidence = None

        if (
            frozen_target.target_type == "PRODUCT"
            and frozen_target.product_id is not None
        ):
            evidence = retrieve_frozen_product_evidence(
                session,
                tenant_id=tenant_id,
                product_id=frozen_target.product_id,
            )

        if (
            evidence is not None
            and reservation_projection is not None
            and session_factory is not None
            and demo_session_id is not None
            and settings is not None
        ):
            try:
                grounded = (
                    run_reservation_grounded_explanation(
                        factory=session_factory,
                        settings=settings,
                        tenant_id=tenant_id,
                        demo_session_id=(
                            demo_session_id
                        ),
                        request_id=(
                            "reservation-analysis-"
                            f"{request_message.id}"
                        ),
                        question=(
                            request_message.content
                        ),
                        projection=(
                            reservation_projection
                        ),
                    )
                )

            except (
                DemoQuotaDenied,
                GroundedProviderError,
                GroundedProviderTimeout,
                ValueError,
            ):
                answer = AiAnswerContract(
                    conclusion=(
                        "예약 부족 근거는 확인했지만 "
                        "AI 설명을 안전하게 완료하지 "
                        "못했습니다."
                    ),
                    key_facts=(),
                    evidence_ids=(
                        evidence.evidence_id,
                    ),
                    next_checks=(
                        "예약 위험과 입고 상태를 "
                        "다시 확인하세요.",
                    ),
                    status=ConversationStatus.HOLD,
                )
                validate_answer_contract(
                    answer
                )
                return AnalysisRuntimeResult(
                    answer,
                    (evidence.metadata(),),
                )

            output = grounded.output

            answer = AiAnswerContract(
                conclusion=output.conclusion,
                key_facts=(
                    output.used_facts
                ),
                evidence_ids=tuple(
                    item.source_id
                    for item
                    in output.citations
                ),
                next_checks=(
                    (output.next_check,)
                    if output.next_check
                    else ()
                ),
                status=(
                    ConversationStatus.ANSWER
                    if output.status
                    == ExplanationStatus.ANSWER
                    else ConversationStatus.HOLD
                ),
            )

            validate_answer_contract(
                answer
            )

            return AnalysisRuntimeResult(
                answer,
                (evidence.metadata(),),
            )
        if evidence is not None:
            # TEST/비-provider 호출 경로는 기존 deterministic 결과를 유지한다.
            if (
                session_factory is None
                or demo_session_id is None
                or settings is None
            ):
                answer = AiAnswerContract(
                    conclusion=(
                        "저장된 Product 근거에서 요청한 "
                        "상품을 확인했습니다."
                    ),
                    key_facts=(
                        f"상품명: {evidence.product_name}",
                        f"상품 코드: {evidence.product_code}",
                        "확인 범위: 상품 master 정보",
                    ),
                    evidence_ids=(evidence.evidence_id,),
                    next_checks=(
                        "주문·재고 판단은 별도 권위 자료를 확인하세요.",
                    ),
                    status=ConversationStatus.ANSWER,
                )
                validate_answer_contract(answer)

                return AnalysisRuntimeResult(
                    answer,
                    (evidence.metadata(),),
                )

            metadata = evidence.metadata()

            try:
                grounded = run_product_grounded_explanation(
                    factory=session_factory,
                    settings=settings,
                    tenant_id=tenant_id,
                    demo_session_id=demo_session_id,
                    request_id=(
                        f"product-analysis-{request_message.id}"
                    ),
                    question=request_message.content,
                    data_mode=(
                        str(
                            metadata.get("data_mode")
                            or frozen_target.data_mode
                            or "SYNTHETIC_DEMO"
                        )
                    ),
                    evidence_id=evidence.evidence_id,
                    evidence_version=str(
                        metadata.get("content_hash")
                        or "C16_PRODUCT"
                    ),
                    evidence_excerpt=(
                        f"상품명: {evidence.product_name}\n"
                        f"상품 코드: {evidence.product_code}\n"
                        "범위: 상품 master 정보"
                    ),
                )

            except (
                DemoQuotaDenied,
                GroundedProviderError,
                GroundedProviderTimeout,
                ValueError,
            ):
                answer = AiAnswerContract(
                    conclusion=(
                        "검증된 Product 근거는 확인했지만 "
                        "AI 설명을 안전하게 완료하지 못했습니다."
                    ),
                    key_facts=(
                        f"상품명: {evidence.product_name}",
                        f"상품 코드: {evidence.product_code}",
                    ),
                    evidence_ids=(evidence.evidence_id,),
                    next_checks=(
                        "잠시 후 다시 분석하거나 Product 근거를 확인하세요.",
                    ),
                    status=ConversationStatus.HOLD,
                )

                validate_answer_contract(answer)

                return AnalysisRuntimeResult(
                    answer,
                    (metadata,),
                )

            output = grounded.output

            if output.status == ExplanationStatus.HOLD:
                answer = AiAnswerContract(
                    conclusion=output.conclusion,
                    key_facts=(),
                    evidence_ids=(evidence.evidence_id,),
                    next_checks=(
                        (output.next_check,)
                        if output.next_check
                        else ()
                    ),
                    status=ConversationStatus.HOLD,
                )
            else:
                answer = AiAnswerContract(
                    conclusion=output.conclusion,
                    key_facts=output.used_facts,
                    evidence_ids=(evidence.evidence_id,),
                    next_checks=(
                        (output.next_check,)
                        if output.next_check
                        else ()
                    ),
                    status=ConversationStatus.ANSWER,
                )

            validate_answer_contract(answer)

            return AnalysisRuntimeResult(
                answer,
                (metadata,),
            )
        answer = AiAnswerContract(
            conclusion="현재 대상에 연결된 검증 가능한 Product 근거가 없어 분석을 보류합니다.",
            key_facts=("분석 방식: HYBRID",), evidence_ids=(),
            next_checks=("현재 Product와 C16 근거의 연결 상태를 확인하세요.",),
            status=ConversationStatus.HOLD,
        )
        validate_answer_contract(answer)
        return AnalysisRuntimeResult(answer)
    if request_message.analysis_kind not in {"HYBRID", "RELATION_DOCUMENT"}:
        raise C09ContractError("HOLD", "UNSUPPORTED_ANALYSIS_KIND")
    if (
        request_message.analysis_kind
        == "RELATION_DOCUMENT"
    ):
        if (
            frozen_target.target_type
            != "PRODUCT"
            or frozen_target.product_id is None
            or neo4j_driver is None
        ):
            answer = AiAnswerContract(
                conclusion=(
                    "Graph 관계 분석에 필요한 "
                    "검증된 대상 또는 runtime이 "
                    "준비되지 않았습니다."
                ),
                key_facts=(
                    "분석 방식: RELATION_DOCUMENT",
                ),
                evidence_ids=(),
                next_checks=(
                    "Graph 연결 상태를 확인하세요.",
                ),
                status=ConversationStatus.HOLD,
            )

            validate_answer_contract(answer)
            return AnalysisRuntimeResult(
                answer
            )

        graph_result = analyze_product_graph(
            neo4j_driver,
            tenant_id=tenant_id,
            product_id=frozen_target.product_id,
        )

        status = {
            "ANSWER": ConversationStatus.ANSWER,
            "NO_EDGE": ConversationStatus.NO_EDGE,
            "HOLD": ConversationStatus.HOLD,
        }[graph_result.status]

        answer = AiAnswerContract(
            conclusion=graph_result.conclusion,
            key_facts=graph_result.key_facts,
            evidence_ids=tuple(
                item.evidence_id
                for item in graph_result.evidence
            ),
            next_checks=(),
            status=status,
        )

        validate_answer_contract(answer)

        return AnalysisRuntimeResult(
            answer,
            tuple(
                {
                    "evidence_id": item.evidence_id,
                    "hop_count": item.hop_count,
                    "path": list(item.path),
                    "relation_types": list(
                        item.relation_types
                    ),
                    "projection_version": (
                        item.projection_version
                    ),
                }
                for item in graph_result.evidence
            ),
        )
    answer = AiAnswerContract(
        conclusion="요청한 분석 방식은 현재 연결되지 않아 결과를 보류합니다.",
        key_facts=(f"분석 방식: {request_message.analysis_kind}",),
        evidence_ids=(),
        next_checks=("검증된 분석 경로가 연결된 뒤 다시 요청하세요.",),
        status=ConversationStatus.HOLD,
    )
    validate_answer_contract(answer)
    return AnalysisRuntimeResult(answer)


def _answer_content(answer: AiAnswerContract) -> str:
    evidence = "; ".join(answer.evidence_ids) if answer.evidence_ids else "확인된 운영 근거 없음"
    return "\n".join(
        (
            f"결론: {answer.conclusion}",
            f"핵심 수치/상태: {'; '.join(answer.key_facts)}",
            f"근거: {evidence}",
            f"다음 확인/조치: {'; '.join(answer.next_checks)}",
        )
    )


def begin_analysis_request(
    session: Session,
    *,
    tenant_id: UUID,
    actor_id: str,
    conversation_id: UUID,
    target: ContextInput,
    intent: Intent,
    analysis_kind: AnalysisKind,
    request_revision: int,
    question: str | None = None,
) -> MessageV2:
    """Fix the owned request identity and immutable context before analysis starts."""
    validate_pre_storage(actor_id, target, intent)

    if question is not None:
        expected_kind, _ = classify_operational_question(question)
        if not isinstance(target, TargetInput):
            raise C09ContractError("HOLD", "QUESTION_CONTEXT_UNSUPPORTED")
        if analysis_kind != (expected_kind if target.target_type == "PRODUCT" else "DETERMINISTIC"):
            raise C09ContractError("HOLD", "QUESTION_ANALYSIS_MISMATCH")

    if analysis_kind not in {"DETERMINISTIC", "HYBRID", "RELATION_DOCUMENT"}:
        raise C09ContractError("HOLD", "UNSUPPORTED_ANALYSIS_KIND")
    row = _owned(session, tenant_id, actor_id, conversation_id, lock=True)
    if row.conversation_status != "ACTIVE":
        raise C09ContractError("CONFLICT", "CONVERSATION_NOT_ACTIVE")
    previous = session.execute(
        select(MessageV2, MessageContextV2)
        .join(
            MessageContextV2,
            (MessageContextV2.tenant_id == MessageV2.tenant_id)
            & (MessageContextV2.message_id == MessageV2.id),
        )
        .where(
            MessageV2.tenant_id == tenant_id,
            MessageV2.conversation_id == conversation_id,
            MessageV2.role == "USER",
        )
        .order_by(MessageV2.message_order.desc())
        .limit(1)
    ).first()
    if previous is None:
        raise C09ContractError("ERROR", "CONVERSATION_CONTEXT_MISSING")
    _, last_context = previous
    if request_revision != last_context.context_revision:
        raise C09ContractError("STALE", "REQUEST_REVISION_MISMATCH")
    resolved = resolve_target(session, tenant_id=tenant_id, target=target)
    if not _related(session, tenant_id, last_context, resolved):
        raise C09ContractError("CONFLICT", "UNRELATED_TARGET_NEW_CONVERSATION_REQUIRED")
    same_target = _same_context(last_context, resolved)
    revision = last_context.context_revision if same_target else request_revision + 1
    last_order = session.scalar(
        select(func.max(MessageV2.message_order)).where(
            MessageV2.tenant_id == tenant_id, MessageV2.conversation_id == conversation_id
        )
    )
    try:
        message = _append(
            session,
            conversation=row,
            target=resolved,
            intent=intent,
            order=last_order + 1,
            revision=revision,
            analysis_kind=analysis_kind,
            question=question,
        )
        row.updated_at = func.now()
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise C09ContractError("CONFLICT", "CONVERSATION_WRITE_CONFLICT") from exc
    return message


def complete_analysis_request(
    session: Session,
    *,
    tenant_id: UUID,
    actor_id: str,
    conversation_id: UUID,
    request_message_id: UUID,
    session_factory: sessionmaker | None = None,
    demo_session_id: UUID | None = None,
    settings: Settings | None = None,
    reservation_projection: (
        ReservationRiskProjection | None
    ) = None,
    neo4j_driver=None,
) -> ConversationV2:
    """Append a result to its original revision, even when the UI moved on."""
    row = _owned(session, tenant_id, actor_id, conversation_id, lock=True)
    if row.conversation_status not in {"ACTIVE", "CLOSED"}:
        raise C09ContractError("CONFLICT", "CONVERSATION_STATUS_UNSUPPORTED")
    pair = session.execute(
        select(MessageV2, MessageContextV2)
        .join(MessageContextV2, MessageContextV2.message_id == MessageV2.id)
        .where(
            MessageV2.tenant_id == tenant_id,
            MessageV2.conversation_id == conversation_id,
            MessageV2.id == request_message_id,
            MessageV2.role == "USER",
        )
    ).first()
    if pair is None:
        raise C09ContractError("MISSING", "ANALYSIS_REQUEST_NOT_FOUND")
    request_message, request_context = pair
    if request_message.analysis_kind not in {"DETERMINISTIC", "HYBRID", "RELATION_DOCUMENT"}:
        raise C09ContractError("CONFLICT", "ANALYSIS_REQUEST_INVALID")
    context_meta = request_context.source_versions or {}
    if request_context.source == "C09_VIEW":
        try:
            view = ViewContextInput.model_validate(context_meta[VIEW_SNAPSHOT_KEY])
        except (KeyError, ValueError) as exc:
            raise C09ContractError("STALE", "ANALYSIS_CONTEXT_INVALID") from exc
        if view.page != request_context.page_type:
            raise C09ContractError("STALE", "ANALYSIS_CONTEXT_INVALID")
        try:
            resolve_target(session, tenant_id=tenant_id, target=view)
        except C09ContractError as exc:
            raise C09ContractError("STALE", "ANALYSIS_CONTEXT_INVALID") from exc
    else:
        entity_id = _context_entity(request_context)
        model = {
            "PRODUCT": ProductV2,
            "INCOMING": IncomingShipmentV2,
            "TASK": TaskV2,
        }.get(request_context.page_type)
        if model is None or entity_id is None or session.scalar(
            select(model.id).where(model.tenant_id == tenant_id, model.id == entity_id)
        ) is None:
            raise C09ContractError("STALE", "ANALYSIS_CONTEXT_INVALID")
    prior_results = session.execute(
        select(MessageContextV2.source_versions)
        .join(MessageV2, MessageV2.id == MessageContextV2.message_id)
        .where(
            MessageV2.tenant_id == tenant_id,
            MessageV2.conversation_id == conversation_id,
            MessageV2.role == "ASSISTANT",
        )
    ).scalars()
    if any((meta or {}).get("c09_analysis_request_id") == str(request_message_id)
           for meta in prior_results):
        raise C09ContractError("CONFLICT", "ANALYSIS_ALREADY_COMPLETED")
    resolved = ResolvedTarget(
        request_context.page_type,
        "",
        request_context.target_label or request_context.page_type,
        request_context.source,
        request_context.data_as_of,
        request_context.data_mode,
        _context_entity(request_context),
        request_context.product_id,
        context_meta.get(VIEW_SNAPSHOT_KEY),
    )
    runtime_result = dispatch_analysis_request(
        session,
        tenant_id=tenant_id,
        request_message=request_message,
        frozen_target=resolved,
        session_factory=session_factory,
        demo_session_id=demo_session_id,
        settings=settings,
        reservation_projection=reservation_projection,
        neo4j_driver=neo4j_driver,
    )
    answer = runtime_result.answer
    last_order = session.scalar(
        select(func.max(MessageV2.message_order)).where(
            MessageV2.tenant_id == tenant_id, MessageV2.conversation_id == conversation_id
        )
    )
    try:
        assistant = MessageV2(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            message_order=last_order + 1,
            role="ASSISTANT",
            content=_answer_content(answer),
            intent=request_message.intent,
            analysis_kind=request_message.analysis_kind,
            response_status=message_status_for_ai(answer.status),
        )
        session.add(assistant)
        session.flush()
        session.add(
            MessageContextV2(
                tenant_id=tenant_id,
                message_id=assistant.id,
                page_type=request_context.page_type,
                target_label=request_context.target_label,
                source=request_context.source,
                product_id=request_context.product_id,
                incoming_shipment_id=request_context.incoming_shipment_id,
                task_id=request_context.task_id,
                data_mode=request_context.data_mode,
                data_as_of=request_context.data_as_of,
                context_revision=request_context.context_revision,
                source_versions={
                    **context_meta,
                    "c09_analysis_request_id": str(request_message_id),
                    **(
                        {
                            (
                                "c17_relation_evidence"
                                if request_message.analysis_kind == "RELATION_DOCUMENT"
                                else "c18_retrieval"
                            ): list(runtime_result.retrieval_evidence)
                        }
                        if runtime_result.retrieval_evidence
                        else {}
                    ),
                },
                evidence_ids=list(answer.evidence_ids),
            )
        )
        row.updated_at = func.now()
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise C09ContractError("CONFLICT", "CONVERSATION_WRITE_CONFLICT") from exc
    return row


def analyze_turn(
    session: Session,
    *,
    tenant_id: UUID,
    actor_id: str,
    conversation_id: UUID,
    target: ContextInput,
    intent: Intent,
    analysis_kind: AnalysisKind,
    request_revision: int,
    session_factory: sessionmaker | None = None,
    demo_session_id: UUID | None = None,
    settings: Settings | None = None,
    reservation_projection: (
        ReservationRiskProjection | None
    ) = None,
    neo4j_driver=None,
    question: str | None = None,
) -> ConversationV2:
    request = begin_analysis_request(
        session, tenant_id=tenant_id, actor_id=actor_id, conversation_id=conversation_id,
        target=target, intent=intent, analysis_kind=analysis_kind,
        request_revision=request_revision, question=question,
    )
    return complete_analysis_request(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        conversation_id=conversation_id,
        request_message_id=request.id,
        session_factory=session_factory,
        demo_session_id=demo_session_id,
        settings=settings,
        reservation_projection=reservation_projection,
        neo4j_driver=neo4j_driver,
    )


def analyze_product_search_turn(
    session: Session,
    *,
    tenant_id: UUID,
    actor_id: str,
    conversation_id: UUID,
    query: str,
    intent: Intent,
    request_revision: int,
    search_service: ProductSearchService | None,
) -> ConversationV2:
    """Authorize, resolve Product, then reuse the C09 frozen analysis path."""
    _owned(session, tenant_id, actor_id, conversation_id)
    target = resolve_product_search_target(
        session, tenant_id=tenant_id, query=query, search_service=search_service,
    )
    return analyze_turn(
        session, tenant_id=tenant_id, actor_id=actor_id,
        conversation_id=conversation_id, target=target, intent=intent,
        analysis_kind="HYBRID", request_revision=request_revision,
    )


def create_product_search_conversation(
    session: Session,
    *,
    tenant_id: UUID,
    actor_id: str,
    query: str,
    search_service: ProductSearchService | None,
) -> ConversationV2:
    """Resolve search text before creating a C09 conversation for an unrelated Product."""
    if not valid_c09_actor_id(actor_id):
        raise C09ContractError("HOLD", "TRUSTED_ACTOR_REQUIRED")
    target = resolve_product_search_target(
        session, tenant_id=tenant_id, query=query, search_service=search_service,
    )
    row = create_conversation(session, tenant_id=tenant_id, actor_id=actor_id, target=target)
    return analyze_turn(
        session, tenant_id=tenant_id, actor_id=actor_id,
        conversation_id=row.id, target=target, intent="INSPECT_TARGET",
        analysis_kind="HYBRID", request_revision=1,
    )


def read_conversation(
    session: Session, *, tenant_id: UUID, actor_id: str, conversation_id: UUID
) -> dict:
    row = _owned(session, tenant_id, actor_id, conversation_id)
    pairs = session.execute(
        select(MessageV2, MessageContextV2)
        .join(
            MessageContextV2,
            (MessageContextV2.tenant_id == MessageV2.tenant_id)
            & (MessageContextV2.message_id == MessageV2.id),
        )
        .where(MessageV2.tenant_id == tenant_id, MessageV2.conversation_id == conversation_id)
        .order_by(MessageV2.message_order)
    ).all()
    messages = []
    for message, context in pairs:
        meta = context.source_versions or {}
        view_snapshot = meta.get(VIEW_SNAPSHOT_KEY)
        if context.source == "C09_VIEW":
            try:
                view = ViewContextInput.model_validate(view_snapshot)
            except ValueError as exc:
                raise C09ContractError("STALE", "ANALYSIS_CONTEXT_INVALID") from exc
            if view.page != context.page_type:
                raise C09ContractError("STALE", "ANALYSIS_CONTEXT_INVALID")
            view_snapshot = view.snapshot()
        entity_id = _context_entity(context)
        target_id = str(entity_id) if entity_id is not None else None
        if context.page_type == "PRODUCT":
            product_no = session.scalar(
                select(ProductV2.cafe24_product_no).where(
                    ProductV2.tenant_id == tenant_id, ProductV2.id == entity_id
                )
            )
            if product_no is None:
                raise C09ContractError("MISSING", "TARGET_NOT_FOUND")
            target_id = str(product_no)
        messages.append(
            {
                "message_id": str(message.id),
                "message_order": message.message_order,
                "role": message.role,
                "content": message.content,
                "response_status": message.response_status,
                "intent": message.intent,
                "analysis_kind": message.analysis_kind,
                "request_message_id": meta.get("c09_analysis_request_id"),
                "evidence_ids": list(context.evidence_ids or []),
                "context": {
                    "context_revision": context.context_revision,
                    "scope": "VIEW" if view_snapshot is not None else "ENTITY",
                    "page": context.page_type if view_snapshot is not None else None,
                    "filters": (
                        view_snapshot.get("filters", {}) if view_snapshot is not None else None
                    ),
                    "search": view_snapshot.get("search") if view_snapshot is not None else None,
                    "date_range": (
                        view_snapshot.get("date_range") if view_snapshot is not None else None
                    ),
                    "sort": view_snapshot.get("sort") if view_snapshot is not None else None,
                    "target_type": None if view_snapshot is not None else context.page_type,
                    "target_id": target_id,
                    "target_label": context.target_label,
                    "source": context.source,
                    "source_as_of": context.data_as_of,
                    "data_mode": context.data_mode,
                },
            }
        )
    runs = session.scalars(
        select(AgentRunV2).where(
            AgentRunV2.tenant_id == tenant_id,
            AgentRunV2.conversation_id == conversation_id,
        )
    ).all()
    current_context = next(
        (message["context"] for message in reversed(messages) if message["role"] == "USER"),
        None,
    )
    return {
        "conversation_id": str(row.id),
        "conversation_status": row.conversation_status,
        "current_context_revision": current_context["context_revision"] if current_context else 0,
        "context": current_context,
        "messages": messages,
        "agent_runs": [
            {
                "workflow_id": run.workflow_id,
                "thread_id": run.thread_id,
                "run_status": run.run_status,
            }
            for run in runs
        ],
    }


def recent_conversations(
    session: Session, *, tenant_id: UUID, actor_id: str, limit: int = 20
) -> list[dict]:
    if not valid_c09_actor_id(actor_id):
        raise C09ContractError("HOLD", "TRUSTED_ACTOR_REQUIRED")
    rows = session.scalars(
        select(ConversationV2)
        .where(
            ConversationV2.tenant_id == tenant_id,
            ConversationV2.owner_actor_id == actor_id,
        )
        .order_by(ConversationV2.updated_at.desc(), ConversationV2.id.desc())
        .limit(limit)
    ).all()
    return [
        read_conversation(session, tenant_id=tenant_id, actor_id=actor_id, conversation_id=row.id)
        for row in rows
    ]


def reopen_conversation(
    session: Session, *, tenant_id: UUID, actor_id: str, conversation_id: UUID
) -> ConversationV2:
    row = _owned(session, tenant_id, actor_id, conversation_id, lock=True)
    if row.conversation_status not in {"ACTIVE", "CLOSED"}:
        raise C09ContractError("CONFLICT", "CONVERSATION_STATUS_UNSUPPORTED")
    if row.conversation_status == "CLOSED":
        row.conversation_status = "ACTIVE"
        session.commit()
    return row
