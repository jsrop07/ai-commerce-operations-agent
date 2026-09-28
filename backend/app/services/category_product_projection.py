"""Day 9 common Cafe24 category and operational-product projection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

CURRENT_CATEGORY_EVIDENCE = "CURRENT_CATEGORY_EVIDENCE"


@dataclass(frozen=True)
class CategoryRecord:
    category_no: int
    parent_category_no: int | None
    as_of: datetime
    source_classification: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class CategoryProductMembership:
    category_no: int
    product_no: int
    as_of: datetime
    source_classification: str
    evidence_ids: tuple[str, ...]
    evidence_type: str = CURRENT_CATEGORY_EVIDENCE


@dataclass(frozen=True)
class ProductRecord:
    product_no: int
    display: str | None
    selling: str | None
    sold_out: str | None
    as_of: datetime
    source_classification: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class CatalogProductProjection:
    product_no: int
    category_nos: tuple[int, ...]
    category_status: str
    display: str | None
    selling: str | None
    sold_out: str | None
    operational: bool
    as_of: datetime
    source_classifications: tuple[str, ...]
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class CategoryScopeProjection:
    category_no: int
    descendant_category_nos: tuple[int, ...]
    direct_product_nos: tuple[int, ...]
    recursive_product_nos: tuple[int, ...]
    direct_product_count: int
    recursive_product_count: int
    source_classifications: tuple[str, ...]
    evidence_ids: tuple[str, ...]


def _require_positive_identifier(
    value: int,
    field: str,
) -> None:
    if type(value) is not int or value < 1:
        raise ValueError(
            f"{field} must be a positive integer"
        )


def project_catalog_products(
    *,
    products: tuple[ProductRecord, ...],
    memberships: tuple[
        CategoryProductMembership,
        ...,
    ],
) -> tuple[CatalogProductProjection, ...]:
    """Keep every product and attach explicit zero-to-many memberships."""

    products_by_no: dict[int, ProductRecord] = {}
    for product in products:
        _require_positive_identifier(
            product.product_no,
            "product_no",
        )
        if product.product_no in products_by_no:
            raise ValueError(
                "duplicate product_no"
            )
        products_by_no[product.product_no] = product

    memberships_by_product: dict[
        int,
        list[CategoryProductMembership],
    ] = {}
    seen_relations: set[tuple[int, int]] = set()

    for membership in memberships:
        _require_positive_identifier(
            membership.category_no,
            "category_no",
        )
        _require_positive_identifier(
            membership.product_no,
            "product_no",
        )
        if (
            membership.evidence_type
            != CURRENT_CATEGORY_EVIDENCE
        ):
            raise ValueError(
                "category membership must remain CURRENT_CATEGORY_EVIDENCE"
            )
        if membership.product_no not in products_by_no:
            raise ValueError(
                "category membership references unknown product"
            )
        relation_key = (
            membership.category_no,
            membership.product_no,
        )
        if relation_key in seen_relations:
            continue
        seen_relations.add(relation_key)
        memberships_by_product.setdefault(
            membership.product_no,
            [],
        ).append(membership)

    projected: list[CatalogProductProjection] = []
    for product_no in sorted(products_by_no):
        product = products_by_no[product_no]
        product_memberships = (
            memberships_by_product.get(
                product_no,
                [],
            )
        )
        category_nos = tuple(
            sorted(
                membership.category_no
                for membership in product_memberships
            )
        )
        projected.append(
            CatalogProductProjection(
                product_no=product_no,
                category_nos=category_nos,
                category_status=(
                    "CATEGORIZED"
                    if category_nos
                    else "UNCATEGORIZED"
                ),
                display=product.display,
                selling=product.selling,
                sold_out=product.sold_out,
                operational=(
                    product.display == "T"
                    and product.selling == "T"
                ),
                as_of=product.as_of,
                source_classifications=tuple(
                    dict.fromkeys(
                        [product.source_classification]
                        + [
                            membership.source_classification
                            for membership in product_memberships
                        ]
                    )
                ),
                evidence_ids=tuple(
                    dict.fromkeys(
                        list(product.evidence_ids)
                        + [
                            evidence_id
                            for membership in product_memberships
                            for evidence_id in membership.evidence_ids
                        ]
                    )
                ),
            )
        )

    return tuple(projected)


def project_category_scope(
    *,
    category_no: int,
    categories: tuple[CategoryRecord, ...],
    memberships: tuple[
        CategoryProductMembership,
        ...,
    ],
) -> CategoryScopeProjection:
    """Resolve every descendant and deduplicate products by product_no."""

    _require_positive_identifier(
        category_no,
        "category_no",
    )
    categories_by_no: dict[int, CategoryRecord] = {}
    children: dict[int, set[int]] = {}
    for category in categories:
        _require_positive_identifier(
            category.category_no,
            "category_no",
        )
        if category.category_no in categories_by_no:
            raise ValueError(
                "duplicate category_no"
            )
        categories_by_no[category.category_no] = category
        if category.parent_category_no is not None:
            _require_positive_identifier(
                category.parent_category_no,
                "parent_category_no",
            )
            children.setdefault(
                category.parent_category_no,
                set(),
            ).add(category.category_no)

    if category_no not in categories_by_no:
        raise ValueError(
            "category_no is not present in category snapshot"
        )

    descendants: set[int] = set()
    visiting: set[int] = set()

    def visit(current: int) -> None:
        if current in visiting:
            raise ValueError(
                "category hierarchy contains a cycle"
            )
        visiting.add(current)
        for child in children.get(current, set()):
            if child in visiting:
                raise ValueError(
                    "category hierarchy contains a cycle"
                )
            if child not in descendants:
                descendants.add(child)
                visit(child)
        visiting.remove(current)

    visit(category_no)
    scope = descendants | {category_no}
    direct_products: set[int] = set()
    recursive_products: set[int] = set()
    included_memberships: list[
        CategoryProductMembership
    ] = []

    for membership in memberships:
        if (
            membership.evidence_type
            != CURRENT_CATEGORY_EVIDENCE
        ):
            raise ValueError(
                "category membership must remain CURRENT_CATEGORY_EVIDENCE"
            )
        if membership.category_no not in scope:
            continue
        _require_positive_identifier(
            membership.product_no,
            "product_no",
        )
        recursive_products.add(
            membership.product_no
        )
        included_memberships.append(membership)
        if membership.category_no == category_no:
            direct_products.add(
                membership.product_no
            )

    included_categories = [
        categories_by_no[number]
        for number in sorted(scope)
    ]
    return CategoryScopeProjection(
        category_no=category_no,
        descendant_category_nos=tuple(
            sorted(descendants)
        ),
        direct_product_nos=tuple(
            sorted(direct_products)
        ),
        recursive_product_nos=tuple(
            sorted(recursive_products)
        ),
        direct_product_count=len(
            direct_products
        ),
        recursive_product_count=len(
            recursive_products
        ),
        source_classifications=tuple(
            dict.fromkeys(
                [
                    category.source_classification
                    for category in included_categories
                ]
                + [
                    membership.source_classification
                    for membership in included_memberships
                ]
            )
        ),
        evidence_ids=tuple(
            dict.fromkeys(
                [
                    evidence_id
                    for category in included_categories
                    for evidence_id in category.evidence_ids
                ]
                + [
                    evidence_id
                    for membership in included_memberships
                    for evidence_id in membership.evidence_ids
                ]
            )
        ),
    )
