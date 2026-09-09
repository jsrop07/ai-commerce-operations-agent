"""FastAPI application factory."""

from fastapi import FastAPI

from backend.app.api.cafe24_oauth import router as cafe24_oauth_router
from backend.app.api.cafe24_smoke import router as cafe24_smoke_router
from backend.app.api.demo import router as demo_router
from backend.app.api.inventory import router as inventory_router
from backend.app.api.mappings import router as mappings_router
from backend.app.api.meta import router as meta_router
from backend.app.core.config import Settings, get_settings
from backend.app.core.observability import (
    RedactCafe24OAuthQueryMiddleware,
    configure_logging,
)
from backend.app.services.ingestion.mapping_queue import MappingReviewQueue
from backend.app.services.offline_sale import OfflineSalePipeline
from backend.app.api.cafe24_bootstrap import (
    router as cafe24_bootstrap_router,
)

def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    configure_logging(resolved.log_level)
    application = FastAPI(title="AI Commerce Operations Agent", version="0.1.0")
    application.add_middleware(RedactCafe24OAuthQueryMiddleware)
    application.state.settings = resolved
    application.state.pipeline = OfflineSalePipeline()
    application.state.inventory_projections = []
    application.state.mapping_queue = MappingReviewQueue()

    application.state.cafe24_oauth_state = None
    application.state.cafe24_authorization_code = None
    application.state.cafe24_oauth_state_created_at = None

    application.state.cafe24_access_token = None
    application.state.cafe24_refresh_token = None
    application.state.cafe24_access_token_expires_at = None
    application.state.cafe24_refresh_token_expires_at = None

    application.state.cafe24_approved_scopes = []
    application.state.cafe24_authorized_mall_id = None
    application.state.cafe24_shop_no = None

    application.include_router(meta_router)
    application.include_router(demo_router)
    application.include_router(cafe24_oauth_router)
    application.include_router(cafe24_smoke_router)
    application.include_router(inventory_router)
    application.include_router(mappings_router)
    application.include_router(cafe24_bootstrap_router)

    return application


app = create_app()
