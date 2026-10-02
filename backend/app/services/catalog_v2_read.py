"""Read-only commerce_ops V2 catalog service."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models_v2.catalog import (
    CategoryV2,
    ProductCategoryV2,
    ProductV2,
)


@dataclass(frozen=True)
class CatalogV2Summary:
    product_count: int
    category_count: int
    product_category_count: int


@dataclass(frozen=True)
class CatalogV2Product:
    id: uuid.UUID
    cafe24_product_no: int
    product_name: str
    product_code: str
    custom_product_code: str | None
    sale_price: Decimal | None
    display_status: str
    selling_status: str
    sold_out: bool
    operational: bool
    category_nos: tuple[int, ...]


def get_catalog_summary(
    session: Session,
    *,
    tenant_id: uuid.UUID,
) -> CatalogV2Summary:
    product_count = session.scalar(
        select(func.count())
        .select_from(ProductV2)
        .where(ProductV2.tenant_id == tenant_id)
    )

    category_count = session.scalar(
        select(func.count())
        .select_from(CategoryV2)
        .where(CategoryV2.tenant_id == tenant_id)
    )

    relation_count = session.scalar(
        select(func.count())
        .select_from(ProductCategoryV2)
        .where(ProductCategoryV2.tenant_id == tenant_id)
    )

    return CatalogV2Summary(
        product_count=int(product_count or 0),
        category_count=int(category_count or 0),
        product_category_count=int(relation_count or 0),
    )


def list_catalog_products(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
) -> list[CatalogV2Product]:
    if limit < 1 or limit > 200:
        raise ValueError("limit must be between 1 and 200")

    if offset < 0:
        raise ValueError("offset must be >= 0")

    products = session.scalars(
        select(ProductV2)
        .where(ProductV2.tenant_id == tenant_id)
        .order_by(ProductV2.cafe24_product_no)
        .offset(offset)
        .limit(limit)
    ).all()

    if not products:
        return []

    product_ids = [product.id for product in products]

    relation_rows = session.execute(
        select(
            ProductCategoryV2.product_id,
            CategoryV2.cafe24_category_no,
        )
        .join(
            CategoryV2,
            (CategoryV2.tenant_id == ProductCategoryV2.tenant_id)
            & (CategoryV2.id == ProductCategoryV2.category_id),
        )
        .where(
            ProductCategoryV2.tenant_id == tenant_id,
            ProductCategoryV2.product_id.in_(product_ids),
        )
        .order_by(
            ProductCategoryV2.product_id,
            CategoryV2.cafe24_category_no,
        )
    ).all()

    category_nos_by_product: dict[
        uuid.UUID,
        list[int],
    ] = {}

    for product_id, category_no in relation_rows:
        category_nos_by_product.setdefault(
            product_id,
            [],
        ).append(int(category_no))

    return [
        CatalogV2Product(
            id=product.id,
            cafe24_product_no=int(product.cafe24_product_no),
            product_name=product.product_name,
            product_code=product.product_code,
            custom_product_code=product.custom_product_code,
            sale_price=product.sale_price,
            display_status=product.display_status,
            selling_status=product.selling_status,
            sold_out=product.sold_out,
            operational=product.operational,
            category_nos=tuple(
                category_nos_by_product.get(
                    product.id,
                    [],
                )
            ),
        )
        for product in products
    ]