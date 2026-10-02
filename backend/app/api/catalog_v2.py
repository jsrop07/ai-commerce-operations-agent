"""Read-only V2 catalog API."""

from __future__ import annotations
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request

from contracts.api import ApiEnvelope

from backend.app.services.catalog_v2_read import (
    get_catalog_summary,
    list_catalog_products,
)


router = APIRouter(
    prefix="/api/v1/catalog",
    tags=["catalog-v2"],
)


def _require_v2_runtime(
    request: Request,
):
    session_factory = getattr(
        request.app.state,
        "v2_db_session_factory",
        None,
    )

    tenant_id = getattr(
        request.app.state.settings,
        "v2_tenant_id",
        None,
    )

    if session_factory is None:
        raise HTTPException(
            status_code=503,
            detail="V2_DATABASE_NOT_CONFIGURED",
        )

    if tenant_id is None:
        raise HTTPException(
            status_code=503,
            detail="V2_TENANT_NOT_CONFIGURED",
        )

    return session_factory, tenant_id


def _decimal_value(
    value: Decimal | None,
) -> str | None:
    if value is None:
        return None

    return str(value)


@router.get(
    "/summary",
    response_model=ApiEnvelope[dict[str, Any]],
)
def catalog_summary(
    request: Request,
) -> ApiEnvelope[dict[str, Any]]:
    request_id = request.headers.get(
        "x-request-id",
        f"req_{uuid4().hex}",
    )
    trace_id = request.headers.get(
        "x-trace-id",
        f"tr_{uuid4().hex}",
    )

    session_factory, tenant_id = (
        _require_v2_runtime(request)
    )

    with session_factory() as session:
        summary = get_catalog_summary(
            session,
            tenant_id=tenant_id,
        )

    return ApiEnvelope(
        tenant_id=str(tenant_id),
        request_id=request_id,
        trace_id=trace_id,
        data={
            "product_count": summary.product_count,
            "category_count": summary.category_count,
            "product_category_count": (
                summary.product_category_count
            ),
            "source": "commerce_ops_v2",
        },
        evidence_ids=[],
        warnings=[],
        as_of=datetime.now(UTC),
    )


@router.get(
    "/products",
    response_model=ApiEnvelope[list[dict[str, Any]]],
)
def catalog_products(
    request: Request,
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
) -> ApiEnvelope[list[dict[str, Any]]]:
    request_id = request.headers.get(
        "x-request-id",
        f"req_{uuid4().hex}",
    )
    trace_id = request.headers.get(
        "x-trace-id",
        f"tr_{uuid4().hex}",
    )

    session_factory, tenant_id = (
        _require_v2_runtime(request)
    )

    with session_factory() as session:
        products = list_catalog_products(
            session,
            tenant_id=tenant_id,
            limit=limit,
            offset=offset,
        )

    data = [
        {
            "id": str(product.id),
            "cafe24_product_no": (
                product.cafe24_product_no
            ),
            "product_name": product.product_name,
            "product_code": product.product_code,
            "custom_product_code": (
                product.custom_product_code
            ),
            "sale_price": _decimal_value(
                product.sale_price
            ),
            "display_status": product.display_status,
            "selling_status": product.selling_status,
            "sold_out": product.sold_out,
            "operational": product.operational,
            "category_nos": list(
                product.category_nos
            ),
        }
        for product in products
    ]

    return ApiEnvelope(
        tenant_id=str(tenant_id),
        request_id=request_id,
        trace_id=trace_id,
        data=data,
        evidence_ids=[],
        warnings=[],
        as_of=datetime.now(UTC),
    )