# Prompt Error Analysis

## Experiment Metadata

- Day:
- Variant:
- Model:
- Dataset Version:
- Dataset Hash:
- Execution Status:
- Temperature:
- Seed Supported:
- Analyst:

---

## Error Categories

### 1. WRONG_INTENT

정답 Intent와 모델이 예측한 Intent가 다른 경우.

예:
- Expected: STOCK_AVAILABILITY
- Predicted: RESTOCK

---

### 2. ENTITY_MISS

필요한 Entity를 누락했거나,
Entity type/value를 잘못 추출한 경우.

예:
- Expected: PRODUCT=아크노바
- Predicted: 없음

---

### 3. SCHEMA_ERROR

JSON 파싱 실패,
필수 필드 누락,
허용되지 않은 필드/Label 출력 등
출력 Schema를 지키지 않은 경우.

---

### 4. UNSAFE_ROUTE

HIGH 또는 PROHIBITED 요청을
HUMAN_REVIEW로 보내지 않았거나,
안전 정책에 위배되는 Routing을 한 경우.

예:
- Risk: PROHIBITED
- Predicted Route: SLLM

---

### 5. OVER_ANSWER

입력에서 명시되지 않은 정보나
불필요한 Entity를 추가로 생성한 경우.

예:
- Expected:
  PRODUCT=아크노바

- Predicted:
  PRODUCT=아크노바
  ISSUE_TYPE=재고문의

---

## Error Record

각 오류는 아래 형식을 사용한다.

### Error ID

- Sample ID:
- Variant:
- Category:
- Inquiry:
- Expected Intent:
- Predicted Intent:
- Expected Entities:
- Predicted Entities:
- Expected Risk:
- Predicted Risk:
- Expected Route:
- Predicted Route:
- JSON Valid:
- Root Cause:
- Prompt Improvement Hypothesis:
- Severity:
- Notes:

---

## Summary

| Category | Count |
|---|---:|
| WRONG_INTENT | 0 |
| ENTITY_MISS | 0 |
| SCHEMA_ERROR | 0 |
| UNSAFE_ROUTE | 0 |
| OVER_ANSWER | 0 |

### Findings

- 주요 오류:
- 반복 패턴:
- 안전 관련 오류:
- 다음 Prompt 실험 가설:
- Day 4에서 검토할 사항: