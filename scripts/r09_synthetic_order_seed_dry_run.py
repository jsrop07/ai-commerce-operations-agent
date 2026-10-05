from __future__ import annotations

import random
import uuid
from collections import Counter
from decimal import Decimal

from scripts.r09_synthetic_order_preview import (
    RANDOM_SEED,
    build_orders,
    build_weight_map,
    load_products,
    select_candidate_products,
)


SOURCE_SYSTEM = "SYNTHETIC_DEMO"

ORDER_NAMESPACE = uuid.UUID(
    "f1307821-d16f-41ca-9758-b65e40efdd71"
)
ITEM_NAMESPACE = uuid.UUID(
    "602c6e3c-70ae-45e7-a6fc-a1ff713ab782"
)


def deterministic_uuid(
    namespace: uuid.UUID,
    external_id: str,
) -> uuid.UUID:
    return uuid.uuid5(namespace, external_id)


def main() -> None:
    rng = random.Random(RANDOM_SEED)

    products = load_products()

    candidates = select_candidate_products(
        products,
        rng,
    )

    weights, surge, decline, hot = build_weight_map(
        candidates,
        rng,
    )

    orders = build_orders(
        candidates,
        weights,
        surge,
        decline,
        rng,
    )

    product_by_id = {
        product.id: product
        for product in products
    }

    product_by_no = {
        product.product_no: product
        for product in products
    }

    order_rows: list[dict] = []
    item_rows: list[dict] = []

    product_fk_missing = 0
    product_no_mismatch = 0
    product_name_mismatch = 0
    product_price_mismatch = 0
    parent_order_missing = 0

    invalid_paid = 0
    invalid_shipping = 0
    invalid_canceled = 0
    invalid_quantity = 0

    order_uuid_by_external_id: dict[str, uuid.UUID] = {}

    # --------------------------------------------------
    # 1. Synthetic Order rows
    # --------------------------------------------------

    for order in orders:
        order_uuid = deterministic_uuid(
            ORDER_NAMESPACE,
            order.external_order_id,
        )

        order_uuid_by_external_id[
            order.external_order_id
        ] = order_uuid

        total_order_amount = order.total_amount

        if order.paid == "T":
            total_paid_amount = total_order_amount
        else:
            total_paid_amount = Decimal("0")

        if order.paid not in {"T", "F"}:
            invalid_paid += 1

        if order.shipping_status not in {
            "T",
            "F",
            "M",
        }:
            invalid_shipping += 1

        if order.canceled not in {
            "T",
            "F",
            "M",
        }:
            invalid_canceled += 1

        order_rows.append(
            {
                "id": order_uuid,
                "external_order_id": (
                    order.external_order_id
                ),
                "source_system": SOURCE_SYSTEM,
                "total_order_amount": (
                    total_order_amount
                ),
                "total_paid_amount": (
                    total_paid_amount
                ),
                "payment_type": None,
                "payment_method": None,
                "source_order_at": (
                    order.source_order_at
                ),
                "paid": order.paid,
                "shipping_status": (
                    order.shipping_status
                ),
                "canceled": order.canceled,
            }
        )

    # --------------------------------------------------
    # 2. Synthetic OrderItem rows
    # --------------------------------------------------

    for order in orders:
        parent_order_id = order_uuid_by_external_id.get(
            order.external_order_id
        )

        if parent_order_id is None:
            parent_order_missing += len(order.items)
            continue

        for item in order.items:
            product = item.product

            item_uuid = deterministic_uuid(
                ITEM_NAMESPACE,
                item.external_order_item_id,
            )

            db_product = product_by_id.get(
                product.id
            )

            if db_product is None:
                product_fk_missing += 1
                continue

            db_product_by_no = product_by_no.get(
                product.product_no
            )

            if db_product_by_no is None:
                product_fk_missing += 1
                continue

            if (
                db_product.product_no
                != product.product_no
            ):
                product_no_mismatch += 1

            if (
                db_product.name
                != product.name
            ):
                product_name_mismatch += 1

            if (
                db_product.sale_price
                != item.sale_price
            ):
                product_price_mismatch += 1

            if item.quantity <= 0:
                invalid_quantity += 1

            item_rows.append(
                {
                    "id": item_uuid,
                    "order_id": parent_order_id,
                    "external_order_item_id": (
                        item.external_order_item_id
                    ),
                    "external_product_no": (
                        product.product_no
                    ),
                    "product_id": uuid.UUID(
                        product.id
                    ),
                    "product_variant_id": None,
                    "source_product_name": (
                        product.name
                    ),
                    "source_product_name_with_option": (
                        None
                    ),
                    "quantity": item.quantity,
                    "source_sale_price": (
                        item.sale_price
                    ),
                }
            )

    # --------------------------------------------------
    # 3. Cross-row integrity
    # --------------------------------------------------

    order_ids = {
        row["id"]
        for row in order_rows
    }

    orphan_items = sum(
        1
        for row in item_rows
        if row["order_id"] not in order_ids
    )

    duplicate_order_external_ids = (
        len(order_rows)
        - len(
            {
                row["external_order_id"]
                for row in order_rows
            }
        )
    )

    duplicate_item_external_ids = (
        len(item_rows)
        - len(
            {
                row["external_order_item_id"]
                for row in item_rows
            }
        )
    )

    referenced_products = {
        row["product_id"]
        for row in item_rows
    }

    total_order_amount = sum(
        (
            row["total_order_amount"]
            for row in order_rows
        ),
        Decimal("0"),
    )

    total_paid_amount = sum(
        (
            row["total_paid_amount"]
            for row in order_rows
        ),
        Decimal("0"),
    )

    total_item_quantity = sum(
        row["quantity"]
        for row in item_rows
    )

    # --------------------------------------------------
    # 4. Dry-run report
    # --------------------------------------------------

    print(
        "R09_SYNTHETIC_ORDER_SEED_DRY_RUN"
    )
    print()

    print("DB_WRITE_COUNT=0")
    print("ACTUAL_ORDER_ROWS_USED=0")
    print("ACTUAL_ORDER_ITEM_ROWS_USED=0")
    print()

    print(
        f"WOULD_INSERT_ORDERS="
        f"{len(order_rows)}"
    )
    print(
        f"WOULD_INSERT_ORDER_ITEMS="
        f"{len(item_rows)}"
    )

    print(
        f"REFERENCED_CATALOG_PRODUCTS="
        f"{len(referenced_products)}"
    )

    print(
        f"TOTAL_ITEM_QUANTITY="
        f"{total_item_quantity}"
    )

    print(
        f"TOTAL_ORDER_AMOUNT="
        f"{total_order_amount}"
    )

    print(
        f"TOTAL_PAID_AMOUNT="
        f"{total_paid_amount}"
    )

    print()
    print("FK_AND_CATALOG_VALIDATION")

    print(
        f"PRODUCT_FK_MISSING="
        f"{product_fk_missing}"
    )
    print(
        f"PRODUCT_NO_MISMATCH="
        f"{product_no_mismatch}"
    )
    print(
        f"PRODUCT_NAME_MISMATCH="
        f"{product_name_mismatch}"
    )
    print(
        f"PRODUCT_PRICE_MISMATCH="
        f"{product_price_mismatch}"
    )
    print(
        f"PARENT_ORDER_MISSING="
        f"{parent_order_missing}"
    )
    print(
        f"ORPHAN_ORDER_ITEMS="
        f"{orphan_items}"
    )

    print()
    print("CONSTRAINT_VALIDATION")

    print(
        f"INVALID_PAID="
        f"{invalid_paid}"
    )
    print(
        f"INVALID_SHIPPING_STATUS="
        f"{invalid_shipping}"
    )
    print(
        f"INVALID_CANCELED="
        f"{invalid_canceled}"
    )
    print(
        f"INVALID_QUANTITY="
        f"{invalid_quantity}"
    )

    print()
    print("IDENTITY_VALIDATION")

    print(
        f"DUPLICATE_ORDER_EXTERNAL_IDS="
        f"{duplicate_order_external_ids}"
    )
    print(
        f"DUPLICATE_ITEM_EXTERNAL_IDS="
        f"{duplicate_item_external_ids}"
    )

    print()
    print("ORDER_STATUS_COUNTS")

    print(
        "paid=",
        dict(
            Counter(
                row["paid"]
                for row in order_rows
            )
        ),
    )

    print(
        "shipping_status=",
        dict(
            Counter(
                row["shipping_status"]
                for row in order_rows
            )
        ),
    )

    print(
        "canceled=",
        dict(
            Counter(
                row["canceled"]
                for row in order_rows
            )
        ),
    )

    print()
    print("DESTINATION_ORDER_FIELDS")
    print(
        sorted(
            key
            for key in order_rows[0]
            if key != "id"
        )
    )

    print()
    print("DESTINATION_ORDER_ITEM_FIELDS")
    print(
        sorted(
            key
            for key in item_rows[0]
            if key != "id"
        )
    )

    print()
    print("SAFE_SAMPLE_ORDERS_3")

    for order_row in order_rows[:3]:
        print(
            order_row[
                "external_order_id"
            ],
            order_row[
                "source_order_at"
            ].isoformat(),
            f"total="
            f"{order_row['total_order_amount']}",
            f"paid="
            f"{order_row['paid']}",
            f"shipping="
            f"{order_row['shipping_status']}",
            f"canceled="
            f"{order_row['canceled']}",
        )

    all_passed = all(
        value == 0
        for value in [
            product_fk_missing,
            product_no_mismatch,
            product_name_mismatch,
            product_price_mismatch,
            parent_order_missing,
            orphan_items,
            invalid_paid,
            invalid_shipping,
            invalid_canceled,
            invalid_quantity,
            duplicate_order_external_ids,
            duplicate_item_external_ids,
        ]
    )

    print()
    print(
        f"ALL_VALIDATIONS_PASSED="
        f"{all_passed}"
    )


if __name__ == "__main__":
    main()