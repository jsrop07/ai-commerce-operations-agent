"""Read-only commerce_ops V2 catalog service."""

from __future__ import annotations

import uuid
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from sqlalchemy import String, cast, func, or_, select
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
class CatalogV2Category:
    cafe24_category_no: int
    category_name: str


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
    categories: tuple[CatalogV2Category, ...]


@dataclass(frozen=True)
class CatalogProductFilters:
    q: str | None = None
    display_status: str | None = None
    selling_status: str | None = None
    sold_out: bool | None = None
    price_min: Decimal | None = None
    price_max: Decimal | None = None
    product_no_min: int | None = None
    product_no_max: int | None = None
    category_no: int | None = None


def list_catalog_categories(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    depth: int,
    parent_category_id: uuid.UUID | None = None,
) -> list[CategoryV2]:
    conditions = [CategoryV2.tenant_id == tenant_id, CategoryV2.category_depth == depth]
    if depth == 1:
        conditions.append(CategoryV2.parent_category_id.is_(None))
    else:
        conditions.append(CategoryV2.parent_category_id == parent_category_id)
    return list(session.scalars(
        select(CategoryV2).where(*conditions).order_by(CategoryV2.cafe24_category_no)
    ).all())


def _descendant_category_ids(tenant_id: uuid.UUID, category_no: int):
    descendants = (
        select(CategoryV2.id)
        .where(CategoryV2.tenant_id == tenant_id,
               CategoryV2.cafe24_category_no == category_no)
        .cte("catalog_descendants", recursive=True)
    )
    child = CategoryV2.__table__.alias("catalog_child")
    descendants = descendants.union_all(
        select(child.c.id).where(
            child.c.tenant_id == tenant_id,
            child.c.parent_category_id == descendants.c.id,
        )
    )
    return select(descendants.c.id)


def _numeric_search_value(query: str) -> Decimal | None:
    if not re.fullmatch(r"[+-]?\d+(?:\.\d+)?", query):
        return None
    try:
        value = Decimal(query)
    except InvalidOperation:
        return None
    return value if value.is_finite() else None


def _product_conditions(tenant_id: uuid.UUID, filters: CatalogProductFilters):
    conditions = [ProductV2.tenant_id == tenant_id]
    if filters.display_status is not None:
        conditions.append(ProductV2.display_status == filters.display_status)
    if filters.selling_status is not None:
        conditions.append(ProductV2.selling_status == filters.selling_status)
    if filters.sold_out is not None:
        conditions.append(ProductV2.sold_out == filters.sold_out)
    if filters.price_min is not None:
        conditions.append(ProductV2.sale_price >= filters.price_min)
    if filters.price_max is not None:
        conditions.append(ProductV2.sale_price <= filters.price_max)
    if filters.product_no_min is not None:
        conditions.append(ProductV2.cafe24_product_no >= filters.product_no_min)
    if filters.product_no_max is not None:
        conditions.append(ProductV2.cafe24_product_no <= filters.product_no_max)
    if filters.category_no is not None:
        category_match = (
            select(ProductCategoryV2.product_id)
            .where(
                ProductCategoryV2.tenant_id == tenant_id,
                ProductCategoryV2.product_id == ProductV2.id,
                ProductCategoryV2.category_id.in_(
                    _descendant_category_ids(tenant_id, filters.category_no)
                ),
            )
            .exists()
        )
        conditions.append(category_match)

    if filters.q is not None:
        escaped = filters.q.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        category_match = (
            select(ProductCategoryV2.product_id)
            .join(
                CategoryV2,
                (CategoryV2.tenant_id == ProductCategoryV2.tenant_id)
                & (CategoryV2.id == ProductCategoryV2.category_id),
            )
            .where(
                ProductCategoryV2.tenant_id == tenant_id,
                ProductCategoryV2.product_id == ProductV2.id,
                or_(
                    cast(CategoryV2.cafe24_category_no, String).like(pattern, escape="\\"),
                    func.lower(CategoryV2.category_name).like(pattern, escape="\\"),
                ),
            )
            .exists()
        )
        text_matches = [
            func.lower(ProductV2.product_name).like(pattern, escape="\\"),
            func.lower(ProductV2.product_code).like(pattern, escape="\\"),
            func.lower(ProductV2.custom_product_code).like(pattern, escape="\\"),
            cast(ProductV2.cafe24_product_no, String).like(pattern, escape="\\"),
            category_match,
        ]
        numeric_value = _numeric_search_value(filters.q)
        if numeric_value is not None:
            text_matches.append(ProductV2.sale_price == numeric_value)
            if numeric_value == numeric_value.to_integral_value() and 0 <= numeric_value <= 9223372036854775807:
                text_matches.append(ProductV2.cafe24_product_no == int(numeric_value))
        conditions.append(or_(*text_matches))
    return conditions


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


def count_catalog_products(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    filters: CatalogProductFilters = CatalogProductFilters(),
) -> int:
    return int(session.scalar(
        select(func.count())
        .select_from(ProductV2)
        .where(*_product_conditions(tenant_id, filters))
    ) or 0)


def list_catalog_products(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
    filters: CatalogProductFilters = CatalogProductFilters(),
    sort_by: str = "cafe24_product_no",
    sort_dir: str = "desc",
) -> list[CatalogV2Product]:
    if limit < 1 or limit > 200:
        raise ValueError("limit must be between 1 and 200")

    if offset < 0:
        raise ValueError("offset must be >= 0")
    if sort_by not in {"cafe24_product_no", "sale_price"} or sort_dir not in {"asc", "desc"}:
        raise ValueError("invalid catalog sort")

    sort_column = ProductV2.cafe24_product_no if sort_by == "cafe24_product_no" else ProductV2.sale_price
    sort_expression = sort_column.asc() if sort_dir == "asc" else sort_column.desc()
    if sort_by == "sale_price":
        order_by = (sort_expression.nulls_last(), ProductV2.cafe24_product_no.desc())
    else:
        order_by = (sort_expression,)

    products = session.scalars(
        select(ProductV2)
        .where(*_product_conditions(tenant_id, filters))
        .order_by(*order_by)
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
            CategoryV2.category_name,
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

    categories_by_product: dict[
        uuid.UUID,
        list[CatalogV2Category],
    ] = {}

    for product_id, category_no, category_name in relation_rows:
        categories_by_product.setdefault(
            product_id,
            [],
        ).append(CatalogV2Category(
            cafe24_category_no=int(category_no),
            category_name=category_name,
        ))

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
            category_nos=tuple(category.cafe24_category_no for category in categories_by_product.get(product.id, [])),
            categories=tuple(categories_by_product.get(product.id, [])),
        )
        for product in products
    ]
