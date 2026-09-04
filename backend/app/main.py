"""FastAPI application factory."""

from fastapi import FastAPI

from backend.app.api.demo import router as demo_router
from backend.app.api.meta import router as meta_router
from backend.app.core.config import Settings, get_settings
from backend.app.core.observability import configure_logging
from backend.app.services.offline_sale import OfflineSalePipeline


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    configure_logging(resolved.log_level)
    application = FastAPI(title="AI Commerce Operations Agent", version="0.1.0")
    application.state.settings = resolved
    application.state.pipeline = OfflineSalePipeline()
    application.include_router(meta_router)
    application.include_router(demo_router)
    return application


app = create_app()
