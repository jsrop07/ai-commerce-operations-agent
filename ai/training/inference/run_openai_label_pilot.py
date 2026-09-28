from __future__ import annotations

import json
import os
import time
from pathlib import Path

from openai import OpenAI


MODEL_ID = "gpt-5.6-sol"

INPUT_PATH = Path(
    "artifacts/experiments/day11/safe_pilot_20.jsonl"
)

OUTPUT_PATH = Path(
    "artifacts/experiments/day11/openai_label_pilot_20_results.jsonl"
)

SUMMARY_PATH = Path(
    "artifacts/experiments/day11/openai_label_pilot_20_summary.json"
)


SYSTEM_PROMPT = """
당신은 보드게임 커머스 고객문의 NLU 분류기입니다.

고객에게 답변하지 말고 분류 JSON만 생성하세요.

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
- AFTER_SERVICE

분류 기준:
- AFTER_SERVICE:
  상품 수령 후 부품 누락, 파손, 오배송, 구성품 이상,
  부품 불량, 교체 부품 요청 등 A/S 문의
- RETURN_EXCHANGE:
  반품 또는 교환 자체를 명확하게 요청
- REFUND_CANCEL:
  환불, 결제 취소, 주문 취소 요청
- STOCK_AVAILABILITY:
  현재 재고가 있는지 묻는 문의
- RESTOCK:
  향후 재입고 여부 또는 재입고 시점을 묻는 문의
- DELIVERY:
  배송 상태, 배송 방법, 수령 관련 문의
- RESERVATION_PREORDER:
  예약 구매 또는 선주문 문의
- PRODUCT_INFO:
  정상 상품의 사양, 구성, 특징 관련 문의
- COMPATIBILITY:
  상품 간 호환 여부 문의
- ORDER_STATUS:
  주문 처리 상태 문의
- OTHER:
  문의이지만 위 intent에 적합하지 않음

eligible_for_nlu=false인 경우:
- intent는 null
- entities는 빈 배열
- exclusion_reason은
  NON_INQUIRY / INSUFFICIENT_CONTEXT / OUT_OF_SCOPE 중 하나

eligible_for_nlu=true인 경우:
- exclusion_reason은 null
- intent는 반드시 위 허용값 중 하나

고위험 기준:
- 환불/취소
- 개인정보 변경
- 배송지/수령인 변경
- 가격 변경
- 실제 주문/재고 변경
등 외부 상태 변경 요청은 PROHIBITED 및 human_review_required=true.

이 결과는 proposed label이며 최종 truth가 아닙니다.
"""


SCHEMA = {
    "type": "object",
    "properties": {
        "eligible_for_nlu": {
            "type": "boolean",
        },
        "exclusion_reason": {
            "type": ["string", "null"],
            "enum": [
                "NON_INQUIRY",
                "INSUFFICIENT_CONTEXT",
                "OUT_OF_SCOPE",
                None,
            ],
        },
        "intent": {
            "type": ["string", "null"],
            "enum": [
                "PRODUCT_INFO",
                "COMPATIBILITY",
                "STOCK_AVAILABILITY",
                "RESTOCK",
                "ORDER_STATUS",
                "DELIVERY",
                "RESERVATION_PREORDER",
                "RETURN_EXCHANGE",
                "REFUND_CANCEL",
                "OTHER",
                "AFTER_SERVICE",
                None,
            ],
        },
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": [
                            "PRODUCT",
                            "SKU",
                            "BRAND",
                            "CATEGORY",
                            "LANGUAGE",
                            "ORDER_REF",
                            "QUANTITY",
                            "DATE_TIME",
                            "CHANNEL",
                            "ISSUE_TYPE",
                        ],
                    },
                    "value": {
                        "type": "string",
                    },
                },
                "required": [
                    "type",
                    "value",
                ],
                "additionalProperties": False,
            },
        },
        "risk": {
            "type": "string",
            "enum": [
                "LOW",
                "MEDIUM",
                "HIGH",
                "PROHIBITED",
            ],
        },
        "human_review_required": {
            "type": "boolean",
        },
    },
    "required": [
        "eligible_for_nlu",
        "exclusion_reason",
        "intent",
        "entities",
        "risk",
        "human_review_required",
    ],
    "additionalProperties": False,
}


def load_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]


def main() -> int:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY environment variable is missing"
        )

    client = OpenAI()

    rows = load_jsonl(INPUT_PATH)

    print(f"MODEL_ID={MODEL_ID}")
    print(f"INPUT_ROWS={len(rows)}")
    print("STORE=False")
    print("TEST_DATA_USED=False")

    results = []

    for index, row in enumerate(rows, start=1):
        started = time.perf_counter()

        try:
            response = client.responses.create(
                model=MODEL_ID,
                store=False,
                reasoning={
                    "effort": "low",
                },
                instructions=SYSTEM_PROMPT,
                input=row["input_text"],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "commerce_nlu_label",
                        "schema": SCHEMA,
                        "strict": True,
                    }
                },
            )

            latency = time.perf_counter() - started

            proposal = json.loads(
                response.output_text
            )

            usage = response.usage

            result = {
                "record_id": row["record_id"],
                "group_id": row["group_id"],
                "model_id": MODEL_ID,
                "proposal": proposal,
                "schema_valid": True,
                "error": None,
                "latency_seconds": round(
                    latency,
                    4,
                ),
                "input_tokens": (
                    usage.input_tokens
                    if usage
                    else None
                ),
                "output_tokens": (
                    usage.output_tokens
                    if usage
                    else None
                ),
                "total_tokens": (
                    usage.total_tokens
                    if usage
                    else None
                ),
                "truth_promoted": False,
                "review_status": "REVIEW_REQUIRED",
            }

            print(
                f"[{index:02d}/{len(rows)}] "
                f"record_id={row['record_id']} "
                f"valid=True "
                f"latency={latency:.3f}s"
            )

        except Exception as exc:
            latency = time.perf_counter() - started

            result = {
                "record_id": row["record_id"],
                "group_id": row["group_id"],
                "model_id": MODEL_ID,
                "proposal": None,
                "schema_valid": False,
                "error": (
                    f"{type(exc).__name__}: "
                    f"{str(exc)[:300]}"
                ),
                "latency_seconds": round(
                    latency,
                    4,
                ),
                "truth_promoted": False,
                "review_status": "REVIEW_REQUIRED",
            }

            print(
                f"[{index:02d}/{len(rows)}] "
                f"record_id={row['record_id']} "
                f"valid=False "
                f"error={type(exc).__name__}"
            )

        results.append(result)

    OUTPUT_PATH.write_text(
        "\n".join(
            json.dumps(
                row,
                ensure_ascii=False,
            )
            for row in results
        )
        + "\n",
        encoding="utf-8",
    )

    valid = [
        row
        for row in results
        if row["schema_valid"]
    ]

    latencies = [
        row["latency_seconds"]
        for row in results
    ]

    summary = {
        "model_id": MODEL_ID,
        "input_rows": len(results),
        "valid_count": len(valid),
        "invalid_count": (
            len(results) - len(valid)
        ),
        "schema_valid_rate": (
            len(valid) / len(results)
            if results
            else 0.0
        ),
        "latency_seconds": {
            "min": min(latencies),
            "max": max(latencies),
            "mean": round(
                sum(latencies) / len(latencies),
                4,
            ),
        },
        "input_tokens": sum(
            row.get("input_tokens") or 0
            for row in results
        ),
        "output_tokens": sum(
            row.get("output_tokens") or 0
            for row in results
        ),
        "total_tokens": sum(
            row.get("total_tokens") or 0
            for row in results
        ),
        "truth_promoted": 0,
        "test_data_used": False,
        "status": "PROPOSALS_REQUIRE_HUMAN_REVIEW",
    }

    SUMMARY_PATH.write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print("=== SUMMARY ===")
    print(f"INPUT_ROWS={len(results)}")
    print(f"VALID={len(valid)}")
    print(
        f"INVALID={len(results) - len(valid)}"
    )
    print(
        "SCHEMA_VALID_RATE="
        f"{summary['schema_valid_rate']}"
    )
    print(
        "TOTAL_TOKENS="
        f"{summary['total_tokens']}"
    )
    print("TRUTH_PROMOTED=0")
    print("TEST_DATA_USED=False")
    print(f"OUTPUT={OUTPUT_PATH}")
    print(f"SUMMARY={SUMMARY_PATH}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())