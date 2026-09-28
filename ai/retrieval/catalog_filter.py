from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class CatalogFilter:
    category_no: int | None = None
    recursive_category: bool = False
    operational: bool | None = None
    sold_out: bool | None = None
    category_status: str | None = None


def build_descendant_map(
    categories: Iterable[dict[str, Any]],
) -> dict[int, set[int]]:
    """
    각 category_no에 대해 자기 자신 + 모든 descendant를 반환한다.
    """

    children: dict[int, set[int]] = defaultdict(set)
    category_nos: set[int] = set()

    for category in categories:
        category_no = int(category["category_no"])
        category_nos.add(category_no)

        parent = category.get("parent_category_no")

        if parent is not None:
            children[int(parent)].add(category_no)

    result: dict[int, set[int]] = {}

    for root in category_nos:
        visited: set[int] = set()
        stack = [root]

        while stack:
            current = stack.pop()

            if current in visited:
                continue

            visited.add(current)
            stack.extend(
                children.get(current, set())
            )

        result[root] = visited

    return result


def product_matches(
    product: dict[str, Any],
    *,
    filter_: CatalogFilter,
    descendant_map: dict[int, set[int]],
) -> bool:
    if filter_.operational is not None:
        if bool(product["operational"]) != filter_.operational:
            return False

    if filter_.sold_out is not None:
        sold_out = str(
            product["sold_out"]
        ).upper() == "T"

        if sold_out != filter_.sold_out:
            return False

    if filter_.category_status is not None:
        if (
            str(product["category_status"])
            != filter_.category_status
        ):
            return False

    if filter_.category_no is not None:
        product_categories = {
            int(value)
            for value in product.get(
                "category_nos",
                [],
            )
        }

        if filter_.recursive_category:
            allowed = descendant_map.get(
                filter_.category_no,
                {filter_.category_no},
            )
        else:
            allowed = {
                filter_.category_no
            }

        if not product_categories.intersection(
            allowed
        ):
            return False

    return True


def filter_products(
    products: Iterable[dict[str, Any]],
    *,
    filter_: CatalogFilter,
    descendant_map: dict[int, set[int]],
) -> list[dict[str, Any]]:
    """
    product_no identity 기준으로 결과를 dedupe한다.
    """

    matched: dict[int, dict[str, Any]] = {}

    for product in products:
        if not product_matches(
            product,
            filter_=filter_,
            descendant_map=descendant_map,
        ):
            continue

        matched[int(product["product_no"])] = product

    return [
        matched[product_no]
        for product_no in sorted(matched)
    ]