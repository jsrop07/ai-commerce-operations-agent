from __future__ import annotations
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.main import create_app
from backend.app.models_v2.catalog import (
    ProductV2,
    ProductVariantV2,
)

DEMO_TENANT_ID = UUID(
    "35556e27-4200-4712-8ac5-e5a569a91c47"
)

def main() -> None:
    settings = Settings()
    engine = create_engine(
        settings.postgres_v2_url
    )

    with Session(engine) as db:
        product = db.scalar(
            select(ProductV2).where(
                ProductV2.tenant_id
                == DEMO_TENANT_ID,
                ProductV2.product_code
                == "DEMO-P-0009",
            )
        )

        if product is None:
            print("HERO_PRODUCT_NOT_FOUND")
            return

        print(
            "PRODUCT_ID=",
            product.id,
        )

        print(
            "PRODUCT_CODE=",
            product.product_code,
        )

        variants = db.scalars(
            select(ProductVariantV2).where(
                ProductVariantV2.tenant_id
                == DEMO_TENANT_ID,
                ProductVariantV2.product_id
                == product.id,
            )
        ).all()

        print("VARIANTS=")

        for variant in variants:
            print(
                variant.id,
                variant.variant_code,
                variant.option_name,
            )

    app = create_app()

    with TestClient(
        app,
        base_url="https://testserver",
    ):
        print(
            "RESERVATION_PROJECTIONS="
        )

        for projection in (
            app.state
            .reservation_risk_projections
        ):
            print(
                "reservation_id=",
                projection.reservation_id,
                "sku_id=",
                projection.sku_id,
                "required=",
                projection.required_qty,
                "secured=",
                projection.secured_qty,
                "confirmed=",
                projection.confirmed_incoming_qty,
                "shortage=",
                projection.shortage,
            )


if __name__ == "__main__":
    main()