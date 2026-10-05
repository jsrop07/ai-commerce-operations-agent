from __future__ import annotations

import argparse
import os
import random
import uuid
from collections import Counter
from decimal import Decimal

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from backend.app.models_v2.catalog import ProductV2
from backend.app.models_v2.operations import OrderItemV2, OrderV2
from backend.app.models_v2.tenant import TenantV2
from scripts.r09_synthetic_order_preview import (
    RANDOM_SEED,
    build_orders,
    build_weight_map,
    load_products,
    select_candidate_products,
)


TARGET_TENANT_ID = uuid.UUID(
    "9ca31a68-a1d8-468e-9787-2677415b86ba"
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


def get_database_url() -> str:
    url = os.getenv("POSTGRES_V2_URL")

    if not url:
        raise RuntimeError(
            "POSTGRES_V2_URL is required. "
            "Do not put the password in this script."
        )

    return url


def generate_synthetic_rows() -> tuple[list[dict], list[dict]]:
    rng = random.Random(RANDOM_SEED)

    products = load_products()
    candidates = select_candidate_products(products, rng)

    weights, surge, decline, _hot = build_weight_map(
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

    order_rows: list[dict] = []
    item_rows: list[dict] = []

    for order in orders:
        order_uuid = deterministic_uuid(
            ORDER_NAMESPACE,
            order.external_order_id,
        )

        total_order_amount = order.total_amount

        total_paid_amount = (
            total_order_amount
            if order.paid == "T"
            else Decimal("0")
        )

        order_rows.append(
            {
                "id": order_uuid,
                "tenant_id": TARGET_TENANT_ID,
                "external_order_id": order.external_order_id,
                "source_system": SOURCE_SYSTEM,
                "total_order_amount": total_order_amount,
                "total_paid_amount": total_paid_amount,
                "payment_type": None,
                "payment_method": None,
                "source_order_at": order.source_order_at,
                "paid": order.paid,
                "shipping_status": order.shipping_status,
                "canceled": order.canceled,
            }
        )

        for item in order.items:
            item_uuid = deterministic_uuid(
                ITEM_NAMESPACE,
                item.external_order_item_id,
            )

            item_rows.append(
                {
                    "id": item_uuid,
                    "tenant_id": TARGET_TENANT_ID,
                    "order_id": order_uuid,
                    "external_order_item_id": (
                        item.external_order_item_id
                    ),
                    "external_product_no": (
                        item.product.product_no
                    ),
                    "product_id": uuid.UUID(
                        item.product.id
                    ),
                    "product_variant_id": None,
                    "source_product_name": (
                        item.product.name
                    ),
                    "source_product_name_with_option": None,
                    "quantity": item.quantity,
                    "source_sale_price": item.sale_price,
                }
            )

    return order_rows, item_rows


def validate_before_write(
    session: Session,
    order_rows: list[dict],
    item_rows: list[dict],
) -> None:
    tenant = session.get(
        TenantV2,
        TARGET_TENANT_ID,
    )

    if tenant is None:
        raise RuntimeError(
            "TARGET_TENANT_NOT_FOUND"
        )

    if tenant.environment != "LOCAL":
        raise RuntimeError(
            f"TARGET_TENANT_ENVIRONMENT_FORBIDDEN:"
            f"{tenant.environment}"
        )

    if tenant.status != "ACTIVE":
        raise RuntimeError(
            f"TARGET_TENANT_NOT_ACTIVE:"
            f"{tenant.status}"
        )

    existing_synthetic_orders = session.scalar(
        select(func.count())
        .select_from(OrderV2)
        .where(
            OrderV2.tenant_id == TARGET_TENANT_ID,
            OrderV2.source_system == SOURCE_SYSTEM,
        )
    )

    if existing_synthetic_orders:
        raise RuntimeError(
            "SYNTHETIC_DEMO_ORDERS_ALREADY_EXIST:"
            f"{existing_synthetic_orders}"
        )

    product_ids = {
        row["product_id"]
        for row in item_rows
    }

    db_products = session.execute(
        select(
            ProductV2.id,
            ProductV2.cafe24_product_no,
            ProductV2.product_name,
            ProductV2.sale_price,
            ProductV2.tenant_id,
        )
        .where(ProductV2.id.in_(product_ids))
    ).all()

    if len(db_products) != len(product_ids):
        raise RuntimeError(
            "CATALOG_PRODUCT_FK_MISSING"
        )

    db_product_map = {
        row.id: row
        for row in db_products
    }

    for item in item_rows:
        product = db_product_map.get(
            item["product_id"]
        )

        if product is None:
            raise RuntimeError(
                "PRODUCT_NOT_FOUND"
            )

        if product.tenant_id != TARGET_TENANT_ID:
            raise RuntimeError(
                "PRODUCT_TENANT_MISMATCH"
            )

        if (
            product.cafe24_product_no
            != item["external_product_no"]
        ):
            raise RuntimeError(
                "PRODUCT_NO_MISMATCH"
            )

        if (
            product.product_name
            != item["source_product_name"]
        ):
            raise RuntimeError(
                "PRODUCT_NAME_MISMATCH"
            )

        if (
            product.sale_price
            != item["source_sale_price"]
        ):
            raise RuntimeError(
                "PRODUCT_PRICE_MISMATCH"
            )

    order_ids = {
        row["id"]
        for row in order_rows
    }

    if len(order_ids) != len(order_rows):
        raise RuntimeError(
            "DUPLICATE_ORDER_IDS"
        )

    item_ids = {
        row["id"]
        for row in item_rows
    }

    if len(item_ids) != len(item_rows):
        raise RuntimeError(
            "DUPLICATE_ITEM_IDS"
        )

    for item in item_rows:
        if item["order_id"] not in order_ids:
            raise RuntimeError(
                "ORPHAN_ORDER_ITEM"
            )

        if item["quantity"] <= 0:
            raise RuntimeError(
                "INVALID_QUANTITY"
            )

    for order in order_rows:
        if order["paid"] not in {"T", "F"}:
            raise RuntimeError(
                "INVALID_PAID"
            )

        if order["shipping_status"] not in {
            "T",
            "F",
            "M",
        }:
            raise RuntimeError(
                "INVALID_SHIPPING_STATUS"
            )

        if order["canceled"] not in {
            "T",
            "F",
            "M",
        }:
            raise RuntimeError(
                "INVALID_CANCELED"
            )


def print_report(
    order_rows: list[dict],
    item_rows: list[dict],
    *,
    apply: bool,
) -> None:
    print("R09_SYNTHETIC_ORDER_SEED")
    print()

    print(f"MODE={'APPLY' if apply else 'DRY_RUN'}")
    print(
        f"DB_WRITE_REQUESTED="
        f"{1 if apply else 0}"
    )

    print(
        f"TARGET_TENANT_ID="
        f"{TARGET_TENANT_ID}"
    )

    print(
        f"SOURCE_SYSTEM="
        f"{SOURCE_SYSTEM}"
    )

    print(
        f"ORDERS={len(order_rows)}"
    )

    print(
        f"ORDER_ITEMS={len(item_rows)}"
    )

    print(
        "REFERENCED_PRODUCTS="
        f"{len({x['product_id'] for x in item_rows})}"
    )

    print(
        "TOTAL_ITEM_QUANTITY="
        f"{sum(x['quantity'] for x in item_rows)}"
    )

    print(
        "paid=",
        dict(
            Counter(
                x["paid"]
                for x in order_rows
            )
        ),
    )

    print(
        "shipping_status=",
        dict(
            Counter(
                x["shipping_status"]
                for x in order_rows
            )
        ),
    )

    print(
        "canceled=",
        dict(
            Counter(
                x["canceled"]
                for x in order_rows
            )
        ),
    )


def insert_rows(
    session: Session,
    order_rows: list[dict],
    item_rows: list[dict],
) -> None:
    orders = [
        OrderV2(**row)
        for row in order_rows
    ]

    items = [
        OrderItemV2(**row)
        for row in item_rows
    ]

    session.add_all(orders)
    session.flush()

    session.add_all(items)
    session.flush()


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually insert synthetic rows.",
    )

    args = parser.parse_args()

    order_rows, item_rows = (
        generate_synthetic_rows()
    )

    engine = create_engine(
        get_database_url(),
        pool_pre_ping=True,
    )

    with Session(engine) as session:
        validate_before_write(
            session,
            order_rows,
            item_rows,
        )

        print_report(
            order_rows,
            item_rows,
            apply=args.apply,
        )

        if not args.apply:
            print()
            print("DB_WRITE_COUNT=0")
            print("VALIDATION=PASS")
            print(
                "Run again with --apply only "
                "after explicit approval."
            )
            return

        insert_rows(
            session,
            order_rows,
            item_rows,
        )

        session.commit()

        inserted_orders = session.scalar(
            select(func.count())
            .select_from(OrderV2)
            .where(
                OrderV2.tenant_id == (
                    TARGET_TENANT_ID
                ),
                OrderV2.source_system == (
                    SOURCE_SYSTEM
                ),
            )
        )

        inserted_items = session.scalar(
            select(func.count())
            .select_from(OrderItemV2)
            .join(
                OrderV2,
                OrderV2.id == (
                    OrderItemV2.order_id
                ),
            )
            .where(
                OrderV2.tenant_id == (
                    TARGET_TENANT_ID
                ),
                OrderV2.source_system == (
                    SOURCE_SYSTEM
                ),
            )
        )

        print()
        print(
            f"INSERTED_ORDERS="
            f"{inserted_orders}"
        )

        print(
            f"INSERTED_ORDER_ITEMS="
            f"{inserted_items}"
        )

        if (
            inserted_orders != 600
            or inserted_items != 1700
        ):
            raise RuntimeError(
                "POST_INSERT_COUNT_MISMATCH"
            )

        print("POST_INSERT_VALIDATION=PASS")


if __name__ == "__main__":
    main()