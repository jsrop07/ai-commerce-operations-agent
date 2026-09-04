from fastapi.testclient import TestClient

from backend.app.core.config import Environment, Settings, WriteMode
from backend.app.main import create_app


def test_health_ready_meta_production_read() -> None:
    settings = Settings(
        environment=Environment.PRODUCTION_READ,
        write_mode=WriteMode.DISABLED,
        global_write_kill=True,
    )
    client = TestClient(create_app(settings))
    assert client.get("/api/v1/health").json()["status"] == "ok"
    assert client.get("/api/v1/ready").json()["status"] == "ready"
    meta = client.get("/api/v1/meta").json()
    assert meta["environment"] == "PRODUCTION_READ"
    assert meta["write_mode"] == "disabled"
    assert meta["global_write_kill"] is True


def test_unsafe_production_configuration_rejected() -> None:
    try:
        Settings(
            environment=Environment.PRODUCTION_READ,
            write_mode=WriteMode.DEMO_ONLY,
            global_write_kill=False,
        )
    except ValueError as exc:
        assert "PRODUCTION_READ" in str(exc)
    else:
        raise AssertionError("unsafe production settings accepted")
