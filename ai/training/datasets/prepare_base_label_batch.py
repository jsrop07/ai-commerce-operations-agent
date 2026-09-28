from __future__ import annotations

import json
from pathlib import Path


INPUT_PATH = Path(
    "artifacts/experiments/day11/external_safe_candidates.jsonl"
)

OUTPUT_PATH = Path(
    "artifacts/experiments/day11/base_label_pilot_20.jsonl"
)

PILOT_SIZE = 20

SYSTEM_PROMPT = """
너는 보드게임 커머스 고객 문의를 구조화하는 NLU 분류기다.

입력은 개인정보 외부 전송 게이트를 통과한 비식별 고객 문의다.
고객에게 답변하지 말고 문의의 의미만 분류한다.
결과는 반드시 JSON object 하나만 출력한다.

eligible_for_nlu:
- true: 실제 운영 문의로 NLU 학습 후보에 적합
- false: 감사글, 후기, 매장 소개, 단순 게시글, 문맥 부족 등

exclusion_reason 허용값:
- null
- NON_INQUIRY
- INSUFFICIENT_CONTEXT
- OUT_OF_SCOPE

intent 허용값:
- PRODUCT_INFO
- COMPATIBILITY
- STOCK_AVAILABILITY
- RESTOCK
- ORDER_STATUS
- DELIVERY
- RESERVATION_PREORDER
- RETURN_EXCHANGE
- REFUND_CANCEL
- OTHER

entity type 허용값:
- PRODUCT
- SKU
- BRAND
- CATEGORY
- LANGUAGE
- ORDER_REF
- QUANTITY
- DATE_TIME
- CHANNEL
- ISSUE_TYPE

risk 허용값:
- LOW
- MEDIUM
- HIGH
- PROHIBITED

분류 원칙:
- 파손, 구성품 누락, 불량, 오배송은 단순 PRODUCT_INFO로 분류하지 않는다.
- 환불 또는 주문 취소 요청은 REFUND_CANCEL이며 PROHIBITED다.
- 고객정보, 배송지, 수령지, 가격, 주문, 실제 재고를 변경해 달라는 요청은
  AI가 자동 실행할 수 없으므로 PROHIBITED 및 human_review_required=true다.
- 단순 배송 일정이나 진행 조회와 변경 요청을 구분한다.
- 예약구매/프리오더 관련 문의는 RESERVATION_PREORDER를 우선 검토한다.
- 문의가 아닌 게시글은 eligible_for_nlu=false로 한다.
- 애매하면 억지로 추측하지 않는다.

출력 형식:
{
  "eligible_for_nlu": true,
  "exclusion_reason": null,
  "intent": "DELIVERY",
  "entities": [
    {
      "type": "ISSUE_TYPE",
      "value": "배송 지연"
    }
  ],
  "risk": "MEDIUM",
  "human_review_required": false
}

이 결과는 운영자 검수 전 후보 label일 뿐이며 학습 정답이 아니다.
""".strip()


def load_rows() -> list[dict]:
    rows = []

    with INPUT_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))

    return rows


def main() -> int:
    rows = load_rows()

    pilot = rows[:PILOT_SIZE]

    with OUTPUT_PATH.open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as f:
        for row in pilot:
            output = {
                "record_id": row["record_id"],
                "group_id": row["group_id"],
                "messages": [
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": row["input_text"],
                    },
                ],
            }

            f.write(
                json.dumps(
                    output,
                    ensure_ascii=False,
                )
                + "\n"
            )

    print(f"SOURCE_ROWS={len(rows)}")
    print(f"PILOT_ROWS={len(pilot)}")
    print(f"OUTPUT={OUTPUT_PATH}")
    print("TEST_DATA_USED=False")
    print("STATUS=BASE_LABEL_PILOT_PREPARED")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())