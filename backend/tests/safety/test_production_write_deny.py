import pytest

from backend.app.core.config import Environment, Settings, WriteMode
from backend.app.core.policies.write_policy import (
    AuditSink,
    ExternalWritePolicy,
    PolicyDenied,
    RecordingWriteTransport,
    SafeWriteGateway,
    WriteAction,
)


def build_gateway() -> tuple[SafeWriteGateway, AuditSink, RecordingWriteTransport]:
    settings = Settings(
        environment=Environment.PRODUCTION_READ,
        write_mode=WriteMode.DISABLED,
        global_write_kill=True,
    )
    audit = AuditSink()
    transport = RecordingWriteTransport()
    return SafeWriteGateway(ExternalWritePolicy(settings, audit), transport), audit, transport


def test_production_write_denied_before_transport() -> None:
    gateway, audit, transport = build_gateway()
    with pytest.raises(PolicyDenied, match="POLICY_DENIED"):
        gateway.execute(WriteAction.CHANGE_INVENTORY, "corr_safety_1")
    assert transport.write_call_count == 0
    assert len(audit.events) == 1
    assert audit.events[0].policy == "NFR-SAFE-001"
