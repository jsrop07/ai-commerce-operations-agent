from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

SNAPSHOT_PATH = (
    ROOT
    / "artifacts"
    / "experiments"
    / "OPS-R07-PRE"
    / "private"
    / "product"
    / "product_safe_snapshot.jsonl"
)

OUTPUT_DIR = (
    ROOT
    / "artifacts"
    / "experiments"
    / "OPS-RAG-SCALE-01"
    / "private"
)

DRAFT_PATH = OUTPUT_DIR / "actual_product_dev24_draft.jsonl"
REVIEW_PATH = OUTPUT_DIR / "actual_product_dev24_review.csv"
MANIFEST_PATH = OUTPUT_DIR / "actual_product_dev24_manifest.json"

SEED = "R07-PRE-E08-20260929"

EXPECTED_SNAPSHOT_SHA256 = (
    "6438ad2ca5a21d4d30b1bf5bacbeb186"
    "679df1c16369fbc8eacc9cca3f1a9892"
)

EXPECTED_MANIFEST_SHA256 = (
    "4933b41ef73ca05714af08e5544c109e"
    "0502c043457e942f04ff976067539da9"
)

EXPECTED_RECORD_VERSION = (
    "product-file-set-sha256:"
    "fe4737287d33d8ca58fdfd15c0650e35"
    "bfbdbb54db9a83bef7798e8b7b4d6d7c"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_snapshot() -> list[dict]:
    actual_hash = sha256_file(SNAPSHOT_PATH)
    if actual_hash != EXPECTED_SNAPSHOT_SHA256:
        raise RuntimeError(
            "snapshot hash mismatch: "
            f"{actual_hash}"
        )

    rows = [
        json.loads(line)
        for line in SNAPSHOT_PATH.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]

    if len(rows) != 2167:
        raise RuntimeError(
            f"unexpected snapshot count: {len(rows)}"
        )

    versions = {
        row.get("version")
        for row in rows
    }
    if versions != {EXPECTED_RECORD_VERSION}:
        raise RuntimeError(
            f"unexpected record versions: {versions}"
        )

    qualities = {
        row.get("quality_status")
        for row in rows
    }
    if qualities != {
        "APPROVED_FOR_R07_PRE_PRODUCT_EVAL"
    }:
        raise RuntimeError(
            f"unexpected quality status: {qualities}"
        )

    return rows


def stable_key(row: dict, salt: str) -> str:
    raw = (
        f"{SEED}|{salt}|{row['product_no']}"
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def choose(
    rows: list[dict],
    count: int,
    salt: str,
    used: set[int],
) -> list[dict]:
    candidates = [
        row for row in rows
        if int(row["product_no"]) not in used
    ]
    candidates.sort(
        key=lambda row: stable_key(row, salt)
    )

    selected = candidates[:count]
    if len(selected) != count:
        raise RuntimeError(
            f"not enough candidates for {salt}"
        )

    for row in selected:
        used.add(int(row["product_no"]))

    return selected


def normalize(text: str) -> str:
    return re.sub(
        r"\s+",
        " ",
        re.sub(
            r"[^0-9A-Za-z가-힣]+",
            " ",
            text,
        ),
    ).strip().lower()


def unique_partial(
    product_name: str,
    all_names: list[str],
) -> str | None:
    tokens = [
        token
        for token in normalize(product_name).split()
        if len(token) >= 2
    ]

    candidates: list[str] = []

    for width in (3, 2):
        if len(tokens) < width:
            continue

        for start in range(
            0,
            len(tokens) - width + 1,
        ):
            candidate = " ".join(
                tokens[start:start + width]
            )

            if (
                candidate
                and candidate
                != normalize(product_name)
            ):
                candidates.append(candidate)

    candidates = sorted(
        set(candidates),
        key=lambda value: (
            -len(value),
            value,
        ),
    )

    normalized_names = [
        normalize(name)
        for name in all_names
    ]

    for candidate in candidates:
        matches = sum(
            candidate in name
            for name in normalized_names
        )
        if matches == 1:
            return candidate

    return None


def source_id(row: dict) -> str:
    return f"product:{row['product_no']}"


def build_case(
    case_id: str,
    case_group: str,
    query: str,
    row: dict,
) -> dict:
    return {
        "case_id": case_id,
        "case_group": case_group,
        "category": "PRODUCT",
        "query": query,
        "answerability": "ANSWERABLE",
        "hold_reason": None,
        "expected_product_no": row["product_no"],
        "expected_answer": row["product_name"],
        "evidence": [
            {
                "source_id": source_id(row),
                "version": row["version"],
            }
        ],
        "relation_tags": [],
        "split": "DEV",
        "data_mode": "PRIVATE_ACTUAL_EVAL",
        "review_status": (
            "DRAFT_NEEDS_HUMAN_REVIEW"
        ),
    }


def main() -> None:
    rows = load_snapshot()
    by_no = {
        int(row["product_no"]): row
        for row in rows
    }

    all_names = [
        row["product_name"]
        for row in rows
    ]

    custom_counts = Counter(
        str(row["custom_product_code"]).strip()
        for row in rows
        if row.get("custom_product_code")
    )

    unique_custom_rows = [
        row
        for row in rows
        if row.get("custom_product_code")
        and custom_counts[
            str(
                row["custom_product_code"]
            ).strip()
        ] == 1
    ]

    partial_rows = [
        row
        for row in rows
        if unique_partial(
            row["product_name"],
            all_names,
        )
        is not None
    ]

    fixed_product_nos = {
        18,
        114,
        538,
        609,
        823,
        1031,
        1285,
        1635,
        2153,
        2154,
    }

    missing_fixed = sorted(
        fixed_product_nos
        - set(by_no)
    )
    if missing_fixed:
        raise RuntimeError(
            f"fixed products missing: {missing_fixed}"
        )

    used = set(fixed_product_nos)

    exact_rows = choose(
        rows,
        4,
        "exact-name",
        used,
    )

    partial_selected = choose(
        partial_rows,
        4,
        "partial-name",
        used,
    )

    product_code_rows = choose(
        rows,
        3,
        "product-code",
        used,
    )

    custom_code_rows = choose(
        unique_custom_rows,
        3,
        "custom-product-code",
        used,
    )

    draft_specs: list[
        tuple[str, str, dict]
    ] = []

    for row in exact_rows:
        draft_specs.append(
            (
                "exact_name",
                row["product_name"],
                row,
            )
        )

    for row in partial_selected:
        partial = unique_partial(
            row["product_name"],
            all_names,
        )
        if not partial:
            raise RuntimeError(
                "partial generation failed"
            )

        draft_specs.append(
            (
                "partial_name",
                partial,
                row,
            )
        )

    for row in product_code_rows:
        draft_specs.append(
            (
                "product_code",
                str(row["product_code"]),
                row,
            )
        )

    for row in custom_code_rows:
        draft_specs.append(
            (
                "custom_product_code",
                str(
                    row["custom_product_code"]
                ),
                row,
            )
        )

    # PRE-ORDER 2
    draft_specs.extend(
        [
            (
                "preorder",
                "예약 상품 OGOR MAWTRIBES GLUTTONS",
                by_no[2153],
            ),
            (
                "preorder",
                "예약 상품 OGOR MAWTRIBES IRONGUTS",
                by_no[2154],
            ),
        ]
    )

    # 카테고리 의미를 포함한 질의 2
    draft_specs.extend(
        [
            (
                "category_guided",
                "워해머 40K 스타터 세트",
                by_no[114],
            ),
            (
                "category_guided",
                "블랙 리전 콘트라스트 페인트",
                by_no[1635],
            ),
        ]
    )

    # 복합 조건형 3
    draft_specs.extend(
        [
            (
                "compound",
                "Tyranids Gargoyles",
                by_no[609],
            ),
            (
                "compound",
                "Ogor Mawtribes Ironguts",
                by_no[823],
            ),
            (
                "compound",
                "Middle-Earth Elrond Rivendell",
                by_no[1285],
            ),
        ]
    )

    # 자연어 의미 검색 3
    draft_specs.extend(
        [
            (
                "semantic",
                "카오스 나이츠용 워독 제품을 찾아줘",
                by_no[18],
            ),
            (
                "semantic",
                "오크 진영 페인보이 미니어처를 찾아줘",
                by_no[538],
            ),
            (
                "semantic",
                "작은 사이즈 시타델 아티피서 레이어 붓을 찾아줘",
                by_no[1031],
            ),
        ]
    )

    if len(draft_specs) != 24:
        raise RuntimeError(
            f"DEV24 count != 24: {len(draft_specs)}"
        )

    cases = []

    for index, (
        group,
        query,
        row,
    ) in enumerate(
        draft_specs,
        start=1,
    ):
        cases.append(
            build_case(
                f"R07P-D-{index:03d}",
                group,
                query,
                row,
            )
        )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with DRAFT_PATH.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        for case in cases:
            handle.write(
                json.dumps(
                    case,
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n"
            )

    with REVIEW_PATH.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        fieldnames = [
            "case_id",
            "case_group",
            "query",
            "expected_product_no",
            "expected_product_name",
            "category_nos",
            "answerability",
            "review_decision",
            "evidence_correct",
            "semantic_duplicate",
            "reviewed_query",
            "reviewed_answerability",
            "hold_reason",
            "notes",
        ]

        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
        )
        writer.writeheader()

        for case in cases:
            row = by_no[
                int(
                    case[
                        "expected_product_no"
                    ]
                )
            ]

            writer.writerow(
                {
                    "case_id": case["case_id"],
                    "case_group": (
                        case["case_group"]
                    ),
                    "query": case["query"],
                    "expected_product_no": (
                        case[
                            "expected_product_no"
                        ]
                    ),
                    "expected_product_name": (
                        case[
                            "expected_answer"
                        ]
                    ),
                    "category_nos": json.dumps(
                        row.get(
                            "category_nos"
                        )
                        or [],
                        ensure_ascii=False,
                    ),
                    "answerability": (
                        case["answerability"]
                    ),
                    "review_decision": "",
                    "evidence_correct": "",
                    "semantic_duplicate": "",
                    "reviewed_query": "",
                    "reviewed_answerability": "",
                    "hold_reason": "",
                    "notes": "",
                }
            )

    group_counts = Counter(
        case["case_group"]
        for case in cases
    )

    manifest = {
        "experiment_id": "OPS-RAG-SCALE-01",
        "task_id": "R07-PRE-AI-01",
        "experiment": "E08",
        "scope": "PRODUCT_ONLY",
        "status": (
            "DRAFT_NEEDS_HUMAN_REVIEW"
        ),
        "dev_count": len(cases),
        "seed": SEED,
        "source_support": {
            "PRODUCT": "SUPPORTED",
            "POLICY": "MISSING",
            "INVENTORY_SNAPSHOT": "BLOCKED",
            "INCOMING_STOCK": "MISSING",
            "C02": "BLOCKED",
        },
        "source_snapshot": str(
            SNAPSHOT_PATH.relative_to(ROOT)
        ).replace("\\", "/"),
        "snapshot_sha256": (
            EXPECTED_SNAPSHOT_SHA256
        ),
        "backend_manifest_sha256": (
            EXPECTED_MANIFEST_SHA256
        ),
        "record_version": (
            EXPECTED_RECORD_VERSION
        ),
        "query_type_counts": dict(
            sorted(group_counts.items())
        ),
        "final12_used": False,
        "human_review_completed": False,
    }

    MANIFEST_PATH.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print("R07_PRE_DEV24_DRAFT_OK")
    print("dev_count=", len(cases))
    print(
        "query_type_counts=",
        dict(sorted(group_counts.items())),
    )
    print(
        "draft_sha256=",
        sha256_file(DRAFT_PATH),
    )
    print(
        "review_sha256=",
        sha256_file(REVIEW_PATH),
    )
    print(
        "draft_path=",
        DRAFT_PATH,
    )
    print(
        "review_path=",
        REVIEW_PATH,
    )
    print(
        "manifest_path=",
        MANIFEST_PATH,
    )


if __name__ == "__main__":
    main()