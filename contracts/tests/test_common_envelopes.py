from datetime import UTC, datetime

from contracts.api import ApiEnvelope, ApiError, ErrorBody


def test_common_success_and_error_contracts() -> None:
    success = ApiEnvelope(
        tenant_id="demo_store",
        request_id="req_1",
        trace_id="tr_1",
        data={"ok": True},
        as_of=datetime.now(UTC),
    )
    error = ApiError(
        error=ErrorBody(code="POLICY_DENIED", message="denied", retryable=False),
        request_id="req_1",
        trace_id="tr_1",
    )
    assert success.schema_version == "1.0"
    assert error.error.code == "POLICY_DENIED"
