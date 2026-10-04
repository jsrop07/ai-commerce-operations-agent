"""Read-only V2 catalog API."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from backend.app.core.config import Environment
from backend.app.db.bootstrap_v2 import TENANT_ENVIRONMENT, TENANT_NAME, TENANT_STATUS
from backend.app.models_v2.tenant import TenantV2
from backend.app.services.catalog_v2_read import (
    CatalogProductFilters,
    count_catalog_products,
    get_catalog_summary,
    list_catalog_categories,
    list_catalog_products,
)
from contracts.api import ApiEnvelope

router = APIRouter(
    prefix="/api/v1/catalog",
    tags=["catalog-v2"],
)


class CatalogSummaryData(BaseModel):
    product_count: int
    category_count: int
    product_category_count: int
    source: Literal["commerce_ops_v2"]
    source_as_of: None


class CatalogCategoryData(BaseModel):
    cafe24_category_no: int
    category_name: str


class CatalogHierarchyCategoryData(CatalogCategoryData):
    id: str
    category_depth: int
    parent_category_id: str | None


class CatalogProductData(BaseModel):
    id: str
    cafe24_product_no: int
    product_name: str
    product_code: str
    custom_product_code: str | None
    sale_price: str | None
    display_status: str
    selling_status: str
    sold_out: bool
    operational: bool
    category_nos: list[int]
    categories: list[CatalogCategoryData]


class CatalogProductsPage(BaseModel):
    items: list[CatalogProductData]
    total: int
    limit: int
    offset: int
    source_as_of: None


def _require_v2_runtime(
    request: Request,
):
    if request.app.state.settings.environment not in {
        Environment.LOCAL,
        Environment.TEST,
    }:
        raise HTTPException(status_code=403, detail="V2_CATALOG_ENVIRONMENT_FORBIDDEN")

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


def _require_catalog_tenant(session, tenant_id) -> None:
    tenant = session.get(TenantV2, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=503, detail="V2_TENANT_NOT_FOUND")
    if (
        tenant.name != TENANT_NAME
        or tenant.environment != TENANT_ENVIRONMENT
        or tenant.status != TENANT_STATUS
    ):
        raise HTTPException(status_code=403, detail="V2_TENANT_FORBIDDEN")


def _decimal_value(
    value: Decimal | None,
) -> str | None:
    if value is None:
        return None

    return str(value)


@router.get(
    "/summary",
    response_model=ApiEnvelope[CatalogSummaryData],
)
def catalog_summary(
    request: Request,
) -> ApiEnvelope[CatalogSummaryData]:
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
        _require_catalog_tenant(session, tenant_id)
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
            "source_as_of": None,
        },
        evidence_ids=[],
        warnings=[],
        as_of=datetime.now(UTC),
    )


@router.get(
    "/categories",
    response_model=ApiEnvelope[list[CatalogHierarchyCategoryData]],
)
def catalog_categories(
    request: Request,
    depth: int = Query(..., ge=1, le=3),
    parent_category_id: UUID | None = None,
) -> ApiEnvelope[list[CatalogHierarchyCategoryData]]:
    if (depth == 1 and parent_category_id is not None) or (depth > 1 and parent_category_id is None):
        raise HTTPException(status_code=422, detail="INVALID_CATEGORY_PARENT")

    session_factory, tenant_id = _require_v2_runtime(request)
    with session_factory() as session:
        _require_catalog_tenant(session, tenant_id)
        categories = list_catalog_categories(
            session,
            tenant_id=tenant_id,
            depth=depth,
            parent_category_id=parent_category_id,
        )

    return ApiEnvelope(
        tenant_id=str(tenant_id),
        request_id=request.headers.get("x-request-id", f"req_{uuid4().hex}"),
        trace_id=request.headers.get("x-trace-id", f"tr_{uuid4().hex}"),
        data=[{
            "id": str(category.id),
            "cafe24_category_no": category.cafe24_category_no,
            "category_name": category.category_name,
            "category_depth": category.category_depth,
            "parent_category_id": str(category.parent_category_id) if category.parent_category_id else None,
        } for category in categories],
        evidence_ids=[],
        warnings=[],
        as_of=datetime.now(UTC),
    )


@router.get(
    "/products",
    response_model=ApiEnvelope[CatalogProductsPage],
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
    q: str | None = Query(default=None, min_length=1, max_length=255),
    display_status: Literal["T", "F"] | None = None,
    selling_status: Literal["T", "F"] | None = None,
    sold_out: bool | None = None,
    price_min: Decimal | None = Query(default=None, ge=0),
    price_max: Decimal | None = Query(default=None, ge=0),
    product_no_min: int | None = Query(default=None, ge=0),
    product_no_max: int | None = Query(default=None, ge=0),
    category_no: int | None = Query(default=None, ge=0),
    sort_by: Literal["cafe24_product_no", "sale_price"] = "cafe24_product_no",
    sort_dir: Literal["asc", "desc"] = "desc",
) -> ApiEnvelope[CatalogProductsPage]:
    if price_min is not None and price_max is not None and price_min > price_max:
        raise HTTPException(status_code=422, detail="PRICE_MIN_GREATER_THAN_MAX")
    if product_no_min is not None and product_no_max is not None and product_no_min > product_no_max:
        raise HTTPException(status_code=422, detail="PRODUCT_NO_MIN_GREATER_THAN_MAX")
    if q is not None:
        q = q.strip()
        if not q:
            raise HTTPException(status_code=422, detail="SEARCH_QUERY_EMPTY")

    filters = CatalogProductFilters(
        q=q,
        display_status=display_status,
        selling_status=selling_status,
        sold_out=sold_out,
        price_min=price_min,
        price_max=price_max,
        product_no_min=product_no_min,
        product_no_max=product_no_max,
        category_no=category_no,
    )
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
        _require_catalog_tenant(session, tenant_id)
        total = count_catalog_products(session, tenant_id=tenant_id, filters=filters)
        products = list_catalog_products(
            session,
            tenant_id=tenant_id,
            limit=limit,
            offset=offset,
            filters=filters,
            sort_by=sort_by,
            sort_dir=sort_dir,
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
            "categories": [
                {
                    "cafe24_category_no": category.cafe24_category_no,
                    "category_name": category.category_name,
                }
                for category in product.categories
            ],
        }
        for product in products
    ]

    return ApiEnvelope(
        tenant_id=str(tenant_id),
        request_id=request_id,
        trace_id=trace_id,
        data={
            "items": data,
            "total": total,
            "limit": limit,
            "offset": offset,
            "source_as_of": None,
        },
        evidence_ids=[],
        warnings=[],
        as_of=datetime.now(UTC),
    )
