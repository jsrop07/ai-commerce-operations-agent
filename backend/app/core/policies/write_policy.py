"""NFR-SAFE-001 deny-before-transport policy."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from backend.app.core.config import Environment, Settings, WriteMode


class WriteAction(StrEnum):
    REFUND = "refund"
    CANCEL_ORDER = "cancel_order"
    CHANGE_PRICE = "change_price"
    CHANGE_INVENTORY = "change_inventory"
    CHANGE_CUSTOMER_PII = "change_customer_pii"


class PolicyDenied(RuntimeError):
    code = "POLICY_DENIED"


@dataclass(frozen=True)
class AuditEvent:
    action: str
    outcome: str
    reason: str
    tenant_id: str
    correlation_id: str
    policy: str = "NFR-SAFE-001"
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class AuditSink:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def append(self, event: AuditEvent) -> None:
        self.events.append(event)


class ExternalWritePolicy:
    def __init__(self, settings: Settings, audit: AuditSink) -> None:
        self.settings = settings
        self.audit = audit

    def authorize(self, action: WriteAction, correlation_id: str) -> None:
        denied = (
            self.settings.environment == Environment.PRODUCTION_READ
            or self.settings.write_mode == WriteMode.DISABLED
            or self.settings.global_write_kill
        )
        if denied:
            reason = "global_kill_or_read_only_environment"
            self.audit.append(
                AuditEvent(
                    action=action,
                    outcome="DENIED",
                    reason=reason,
                    tenant_id=self.settings.tenant_id,
                    correlation_id=correlation_id,
                )
            )
            raise PolicyDenied(f"{PolicyDenied.code}: {reason}")


class RecordingWriteTransport:
    """Fake transport called only after policy authorization."""

    def __init__(self) -> None:
        self.write_call_count = 0

    def execute(self, action: WriteAction) -> None:
        self.write_call_count += 1


class SafeWriteGateway:
    def __init__(self, policy: ExternalWritePolicy, transport: RecordingWriteTransport) -> None:
        self.policy = policy
        self.transport = transport

    def execute(self, action: WriteAction, correlation_id: str) -> None:
        self.policy.authorize(action, correlation_id)
        self.transport.execute(action)
