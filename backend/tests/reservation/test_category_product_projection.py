"""Day 9 common category/product projection tests."""

from datetime import UTC, datetime

import pytest

from backend.app.services.category_product_projection import (
    CategoryProductMembership,
    CategoryRecord,
    ProductRecord,
    project_catalog_products,
    project_category_scope,
)
from backend.app.services.reservation_service import (
    ReservationIdentification,
    ReservationIdentificationInput,
    identify_reservation,
)

AS_OF = datetime(2026, 9, 10, tzinfo=UTC)


def product(
    product_no: int,
    *,
    display: str = "T",
    selling: str = "T",
    sold_out: str = "F",
) -> ProductRecord:
    return ProductRecord(
        product_no=product_no,
        display=display,
        selling=selling,
        sold_out=sold_out,
        as_of=AS_OF,
        source_classification="SANITIZED_REAL",
        evidence_ids=(f"product-{product_no}",),
    )


def membership(
    category_no: int,
    product_no: int,
) -> CategoryProductMembership:
    return CategoryProductMembership(
        category_no=category_no,
        product_no=product_no,
        as_of=AS_OF,
        source_classification="LIVE_READ",
        evidence_ids=(
            f"membership-{category_no}-{product_no}",
        ),
    )


def category(
    category_no: int,
    parent_category_no: int | None,
) -> CategoryRecord:
    return CategoryRecord(
        category_no=category_no,
        parent_category_no=parent_category_no,
        as_of=AS_OF,
        source_classification="SANITIZED_REAL",
        evidence_ids=(f"category-{category_no}",),
    )


def test_membership_zero_one_and_many_are_preserved() -> None:
    result = project_catalog_products(
        products=(
            product(1),
            product(2),
            product(3),
        ),
        memberships=(
            membership(10, 2),
            membership(10, 3),
            membership(20, 3),
        ),
    )

    assert result[0].category_status == "UNCATEGORIZED"
    assert result[0].category_nos == ()
    assert result[1].category_nos == (10,)
    assert result[2].category_nos == (10, 20)


def test_parent_scope_is_recursive_and_deduplicates_products() -> None:
    scope = project_category_scope(
        category_no=1,
        categories=(
            category(1, None),
            category(2, 1),
            category(3, 2),
        ),
        memberships=(
            membership(2, 100),
            membership(3, 100),
            membership(3, 200),
        ),
    )

    assert scope.descendant_category_nos == (2, 3)
    assert scope.direct_product_count == 0
    assert scope.recursive_product_count == 2
    assert scope.direct_product_nos == ()
    assert scope.recursive_product_nos == (100, 200)


def test_operational_product_requires_display_and_selling() -> None:
    result = project_catalog_products(
        products=(
            product(1),
            product(2, display="F"),
            product(3, selling="F"),
        ),
        memberships=(),
    )

    assert result[0].operational is True
    assert result[1].operational is False
    assert result[2].operational is False


def test_sold_out_does_not_make_operational_product_inactive() -> None:
    result = project_catalog_products(
        products=(
            product(1, sold_out="T"),
        ),
        memberships=(),
    )

    assert result[0].operational is True
    assert result[0].sold_out == "T"


def test_operational_uncategorized_product_remains_in_catalog() -> None:
    result = project_catalog_products(
        products=(product(35),),
        memberships=(),
    )

    assert len(result) == 1
    assert result[0].product_no == 35
    assert result[0].category_status == "UNCATEGORIZED"
    assert result[0].operational is True


def test_current_operational_category_state_is_not_historical_truth() -> None:
    catalog = project_catalog_products(
        products=(product(1),),
        memberships=(membership(56, 1),),
    )
    assert catalog[0].operational is True

    historical = identify_reservation(
        ReservationIdentificationInput(
            order_id="historical-order",
            current_category="PRE-ORDER",
        )
    )

    assert historical.status == (
        ReservationIdentification.UNKNOWN
    )
    assert (
        "CURRENT_CATEGORY_ONLY_NOT_VALID_TIME_EVIDENCE"
        in historical.reasons
    )


def test_membership_cannot_be_promoted_to_historical_evidence() -> None:
    invalid = CategoryProductMembership(
        category_no=56,
        product_no=1,
        as_of=AS_OF,
        source_classification="LIVE_READ",
        evidence_ids=("membership-56-1",),
        evidence_type=(
            "HISTORICAL_RESERVATION_EVIDENCE"
        ),
    )

    with pytest.raises(
        ValueError,
        match="CURRENT_CATEGORY_EVIDENCE",
    ):
        project_catalog_products(
            products=(product(1),),
            memberships=(invalid,),
        )
