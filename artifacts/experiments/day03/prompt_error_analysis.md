# Day 03 Prompt Error Analysis

## Experiment Metadata

* Day: AI/ML Day 3
* Model: gpt-5.6-luna
* Dataset: golden_nlu_v0.1
* Dataset Hash: 17f86dcefa6401bb93fb9e8c8274da4e37724d79a1971f6aa034aed7b96a93f5
* Split: validation
* Sample Count: 8
* Execution Status: MODEL_API
* Temperature: 0
* Seed Supported: false
* Variants:

  * inquiry_zero_shot
  * inquiry_structured
  * inquiry_fewshot

---

# 1. Variant Summary

| Variant    | Error Samples | WRONG_INTENT | ENTITY_MISS | SCHEMA_ERROR | UNSAFE_ROUTE | OVER_ANSWER |
| ---------- | ------------: | -----------: | ----------: | -----------: | -----------: | ----------: |
| Zero-shot  |             7 |            0 |           0 |            0 |            0 |           7 |
| Structured |             7 |            1 |           0 |            0 |            0 |           7 |
| Few-shot   |             2 |            1 |           0 |            0 |            0 |           1 |

---

# 2. Representative Error Cases

## Error 01 — Zero-shot Entity Over-generation

* Sample ID: nlu_validation_001
* Variant: inquiry_zero_shot
* Category: OVER_ANSWER
* Expected Intent: PRODUCT_INFO
* Predicted Intent: PRODUCT_INFO
* Expected Entities:

  * PRODUCT = 황금 숲
* Predicted Entities:

  * PRODUCT = 황금 숲
  * ISSUE_TYPE = 플레이 시간
* Expected Risk: LOW
* Predicted Risk: LOW
* Expected Route: SLLM
* Predicted Route: SLLM
* JSON Valid: true
* Severity: LOW

### Root Cause

Intent 자체는 정확했지만 문의 목적을 나타내는 표현까지 ISSUE_TYPE Entity로 추출했다.

현재 Golden annotation은 실제 상품이나 명시적인 운영 Entity만 추출하는 방향인데, Zero-shot Prompt에서는 Entity 추출 범위를 충분히 제한하지 못했다.

### Prompt Improvement Hypothesis

Entity는 단순히 문의의 주제를 설명하는 문구가 아니라 이후 검색·조회·라우팅에 실제로 사용되는 명시적인 값만 추출하도록 제한한다.

---

## Error 02 — Zero-shot Generic Entity Over-generation and Risk Under-classification

* Sample ID: nlu_validation_006
* Variant: inquiry_zero_shot
* Category: OVER_ANSWER
* Expected Intent: RESERVATION_PREORDER
* Predicted Intent: RESERVATION_PREORDER
* Expected Entities: none
* Predicted Entities:

  * PRODUCT = 상품
* Expected Risk: MEDIUM
* Predicted Risk: LOW
* Expected Route: SLLM
* Predicted Route: SLLM
* JSON Valid: true
* Severity: MEDIUM

### Root Cause

실제 상품명이 아닌 일반 명사 `상품`을 PRODUCT Entity로 추출했다.

또한 예약/선주문 관련 문의를 Golden 기준 MEDIUM이 아닌 LOW로 평가했다.

현재 공식 Error Category에는 별도 RISK_MISCLASSIFICATION 항목이 없으므로 OVER_ANSWER로 분류하되 Risk mismatch를 함께 기록한다.

### Prompt Improvement Hypothesis

`상품`, `제품`, `물건` 같은 일반 명사는 실제 상품을 특정할 수 없으므로 PRODUCT Entity로 추출하지 않는 규칙이 필요하다.

예약/선주문 관련 Risk 기준도 Prompt에서 보다 명확하게 고정할 필요가 있다.

---

## Error 03 — Zero-shot Risk Level Mismatch

* Sample ID: nlu_validation_008
* Variant: inquiry_zero_shot
* Category: OVER_ANSWER
* Expected Intent: REFUND_CANCEL
* Predicted Intent: REFUND_CANCEL
* Expected Entities: none
* Predicted Entities:

  * ISSUE_TYPE = 주문 취소
* Expected Risk: PROHIBITED
* Predicted Risk: HIGH
* Expected Route: HUMAN_REVIEW
* Predicted Route: HUMAN_REVIEW
* JSON Valid: true
* Severity: HIGH

### Root Cause

운영 안전 Route 자체는 HUMAN_REVIEW로 정확했지만 Risk 등급을 PROHIBITED가 아니라 HIGH로 예측했다.

따라서 현재 High-risk Routing metric은 성공으로 계산되지만 Risk classification 자체는 정답이 아니다.

### Prompt Improvement Hypothesis

환불·주문취소처럼 Production에서 자동 실행이 금지된 요청은 단순 HIGH가 아니라 PROHIBITED로 분류해야 한다는 규칙을 강화한다.

### Metric Limitation

이 사례 때문에 `high_risk_routing = 1.0`만으로 Risk 분류 품질까지 완벽했다고 해석해서는 안 된다.

향후 `risk_accuracy` 또는 `risk_macro_f1` Metric 추가를 검토한다.

---

## Error 04 — Structured Intent Confusion

* Sample ID: nlu_validation_006
* Variant: inquiry_structured
* Category:

  * WRONG_INTENT
  * OVER_ANSWER
* Expected Intent: RESERVATION_PREORDER
* Predicted Intent: DELIVERY
* Expected Entities: none
* Predicted Entities:

  * ISSUE_TYPE = 출고
  * PRODUCT = 예약한 상품
* Expected Risk: MEDIUM
* Predicted Risk: LOW
* Expected Route: SLLM
* Predicted Route: SLLM
* JSON Valid: true
* Severity: MEDIUM

### Root Cause

예약 상품의 출고 관련 표현에 지나치게 반응하여 문의의 상위 맥락인 RESERVATION_PREORDER보다 DELIVERY를 우선 선택했다.

또한 `예약한 상품`처럼 실제 상품명이 아닌 표현을 PRODUCT Entity로 잘못 추출했다.

### Prompt Improvement Hypothesis

예약·선주문 상품의 상태나 출고 시점을 묻더라도 문의의 핵심 대상이 예약 주문이라면 RESERVATION_PREORDER를 우선하도록 Intent precedence 규칙을 추가한다.

---

## Error 05 — Few-shot Temporal Entity Disagreement

* Sample ID: nlu_validation_005
* Variant: inquiry_fewshot
* Category: OVER_ANSWER
* Expected Intent: DELIVERY
* Predicted Intent: DELIVERY
* Expected Entities: none
* Predicted Entities:

  * DATE_TIME = 이번 주 안에
* Expected Risk: LOW
* Predicted Risk: LOW
* Expected Route: SLLM
* Predicted Route: SLLM
* JSON Valid: true
* Severity: LOW

### Root Cause

모델은 입력에 명시된 시간 표현 `이번 주 안에`를 DATE_TIME Entity로 추출했지만 Golden annotation에는 Entity가 없다.

### Annotation Review Required

현재 허용 Entity taxonomy에는 DATE_TIME이 존재한다.

따라서 이 사례는 모델의 명백한 오류라고 단정하기 어렵고 Golden Dataset의 Entity annotation guideline이 불명확할 가능성이 있다.

Day 4에서 다음 중 하나를 결정해야 한다.

1. `이번 주`, `내일`, `다음 달` 등의 명시적 시간 표현을 DATE_TIME으로 정답 처리한다.
2. 운영상 실제 조회 Key로 활용할 시간 표현만 DATE_TIME으로 인정한다.

Golden Dataset 기준을 확정한 뒤 재평가가 필요하다.

---

## Error 06 — Few-shot Reservation vs Delivery Confusion

* Sample ID: nlu_validation_006
* Variant: inquiry_fewshot
* Category: WRONG_INTENT
* Expected Intent: RESERVATION_PREORDER
* Predicted Intent: DELIVERY
* Expected Entities: none
* Predicted Entities: none
* Expected Risk: MEDIUM
* Predicted Risk: LOW
* Expected Route: SLLM
* Predicted Route: SLLM
* JSON Valid: true
* Severity: MEDIUM

### Root Cause

Few-shot Examples가 Entity 추출에는 큰 도움을 주었지만 예약 상품의 출고 관련 문의에서 RESERVATION_PREORDER와 DELIVERY의 경계를 충분히 학습시키지 못했다.

Structured Prompt에서도 동일 Sample을 DELIVERY로 잘못 분류했으므로 일회성 오류보다는 Intent definition 또는 Golden guideline의 경계 문제일 가능성이 있다.

### Prompt Improvement Hypothesis

향후 Few-shot Example에 다음과 같은 hard-negative pair를 추가한다.

* 일반 주문 배송 문의 → DELIVERY
* 예약/선주문 상품의 출시·출고·수령 시점 문의 → RESERVATION_PREORDER

단, validation/test 문장의 exact 또는 near-duplicate Example은 사용하지 않는다.

---

# 3. Cross-Variant Findings

## Finding 1 — Zero-shot은 Intent보다 Entity Precision이 문제

Zero-shot은 Validation 8건에서 Intent를 모두 맞혔지만 7건에서 불필요한 Entity를 추가했다.

따라서 현재 Zero-shot의 주요 문제는 Intent classification보다 Entity over-generation이다.

---

## Finding 2 — Structured Prompt가 자동으로 성능을 개선하지 않았다

Structured Prompt는 Zero-shot보다 입력 Token이 크게 증가했지만 Intent와 Entity 성능이 오히려 감소했다.

Prompt에 규칙을 많이 추가하는 것 자체가 성능 개선을 보장하지 않는다.

---

## Finding 3 — Few-shot은 Entity 추출에 가장 효과적이었다

Few-shot은 Entity F1이 0.8889로 상승했고 Error Sample도 2건으로 감소했다.

다만 RESERVATION_PREORDER와 DELIVERY 혼동은 해결하지 못했다.

---

## Finding 4 — Golden Annotation Guideline 검토가 필요하다

`DATE_TIME = 이번 주 안에`와 같이 taxonomy상 허용되는 Entity를 모델이 추출했음에도 Golden에는 존재하지 않는 사례가 확인됐다.

따라서 Prompt 성능을 추가 비교하기 전에 Entity annotation guideline을 명확히 해야 한다.

---

## Finding 5 — High-risk Routing과 Risk Classification은 서로 다른 문제다

REFUND_CANCEL 사례에서 Route는 HUMAN_REVIEW로 올바르게 설정됐지만 Risk가 PROHIBITED가 아닌 HIGH로 예측됐다.

따라서 현재 `high_risk_routing`만으로 Risk classification 품질을 평가하기 어렵다.

향후 평가 Metric으로 다음을 검토한다.

* Risk Accuracy
* Risk Macro F1
* PROHIBITED Recall

---

# 4. Day 4 Review Items

1. Golden Dataset Entity annotation guideline 검토
2. DATE_TIME 추출 기준 확정
3. Generic noun을 PRODUCT Entity로 인정할지 여부 확정
4. RESERVATION_PREORDER와 DELIVERY precedence 규칙 검토
5. HIGH와 PROHIBITED 구분 규칙 검토
6. Risk Accuracy / Risk Macro F1 Metric 추가 여부 검토
7. Prompt 후보별 품질·Latency·Token·Cost 종합 비교
8. 현재 8건 Validation 결과를 최종 성능으로 과도하게 해석하지 않음

---

# 5. Conclusion

Day 3 결과만으로 최종 Prompt를 확정하지 않는다.

현재 실험은 Prompt baseline과 실패 패턴을 확보하기 위한 소규모 Validation 실험이다.

현재 관찰된 경향은 다음과 같다.

* Zero-shot: Intent 성능은 가장 높지만 Entity over-generation이 많음
* Structured: 비용과 Token은 증가했지만 품질 개선이 확인되지 않음
* Few-shot: Entity 성능과 전체 오류 수는 가장 우수하지만 예약/배송 Intent 혼동이 남아 있음

최종 채택 여부는 이후 더 큰 평가 데이터, Risk 평가, sLLM/QLoRA 실험 결과와 함께 판단한다.
