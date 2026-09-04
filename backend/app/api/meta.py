"""Health, readiness, and non-sensitive runtime metadata."""

from fastapi import APIRouter, Request

from backend.app.core.config import Settings
from contracts.events import EVENT_SCHEMA_VERSION

router = APIRouter(prefix="/api/v1", tags=["meta"])


def _settings(request: Request) -> Settings:
    return request.app.state.settings


@router.get("/health")
def health(request: Request) -> dict[str, object]:
    settings = _settings(request)
    return {
        "status": "ok",
        "environment": settings.environment,
        "contract_version": EVENT_SCHEMA_VERSION,
        "write_mode": settings.write_mode,
        "global_write_kill": settings.global_write_kill,
    }


@router.get("/ready")
def ready(request: Request) -> dict[str, object]:
    settings = _settings(request)
    return {"status": "ready", "environment": settings.environment}


@router.get("/meta")
def meta(request: Request) -> dict[str, object]:
    settings = _settings(request)
    return {
        "service": "ai-commerce-operations-agent",
        "environment": settings.environment,
        "schema_version": EVENT_SCHEMA_VERSION,
        "write_mode": settings.write_mode,
        "global_write_kill": settings.global_write_kill,
    }
