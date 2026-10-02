"""Bootstrap the local V2 tenant safely."""

from __future__ import annotations

from sqlalchemy import select

from backend.app.core.config import get_settings
from backend.app.db.session_v2 import (
    build_v2_engine,
    build_v2_session_factory,
)
from backend.app.models_v2.tenant import TenantV2


TENANT_NAME = "commerce_ops_local"
TENANT_ENVIRONMENT = "LOCAL"
TENANT_STATUS = "ACTIVE"


def main() -> None:
    settings = get_settings()

    if not settings.postgres_v2_url:
        raise RuntimeError("POSTGRES_V2_URL is not configured")

    engine = build_v2_engine(settings.postgres_v2_url)
    session_factory = build_v2_session_factory(engine)

    try:
        with session_factory() as session:
            existing = session.scalars(
                select(TenantV2).where(
                    TenantV2.name == TENANT_NAME,
                    TenantV2.environment == TENANT_ENVIRONMENT,
                )
            ).all()

            if len(existing) > 1:
                raise RuntimeError(
                    "multiple V2 bootstrap tenants found"
                )

            if existing:
                tenant = existing[0]

                if tenant.status != TENANT_STATUS:
                    raise RuntimeError(
                        "existing V2 bootstrap tenant has unexpected status"
                    )

                print("TENANT_CREATED=False")
                print(f"TENANT_ID={tenant.id}")
                return

            tenant = TenantV2(
                name=TENANT_NAME,
                environment=TENANT_ENVIRONMENT,
                status=TENANT_STATUS,
            )

            session.add(tenant)
            session.commit()
            session.refresh(tenant)

            print("TENANT_CREATED=True")
            print(f"TENANT_ID={tenant.id}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()