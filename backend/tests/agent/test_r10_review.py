"""R10 Backend review seam tests using a fixed SYNTHETIC start fixture."""

from __future__ import annotations

from copy import deepcopy

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from ai.agents.reservation_replan_graph import TASK_TYPE, AgentState
from backend.app.core.config import Environment, Settings
from backend.app.db.session import build_engine
from backend.app.main import create_app
from backend.app.models.agent import AgentRun
from backend.app.services.agent_run_repository import get_agent_run
from backend.app.services.agent_workflow_runtime import (
    AgentWorkflowSafetyViolation,
    run_and_checkpoint_reservation_replan,
)

WORKFLOW_ID = "r10-synthetic"
THREAD_ID = "fixed-thread"
TENANT_ID = "test_tenant"
REVIEW_URL = f"/api/v1/workflows/{WORKFLOW_ID}/threads/{THREAD_ID}/review"
STATE_URL = f"/api/v1/workflows/{WORKFLOW_ID}/threads/{THREAD_ID}/state"


def _state() -> AgentState:
    return AgentState(
        workflow_id=WORKFLOW_ID, thread_id=THREAD_ID, tenant_id=TENANT_ID,
        schema_version="agent-state.v0.1", current_node="", status="RUNNING",
        task_type=TASK_TYPE,
        entities={"data_mode": "SYNTHETIC", "source": "R10_FIXED_FIXTURE"},
        evidence_ids=["ev_synthetic_r10"],
        rule_results={"replan_required": True, "requires_ai_assist": False,
                      "incoming_delay_days": 3},
        proposed_actions=[], transition_history=[], provider_write_count=0,
    )


def _runtime(tmp_path, *, actor="operator_a", tenant=TENANT_ID, environment=Environment.TEST):
    url = f"sqlite:///{tmp_path / 'r10.sqlite'}"
    engine = build_engine(url)
    AgentRun.__table__.create(engine, checkfirst=True)
    settings = Settings(
        database_url=url, tenant_id=tenant, c09_dev_actor_id=actor,
        environment=environment,
    )
    return engine, TestClient(create_app(settings, db_engine=engine))


def _seed(engine):
    original = _state()
    frozen = deepcopy(original)
    with Session(engine) as session:
        result = run_and_checkpoint_reservation_replan(session, initial_state=original)
        # Simulate a persisted owner field. No authoritative start binding exists yet.
        row = get_agent_run(session, tenant_id=TENANT_ID, workflow_id=WORKFLOW_ID,
                            thread_id=THREAD_ID)
        stored = deepcopy(row.state)
        stored["owner_actor_id"] = "operator_a"
        row.state = stored
        session.commit()
    assert original == frozen
    assert result["status"] == "WAITING"
    assert result["provider_write_count"] == 0
    return frozen


def _row(engine):
    with Session(engine) as session:
        row = get_agent_run(session, tenant_id=TENANT_ID, workflow_id=WORKFLOW_ID,
                            thread_id=THREAD_ID)
        assert row is not None
        return row.status, row.checkpoint_version, deepcopy(row.state)


def _request(decision="APPROVE", key="review-1", version=1, **extra):
    return {
        "decision": decision, "expected_checkpoint_version": version,
        "idempotency_key": key, **extra,
    }


class RecordingAIResume:
    """Contract fake; its status is arbitrary and is not an AI graph assertion."""

    def __init__(self, *, status="RUNNING", mutate=None):
        self.calls = []
        self.status = status
        self.mutate = mutate

    def __call__(self, **kwargs):
        self.calls.append(deepcopy(kwargs))
        result = deepcopy(kwargs["persisted_state"])
        result.update({
            "status": self.status, "current_node": "fake_ai_handoff_result",
            "reason": "FAKE_AI_RESULT_FOR_BACKEND_TEST", "provider_write_count": 0,
        })
        if self.mutate:
            self.mutate(result)
        return result


def test_sqlite_persistence_restart_and_missing_ai_handoff(tmp_path):
    engine, _ = _runtime(tmp_path)
    _seed(engine)
    engine.dispose()
    # SQLITE_PERSISTENCE_RESTART_TEST: fresh engine, app, client and session.
    engine, client = _runtime(tmp_path)
    state = client.get(STATE_URL)
    assert state.status_code == 200
    assert state.json()["status"] == "WAITING"
    assert state.json()["checkpoint_version"] == 1
    missing_ai = client.post(REVIEW_URL, json=_request())
    assert missing_ai.status_code == 503
    assert missing_ai.json()["detail"] == "AI_HANDOFF_REQUIRED"
    assert _row(engine)[0:2] == ("WAITING", 1)
    fake = RecordingAIResume()
    client.app.state.agent_resume_callable = fake
    response = client.post(REVIEW_URL, json=_request())
    assert response.status_code == 200
    assert response.json()["status"] == "RUNNING"
    assert response.json()["checkpoint_version"] == 2
    assert len(fake.calls) == 1
    engine.dispose()


def test_approve_calls_ai_seam_once_with_identity_and_replay_zero_effect(tmp_path):
    engine, client = _runtime(tmp_path)
    original = _seed(engine)
    fake = RecordingAIResume()
    client.app.state.agent_resume_callable = fake
    assert client.post(REVIEW_URL, json=_request(version=9)).status_code == 409
    assert len(fake.calls) == 0
    assert _row(engine)[1] == 1
    first = client.post(REVIEW_URL, json=_request())
    assert first.status_code == 200
    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert (call["workflow_id"], call["thread_id"], call["tenant_id"],
            call["checkpoint_version"]) == (WORKFLOW_ID, THREAD_ID, TENANT_ID, 1)
    assert call["decision"] == "APPROVE"
    assert call["persisted_state"]["rule_results"] == original["rule_results"]
    assert client.post(REVIEW_URL, json=_request()).json()["checkpoint_version"] == 2
    assert len(fake.calls) == 1
    assert client.post(REVIEW_URL, json=_request("REJECT")).status_code == 409
    assert client.post(REVIEW_URL, json=_request(key="new", version=2)).status_code == 409
    assert _row(engine)[1] == 2
    engine.dispose()


def test_edit_passes_separate_reviewed_proposal_and_preserves_original(tmp_path):
    engine, client = _runtime(tmp_path)
    original = _seed(engine)
    fake = RecordingAIResume()
    client.app.state.agent_resume_callable = fake
    edit = _request("EDIT", review_override={"proposed_delay_days": 5})
    response = client.post(REVIEW_URL, json=edit)
    assert response.status_code == 200
    assert len(fake.calls) == 1
    assert fake.calls[0]["reviewed_proposal"]["review_override"] == {
        "proposed_delay_days": 5,
    }
    assert fake.calls[0]["persisted_state"]["rule_results"] == original["rule_results"]
    _, version, state = _row(engine)
    assert version == 2
    assert state["reviewed_proposal"]["review_override"] == {"proposed_delay_days": 5}
    assert state["rule_results"] == original["rule_results"]
    assert state["entities"] == original["entities"]
    assert state["proposed_actions"][0]["rule_results"] == original["rule_results"]
    assert client.post(REVIEW_URL, json=edit).json()["checkpoint_version"] == 2
    assert len(fake.calls) == 1
    engine.dispose()


def test_reject_is_backend_terminal_and_does_not_call_ai(tmp_path):
    engine, client = _runtime(tmp_path)
    _seed(engine)
    fake = RecordingAIResume()
    client.app.state.agent_resume_callable = fake
    rejected = client.post(REVIEW_URL, json=_request("REJECT"))
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "BLOCKED"
    status, version, state = _row(engine)
    assert (status, version, state["next_allowed_nodes"]) == ("BLOCKED", 2, [])
    assert len(fake.calls) == 0
    assert client.post(REVIEW_URL, json=_request("REJECT")).json()["checkpoint_version"] == 2
    assert client.post(REVIEW_URL, json=_request(key="again", version=2)).status_code == 409
    engine.dispose()


def test_validation_isolation_and_unsafe_checkpoint(tmp_path):
    engine, client = _runtime(tmp_path)
    assert client.post(REVIEW_URL, json=_request()).status_code == 404
    _seed(engine)
    fake = RecordingAIResume()
    client.app.state.agent_resume_callable = fake
    assert client.post(REVIEW_URL, json=_request("EDIT")).status_code == 422
    assert client.post(REVIEW_URL, json=_request(
        "APPROVE", review_override={"proposed_delay_days": 5},
    )).status_code == 422
    assert client.post(REVIEW_URL, json=_request(version=0)).status_code == 422
    assert len(fake.calls) == 0
    _, other_actor = _runtime(tmp_path, actor="operator_b")
    assert other_actor.get(STATE_URL).status_code == 404
    assert other_actor.post(REVIEW_URL, json=_request()).status_code == 404
    _, other_tenant = _runtime(tmp_path, tenant="other_tenant")
    assert other_tenant.post(REVIEW_URL, json=_request()).status_code == 404
    # Removing the test-supplied JSON owner demonstrates OWNER_BINDING_OPEN.
    with Session(engine) as session:
        row = get_agent_run(session, tenant_id=TENANT_ID, workflow_id=WORKFLOW_ID,
                            thread_id=THREAD_ID)
        no_owner = deepcopy(row.state)
        del no_owner["owner_actor_id"]
        row.state = no_owner
        session.commit()
    assert client.post(REVIEW_URL, json=_request()).status_code == 404
    with Session(engine) as session:
        row = get_agent_run(session, tenant_id=TENANT_ID, workflow_id=WORKFLOW_ID,
                            thread_id=THREAD_ID)
        state = deepcopy(row.state)
        state["owner_actor_id"] = "operator_a"
        state["proposed_actions"][0]["external_write"] = True
        row.state = state
        session.commit()
    assert client.post(REVIEW_URL, json=_request()).status_code == 422
    assert len(fake.calls) == 0
    assert _row(engine)[1] == 1
    engine.dispose()


@pytest.mark.parametrize("terminal_status", ["BLOCKED", "FAILED", "COMPLETED"])
def test_terminal_status_cannot_resume(tmp_path, terminal_status):
    engine, client = _runtime(tmp_path)
    _seed(engine)
    fake = RecordingAIResume()
    client.app.state.agent_resume_callable = fake
    with Session(engine) as session:
        row = get_agent_run(session, tenant_id=TENANT_ID, workflow_id=WORKFLOW_ID,
                            thread_id=THREAD_ID)
        row.status = terminal_status
        session.commit()
    assert client.post(REVIEW_URL, json=_request()).status_code == 409
    assert len(fake.calls) == 0
    engine.dispose()


def test_ai_contract_and_storage_failure_cannot_claim_success(tmp_path, monkeypatch):
    engine, client = _runtime(tmp_path)
    unsafe = _state()
    unsafe["provider_write_count"] = 1
    with Session(engine) as session, pytest.raises(AgentWorkflowSafetyViolation):
        run_and_checkpoint_reservation_replan(session, initial_state=unsafe)
    _seed(engine)
    client.app.state.agent_resume_callable = RecordingAIResume(
        mutate=lambda state: state.update(provider_write_count=1)
    )
    assert client.post(REVIEW_URL, json=_request()).status_code == 422
    assert _row(engine)[1] == 1
    client.app.state.agent_resume_callable = RecordingAIResume(
        mutate=lambda state: state["rule_results"].update(incoming_delay_days=99)
    )
    assert client.post(REVIEW_URL, json=_request()).status_code == 503
    assert _row(engine)[1] == 1
    client.app.state.agent_resume_callable = RecordingAIResume()

    def fail_save(*args, **kwargs):
        raise RuntimeError("storage unavailable")

    monkeypatch.setattr(
        "backend.app.services.agent_workflow_runtime.save_agent_checkpoint", fail_save
    )
    with pytest.raises(RuntimeError, match="storage unavailable"):
        client.post(REVIEW_URL, json=_request())
    assert _row(engine)[0:2] == ("WAITING", 1)
    engine.dispose()


def test_trusted_actor_and_environment_gates(tmp_path):
    engine, _ = _runtime(tmp_path)
    _seed(engine)
    url = f"sqlite:///{tmp_path / 'r10.sqlite'}"
    no_actor = TestClient(create_app(Settings(database_url=url, tenant_id=TENANT_ID),
                                     db_engine=engine))
    assert no_actor.post(REVIEW_URL, json=_request()).status_code == 403
    production = TestClient(create_app(Settings(
        database_url=url, tenant_id=TENANT_ID, environment=Environment.PRODUCTION_READ,
    ), db_engine=engine))
    assert production.post(REVIEW_URL, json=_request()).status_code == 403
    engine.dispose()
