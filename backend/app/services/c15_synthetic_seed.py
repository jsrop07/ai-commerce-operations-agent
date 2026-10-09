"""C15 standalone synthetic catalog and R09-shaped demand, with no I/O."""

from __future__ import annotations

import hashlib
import json
import random
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from scripts.r09_synthetic_order_preview import make_item_counts, random_order_date

TENANT_ID = uuid.UUID("35556e27-4200-4712-8ac5-e5a569a91c47")
SEED_VERSION = "demo-c15-20261006-v1"
SOURCE_SYSTEM = "SYNTHETIC_DEMO"
AS_OF = datetime(2026, 10, 4, 23, 59, tzinfo=UTC)
NAMESPACE = uuid.UUID("a692ea32-8a83-49c8-961e-27cf590684c3")
PRODUCT_NO_BASE = 9_150_000_000
CATEGORY_NO_BASE = 9_151_000_000

# Key, root, branch, leaf, naming stems. All names are newly authored demo copy.
LEAVES = (
    (
        "strategy",
        "Board Games",
        "Strategy & Adventure",
        "Strategy Games",
        ("왕국의 길", "항구 상인들", "산맥의 시장", "과수원 왕국", "강의 수도"),
    ),
    (
        "cooperative",
        "Board Games",
        "Strategy & Adventure",
        "Cooperative Games",
        (
            "우주 구조대",
            "등불지기들",
            "숲속 탐사대",
            "바다의 신호",
            "정상 수색대",
        ),
    ),
    (
        "adventure",
        "Board Games",
        "Strategy & Adventure",
        "Adventure Games",
        (
            "숨은 계곡의 비밀",
            "태엽 도시의 통로",
            "섬의 탐험가들",
            "수정 동굴의 지도",
            "하늘길 여행",
        ),
    ),
    (
        "family",
        "Board Games",
        "Casual Games",
        "Family Games",
        (
            "정원 산책",
            "아침 시장",
            "꼬마 발명가들",
            "무지개 건너기",
            "마을 축제",
        ),
    ),
    (
        "party",
        "Board Games",
        "Casual Games",
        "Party Games",
        ("비밀 신호", "재빠른 그림", "말의 소용돌이", "수상한 손님", "왁자지껄 한 줄"),
    ),
    (
        "trading",
        "Card Games",
        "Card Games",
        "Trading Card Games",
        ("태양의 순환", "숲의 전설", "도시의 챔피언", "밀물의 이야기", "별빛 리그"),
    ),
    (
        "deck",
        "Card Games",
        "Card Games",
        "Deck-Building Games",
        ("길드의 선택", "달빛 시장", "성채의 카드", "개척자의 덱", "경이의 기록관"),
    ),
    (
        "sleeves",
        "Card Games",
        "Card Accessories",
        "Sleeves",
        (
            "프리미엄 카드 슬리브",
            "무광 카드 슬리브",
            "투명 카드 슬리브",
            "컬러 카드 슬리브",
            "대회용 카드 슬리브",
        ),
    ),
    (
        "deckbox",
        "Card Games",
        "Card Accessories",
        "Deck Boxes",
        (
            "휴대용 덱 박스",
            "트윈 덱 케이스",
            "자석식 덱 박스",
            "소형 덱 케이스",
            "소장용 덱 박스",
        ),
    ),
    (
        "starter",
        "Tabletop Games",
        "Tactical Games",
        "Starter Sets",
        (
            "강철 선봉대 입문 세트",
            "변경 순찰대 입문 세트",
            "태엽 수비대 입문 세트",
            "북부 함대 입문 세트",
            "구리 군단 입문 세트",
        ),
    ),
    (
        "expansion",
        "Tabletop Games",
        "Tactical Games",
        "Expansion Sets",
        (
            "변경 전초기지 확장 세트",
            "폭풍 항구 확장 세트",
            "철의 능선 확장 세트",
            "푸른 변경 확장 세트",
            "노을 성채 확장 세트",
        ),
    ),
    (
        "miniatures",
        "Tabletop Games",
        "Tactical Games",
        "Miniature Sets",
        (
            "순찰자 미니어처 세트",
            "비행선 승무원 미니어처",
            "사막 정찰대 미니어처",
            "항구 수비대 미니어처",
            "계곡 수호자 미니어처",
        ),
    ),
    (
        "terrain",
        "Tabletop Games",
        "Scenery",
        "Terrain & Scenery",
        (
            "조립식 마을 지형 세트",
            "숲길 지형 세트",
            "무너진 탑 지형 세트",
            "돌다리 지형 세트",
            "항구 부두 지형 세트",
        ),
    ),
    (
        "acrylic",
        "Hobby & Painting",
        "Paint",
        "Acrylic Paint",
        (
            "아크릴 기본 색상 세트",
            "아크릴 원색 물감",
            "흙빛 아크릴 물감",
            "파스텔 아크릴 세트",
            "선명한 아크릴 물감",
        ),
    ),
    (
        "effect",
        "Hobby & Painting",
        "Paint",
        "Special Effect Paint",
        (
            "금속 효과 도료",
            "발광 효과 도료",
            "질감 효과 도료",
            "서리 효과 도료",
            "진주빛 효과 도료",
        ),
    ),
    (
        "air",
        "Hobby & Painting",
        "Paint",
        "Air Paint",
        (
            "에어브러시 색상 세트",
            "에어브러시 정밀 도료",
            "따뜻한 색 에어브러시 세트",
            "차가운 색 에어브러시 세트",
            "중간 색 에어브러시 세트",
        ),
    ),
    (
        "wash",
        "Hobby & Painting",
        "Paint",
        "Shade & Wash",
        (
            "부드러운 음영 워시",
            "짙은 색조 워시",
            "세피아 음영 워시",
            "차가운 그림자 워시",
            "따뜻한 명암 워시",
        ),
    ),
    (
        "brush",
        "Hobby & Painting",
        "Hobby Supplies",
        "Brushes",
        (
            "정밀 붓 세트",
            "세부 표현 붓 세트",
            "드라이브러시 세트",
            "초정밀 붓",
            "넓은 면 붓",
        ),
    ),
    (
        "tools",
        "Hobby & Painting",
        "Hobby Supplies",
        "Hobby Tools",
        (
            "취미 공구 세트",
            "정밀 니퍼",
            "모형 제작 칼 세트",
            "조립용 핀셋 세트",
            "공작용 커팅 매트",
        ),
    ),
    (
        "dice",
        "Accessories",
        "Gaming Accessories",
        "Dice",
        (
            "대리석 무늬 주사위 세트",
            "투명 주사위 세트",
            "무지개 주사위 세트",
            "금속 주사위 세트",
            "휴대용 주사위 꾸러미",
        ),
    ),
    (
        "playmat",
        "Accessories",
        "Gaming Accessories",
        "Playmats",
        (
            "숲속 플레이매트",
            "한밤의 플레이매트",
            "바다 플레이매트",
            "산맥 플레이매트",
            "도시 플레이매트",
        ),
    ),
    (
        "storage",
        "Accessories",
        "Gaming Accessories",
        "Storage",
        (
            "조립식 게임 정리함",
            "휴대용 게임 정리함",
            "토큰 보관 트레이",
            "소형 게임 케이스",
            "카드 보관함",
        ),
    ),
    (
        "tokens",
        "Accessories",
        "Gaming Accessories",
        "Tokens & Markers",
        (
            "나무 토큰 세트",
            "색상 마커 묶음",
            "점수 토큰 세트",
            "아크릴 마커 세트",
            "차례 표시 토큰 세트",
        ),
    ),
    (
        "puzzles",
        "Gifts & Puzzles",
        "Puzzles",
        "Jigsaw Puzzles",
        (
            "도시의 불빛 퍼즐",
            "정원 창가 퍼즐",
            "산속의 아침 퍼즐",
            "바다 지도 퍼즐",
            "마을의 밤 퍼즐",
        ),
    ),
)

# The English path segments remain private identity keys for existing category UUIDs.
# Only category_name is shown to users and translated here.
CATEGORY_DISPLAY_NAMES = {
    "Board Games": "보드게임",
    "Strategy & Adventure": "전략·모험 게임",
    "Strategy Games": "전략 게임",
    "Cooperative Games": "협력 게임",
    "Adventure Games": "모험 게임",
    "Casual Games": "가벼운 게임",
    "Family Games": "가족 게임",
    "Party Games": "파티 게임",
    "Card Games": "카드 게임",
    "Trading Card Games": "트레이딩 카드 게임",
    "Deck-Building Games": "덱 빌딩 게임",
    "Card Accessories": "카드 용품",
    "Sleeves": "카드 슬리브",
    "Deck Boxes": "덱 박스",
    "Tabletop Games": "테이블탑 게임",
    "Tactical Games": "전술 게임",
    "Starter Sets": "입문 세트",
    "Expansion Sets": "확장 세트",
    "Miniature Sets": "미니어처 세트",
    "Scenery": "지형 모형",
    "Terrain & Scenery": "지형·배경 모형",
    "Hobby & Painting": "취미·도색 용품",
    "Paint": "도료",
    "Acrylic Paint": "아크릴 도료",
    "Special Effect Paint": "특수 효과 도료",
    "Air Paint": "에어브러시 도료",
    "Shade & Wash": "음영·워시",
    "Hobby Supplies": "취미 공예 용품",
    "Brushes": "붓",
    "Hobby Tools": "취미 공구",
    "Accessories": "게임 용품",
    "Gaming Accessories": "게임 보조 용품",
    "Dice": "주사위",
    "Playmats": "플레이매트",
    "Storage": "보관 용품",
    "Tokens & Markers": "토큰·마커",
    "Gifts & Puzzles": "선물·퍼즐",
    "Puzzles": "퍼즐",
    "Jigsaw Puzzles": "직소 퍼즐",
    "PRE-ORDER": "예약 판매",
}
CATEGORY_DISPLAY_PATH_OVERRIDES = {("Card Games", "Card Games"): "카드 게임 장르"}

DEPARTMENT_COUNTS = {
    "Board Games": 35,
    "Card Games": 20,
    "Tabletop Games": 32,
    "Hobby & Painting": 28,
    "Accessories": 25,
    "Gifts & Puzzles": 7,
}
PRICES = (
    [Decimal(8000 + i * 400) for i in range(26)]
    + [Decimal(32000 + i * 1100) for i in range(16)]
    + [Decimal(55000 + i * 500) for i in range(34)]
    + [Decimal(72000 + i * 700) for i in range(37)]
    + [Decimal(110000 + i * 3000) for i in range(21)]
    + [Decimal(205000 + i * 12000) for i in range(16)]
)
STATUS_COUNTS = (
    (104, "T", "T", False),
    (36, "T", "T", True),
    (7, "F", "F", True),
    (2, "F", "T", True),
    (1, "F", "T", False),
)


def identity(kind: str, key: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, f"{TENANT_ID}:{SEED_VERSION}:{kind}:{key}")


@dataclass(frozen=True)
class SeedBundle:
    categories: list[dict]
    products: list[dict]
    product_categories: list[dict]
    variants: list[dict]
    orders: list[dict]
    order_items: list[dict]
    manifest: dict


def _categories() -> tuple[list[dict], dict[tuple[str, ...], dict]]:
    paths = []
    for _, root, branch, leaf, _ in LEAVES:
        for path in ((root,), (root, branch), (root, branch, leaf)):
            if path not in paths:
                paths.append(path)
    paths.append(("PRE-ORDER",))
    rows, by_path = [], {}
    for sequence, path in enumerate(paths, 1):
        row = dict(
            id=identity("category", "/".join(path)),
            tenant_id=TENANT_ID,
            cafe24_category_no=CATEGORY_NO_BASE + sequence,
            category_name=CATEGORY_DISPLAY_PATH_OVERRIDES.get(
                path, CATEGORY_DISPLAY_NAMES[path[-1]]
            ),
            category_depth=len(path),
            parent_category_id=by_path[path[:-1]]["id"] if len(path) > 1 else None,
            source_as_of=AS_OF,
        )
        rows.append(row)
        by_path[path] = row
    return rows, by_path


def _catalog():
    categories, by_path = _categories()
    groups = {name: [] for name in DEPARTMENT_COUNTS}
    for leaf in LEAVES:
        groups[leaf[1]].append(leaf)
    chosen = []
    for department, count in DEPARTMENT_COUNTS.items():
        leaves = groups[department]
        for i in range(count):
            leaf = leaves[i % len(leaves)]
            cycle = i // len(leaves)
            base = leaf[4][cycle % len(leaf[4])]
            edition = ("", " 플러스", " 프리미엄", " 한정판")[
                cycle // len(leaf[4])
            ]
            chosen.append((department, leaf, base + edition))
    # Three intentionally uncategorized products are additional catalog entries.
    for name in ("수수께끼 취미 꾸러미", "주말 탐험 상자", "상상력 선물 꾸러미"):
        chosen.append((None, None, name))
    assert len(chosen) == 150 and len({c[2] for c in chosen}) == 150
    rng = random.Random(20261006)
    prices = PRICES[:]
    statuses = [
        (display, selling, soldout)
        for count, display, selling, soldout in STATUS_COUNTS
        for _ in range(count)
    ]
    rng.shuffle(prices)
    rng.shuffle(statuses)
    products, relations, variants = [], [], []
    preorder_indexes = {8, 29, 47, 64, 82, 104, 132}
    extra_indexes = {21, 59, 118}
    for i, (department, leaf, name) in enumerate(chosen):
        n = i + 1
        product_id = identity("product", str(n))
        display, selling, soldout = statuses[i]
        products.append(
            dict(
                id=product_id,
                tenant_id=TENANT_ID,
                cafe24_product_no=PRODUCT_NO_BASE + n,
                product_name=name,
                product_code=f"DEMO-P-{n:04d}",
                custom_product_code=f"DEMO-CUSTOM-{n:04d}" if n <= 146 else None,
                sale_price=prices[i],
                display_status=display,
                selling_status=selling,
                sold_out=soldout,
                operational=True,
                source_as_of=AS_OF,
            )
        )
        if leaf:
            root, branch, leaf_name = leaf[1:4]
            cat = by_path[(root, branch, leaf_name)]
            relations.append(
                dict(tenant_id=TENANT_ID, product_id=product_id, category_id=cat["id"])
            )
        if i in preorder_indexes:
            relations.append(
                dict(
                    tenant_id=TENANT_ID,
                    product_id=product_id,
                    category_id=by_path[("PRE-ORDER",)]["id"],
                )
            )
        if i in extra_indexes:
            # A second, distinct leaf in the same department.
            alt = next(x for x in groups[department] if x[0] != leaf[0])
            relations.append(
                dict(
                    tenant_id=TENANT_ID, product_id=product_id, category_id=by_path[alt[1:4]]["id"]
                )
            )
        # Twenty products have an alternate SKU; six of those have a third.
        # The choices span board, card, tabletop, paint and accessories.
        variant_count = 1 + (i in set(range(0, 140, 7))) + (i in {0, 28, 56, 84, 112, 133})
        for option in range(variant_count):
            code = f"DEMO-SKU-{n:04d}-{option + 1:02d}"
            variants.append(
                dict(
                    id=identity("variant", code),
                    tenant_id=TENANT_ID,
                    product_id=product_id,
                    variant_code=code,
                    option_name=("기본형", "다른 구성", "고급형")[option],
                    barcode=None,
                    variant_status="ACTIVE",
                )
            )
    return categories, products, relations, variants, preorder_indexes


def _orders(products, variants, preorder_indexes):
    rng = random.Random(20261004)
    counts = make_item_counts(rng)
    preorder_orders = set(rng.sample(range(600), 100))
    hot = [i for i in range(0, 147, 10) if i not in preorder_indexes][:15]
    warm = [i for i in range(147) if i not in hot and i not in preorder_indexes][:38] + sorted(
        preorder_indexes
    )
    # Fill the middle group with 45 unique products; the remainder are the tail.
    warm = list(dict.fromkeys(warm))[:45]
    tail = [i for i in range(150) if i not in hot and i not in warm]
    assert len(hot) == 15 and len(warm) == 45 and len(tail) == 90

    def spread(indices, count):
        return [indices[i % len(indices)] for i in range(count)]

    pre = spread(sorted(preorder_indexes), 100)
    regular_warm = [i for i in warm if i not in preorder_indexes]
    slots = spread(hot, 700) + spread(regular_warm, 540) + spread(tail, 360)
    rng.shuffle(slots)
    # Exactly 92 lines get quantity 2: top 50, middle 40, tail 2.
    bonus_remaining = {"hot": 50, "warm": 40, "tail": 2}
    group_of = {i: "hot" for i in hot} | {i: "warm" for i in warm} | {i: "tail" for i in tail}
    orders, items = [], []
    order_indices = list(range(600))
    rng.shuffle(order_indices)
    unpaid = set(order_indices[:33])
    canceled_yes = set(order_indices[33:66])
    canceled_unknown = set(order_indices[66:80])
    paid = ["F" if i in unpaid else "T" for i in range(600)]
    canceled = [
        "T" if i in canceled_yes else "M" if i in canceled_unknown else "F" for i in range(600)
    ]
    remaining = order_indices[80:]
    shipping = ["" for _ in range(600)]
    for i in unpaid | canceled_yes:
        shipping[i] = "F"
    for i in canceled_unknown:
        shipping[i] = "M"
    for i in remaining[:31]:
        shipping[i] = "F"
    for i in remaining[31:71]:
        shipping[i] = "M"
    for i in remaining[71:]:
        shipping[i] = "T"
    variant_by_product = {}
    for variant in variants:
        variant_by_product.setdefault(variant["product_id"], variant)
    item_seq = 0
    for index, count in enumerate(counts):
        order_key = f"C15-{SEED_VERSION}-ORD-{index + 1:06d}"
        order_id = identity("order", str(index + 1))
        date = random_order_date(rng)
        order_items = []
        used = set()
        if index in preorder_orders:
            product_index = pre.pop()
            used.add(product_index)
            order_items.append(product_index)
        for _ in range(count - len(order_items)):
            for position, candidate in enumerate(slots):
                if candidate not in used:
                    product_index = slots.pop(position)
                    break
            else:
                raise AssertionError("insufficient distinct catalog products")
            used.add(product_index)
            order_items.append(product_index)
        total = Decimal(0)
        for product_index in order_items:
            product = products[product_index]
            item_seq += 1
            group = group_of[product_index]
            quantity = 2 if bonus_remaining[group] > 0 else 1
            bonus_remaining[group] -= quantity - 1
            total += product["sale_price"] * quantity
            items.append(
                dict(
                    id=identity("item", str(item_seq)),
                    tenant_id=TENANT_ID,
                    order_id=order_id,
                    external_order_item_id=f"C15-{SEED_VERSION}-ITEM-{item_seq:06d}",
                    external_product_no=product["cafe24_product_no"],
                    product_id=product["id"],
                    product_variant_id=variant_by_product[product["id"]]["id"],
                    source_product_name=product["product_name"],
                    source_product_name_with_option=None,
                    quantity=quantity,
                    source_sale_price=product["sale_price"],
                )
            )
        orders.append(
            dict(
                id=order_id,
                tenant_id=TENANT_ID,
                external_order_id=order_key,
                source_system=SOURCE_SYSTEM,
                paid=paid[index],
                shipping_status=shipping[index],
                canceled=canceled[index],
                total_order_amount=total,
                total_paid_amount=total if paid[index] == "T" else Decimal(0),
                payment_type=None,
                payment_method=None,
                source_order_at=date,
            )
        )
    assert not slots and not pre and not any(bonus_remaining.values())
    return orders, items, (hot, warm, tail)


def _canonical(value):
    if isinstance(value, (uuid.UUID, Decimal)):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(type(value).__name__)


def generate_seed() -> SeedBundle:
    categories, products, relations, variants, preorder = _catalog()
    orders, items, popularity = _orders(products, variants, preorder)
    payload = dict(
        categories=categories,
        products=products,
        product_categories=relations,
        variants=variants,
        orders=orders,
        order_items=items,
    )
    seed_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=_canonical, separators=(",", ":")).encode()
    ).hexdigest()
    counts = {key: len(value) for key, value in payload.items()}
    manifest = dict(
        seed_version=SEED_VERSION,
        seed_hash=seed_hash,
        tenant_id=str(TENANT_ID),
        source_system=SOURCE_SYSTEM,
        data_mode=SOURCE_SYSTEM,
        as_of=AS_OF.isoformat(),
        counts=counts,
        hero_product_id=str(products[8]["id"]),
        hero_variant_id=str(
            next(v["id"] for v in variants if v["product_id"] == products[8]["id"])
        ),
        hero_future_fact={"required": 5, "secured": 1, "confirmed_incoming": 2, "shortage": 2},
        popularity_groups={
            "hot": len(popularity[0]),
            "warm": len(popularity[1]),
            "tail": len(popularity[2]),
        },
    )
    bundle = SeedBundle(**payload, manifest=manifest)
    validate_seed(bundle)
    return bundle


def validate_seed(bundle: SeedBundle) -> None:
    b = bundle
    assert [len(b.products), len(b.orders), len(b.order_items), len(b.variants)] == [
        150,
        600,
        1700,
        176,
    ]
    assert sum(x["quantity"] for x in b.order_items) == 1792
    for rows in (b.categories, b.products, b.variants, b.orders, b.order_items):
        assert len({row["id"] for row in rows}) == len(rows)
        assert all(row["tenant_id"] == TENANT_ID for row in rows)
    category_ids = {r["id"] for r in b.categories}
    product_ids = {r["id"] for r in b.products}
    variant_map = {r["id"]: r["product_id"] for r in b.variants}
    order_ids = {r["id"] for r in b.orders}
    assert all(
        r["parent_category_id"] in category_ids for r in b.categories if r["parent_category_id"]
    )
    assert all(
        r["product_id"] in product_ids and r["category_id"] in category_ids
        for r in b.product_categories
    )
    assert all(r["product_id"] in product_ids for r in b.variants)
    assert all(
        r["order_id"] in order_ids
        and r["product_id"] in product_ids
        and variant_map[r["product_variant_id"]] == r["product_id"]
        for r in b.order_items
    )
    assert Counter(r["paid"] for r in b.orders) == {"T": 567, "F": 33}
    assert Counter(r["shipping_status"] for r in b.orders) == {"F": 97, "T": 449, "M": 54}
    assert Counter(r["canceled"] for r in b.orders) == {"T": 33, "F": 553, "M": 14}
    assert all(r["source_system"] == SOURCE_SYSTEM for r in b.orders)
    assert len(product_ids - {r["product_id"] for r in b.product_categories}) == 3
    assert len({r["external_order_id"] for r in b.orders}) == 600
    assert len({r["external_order_item_id"] for r in b.order_items}) == 1700
