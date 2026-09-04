import argparse
import hashlib
import json
import random
from pathlib import Path
from typing import Any
import hmac
import os

GENERATOR_VERSION = "synthetic-generator.v0.1"

INTENT_TEMPLATES = {
    "PRODUCT_INFO": [
        "{product}은 몇 명이서 플레이할 수 있나요?",
        "{product}의 플레이 시간은 어느 정도인가요?",
    ],
    "COMPATIBILITY": [
        "{expansion}만으로 플레이 가능한가요?",
        "{expansion}이 {product}과 호환되나요?",
    ],
    "STOCK_AVAILABILITY": [
        "{product} 지금 재고 있나요?",
        "{product} 오늘 구매 가능한가요?",
    ],
    "RESTOCK": [
        "{product} 재입고 예정이 있나요?",
        "{product}은 언제 다시 들어오나요?",
    ],
    "DELIVERY": [
        "{product} 주문하면 언제 출고되나요?",
        "{product} 이번 주 안에 받을 수 있나요?",
    ],
    "RESERVATION_PREORDER": [
        "{product} 예약 구매 가능한가요?",
        "{product} 예약분은 언제 출고되나요?",
    ],
}


PRODUCTS = [
    {
        "product_id": "demo_product_001",
        "name": "별빛 탐험대",
        "category": "BOARD_GAME",
    },
    {
        "product_id": "demo_product_002",
        "name": "구름 도시",
        "category": "BOARD_GAME",
    },
    {
        "product_id": "demo_product_003",
        "name": "황금 숲",
        "category": "BOARD_GAME",
    },
]


EXPANSIONS = [
    {
        "product_id": "demo_expansion_001",
        "name": "별빛 탐험대: 붉은 달",
        "relation": "EXPANSION_OF",
        "target_product_id": "demo_product_001",
    },
    {
        "product_id": "demo_expansion_002",
        "name": "구름 도시: 북쪽 항로",
        "relation": "EXPANSION_OF",
        "target_product_id": "demo_product_002",
    },
]


def stable_hash(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()


def generate_record(
    rng: random.Random,
    index: int,
) -> dict[str, Any]:
    intent = rng.choice(sorted(INTENT_TEMPLATES))

    product = rng.choice(PRODUCTS)
    expansion = rng.choice(EXPANSIONS)

    template = rng.choice(INTENT_TEMPLATES[intent])

    text = template.format(
        product=product["name"],
        expansion=expansion["name"],
    )

    entities = [
        {
            "type": "PRODUCT",
            "value": product["name"],
            "canonical_id": product["product_id"],
        }
    ]

    relations: list[dict[str, str]] = []

    if intent == "COMPATIBILITY":
        entities.append(
            {
                "type": "PRODUCT",
                "value": expansion["name"],
                "canonical_id": expansion["product_id"],
            }
        )

        relations.append(
            {
                "relation_type": expansion["relation"],
                "from_id": expansion["product_id"],
                "to_id": expansion["target_product_id"],
            }
        )

    return {
        "record_id": f"syn_{index:04d}",
        "source": "SYNTHETIC",
        "generator_version": GENERATOR_VERSION,
        "intent": intent,
        "text": text,
        "entities": entities,
        "relations": relations,
        "human_validated": False,
    }


def generate_dataset(
    seed: int,
    count: int,
) -> dict[str, Any]:
    if count <= 0:
        raise ValueError("count must be positive")

    rng = random.Random(seed)

    records = [
        generate_record(
            rng=rng,
            index=index,
        )
        for index in range(1, count + 1)
    ]

    payload = {
        "schema_version": "synthetic-dataset.v0.1",
        "generator_version": GENERATOR_VERSION,
        "seed": seed,
        "count": count,
        "records": records,
    }

    payload["dataset_hash"] = stable_hash(records)

    return payload


def find_private_overlap(
    payload: dict[str, Any],
    forbidden_strings: list[str],
) -> list[str]:
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
    )

    return sorted(
        value
        for value in forbidden_strings
        if value and value in serialized
    )


def load_forbidden_strings(
    path: Path,
) -> list[str]:
    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        payload = json.load(file)

    return payload["forbidden_strings"]


def write_dataset(
    payload: dict[str, Any],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            payload,
            file,
            ensure_ascii=False,
            indent=2,
        )


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
    )

    parser.add_argument(
        "--count",
        type=int,
        default=20,
    )

    parser.add_argument(
        "--private-fixture",
        type=Path,
        default=Path(
            "ai/tests/fixtures/"
            "private_unique_strings_fixture.json"
        ),
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "artifacts/experiments/day02/"
            "synthetic_seed_42.json"
        ),
    )

    args = parser.parse_args()

    dataset = generate_dataset(
        seed=args.seed,
        count=args.count,
    )

    forbidden_strings = load_forbidden_strings(
        args.private_fixture
    )

    overlaps = find_private_overlap(
        dataset,
        forbidden_strings,
    )

    if overlaps:
        print(
            "SYNTHETIC_PRIVATE_OVERLAP_FAILED "
            f"count={len(overlaps)}"
        )

        for overlap in overlaps:
            print(overlap)

        return 1

    write_dataset(
        dataset,
        args.output,
    )

    print(
        "SYNTHETIC_GENERATION_OK "
        f"seed={args.seed} "
        f"count={args.count} "
        f"private_overlap=0"
    )

    print(
        f"DATASET_HASH={dataset['dataset_hash']}"
    )

    print(
        f"OUTPUT={args.output}"
    )

    return 0

def normalize_overlap_value(value: str) -> str:
    return " ".join(
        value.strip().lower().split()
    )


def fingerprint_value(
    value: str,
    secret_key: str,
) -> str:
    normalized = normalize_overlap_value(value)

    return hmac.new(
        secret_key.encode("utf-8"),
        normalized.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def build_private_fingerprint_set(
    unique_strings: list[str],
    secret_key: str,
) -> set[str]:
    return {
        fingerprint_value(
            value,
            secret_key,
        )
        for value in unique_strings
        if isinstance(value, str)
        and value.strip()
    }


def extract_synthetic_strings(
    payload: dict[str, Any],
) -> set[str]:
    values: set[str] = set()

    for record in payload["records"]:
        text = record.get("text")

        if isinstance(text, str):
            values.add(text)

        for entity in record.get(
            "entities",
            [],
        ):
            value = entity.get("value")

            if isinstance(value, str):
                values.add(value)

    return values


def find_private_fingerprint_overlap(
    payload: dict[str, Any],
    private_unique_strings: list[str],
    secret_key: str,
) -> list[str]:
    private_fingerprints = build_private_fingerprint_set(
        private_unique_strings,
        secret_key,
    )

    synthetic_strings = extract_synthetic_strings(
        payload
    )

    overlapping_hashes = []

    for value in synthetic_strings:
        fingerprint = fingerprint_value(
            value,
            secret_key,
        )

        if fingerprint in private_fingerprints:
            overlapping_hashes.append(
                fingerprint
            )

    return sorted(
        set(overlapping_hashes)
    )

if __name__ == "__main__":
    raise SystemExit(main())