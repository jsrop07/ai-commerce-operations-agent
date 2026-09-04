import pytest

from backend.app.core.policies.write_policy import PolicyDenied, WriteAction
from backend.tests.safety.test_production_write_deny import build_gateway


@pytest.mark.parametrize("action", list(WriteAction))
def test_all_write_like_actions_stop_before_transport(action: WriteAction) -> None:
    gateway, audit, transport = build_gateway()
    with pytest.raises(PolicyDenied):
        gateway.execute(action, f"corr_{action}")
    assert transport.write_call_count == 0
    assert len(audit.events) == 1
