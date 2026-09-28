from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from backend.app.services.category_product_projection import (
    CategoryProductMembership,
    CategoryRecord,
    ProductRecord,
    project_catalog_products,
    project_category_scope,
)
from backend.app.services.current_reservation_demand import (
    CurrentReservationOrderItem,
    project_current_reservation_demand,
)


ROOT = Path(
    r"C:\ai-commerce-private\cafe24\cafe24\sanitized"
)

PREORDER_CATEGORY_NO = 56


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None

    text = value.strip().replace("Z", "+00:00")

    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)

    return parsed.astimezone(UTC)


def fallback_as_of(path: Path) -> datetime:
    return datetime.fromtimestamp(
        path.stat().st_mtime,
        tz=UTC,
    )


# --------------------------------------------------
# 1. Categories
# --------------------------------------------------

category_latest: dict[int, tuple[Path, dict]] = {}

for path in sorted((ROOT / "categories").glob("*.json")):
    payload = load_json(path)

    for record in payload.get("records", []):
        if not isinstance(record, dict):
            continue

        category_no = record.get("category_no")
        if category_no is None:
            continue

        category_latest[int(category_no)] = (
            path,
            record,
        )

categories: list[CategoryRecord] = []

for category_no in sorted(category_latest):
    path, record = category_latest[category_no]

    parent = record.get("parent_category_no")
    if parent is not None:
        parent = int(parent)

    categories.append(
        CategoryRecord(
            category_no=category_no,
            parent_category_no=parent,
            as_of=fallback_as_of(path),
            source_classification="SANITIZED_REAL",
            evidence_ids=(
                f"category:{category_no}:{path.stem}",
            ),
        )
    )


# --------------------------------------------------
# 2. Products
#    product_no별 updated_date 최신 1건
# --------------------------------------------------

product_latest: dict[
    int,
    tuple[datetime, Path, dict],
] = {}

for path in sorted((ROOT / "products").glob("*.json")):
    payload = load_json(path)

    for record in payload.get("records", []):
        if not isinstance(record, dict):
            continue

        product_no = record.get("product_no")
        if product_no is None:
            continue

        product_no = int(product_no)

        updated_at = (
            parse_datetime(record.get("updated_date"))
            or fallback_as_of(path)
        )

        previous = product_latest.get(product_no)

        if (
            previous is None
            or updated_at >= previous[0]
        ):
            product_latest[product_no] = (
                updated_at,
                path,
                record,
            )

products: list[ProductRecord] = []

for product_no in sorted(product_latest):
    as_of, path, record = product_latest[product_no]

    products.append(
        ProductRecord(
            product_no=product_no,
            display=record.get("display"),
            selling=record.get("selling"),
            sold_out=record.get("sold_out"),
            as_of=as_of,
            source_classification="SANITIZED_REAL",
            evidence_ids=(
                f"product:{product_no}:{path.stem}",
            ),
        )
    )


# --------------------------------------------------
# 3. Category ↔ Product memberships
# --------------------------------------------------

membership_latest: dict[
    tuple[int, int],
    CategoryProductMembership,
] = {}

for path in sorted(
    (ROOT / "category_product_relations").glob("*.json")
):
    payload = load_json(path)

    for record in payload.get("records", []):
        if not isinstance(record, dict):
            continue

        category_no = record.get("category_no")
        product_no = record.get("product_no")

        if category_no is None or product_no is None:
            continue

        evidence_type = record.get(
            "evidence_type",
            "CURRENT_CATEGORY_EVIDENCE",
        )

        if evidence_type != "CURRENT_CATEGORY_EVIDENCE":
            continue

        as_of = (
            parse_datetime(record.get("as_of"))
            or fallback_as_of(path)
        )

        key = (
            int(category_no),
            int(product_no),
        )

        membership = CategoryProductMembership(
            category_no=int(category_no),
            product_no=int(product_no),
            as_of=as_of,
            source_classification=str(
                record.get(
                    "source_classification",
                    "SANITIZED_REAL",
                )
            ),
            evidence_ids=(
                str(
                    record.get("evidence_id")
                    or f"category-product:{key[0]}:{key[1]}"
                ),
            ),
            evidence_type="CURRENT_CATEGORY_EVIDENCE",
        )

        previous = membership_latest.get(key)

        if (
            previous is None
            or membership.as_of >= previous.as_of
        ):
            membership_latest[key] = membership

memberships = tuple(
    membership_latest[key]
    for key in sorted(membership_latest)
)


# --------------------------------------------------
# 4. 실제 Catalog Projection 실행
# --------------------------------------------------

catalog = project_catalog_products(
    products=tuple(products),
    memberships=memberships,
)

catalog_by_no = {
    product.product_no: product
    for product in catalog
}

operational_products = [
    product
    for product in catalog
    if product.operational
]

uncategorized_products = [
    product
    for product in catalog
    if product.category_status == "UNCATEGORIZED"
]

uncategorized_operational = [
    product
    for product in uncategorized_products
    if product.operational
]


# --------------------------------------------------
# 5. PRE-ORDER Category Scope 실행
# --------------------------------------------------

preorder_scope = project_category_scope(
    category_no=PREORDER_CATEGORY_NO,
    categories=tuple(categories),
    memberships=memberships,
)

preorder_operational_product_nos = {
    product_no
    for product_no
    in preorder_scope.recursive_product_nos
    if (
        product_no in catalog_by_no
        and catalog_by_no[product_no].operational
    )
}


# --------------------------------------------------
# 6. Orders
#
# 중요:
# 기존 수동 집계(any snapshot)와
# 최신 관측(latest observation)을 둘 다 확인한다.
# --------------------------------------------------

all_order_records: list[dict] = []

latest_order_by_id: dict[
    str,
    tuple[Path, dict],
] = {}

for path in sorted((ROOT / "orders").glob("*.json")):
    payload = load_json(path)

    for record in payload.get("records", []):
        if not isinstance(record, dict):
            continue

        order_id = record.get("order_id")
        if not order_id:
            continue

        order_id = str(order_id)

        all_order_records.append(record)

        # sorted(path) 순으로 읽으므로
        # 나중 snapshot 관측이 앞의 것을 덮는다.
        latest_order_by_id[order_id] = (
            path,
            record,
        )


legacy_operational_order_ids = {
    str(record["order_id"])
    for record in all_order_records
    if (
        record.get("order_id")
        and str(record.get("shipping_status")) == "F"
        and str(record.get("canceled")) == "F"
    )
}

latest_operational_order_ids = {
    order_id
    for order_id, (_, record)
    in latest_order_by_id.items()
    if (
        str(record.get("shipping_status")) == "F"
        and str(record.get("canceled")) == "F"
    )
}

latest_partial_cancel_order_ids = {
    order_id
    for order_id, (_, record)
    in latest_order_by_id.items()
    if (
        str(record.get("shipping_status")) == "F"
        and str(record.get("canceled")) == "M"
    )
}
# --------------------------------------------------
# 7. Order Items → Parent Order Join
#
# 동일 order_item_code가 여러 snapshot에 반복 관측될 수 있으므로
# 최신 snapshot 관측 1건만 materialize한다.
# --------------------------------------------------

raw_order_item_record_count = 0

latest_order_item_by_code: dict[
    str,
    tuple[Path, dict],
] = {}

for path in sorted(
    (ROOT / "order_items").glob("*.json")
):
    payload = load_json(path)

    for record in payload.get("records", []):
        if not isinstance(record, dict):
            continue

        item_code = record.get("order_item_code")

        if not item_code:
            continue

        raw_order_item_record_count += 1

        # snapshot 파일을 시간순 이름으로 읽고
        # 같은 order_item_code가 다시 나오면 최신 관측으로 교체
        latest_order_item_by_code[str(item_code)] = (
            path,
            record,
        )


unique_order_item_count = len(
    latest_order_item_by_code
)

duplicate_order_item_observation_count = (
    raw_order_item_record_count
    - unique_order_item_count
)


current_items: list[CurrentReservationOrderItem] = []

for item_code in sorted(latest_order_item_by_code):
    path, record = latest_order_item_by_code[
        item_code
    ]

    product_no = record.get("product_no")

    if product_no is None:
        continue

    # 기존 프로젝트에서 이미 검증한 parent order 계약
    parts = item_code.rsplit("-", 1)

    if len(parts) != 2:
        continue

    order_id = parts[0]

    latest_order = latest_order_by_id.get(order_id)

    if latest_order is None:
        continue

    _, order_record = latest_order

    quantity = record.get("quantity")

    if quantity is not None:
        quantity = int(quantity)

    current_items.append(
        CurrentReservationOrderItem(
            order_id=order_id,
            order_item_id=item_code,
            product_no=int(product_no),
            quantity=quantity,
            shipping_status=str(
                order_record.get("shipping_status")
            ),
            canceled=str(
                order_record.get("canceled")
            ),
            sku_id=(
                str(record.get("variant_code"))
                if record.get("variant_code") is not None
                else None
            ),
            paid=(
                str(order_record.get("paid"))
                if order_record.get("paid") is not None
                else None
            ),
            source_classification="SANITIZED_REAL",
            evidence_ids=(
                f"order:{order_id}",
                f"order-item:{item_code}",
            ),
        )
    )


print()
print(
    "RAW_ORDER_ITEM_RECORDS=",
    raw_order_item_record_count,
)
print(
    "UNIQUE_ORDER_ITEMS=",
    unique_order_item_count,
)
print(
    "DUPLICATE_ORDER_ITEM_OBSERVATIONS=",
    duplicate_order_item_observation_count,
)

# --------------------------------------------------
# 8. 실제 Current Reservation Projection 실행
# --------------------------------------------------

demand_projection = project_current_reservation_demand(
    catalog_products=catalog,
    category_scope=preorder_scope,
    order_items=tuple(current_items),
)

confirmed_demands = demand_projection.demands

confirmed_required_qty = sum(
    demand.required_qty or 0
    for demand in confirmed_demands
)

quantity_unknown = sum(
    1
    for demand in confirmed_demands
    if demand.required_qty is None
)

preorder_confirmed_order_ids: set[str] = set()
preorder_confirmed_item_count = 0

for item in current_items:
    if (
        item.product_no
        not in preorder_operational_product_nos
    ):
        continue

    if (
        item.shipping_status == "F"
        and item.canceled == "F"
    ):
        preorder_confirmed_order_ids.add(
            item.order_id
        )
        preorder_confirmed_item_count += 1


partial_preorder_reviews = [
    item
    for item in demand_projection.review_items
    if item.reason
    == "PARTIAL_CANCEL_REMAINING_QUANTITY_UNKNOWN"
]


# --------------------------------------------------
# 9. Aggregate 출력
# --------------------------------------------------

print()
print("=== DAY 9 SANITIZED_REAL MATERIALIZATION ===")
print()

print("UNIQUE_PRODUCTS=", len(catalog))
print(
    "OPERATIONAL_PRODUCTS=",
    len(operational_products),
)
print(
    "UNCATEGORIZED_PRODUCTS=",
    len(uncategorized_products),
)
print(
    "UNCATEGORIZED_OPERATIONAL_PRODUCTS=",
    len(uncategorized_operational),
)

print()

print(
    "PREORDER_DIRECT_PRODUCTS=",
    preorder_scope.direct_product_count,
)
print(
    "PREORDER_RECURSIVE_PRODUCTS=",
    preorder_scope.recursive_product_count,
)
print(
    "PREORDER_OPERATIONAL_PRODUCTS=",
    len(preorder_operational_product_nos),
)

print()

print(
    "LEGACY_ANY_SNAPSHOT_OPERATIONAL_ORDERS=",
    len(legacy_operational_order_ids),
)
print(
    "LATEST_OPERATIONAL_ORDERS=",
    len(latest_operational_order_ids),
)

print()

print(
    "PREORDER_CONFIRMED_ORDERS=",
    len(preorder_confirmed_order_ids),
)
print(
    "PREORDER_CONFIRMED_ITEMS=",
    preorder_confirmed_item_count,
)
print(
    "PREORDER_CONFIRMED_REQUIRED_QTY=",
    confirmed_required_qty,
)
print(
    "PREORDER_QUANTITY_UNKNOWN=",
    quantity_unknown,
)
print(
    "PREORDER_PARTIAL_CANCEL_REVIEW_ITEMS=",
    len(partial_preorder_reviews),
)

print()

print(
    "PROJECTION_CONFIRMED_ORDER_COUNT=",
    getattr(
        demand_projection,
        "confirmed_order_count",
        "FIELD_NOT_AVAILABLE",
    ),
)
print(
    "PROJECTION_CONFIRMED_ORDER_ITEM_COUNT=",
    getattr(
        demand_projection,
        "confirmed_order_item_count",
        "FIELD_NOT_AVAILABLE",
    ),
)
print(
    "PROJECTION_CONFIRMED_REQUIRED_QTY=",
    getattr(
        demand_projection,
        "confirmed_required_qty",
        "FIELD_NOT_AVAILABLE",
    ),
)

print()

expected = {
    "UNIQUE_PRODUCTS": (len(catalog), 2167),
    "OPERATIONAL_PRODUCTS": (
        len(operational_products),
        2019,
    ),
    "UNCATEGORIZED_PRODUCTS": (
        len(uncategorized_products),
        35,
    ),
    "UNCATEGORIZED_OPERATIONAL_PRODUCTS": (
        len(uncategorized_operational),
        8,
    ),
    "PREORDER_DIRECT_PRODUCTS": (
        preorder_scope.direct_product_count,
        48,
    ),
    "PREORDER_OPERATIONAL_PRODUCTS": (
        len(preorder_operational_product_nos),
        46,
    ),
    "PREORDER_CONFIRMED_ORDERS": (
        len(preorder_confirmed_order_ids),
        6,
    ),
    "PREORDER_CONFIRMED_ITEMS": (
        preorder_confirmed_item_count,
        7,
    ),
    "PREORDER_CONFIRMED_REQUIRED_QTY": (
        confirmed_required_qty,
        8,
    ),
    "PREORDER_QUANTITY_UNKNOWN": (
        quantity_unknown,
        0,
    ),
    "PREORDER_PARTIAL_CANCEL_REVIEW_ITEMS": (
        len(partial_preorder_reviews),
        1,
    ),
}

print("=== EXPECTED VALUE CHECK ===")

all_pass = True

for name, (actual, wanted) in expected.items():
    passed = actual == wanted

    print(
        name,
        "actual=",
        actual,
        "expected=",
        wanted,
        "PASS" if passed else "FAIL",
    )

    if not passed:
        all_pass = False

print()

if (
    len(legacy_operational_order_ids)
    != len(latest_operational_order_ids)
):
    print(
        "NOTICE=ORDER_SNAPSHOT_STATUS_DRIFT_DETECTED"
    )
    print(
        "기존 any-snapshot 방식과 최신 관측 방식의 "
        "operational 주문 수가 다릅니다."
    )
    print(
        "이 경우 LATEST_OPERATIONAL_ORDERS를 "
        "현재 상태 기준으로 우선 검토해야 합니다."
    )

print()
print(
    "RESULT=",
    "PASS" if all_pass else "REVIEW_REQUIRED",
)