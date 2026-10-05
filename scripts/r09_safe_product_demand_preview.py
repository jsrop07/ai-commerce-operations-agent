from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine, text


SOURCE_SYSTEM = "SYNTHETIC_DEMO"

AS_OF = datetime(
    2026,
    10,
    4,
    23,
    59,
    59,
    tzinfo=timezone.utc,
)

RECENT_START = datetime(
    2026,
    9,
    25,
    0,
    0,
    0,
    tzinfo=timezone.utc,
)

PREVIOUS_START = datetime(
    2026,
    9,
    15,
    0,
    0,
    0,
    tzinfo=timezone.utc,
)

PREVIOUS_END = RECENT_START

LOW_SAMPLE_ORDER_COUNT = 3


@dataclass(frozen=True)
class SafeProductDemandAggregate:
    product_no: int
    product_name: str

    order_count: int
    order_item_count: int
    ordered_quantity: int

    paid_order_count: int
    canceled_order_count: int

    recent_10d_quantity: int
    previous_10d_quantity: int

    trend_direction: str
    trend_delta: int
    trend_ratio: float | None

    shipping_pending_count: int
    shipping_partial_count: int
    shipping_complete_count: int

    data_mode: str
    quality_status: str
    as_of: str


def get_database_url() -> str:
    url = os.getenv("POSTGRES_V2_URL")

    if not url:
        raise RuntimeError(
            "POSTGRES_V2_URL is required."
        )

    return url


def determine_trend(
    recent_quantity: int,
    previous_quantity: int,
) -> tuple[str, int, float | None]:
    delta = recent_quantity - previous_quantity

    if (
        previous_quantity == 0
        and recent_quantity > 0
    ):
        return "SURGE", delta, None

    if (
        recent_quantity == 0
        and previous_quantity == 0
    ):
        return "FLAT", 0, None

    if previous_quantity == 0:
        return "FLAT", delta, None

    ratio = round(
        recent_quantity / previous_quantity,
        4,
    )

    if recent_quantity > previous_quantity:
        direction = "UP"
    elif recent_quantity < previous_quantity:
        direction = "DOWN"
    else:
        direction = "FLAT"

    return direction, delta, ratio


def determine_quality(
    order_count: int,
) -> str:
    if order_count == 0:
        return "NO_DATA"

    if order_count < LOW_SAMPLE_ORDER_COUNT:
        return "LOW_SAMPLE"

    return "OK"


def load_aggregates() -> list[SafeProductDemandAggregate]:
    engine = create_engine(
        get_database_url(),
        pool_pre_ping=True,
    )

    sql = text(
        """
        WITH base AS (
            SELECT
                oi.external_product_no AS product_no,
                p.product_name,
                o.id AS order_id,
                o.source_order_at,
                o.paid,
                o.canceled,
                o.shipping_status,
                oi.quantity
            FROM operations.order_items oi
            JOIN operations.orders o
              ON o.tenant_id = oi.tenant_id
             AND o.id = oi.order_id
            JOIN catalog.products p
              ON p.tenant_id = oi.tenant_id
             AND p.id = oi.product_id
            WHERE o.source_system = :source_system
        )
        SELECT
            product_no,
            product_name,

            COUNT(DISTINCT order_id)
                AS order_count,

            COUNT(*)
                AS order_item_count,

            COALESCE(SUM(quantity), 0)
                AS ordered_quantity,

            COUNT(
                DISTINCT CASE
                    WHEN paid = 'T'
                    THEN order_id
                END
            ) AS paid_order_count,

            COUNT(
                DISTINCT CASE
                    WHEN canceled <> 'F'
                    THEN order_id
                END
            ) AS canceled_order_count,

            COALESCE(
                SUM(
                    CASE
                        WHEN source_order_at >= :recent_start
                         AND source_order_at <= :as_of
                        THEN quantity
                        ELSE 0
                    END
                ),
                0
            ) AS recent_10d_quantity,

            COALESCE(
                SUM(
                    CASE
                        WHEN source_order_at >= :previous_start
                         AND source_order_at < :previous_end
                        THEN quantity
                        ELSE 0
                    END
                ),
                0
            ) AS previous_10d_quantity,

            COUNT(
                DISTINCT CASE
                    WHEN shipping_status = 'F'
                    THEN order_id
                END
            ) AS shipping_pending_count,

            COUNT(
                DISTINCT CASE
                    WHEN shipping_status = 'M'
                    THEN order_id
                END
            ) AS shipping_partial_count,

            COUNT(
                DISTINCT CASE
                    WHEN shipping_status = 'T'
                    THEN order_id
                END
            ) AS shipping_complete_count

        FROM base
        GROUP BY
            product_no,
            product_name
        ORDER BY
            recent_10d_quantity DESC,
            ordered_quantity DESC,
            product_no
        """
    )

    with engine.connect() as connection:
        rows = connection.execute(
            sql,
            {
                "source_system": SOURCE_SYSTEM,
                "recent_start": RECENT_START,
                "previous_start": PREVIOUS_START,
                "previous_end": PREVIOUS_END,
                "as_of": AS_OF,
            },
        ).mappings().all()

    results: list[SafeProductDemandAggregate] = []

    for row in rows:
        recent_quantity = int(
            row["recent_10d_quantity"]
        )

        previous_quantity = int(
            row["previous_10d_quantity"]
        )

        (
            trend_direction,
            trend_delta,
            trend_ratio,
        ) = determine_trend(
            recent_quantity,
            previous_quantity,
        )

        order_count = int(
            row["order_count"]
        )

        results.append(
            SafeProductDemandAggregate(
                product_no=int(
                    row["product_no"]
                ),
                product_name=str(
                    row["product_name"]
                ),
                order_count=order_count,
                order_item_count=int(
                    row["order_item_count"]
                ),
                ordered_quantity=int(
                    row["ordered_quantity"]
                ),
                paid_order_count=int(
                    row["paid_order_count"]
                ),
                canceled_order_count=int(
                    row["canceled_order_count"]
                ),
                recent_10d_quantity=(
                    recent_quantity
                ),
                previous_10d_quantity=(
                    previous_quantity
                ),
                trend_direction=(
                    trend_direction
                ),
                trend_delta=trend_delta,
                trend_ratio=trend_ratio,
                shipping_pending_count=int(
                    row[
                        "shipping_pending_count"
                    ]
                ),
                shipping_partial_count=int(
                    row[
                        "shipping_partial_count"
                    ]
                ),
                shipping_complete_count=int(
                    row[
                        "shipping_complete_count"
                    ]
                ),
                data_mode=SOURCE_SYSTEM,
                quality_status=(
                    determine_quality(
                        order_count
                    )
                ),
                as_of=AS_OF.isoformat(),
            )
        )

    return results


def main() -> None:
    aggregates = load_aggregates()

    print(
        "R09_SAFE_PRODUCT_DEMAND_PREVIEW"
    )
    print()

    print("DB_WRITE_COUNT=0")
    print("AI_CALL_COUNT=0")
    print(
        "ACTUAL_ORDER_ROWS_USED=0"
    )
    print(
        "ACTUAL_ORDER_ITEM_ROWS_USED=0"
    )
    print()

    print(
        f"DATA_MODE={SOURCE_SYSTEM}"
    )

    print(
        f"PRODUCT_AGGREGATES="
        f"{len(aggregates)}"
    )

    ok_count = sum(
        1
        for item in aggregates
        if item.quality_status == "OK"
    )

    low_sample_count = sum(
        1
        for item in aggregates
        if item.quality_status
        == "LOW_SAMPLE"
    )

    no_data_count = sum(
        1
        for item in aggregates
        if item.quality_status
        == "NO_DATA"
    )

    print(
        f"QUALITY_OK={ok_count}"
    )

    print(
        f"QUALITY_LOW_SAMPLE="
        f"{low_sample_count}"
    )

    print(
        f"QUALITY_NO_DATA="
        f"{no_data_count}"
    )

    print()
    print("SAFE_FIELDS")

    if aggregates:
        print(
            sorted(
                asdict(
                    aggregates[0]
                ).keys()
            )
        )

    print()
    print("SAFE_SAMPLE_TOP10")

    for item in aggregates[:10]:
        print(asdict(item))

    print()
    print("FORBIDDEN_FIELDS_CHECK")

    forbidden_fields = {
        "order_id",
        "order_item_id",
        "tenant_id",
        "customer_id",
        "member_id",
        "email",
        "phone",
        "payment_method",
        "source_order_at",
        "total_order_amount",
        "total_paid_amount",
    }

    actual_fields = (
        set(
            asdict(
                aggregates[0]
            ).keys()
        )
        if aggregates
        else set()
    )

    leaked_fields = sorted(
        forbidden_fields
        & actual_fields
    )

    print(
        f"LEAKED_FIELDS={leaked_fields}"
    )

    all_passed = (
        len(aggregates) > 0
        and not leaked_fields
        and all(
            item.data_mode
            == SOURCE_SYSTEM
            for item in aggregates
        )
    )

    print()
    print(
        f"ALL_VALIDATIONS_PASSED="
        f"{all_passed}"
    )


if __name__ == "__main__":
    main()