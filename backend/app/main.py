"""FastAPI application factory."""

from threading import Lock
from backend.app.api.orders_summary import router as orders_summary_router
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from backend.app.api.c04 import router as c04_router
from backend.app.api.cafe24_bootstrap import (
    router as cafe24_bootstrap_router,
)
from backend.app.api.cafe24_oauth import router as cafe24_oauth_router
from backend.app.api.cafe24_smoke import router as cafe24_smoke_router
from backend.app.api.catalog_v2 import (
    router as catalog_v2_router,
)
from backend.app.api.conversations_v2 import router as conversations_v2_router
from backend.app.api.demo import router as demo_router
from backend.app.api.inventory import router as inventory_router
from backend.app.api.mappings import router as mappings_router
from backend.app.api.meta import router as meta_router
from backend.app.api.reservations import (
    router as reservations_router,
)
from backend.app.api.retrieval import router as retrieval_router
from backend.app.api.schedule import router as schedule_router
from backend.app.api.workflows import (
    router as workflows_router,
)
from backend.app.core.config import Environment, Settings, get_settings
from backend.app.core.observability import (
    RedactCafe24OAuthQueryMiddleware,
    configure_logging,
)
from backend.app.db.session import build_engine
from backend.app.db.session_v2 import (
    build_v2_engine,
    build_v2_session_factory,
)
from backend.app.services.c04_lookup import C04LookupService
from backend.app.services.corpus_restore import restore_corpus
from backend.app.services.demo_session import COOKIE_NAME, resolve_demo_session
from backend.app.services.ingestion.mapping_queue import MappingReviewQueue
from backend.app.services.offline_sale import OfflineSalePipeline
from backend.app.services.reservation_tasks import ReservationTaskService
from backend.app.services.retrieval_runtime import RetrievalRuntime


def create_app(
    settings: Settings | None = None,
    *,
    db_engine: Engine | None = None,
    v2_db_engine: Engine | None = None,
    c04_lookup_service: C04LookupService | None = None,
) -> FastAPI:
    resolved = settings or get_settings()
    configure_logging(resolved.log_level)
    application = FastAPI( title="AI Commerce Operations Agent", version="0.1.0",)
    if resolved.environment in {Environment.LOCAL, Environment.TEST} and resolved.c09_dev_actor_id:
        @application.middleware("http")
        async def c09_development_actor(request: Request, call_next):
            request.scope["c09_trusted_actor_id"] = resolved.c09_dev_actor_id
            return await call_next(request)

    if resolved.environment == Environment.DEMO:
        @application.middleware("http")
        async def c09_demo_session_actor(request: Request, call_next):
            if (request.url.path.startswith("/api/v1/conversations")
                    or request.url.path == "/api/v1/retrieval/explanations"):
                factory = request.app.state.v2_db_session_factory
                tenant_id = resolved.v2_tenant_id
                if factory is not None and tenant_id is not None:
                    with factory() as db:
                        row = resolve_demo_session(
                            db, tenant_id=tenant_id,
                            token=request.cookies.get(COOKIE_NAME), touch=True,
                        )
                        if row is not None:
                            request.scope["c09_trusted_actor_id"] = row.actor_id
                            request.scope["c22_demo_session_id"] = row.id
            return await call_next(request)

    application.add_middleware(RedactCafe24OAuthQueryMiddleware,)
    # 로컬 Frontend Actual Browser E2E용 CORS.
    # Production Write 허용과는 무관하며 HTTP GET 접근만 허용한다.
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:55174",
            "http://127.0.0.1:55174",
        ],
        allow_credentials=False,
        allow_methods=[
            "GET",
            "POST",
        ],
        allow_headers=[
            "Content-Type",
            "X-Request-ID",
        ],
    )
    application.state.settings = resolved
    application.state.c04_corpus_restore = None
    if c04_lookup_service is None:
        restored = restore_corpus(
            tenant_id=resolved.tenant_id, environment=resolved.environment.value,
        )
        application.state.c04_corpus_restore = restored
        application.state.c04_lookup_service = restored.lookup_service
    else:
        application.state.c04_lookup_service = c04_lookup_service
    application.state.retrieval_runtime = RetrievalRuntime(
        corpus=application.state.c04_corpus_restore, tenant_id=resolved.tenant_id,
        method=resolved.retrieval_method, timeout_seconds=resolved.retrieval_timeout_seconds,
    )
    # Public DEMO reads V2 only. Never construct a legacy/Actual DB engine
    # from DATABASE_URL in that runtime; injected engines remain for tests.
    if db_engine is not None:
        application.state.db_engine = db_engine
    elif resolved.environment == Environment.DEMO:
        # Existing isolated SQLite Demo tests may use the legacy fixture schema.
        # Public DEMO's PostgreSQL DATABASE_URL must never be opened.
        application.state.db_engine = (
            build_engine(resolved.database_url)
            if resolved.database_url.startswith("sqlite") else None
        )
    else:
        application.state.db_engine = build_engine(resolved.database_url)
    application.state.db_session_factory = (
        sessionmaker(
            bind=application.state.db_engine,
            expire_on_commit=False,
        )
        if resolved.environment == Environment.DEMO
        and application.state.db_engine is not None
        else None
    )
    application.state.v2_db_engine = None
    application.state.v2_db_session_factory = None
    application.state.product_search_service = None
    application.state.neo4j_driver = None

    if v2_db_engine is not None:
        application.state.v2_db_engine = v2_db_engine
        application.state.v2_db_session_factory = (
            build_v2_session_factory(v2_db_engine)
        )
    elif resolved.postgres_v2_url:
        application.state.v2_db_engine = build_v2_engine(
            resolved.postgres_v2_url
        )
        application.state.v2_db_session_factory = (
            build_v2_session_factory(
                application.state.v2_db_engine
            )
        )
    if (
        application.state.v2_db_session_factory is not None
        and resolved.environment in {
            Environment.LOCAL,
            Environment.DEMO,
        }
    ):
        from backend.app.services.c18_product_search import ProductSearchService
        application.state.product_search_service = (
            ProductSearchService()
        )
    if (
        resolved.environment in {
            Environment.LOCAL,
            Environment.DEMO,
        }
        and resolved.neo4j_uri
        and resolved.neo4j_user
        and resolved.neo4j_password is not None
        and resolved.neo4j_password.get_secret_value()
    ):
        from neo4j import GraphDatabase

        application.state.neo4j_driver = GraphDatabase.driver(
            resolved.neo4j_uri,
            auth=(
                resolved.neo4j_user,
                resolved.neo4j_password.get_secret_value(),
            ),
        )
    application.state.pipeline = OfflineSalePipeline(
        db_session_factory=application.state.db_session_factory
    )
    application.state.inventory_projections = (
        application.state.pipeline.inventory_projections
    )
    application.state.reservation_risk_projections = []
    application.state.reservation_demo_prepare_lock = Lock()
    application.state.reservation_task_service = ReservationTaskService()
    application.state.mapping_queue = MappingReviewQueue()
    application.state.schedule_launch_event_projections = []
    application.state.schedule_task_projections = []
    application.state.schedule_dependency_projections = []
    application.state.schedule_delay_impact_projections = []
    application.state.schedule_replan_proposals = []

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
    application.include_router(c04_router)
    application.include_router(retrieval_router)
    application.include_router(demo_router)
    application.include_router(cafe24_oauth_router)
    application.include_router(cafe24_smoke_router)
    application.include_router(inventory_router)
    application.include_router(mappings_router)
    application.include_router(cafe24_bootstrap_router)
    application.include_router(reservations_router)
    application.include_router(schedule_router)
    application.include_router(workflows_router)
    application.include_router(catalog_v2_router)
    application.include_router(conversations_v2_router)
    application.include_router(orders_summary_router)
    
    @application.on_event("shutdown")
    def close_neo4j_driver() -> None:
        driver = application.state.neo4j_driver
        if driver is not None:
            driver.close()

    return application


app = create_app()
