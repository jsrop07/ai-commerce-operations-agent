from __future__ import annotations

import json
from pathlib import Path


INPUT_PATH = Path(
    "artifacts/experiments/day11/day11_baseline_comparison.json"
)

SUMMARY_JSON_PATH = Path(
    "artifacts/experiments/day11/day11_baseline_summary.json"
)

SUMMARY_MD_PATH = Path(
    "artifacts/experiments/day11/day11_baseline_summary.md"
)


def pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def main() -> int:
    data = json.loads(
        INPUT_PATH.read_text(encoding="utf-8")
    )

    qwen = data["qwen"]
    openai = data["openai"]

    summary = {
        "schema_version": "day11-baseline-summary.v1",
        "truth_rows": data["truth_rows"],
        "truth_source": data["truth_source"],
        "test_data_used": data["test_data_used"],
        "qwen_base": qwen,
        "large_api_llm": openai,
        "findings": [
            (
                "Qwen Base intent accuracy is usable as a "
                "pre-finetuning baseline but shows substantial "
                "entity taxonomy adherence failures."
            ),
            (
                "Large API LLM achieved full intent agreement "
                "on the reviewed pilot and full schema/entity "
                "taxonomy validity."
            ),
            (
                "Both models showed weaker risk-policy agreement "
                "than intent agreement, so risk and human-review "
                "rules must remain explicit project constraints."
            ),
            (
                "The 20-row set is a reviewed pilot baseline, "
                "not the final independent Test set."
            ),
        ],
        "status": "DAY11_BASELINES_LOCKED",
    }

    SUMMARY_JSON_PATH.write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    md = f"""# Day 11 Baseline Summary

## 기준

- Human-reviewed pilot truth: {data["truth_rows"]} rows
- Test data used: {data["test_data_used"]}
- Truth source: {data["truth_source"]}

## Qwen Base

- Intent Accuracy: {pct(qwen["intent_accuracy"])}
- Risk Accuracy: {pct(qwen["risk_accuracy"])}
- Eligibility Accuracy: {pct(qwen["eligibility_accuracy"])}
- Human Review Accuracy: {pct(qwen["human_review_accuracy"])}
- Full Schema Valid Rate: {pct(qwen["full_schema_valid_rate"])}
- Entity Taxonomy Valid Rate: {pct(qwen["entity_taxonomy_valid_rate"])}
- Entity Valid: {qwen["entity_valid_count"]}/{qwen["entity_count"]}

## Large API LLM

- Intent Accuracy: {pct(openai["intent_accuracy"])}
- Risk Accuracy: {pct(openai["risk_accuracy"])}
- Eligibility Accuracy: {pct(openai["eligibility_accuracy"])}
- Human Review Accuracy: {pct(openai["human_review_accuracy"])}
- Full Schema Valid Rate: {pct(openai["full_schema_valid_rate"])}
- Entity Taxonomy Valid Rate: {pct(openai["entity_taxonomy_valid_rate"])}
- Entity Valid: {openai["entity_valid_count"]}/{openai["entity_count"]}

## 핵심 결론

1. Qwen Base는 Intent 75% 수준의 사전학습 기준선을 확보했다.
2. Qwen Base의 가장 큰 약점은 entity taxonomy adherence다.
3. Large API LLM은 Intent와 구조 준수에서 강한 기준선을 제공한다.
4. Risk/Human Review 판단은 두 모델 모두 프로젝트 정책과 완전히 일치하지 않는다.
5. 따라서 QLoRA 목표에는 Intent뿐 아니라 Entity taxonomy adherence와 Risk/HITL 준수를 포함한다.
6. 본 결과는 20건 reviewed pilot baseline이며 최종 독립 Test 결과가 아니다.

## 상태

DAY11_BASELINES_LOCKED
"""

    SUMMARY_MD_PATH.write_text(
        md,
        encoding="utf-8",
    )

    print(f"JSON={SUMMARY_JSON_PATH}")
    print(f"MARKDOWN={SUMMARY_MD_PATH}")
    print("STATUS=DAY11_BASELINES_LOCKED")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())