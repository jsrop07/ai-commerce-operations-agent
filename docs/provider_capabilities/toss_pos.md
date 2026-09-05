# Toss POS Provider Capability Decision



## 1. 기본 정보



- Provider: TOSS_POS

- Decision ID: D06-BE-01

- Checked At: 2026-09-05

- Core Build Policy: Production Read-Only

- Actual Credential Used: No

- Actual Production API Called: No

- Actual Production Write Called: No



## 2. 프로젝트에서 필요한 Resource



### offline_sales



프로젝트가 Toss POS에서 필요로 하는 최소 판매 정보:



- provider sale/event identity

- product code 또는 상품 식별 정보

- quantity

- occurred_at

- cancellation / return representation

- incremental key 또는 재수집 시 중복을 판별할 source identity



목표는 Toss POS의 상품단위 오프라인 판매를 Canonical Sale Event로 변환하는 것이다.



## 3. 현재 공식 근거 확인 상태

Checked At: 2026-09-05 KST

공식 근거:

1. Toss Place Open API - Order API
   - https://docs.tossplace.com/reference/open-api/order.html

2. Toss Place Open API - 주문 조회
   - https://docs.tossplace.com/reference/open-api/order/order-methods.html

3. Toss Place Open API - 주문 개념 상세
   - https://docs.tossplace.com/reference/open-api/order/order-model.html

4. Toss Place Open API - Catalog API
   - https://docs.tossplace.com/reference/open-api/catalog.html

5. Toss Place Open API 공통 가이드
   - https://docs.tossplace.com/reference/open-api/common.html

공식 문서에서 매장 주문을 GET으로 조회할 수 있음을 확인했다.

주문 목록 조회:

- Method: GET
- Path: /api-public/openapi/v1/merchants/{merchantId}/order/orders
- from: 조회 범위 시작
- to: 조회 범위 종료
- orderStates: 주문 상태
- sources: 주문 채널
- page: 페이지
- size: 페이지 크기
- sortOrder: 정렬 순서

공식 Order DTO에서 확인한 Day 6 필요 필드:

- id: 주문 ID
- source: 주문 채널
- orderState: 주문 상태
- createdAt: 주문 생성 시각
- updatedAt: 주문 변경 시각
- completedAt: 주문 완료 시각
- cancelledAt: 주문 취소 시각
- lineItems[].item.title: 상품명
- lineItems[].item.code: 상품코드
- lineItems[].quantity: 주문 수량

Catalog API에서도 상품 id/title/code/state를 Read할 수 있다.

따라서 Toss POS 상품단위 판매 증분 수집의 선택 방식은 API_POLL로 결정한다.

단, 실제 Credential을 사용한 Production Read는 아직 수행하지 않았으므로 verification_level은 CONTRACT_ONLY로 유지한다.



## 4. Historical Backfill 결정



- historical_backfill_mode: NOT_REQUIRED

- 과거 Toss POS 판매 Export는 현재 Day 6/Day 8 필수 완료조건으로 요구하지 않는다.

- 실제 과거 CSV 부재를 Day 6 Blocking으로 처리하지 않는다.



향후 운영상 필요성과 공식 Export 범위를 확인한 경우 별도 보호 Import 대상으로 재검토한다.



## 5. Incremental Sync 결정

- incremental_mode: API_POLL
- verification_level: CONTRACT_ONLY
- source_quality: OFFICIAL_CONTRACT_VERIFIED
- actual_live_read: false

선택 이유:

Toss Place 공식 Open API에서 주문 목록 GET 조회와 from/to/page/size 조건이 확인되었다.

Day 6에서는 실제 Credential을 사용하지 않고 공식 DTO를 반영한 Synthetic Fixture로 Adapter/Normalizer 계약만 구현한다.

실제 Token/API Key, 인증 연결, Production Read Smoke는 현재 Day 6 완료조건으로 만들지 않는다.

Day 7에서 실제 구현 범위가 될 cursor/checkpoint/retry 전체 로직은 선행 구현하지 않는다.



## 6. Day 6 Fixture 요구 필드

Synthetic Toss Order/Sale fixture 최소 필드:

- order_id
- source
- order_state
- created_at
- updated_at
- completed_at
- cancelled_at
- external_product_code
- external_product_text
- quantity
- amount

공식 DTO 대응:

- order_id <- Order.id
- source <- Order.source
- order_state <- Order.orderState
- created_at <- Order.createdAt
- updated_at <- Order.updatedAt
- completed_at <- Order.completedAt
- cancelled_at <- Order.cancelledAt
- external_product_code <- Order.lineItems[].item.code
- external_product_text <- Order.lineItems[].item.title
- quantity <- Order.lineItems[].quantity

정책:

- 상품코드가 비어 있거나 Canonical SKU를 확정할 수 없으면 Mapping Queue
- quantity 누락 또는 잘못된 값은 추정하지 않음
- 알 수 없는 orderState는 원문 보존 후 quarantine/unknown 정책 적용
- 동일 입력을 다시 처리해도 business effect는 1회
- Fixture 결과를 LIVE_READ라고 표시하지 않음



## 7. Source Identity / Idempotency



공식 Provider event ID가 존재하는 경우:



- provider + tenant + source_event_id + schema_version



공식 Event ID가 없는 Fixture/파일 경로에서는:



- immutable source fields 기반 identity 또는 file source identity를 사용



단, 실제 Provider 규칙이 확인되지 않은 상태에서 production identity 규칙이라고 주장하지 않는다.



## 8. Mapping 정책



상품 식별 우선순위:



1. 승인된 ProviderMapping exact external product code

2. deterministic alias/rule 후보

3. ambiguous candidate

4. unknown



ambiguous 또는 unknown은 자동 병합하지 않는다.



처리:



- VERIFIED → Canonical Sale 처리 가능

- RULE_MATCH → confidence와 provenance 보존

- AMBIGUOUS → Mapping Queue

- UNKNOWN → Mapping Queue

- CONFLICT → 자동 처리 중단



## 9. Write Safety



Core Build에서 Toss POS에 대한 외부 Write는 구현하거나 호출하지 않는다.



금지:



- 재고 변경

- 결제 변경

- 취소

- 환불

- 상품 수정

- POS 설정 변경

- 자동 Webhook 등록



write_call_count 목표는 항상 0이다.



## 10. Day 6 현재 판정

| Resource | Connection Mode | Verification Level | 상태 |
|---|---|---|---|
| orders/offline_sales | API_POLL | CONTRACT_ONLY | 공식 GET Order API/상품단위 필드 확인, Live Credential 미검증 |
| catalog | API_POLL | CONTRACT_ONLY | 공식 GET Catalog API 확인, Live Credential 미검증 |
| historical_sales | NOT_REQUIRED | NOT_VERIFIED | 과거 Export를 Day 6 완료조건으로 요구하지 않음 |
| inventory | UNSUPPORTED | CONTRACT_ONLY | 공식 FAQ 기준 실시간 재고 수량 조회 API 미제공 |



## 11. 다음 검토 조건

현재 선택 방식은 API_POLL이다.

향후 실제 연결 시 다음을 별도 검증한다.

- API Key 인증
- 실제 merchantId
- 실제 Read 권한
- 실제 Order DTO
- page/size 경계
- from/to overlap
- rate limit
- source identity 안정성
- 취소 주문 재수집
- write_call_count=0

이 검증 전에는 verification_level을 LIVE_READ로 승격하지 않는다.
