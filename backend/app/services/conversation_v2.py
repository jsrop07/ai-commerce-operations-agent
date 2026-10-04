"""C09 PRE conversation storage boundary; no model or retrieval execution."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models_v2.ai import AgentRunV2, ConversationV2, MessageContextV2, MessageV2
from backend.app.models_v2.catalog import ProductV2
from backend.app.models_v2.operations import IncomingShipmentV2, TaskIncomingDependencyV2, TaskV2
from backend.app.worker.privacy.text_redaction import EMAIL_PATTERN, ORDER_ID_PATTERN, PHONE_PATTERN

TargetType = Literal["PRODUCT", "INCOMING", "TASK"]
Intent = Literal["INSPECT_TARGET", "FOLLOW_RELATED_TARGET"]
AnalysisKind = Literal["NONE"]


@dataclass(frozen=True)
class TargetInput:
    target_type: TargetType
    target_id: str
    target_label: str
    source: str
    as_of: datetime | None


@dataclass(frozen=True)
class ResolvedTarget:
    target_type: TargetType
    target_id: str
    target_label: str
    source: str
    as_of: datetime | None
    data_mode: str
    entity_id: UUID
    product_id: UUID | None


class C09ContractError(Exception):
    def __init__(self, status: Literal["HOLD", "MISSING", "STALE", "ERROR", "CONFLICT"], code: str):
        super().__init__(code)
        self.status = status
        self.code = code


_SOURCE_BY_TYPE = {
    "PRODUCT": "CAFE24_CATALOG",
    "INCOMING": "OPERATIONS_INCOMING",
    "TASK": "OPERATIONS_TASK",
}
_ACTOR = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_PRODUCT_NUMBER = re.compile(r"^[0-9]{1,18}$")
_FORBIDDEN_HINT = re.compile(
    r"(?:고객\s*(?:이름|성명|전화|주소|메일)|문의\s*원문|배송\s*(?:주소|번호)|"
    r"결제\s*(?:번호|정보)|customer[_ -]?id|order[_ -]?id|inquiry[_ -]?(?:body|text))",
    re.IGNORECASE,
)


def validate_pre_storage(actor_id: str, target: TargetInput, intent: Intent) -> None:
    """Run before any conversation, message, context, log, or checkpoint write."""
    if not _ACTOR.fullmatch(actor_id):
        raise C09ContractError("HOLD", "TRUSTED_ACTOR_REQUIRED")
    if intent not in {"INSPECT_TARGET", "FOLLOW_RELATED_TARGET"}:
        raise C09ContractError("HOLD", "UNSUPPORTED_INTENT")
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


def resolve_target(session: Session, *, tenant_id: UUID, target: TargetInput) -> ResolvedTarget:
    """Resolve external PRODUCT number or scoped UUID to a same-tenant V2 FK."""
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


def _related(
    session: Session, tenant_id: UUID, prior: MessageContextV2, target: ResolvedTarget
) -> bool:
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
    if previous_product is not None and target.product_id == previous_product:
        return True
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
    return False


def _append(
    session: Session,
    *,
    conversation: ConversationV2,
    target: ResolvedTarget,
    intent: Intent,
    order: int,
    revision: int,
) -> None:
    message = MessageV2(
        tenant_id=conversation.tenant_id,
        conversation_id=conversation.id,
        message_order=order,
        role="USER",
        content="선택 대상 확인 요청",
        intent=intent,
        analysis_kind="NONE",
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
        source_versions=None,
        evidence_ids=[],
    )
    session.add(context)


def create_conversation(
    session: Session, *, tenant_id: UUID, actor_id: str, target: TargetInput
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
    if not _ACTOR.fullmatch(actor_id):
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


def append_turn(
    session: Session,
    *,
    tenant_id: UUID,
    actor_id: str,
    conversation_id: UUID,
    target: TargetInput,
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
        .where(MessageV2.tenant_id == tenant_id, MessageV2.conversation_id == conversation_id)
        .order_by(MessageV2.message_order.desc())
        .limit(1)
    ).first()
    if previous is None:
        raise C09ContractError("ERROR", "CONVERSATION_CONTEXT_MISSING")
    last_message, last_context = previous
    if not _related(session, tenant_id, last_context, resolved):
        raise C09ContractError("CONFLICT", "UNRELATED_TARGET_NEW_CONVERSATION_REQUIRED")
    same_target = (
        last_context.page_type == resolved.target_type
        and _context_entity(last_context) == resolved.entity_id
    )
    revision = last_context.context_revision if same_target else last_context.context_revision + 1
    try:
        _append(
            session,
            conversation=row,
            target=resolved,
            intent=intent,
            order=last_message.message_order + 1,
            revision=revision,
        )
        row.updated_at = func.now()
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise C09ContractError("CONFLICT", "CONVERSATION_WRITE_CONFLICT") from exc
    return row


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
        entity_id = _context_entity(context)
        target_id = str(entity_id)
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
                "context": {
                    "context_revision": context.context_revision,
                    "target_type": context.page_type,
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
    return {
        "conversation_id": str(row.id),
        "conversation_status": row.conversation_status,
        "current_context_revision": messages[-1]["context"]["context_revision"] if messages else 0,
        "context": messages[-1]["context"] if messages else None,
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
    if not _ACTOR.fullmatch(actor_id):
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
