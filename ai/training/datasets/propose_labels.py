from __future__ import annotations

import csv
import re
from pathlib import Path


INPUT_PATH = Path(
    "artifacts/experiments/day11/nlu_review_sheet.csv"
)

OUTPUT_PATH = Path(
    "artifacts/experiments/day11/nlu_review_sheet_proposed.csv"
)


INTENT_PATTERNS = {
    "REFUND_CANCEL": [
        r"취소",
        r"환불",
    ],
    "RETURN_EXCHANGE": [
        r"반품",
        r"교환",
        r"불량",
        r"파손",
    ],
    "RESERVATION_PREORDER": [
        r"예약",
        r"프리오더",
        r"선주문",
    ],
    "RESTOCK": [
        r"재입고",
        r"다시\s*입고",
        r"언제\s*들어오",
        r"입고\s*예정",
    ],
    "STOCK_AVAILABILITY": [
        r"재고",
        r"구매\s*가능",
        r"품절",
        r"살\s*수",
    ],
    "ORDER_STATUS": [
        r"주문\s*상태",
        r"주문\s*확인",
        r"접수",
        r"결제\s*확인",
    ],
    "DELIVERY": [
        r"배송",
        r"발송",
        r"출고",
        r"도착",
        r"택배",
        r"수령",
        r"주소",
        r"배송지",
    ],
    "COMPATIBILITY": [
        r"호환",
        r"같이\s*사용",
        r"단독\s*사용",
        r"본판",
        r"확장팩",
    ],
    "PRODUCT_INFO": [
        r"한국어",
        r"한글",
        r"영문",
        r"언어",
        r"구성",
        r"몇\s*명",
        r"인원",
        r"플레이",
        r"규칙",
        r"사이즈",
        r"크기",
    ],
}


def normalize_text(value: str) -> str:
    return " ".join((value or "").strip().split())


def matches_any(text: str, patterns: list[str]) -> bool:
    return any(
        re.search(pattern, text, flags=re.IGNORECASE)
        for pattern in patterns
    )


def propose_intent(text: str) -> str:
    # 위험도가 높은 intent를 먼저 검사한다.
    priority = [
        "REFUND_CANCEL",
        "RETURN_EXCHANGE",
        "RESERVATION_PREORDER",
        "RESTOCK",
        "STOCK_AVAILABILITY",
        "ORDER_STATUS",
        "DELIVERY",
        "COMPATIBILITY",
        "PRODUCT_INFO",
    ]

    for intent in priority:
        if matches_any(text, INTENT_PATTERNS[intent]):
            return intent

    return "OTHER"


def propose_risk(intent: str, text: str) -> str:
    if intent == "REFUND_CANCEL":
        return "PROHIBITED"

    prohibited_change_patterns = [
        r"주소.*변경",
        r"배송지.*변경",
        r"수령지.*변경",
        r"가격.*변경",
        r"재고.*변경",
        r"주문.*변경",
    ]

    if matches_any(text, prohibited_change_patterns):
        return "PROHIBITED"

    if intent in {
        "RETURN_EXCHANGE",
        "RESERVATION_PREORDER",
    }:
        return "MEDIUM"

    if intent == "DELIVERY" and matches_any(
        text,
        [
            r"지연",
            r"안\s*왔",
            r"못\s*받",
            r"문제",
        ],
    ):
        return "MEDIUM"

    return "LOW"


def propose_lookup(intent: str) -> str:
    mapping = {
        "PRODUCT_INFO": ["PRODUCT"],
        "COMPATIBILITY": ["PRODUCT", "PRODUCT_RELATION"],
        "STOCK_AVAILABILITY": ["INVENTORY"],
        "RESTOCK": ["INCOMING_STOCK"],
        "ORDER_STATUS": ["ORDER"],
        "DELIVERY": ["ORDER", "DELIVERY"],
        "RESERVATION_PREORDER": [
            "ORDER",
            "INCOMING_STOCK",
            "LAUNCH_EVENT",
        ],
        "RETURN_EXCHANGE": ["ORDER", "POLICY"],
        "REFUND_CANCEL": ["ORDER", "POLICY"],
        "OTHER": [],
    }

    return "|".join(mapping[intent])


def propose_human_review(
    intent: str,
    risk: str,
) -> str:
    if risk in {"HIGH", "PROHIBITED"}:
        return "true"

    if intent in {
        "RETURN_EXCHANGE",
        "REFUND_CANCEL",
    }:
        return "true"

    return "false"


def main() -> int:
    with INPUT_PATH.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as f:
        rows = list(csv.DictReader(f))

    for row in rows:
        text = normalize_text(row["input_text"])

        intent = propose_intent(text)
        risk = propose_risk(intent, text)
        lookup = propose_lookup(intent)
        human_review = propose_human_review(
            intent,
            risk,
        )

        row["proposed_intent"] = intent

        # 확정 label 필드는 비워 둔다.
        row["intent"] = ""
        row["risk"] = ""
        row["required_lookup_json"] = ""
        row["human_review_required"] = ""
        row["review_status"] = "REVIEW_REQUIRED"

        # 후보값은 review_note에 기록한다.
        row["review_note"] = (
            f"PROPOSED_RISK={risk};"
            f"PROPOSED_LOOKUP={lookup};"
            f"PROPOSED_HUMAN_REVIEW={human_review}"
        )

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_PATH.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=rows[0].keys(),
        )

        writer.writeheader()
        writer.writerows(rows)

    from collections import Counter

    counts = Counter(
        row["proposed_intent"]
        for row in rows
    )

    print(f"ROWS={len(rows)}")
    print("PROPOSED_INTENT_COUNTS=")

    for intent, count in sorted(counts.items()):
        print(f"  {intent}={count}")

    print(f"OUTPUT={OUTPUT_PATH}")
    print("TRUTH_PROMOTED=0")
    print("STATUS=PROPOSALS_CREATED")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())