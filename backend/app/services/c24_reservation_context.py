from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models_v2.catalog import (
    ProductVariantV2,
)
from backend.app.services.reservation_projection import (
    ReservationRiskProjection,
)


class ReservationContextError(RuntimeError):
    pass


def resolve_product_reservation_projection(
    session: Session,
    *,
    tenant_id: UUID,
    product_id: UUID,
    projections: Sequence[
        ReservationRiskProjection
    ],
    projection_tenant_id: str,
) -> ReservationRiskProjection | None:
    """PRODUCT의 variant_code와 예약위험 sku_id를 안전하게 연결한다."""

    variant_codes = tuple(
        code
        for code in session.scalars(
            select(
                ProductVariantV2.variant_code
            ).where(
                ProductVariantV2.tenant_id
                == tenant_id,
                ProductVariantV2.product_id
                == product_id,
                ProductVariantV2.variant_code
                .is_not(None),
            )
        ).all()
        if code
    )

    if not variant_codes:
        return None

    allowed_skus = set(
        variant_codes
    )

    matches = [
        item
        for item in projections
        if (
            item.tenant_id
            == projection_tenant_id
            and item.sku_id in allowed_skus
        )
    ]

    if not matches:
        return None

    if len(matches) != 1:
        raise ReservationContextError(
            "C24_RESERVATION_CONTEXT_AMBIGUOUS"
        )

    projection = matches[0]

    if (
        projection.data_mode
        != "SYNTHETIC_DEMO"
        or projection.source_classification
        != "SYNTHETIC_DEMO"
    ):
        raise ReservationContextError(
            "C24_RESERVATION_CONTEXT_BLOCKED"
        )

    return projection