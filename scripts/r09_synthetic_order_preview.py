from __future__ import annotations

import random
import subprocess
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal


RANDOM_SEED = 20261004

ORDER_COUNT = 600
TARGET_ITEM_COUNT = 1700
CANDIDATE_PRODUCT_COUNT = 500

PREORDER_CATEGORY_NO = 56

END_AT = datetime(2026, 10, 4, 23, 59, tzinfo=UTC)
START_AT = END_AT - timedelta(days=89)


@dataclass(frozen=True)
class Product:
    id: str
    product_no: int
    name: str
    sale_price: Decimal
    is_preorder: bool


@dataclass
class SyntheticOrderItem:
    external_order_item_id: str
    product: Product
    quantity: int
    sale_price: Decimal


@dataclass
class SyntheticOrder:
    external_order_id: str
    source_order_at: datetime
    paid: str
    shipping_status: str
    canceled: str
    items: list[SyntheticOrderItem]

    @property
    def total_amount(self) -> Decimal:
        return sum(
            (item.sale_price * item.quantity for item in self.items),
            Decimal("0"),
        )


def run_psql(sql: str) -> str:
    cmd = [
        "docker",
        "exec",
        "commerce-postgres-test",
        "psql",
        "-U",
        "commerce_test",
        "-d",
        "commerce_ops",
        "-At",
        "-F",
        "\t",
        "-c",
        sql,
    ]

    return subprocess.check_output(
        cmd,
        text=True,
        encoding="utf-8",
    )


def load_products() -> list[Product]:
    sql = f"""
SELECT
    p.id,
    p.cafe24_product_no,
    replace(replace(p.product_name, E'\\t', ' '), E'\\n', ' '),
    p.sale_price,
    CASE WHEN EXISTS (
        SELECT 1
        FROM catalog.product_categories pc
        JOIN catalog.categories c
          ON c.tenant_id = pc.tenant_id
         AND c.id = pc.category_id
        WHERE pc.tenant_id = p.tenant_id
          AND pc.product_id = p.id
          AND c.cafe24_category_no = {PREORDER_CATEGORY_NO}
    )
    THEN 'T'
    ELSE 'F'
    END
FROM catalog.products p
WHERE p.operational = true
  AND p.sale_price IS NOT NULL
  AND p.sale_price > 0
ORDER BY p.cafe24_product_no;
"""

    raw = run_psql(sql)

    products: list[Product] = []

    for line in raw.splitlines():
        parts = line.split("\t")

        if len(parts) != 5:
            continue

        product_id, product_no, name, sale_price, preorder = parts

        products.append(
            Product(
                id=product_id,
                product_no=int(product_no),
                name=name,
                sale_price=Decimal(sale_price),
                is_preorder=preorder == "T",
            )
        )

    return products


def select_candidate_products(
    products: list[Product],
    rng: random.Random,
) -> list[Product]:
    preorder = [p for p in products if p.is_preorder]
    normal = [p for p in products if not p.is_preorder]

    normal_count = CANDIDATE_PRODUCT_COUNT - len(preorder)

    selected_normal = rng.sample(
        normal,
        min(normal_count, len(normal)),
    )

    return preorder + selected_normal


def build_weight_map(
    candidates: list[Product],
    rng: random.Random,
) -> tuple[
    dict[int, float],
    set[int],
    set[int],
    set[int],
]:
    shuffled = candidates[:]
    rng.shuffle(shuffled)

    # 실제 판매순위를 복사하지 않는다.
    # Synthetic 내부에서만 새로운 인기그룹을 만든다.
    hot = {p.product_no for p in shuffled[:40]}
    warm = {p.product_no for p in shuffled[40:150]}

    remaining = shuffled[150:]

    # 최근 10일 상승 / 하락 시나리오 상품도 새로 선정
    surge = {
        p.product_no
        for p in rng.sample(
            remaining,
            min(8, len(remaining)),
        )
    }

    remaining_for_decline = [
        p for p in remaining
        if p.product_no not in surge
    ]

    decline = {
        p.product_no
        for p in rng.sample(
            remaining_for_decline,
            min(8, len(remaining_for_decline)),
        )
    }

    weights: dict[int, float] = {}

    for product in candidates:
        if product.product_no in hot:
            weights[product.product_no] = 2.6
        elif product.product_no in warm:
            weights[product.product_no] = 1.5
        else:
            weights[product.product_no] = 1.0

    return weights, surge, decline, hot


def random_order_date(rng: random.Random) -> datetime:
    seconds = int((END_AT - START_AT).total_seconds())

    return START_AT + timedelta(
        seconds=rng.randint(0, seconds)
    )


def item_quantity(rng: random.Random) -> int:
    # 실제 aggregate에서 qty / item ≈ 1.05였던 분포의 모양만 참고.
    x = rng.random()

    if x < 0.95:
        return 1

    if x < 0.99:
        return 2

    return 3


def choose_product(
    candidates: list[Product],
    base_weights: dict[int, float],
    order_date: datetime,
    surge: set[int],
    decline: set[int],
    rng: random.Random,
    *,
    preorder_only: bool = False,
) -> Product:
    if preorder_only:
        pool = [
            p for p in candidates
            if p.is_preorder
        ]
    else:
        pool = [
            p for p in candidates
            if not p.is_preorder
        ]

    recent_start = END_AT - timedelta(days=9)
    previous_start = END_AT - timedelta(days=19)

    weights: list[float] = []

    for product in pool:
        weight = base_weights[product.product_no]

        # Synthetic recent surge
        if product.product_no in surge:
            if order_date >= recent_start:
                weight *= 5.0
            elif order_date >= previous_start:
                weight *= 1.3

        # Synthetic recent decline
        if product.product_no in decline:
            if order_date >= recent_start:
                weight *= 0.2
            elif order_date >= previous_start:
                weight *= 3.0

        weights.append(weight)

    return rng.choices(
        population=pool,
        weights=weights,
        k=1,
    )[0]


def make_item_counts(
    rng: random.Random,
) -> list[int]:
    # 일단 600주문에 1~5개 품목을 배정한다.
    counts = [
        rng.choices(
            [1, 2, 3, 4, 5],
            weights=[15, 25, 35, 18, 7],
            k=1,
        )[0]
        for _ in range(ORDER_COUNT)
    ]

    # 목표 item 수에 정확히 맞춘다.
    current = sum(counts)

    while current < TARGET_ITEM_COUNT:
        idx = rng.randrange(len(counts))

        if counts[idx] < 5:
            counts[idx] += 1
            current += 1

    while current > TARGET_ITEM_COUNT:
        idx = rng.randrange(len(counts))

        if counts[idx] > 1:
            counts[idx] -= 1
            current -= 1

    return counts


def build_orders(
    candidates: list[Product],
    weights: dict[int, float],
    surge: set[int],
    decline: set[int],
    rng: random.Random,
) -> list[SyntheticOrder]:
    item_counts = make_item_counts(rng)

    orders: list[SyntheticOrder] = []

    # 600개 중 100개 주문은 반드시 PRE-ORDER 상품을 하나 이상 포함
    preorder_order_indexes = set(
        rng.sample(
            range(ORDER_COUNT),
            100,
        )
    )

    item_sequence = 1

    for order_index in range(ORDER_COUNT):
        order_date = random_order_date(rng)

        item_count = item_counts[order_index]

        items: list[SyntheticOrderItem] = []
        used_product_nos: set[int] = set()

        for item_index in range(item_count):
            force_preorder = (
                order_index in preorder_order_indexes
                and item_index == 0
            )

            # 같은 주문에서 같은 상품이 중복 row로 들어가는 것은 피한다.
            for _ in range(100):
                product = choose_product(
                    candidates,
                    weights,
                    order_date,
                    surge,
                    decline,
                    rng,
                    preorder_only=force_preorder,
                )

                if product.product_no not in used_product_nos:
                    break
            else:
                continue

            used_product_nos.add(product.product_no)

            items.append(
                SyntheticOrderItem(
                    external_order_item_id=(
                        f"SYN-ITEM-{item_sequence:06d}"
                    ),
                    product=product,
                    quantity=item_quantity(rng),
                    sale_price=product.sale_price,
                )
            )

            item_sequence += 1

        # 상태는 전부 synthetic.
        paid = "T" if rng.random() < 0.96 else "F"

        cancel_roll = rng.random()

        if cancel_roll < 0.05:
            canceled = "T"
        elif cancel_roll < 0.08:
            canceled = "M"
        else:
            canceled = "F"

        age_days = (END_AT - order_date).days

        if paid == "F":
            shipping_status = "F"
        elif canceled == "T":
            shipping_status = "F"
        elif canceled == "M":
            shipping_status = "M"
        elif age_days <= 3:
            shipping_status = rng.choices(
                ["F", "M", "T"],
                weights=[55, 30, 15],
                k=1,
            )[0]
        elif age_days <= 10:
            shipping_status = rng.choices(
                ["F", "M", "T"],
                weights=[15, 25, 60],
                k=1,
            )[0]
        else:
            shipping_status = rng.choices(
                ["F", "M", "T"],
                weights=[3, 7, 90],
                k=1,
            )[0]

        orders.append(
            SyntheticOrder(
                external_order_id=(
                    f"SYN-ORD-{order_index + 1:06d}"
                ),
                source_order_at=order_date,
                paid=paid,
                shipping_status=shipping_status,
                canceled=canceled,
                items=items,
            )
        )

    return orders


def print_preview(
    products: list[Product],
    candidates: list[Product],
    orders: list[SyntheticOrder],
    hot: set[int],
    surge: set[int],
    decline: set[int],
) -> None:
    items = [
        item
        for order in orders
        for item in order.items
    ]

    sold_qty = Counter()

    for item in items:
        sold_qty[item.product.product_no] += item.quantity

    product_by_no = {
        p.product_no: p
        for p in candidates
    }

    total_qty = sum(sold_qty.values())

    preorder_items = sum(
        1
        for item in items
        if item.product.is_preorder
    )

    preorder_orders = sum(
        1
        for order in orders
        if any(item.product.is_preorder for item in order.items)
    )

    unique_sold = len(sold_qty)

    top_50_qty = sum(
        qty
        for _, qty in sold_qty.most_common(50)
    )

    print("R09_SYNTHETIC_ORDER_PREVIEW")
    print()
    print("DB_WRITE_COUNT=0")
    print("ACTUAL_ORDER_ROWS_USED=0")
    print("ACTUAL_ORDER_ITEM_ROWS_USED=0")
    print()

    print(f"CATALOG_PRODUCTS_AVAILABLE={len(products)}")
    print(f"CANDIDATE_PRODUCTS={len(candidates)}")
    print(f"SYNTHETIC_ORDERS={len(orders)}")
    print(f"SYNTHETIC_ORDER_ITEMS={len(items)}")
    print(f"SYNTHETIC_TOTAL_QUANTITY={total_qty}")
    print(f"UNIQUE_SYNTHETIC_SOLD_PRODUCTS={unique_sold}")
    print(f"PREORDER_ORDERS={preorder_orders}")
    print(f"PREORDER_ORDER_ITEMS={preorder_items}")

    print(
        "AVG_ITEMS_PER_ORDER="
        f"{len(items) / len(orders):.3f}"
    )

    print(
        "AVG_QUANTITY_PER_ITEM="
        f"{total_qty / len(items):.3f}"
    )

    print(
        "TOP50_QUANTITY_SHARE="
        f"{(top_50_qty / total_qty * 100):.2f}%"
    )

    print(f"HOT_PRODUCT_COUNT={len(hot)}")
    print(f"SURGE_PRODUCT_COUNT={len(surge)}")
    print(f"DECLINE_PRODUCT_COUNT={len(decline)}")

    print()
    print("ORDER_STATUS_COUNTS")
    print(
        "paid=",
        dict(Counter(order.paid for order in orders)),
    )
    print(
        "shipping_status=",
        dict(
            Counter(
                order.shipping_status
                for order in orders
            )
        ),
    )
    print(
        "canceled=",
        dict(
            Counter(
                order.canceled
                for order in orders
            )
        ),
    )

    print()
    print("TOP_20_SYNTHETIC_PRODUCTS")

    for rank, (product_no, qty) in enumerate(
        sold_qty.most_common(20),
        start=1,
    ):
        product = product_by_no[product_no]

        labels: list[str] = []

        if product_no in hot:
            labels.append("HOT")
        if product_no in surge:
            labels.append("SURGE")
        if product_no in decline:
            labels.append("DECLINE")
        if product.is_preorder:
            labels.append("PREORDER")

        print(
            f"{rank:02d}. "
            f"product_no={product.product_no} "
            f"qty={qty} "
            f"name={product.name} "
            f"labels={','.join(labels) or '-'}"
        )

    print()
    print("SYNTHETIC_ORDER_SAMPLE_5")

    for order in orders[:5]:
        print(
            order.external_order_id,
            order.source_order_at.isoformat(),
            f"items={len(order.items)}",
            f"total={order.total_amount}",
            f"paid={order.paid}",
            f"shipping={order.shipping_status}",
            f"canceled={order.canceled}",
        )

        for item in order.items:
            print(
                "  ",
                item.external_order_item_id,
                f"product_no={item.product.product_no}",
                f"qty={item.quantity}",
                f"price={item.sale_price}",
                f"name={item.product.name}",
            )


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

    print_preview(
        products,
        candidates,
        orders,
        hot,
        surge,
        decline,
    )


if __name__ == "__main__":
    main()