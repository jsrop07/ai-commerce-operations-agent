# eCount Provider Capability Decision

## 1. 기본 정보

- Provider: ECOUNT
- Decision ID: D06-BE-03
- Checked At: 2026-09-05
- Core Build Policy: Production Read-Only
- Actual Credential Used: No
- Actual Production API Called: No
- Actual Production Write Called: No

## 2. 공식 근거

Official Source:

- ECOUNT Open API
- https://www.ecount.com/kr/ecount/product/erp_open-api

공식 공개 문서에서 확인된 조회 기능:

- 품목: 조회
- 발주서: 조회
- 재고현황: 조회
- 창고별재고현황: 조회

공개 문서에서는 판매 API가 입력으로 표시되어 있으며 판매자료 조회 API는 확인하지 못했다.

eCount는 세부 API 매뉴얼을 로그인 후 제공한다고 안내하므로,
공개 문서에서 확인되지 않은 endpoint, auth, request field, pagination,
rate limit을 추정하여 구현하지 않는다.

## 3. Item / Product

- resource: item
- connection_mode: API_POLL
- verification_level: CONTRACT_ONLY
- source_quality: OFFICIAL_CONTRACT_VERIFIED

공식 Open API에 품목 조회가 존재함을 확인했다.

단 실제 Credential/API 호출은 수행하지 않았으므로 LIVE_READ로 기록하지 않는다.

## 4. Inventory Snapshot

- resource: inventory
- connection_mode: API_POLL
- verification_level: CONTRACT_ONLY
- source_quality: SOURCE_QUALITY_BLOCKED

공식 Open API에서 재고현황 조회가 존재함을 확인했다.

하지만 현재 실제 운영 eCount 재고 데이터는 정합성 문제가 있어
프로젝트의 기준 재고로 사용할 수 없다.

따라서 현재 실제 Snapshot은 다음에 반영하지 않는다.

- Inventory Ledger 기준값
- Expected Inventory 확정값
- AI 확정 답변
- 실제 재고 정상 상태 표시

Day 6에서는 Synthetic Fixture로 계약/Normalizer/Quarantine만 검증한다.

## 5. Warehouse Inventory

- resource: warehouse_inventory
- connection_mode: API_POLL
- verification_level: CONTRACT_ONLY
- source_quality: SOURCE_QUALITY_BLOCKED

공식 Open API에서 창고별재고현황 조회가 존재함을 확인했다.

현재 실제 운영 재고 정합성 문제가 해결되기 전까지
실제 Warehouse Snapshot은 Canonical 기준값으로 적재하지 않는다.

## 6. Incoming Stock

- resource: incoming_stock
- connection_mode: UNKNOWN/BLOCKED
- verification_level: CONTRACT_ONLY
- source_quality: NOT_VERIFIED

공식 공개 문서에서 발주서 조회 API가 존재하는 것은 확인했다.

그러나 발주서가 프로젝트의 confirmed incoming stock과 동일한 의미인지,
입고예정 수량/일자/상태를 충분히 제공하는지는 공개 근거만으로 확인할 수 없다.

따라서 발주서를 임의로 IncomingStock으로 자동 변환하지 않는다.

세부 API 매뉴얼 또는 운영자 확인 후 재검토한다.

## 7. Sale Read

- resource: sale
- connection_mode: UNKNOWN/BLOCKED
- verification_level: CONTRACT_ONLY
- source_quality: NOT_VERIFIED

공식 공개 Open API 표에서는 판매가 입력 API로 표시되어 있으며
판매자료 조회 API는 확인하지 못했다.

따라서 판매 Read endpoint를 추정하여 구현하지 않는다.

## 8. Day 6 Fixture 필수 필드 정책

eCount Inventory Fixture에서 프로젝트가 요구하는 최소 식별 정보:

- external_product_code
- warehouse_code
- unit
- on_hand
- as_of

다음 필드가 없으면 값을 추정하지 않는다.

- external_product_code 누락 → QUARANTINED
- warehouse_code 누락 → QUARANTINED
- unit 누락 → QUARANTINED
- on_hand 누락/비정상 → QUARANTINED
- as_of 누락/비정상 → QUARANTINED

주의:

위 필수성은 현재 Day 6 프로젝트 Canonical/Data Quality 정책이다.
eCount API 자체에서 해당 필드를 모두 필수 Request/Response field라고
공식 확인했다는 의미가 아니다.

실제 API field requiredness는 로그인 후 eCount 세부 API 매뉴얼에서 다시 확인한다.

## 9. Source Identity

Day 6 Synthetic Fixture에서는 deterministic fixture identity를 사용한다.

실제 API용 production source identity 규칙은
eCount의 상세 endpoint/field 계약을 확인하기 전 확정하지 않는다.

동일 Fixture 입력은 Canonical business effect를 한 번만 발생시켜야 한다.

## 10. Source Quality 정책

현재 실제 eCount 데이터:

- source_quality: SOURCE_QUALITY_BLOCKED

의미:

실제 데이터가 존재하지 않는 것이 아니라,
현재 운영 데이터가 프로젝트의 기준값으로 신뢰할 수 없는 상태다.

금지:

- 실제 잘못된 재고를 0으로 변환
- 실제 잘못된 재고를 정상 Snapshot으로 적재
- Fixture 결과를 실제 운영 검증으로 표시
- Synthetic 결과를 LIVE_READ 또는 FILE_IMPORT로 승격

## 11. Write Safety

Core Build에서 eCount 외부 Write API는 호출하지 않는다.

금지:

- 재고 수정
- 구매 입력
- 판매 입력
- 품목 수정
- 생산 입출고
- 기타 운영 ERP 변경

write_call_count 목표는 항상 0이다.

## 12. Day 6 현재 결정표

| Resource | Connection Mode | Verification Level | Source Quality |
|---|---|---|---|
| item | API_POLL | CONTRACT_ONLY | OFFICIAL_CONTRACT_VERIFIED |
| inventory | API_POLL | CONTRACT_ONLY | SOURCE_QUALITY_BLOCKED |
| warehouse_inventory | API_POLL | CONTRACT_ONLY | SOURCE_QUALITY_BLOCKED |
| incoming_stock | UNKNOWN/BLOCKED | CONTRACT_ONLY | NOT_VERIFIED |
| sale | UNKNOWN/BLOCKED | CONTRACT_ONLY | NOT_VERIFIED |

## 13. 다음 검토 조건

다음 자료를 확인하면 판정을 다시 검토한다.

- 로그인 후 eCount 세부 Open API 매뉴얼
- Inventory 상세 Response field
- Warehouse Inventory 상세 Response field
- product code / warehouse / unit field 규칙
- pagination
- rate limit
- authentication
- 발주서와 실제 confirmed incoming stock 관계
- 실제 재고 정합성 회복 후 새 Snapshot

검증 전에는 LIVE_READ로 승격하지 않는다.