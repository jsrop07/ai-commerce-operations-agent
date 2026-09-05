# Cafe24 Provider Capability 결정기록

## 1. 기본 정보

* Provider: `CAFE24`
* 공식 Day: `Day 5`
* 작업 ID: `D05-BE-01`
* 확인일: `2026-09-04`
* 확인자: `user`
* 현재 검증 수준: `DOCUMENT_VERIFIED`
* 실제 Credential 검증: `NO`
* 실제 Read 승인: `NO`
* 현재 연결 방식: `CONTRACT_ONLY`

이 문서는 Cafe24 데이터를 실제 운영 시스템에서 안전하게 조회하기 전에, 공식 문서를 기준으로 어떤 데이터를 어떤 권한과 방식으로 읽을 수 있는지 기록하기 위한 결정기록이다.

실제 Cafe24 API 호출은 이 문서의 공식 근거와 Credential Scope, Read-Only Guard를 모두 확인한 뒤에만 수행한다.

---

## 2. 공통 API 기준

### API 방식

* API 종류: Cafe24 Admin REST API
* 인증 방식: OAuth 2.0
* 통신 방식: HTTPS
* 요청/응답 형식: JSON
* Core Build에서 허용하는 외부 HTTP Method: `GET`만 허용

Cafe24에서 공식적으로 제공하는 조회 API를 통해 실제 데이터를 읽되, 21일 Portfolio Core Build에서는 Cafe24 원본 주문·상품·재고 등의 상태를 변경하지 않는다.

외부 Provider를 대상으로 다음 Method는 허용하지 않는다.

* `POST`
* `PUT`
* `PATCH`
* `DELETE`

허용되지 않은 Method 또는 Path는 실제 HTTP Transport에 도달하기 전에 Backend에서 차단한다.

---

## 3. Resource별 결정

### 3.1 상품 Products

* 프로젝트 계약 메서드: `CommerceProvider.read_products()`
* Capability 상태: `SUPPORTED`
* 연결 방식 후보: `API_POLL`
* 실제 API 검증: `NOT_DONE`

#### 공식 근거

Cafe24 Admin API에서 상품 조회 기능이 공식 제공된다.

확인한 상품 관련 Read API 예:

* `GET /products/{product_no}`
* `GET /products/{product_no}/variants`

상품 조회를 위한 공식 Read Scope가 존재한다.

확인된 Scope 표기:

* `READ_PRODUCT`

확인된 문서상 호출 제한:

* `40 calls/sec`

확인한 Product Read Endpoint의 요청당 item 제한:

* 최대 `100 items`

#### 현재 판단

공식 문서상 상품 조회 API가 존재하므로 `products_read=SUPPORTED`로 판단한다.

하지만 현재 프로젝트에서 사용할 실제 Cafe24 App Credential과 Scope를 아직 확인하지 않았으므로 실제 연동 수준은 `LIVE_READ`가 아니다.

현재는 `CONTRACT_ONLY` 상태를 유지한다.

---

### 3.2 주문 Orders

* 프로젝트 계약 메서드: `CommerceProvider.read_orders()`
* Capability 상태: `SUPPORTED`
* 연결 방식 후보: `API_POLL`
* 실제 API 검증: `NOT_DONE`

#### 공식 근거

Cafe24 Admin API에서 주문 목록 조회 API가 공식 제공된다.

확인한 Endpoint:

`GET /api/v2/admin/orders`

확인된 Read Scope:

`mall.read_order`

주문 조회에서 확인된 검색·페이지 관련 파라미터:

* `limit`
* `offset`
* `start_date`
* `end_date`

한 번의 요청에서 검색 가능한 날짜 범위는 최대 3개월이다.

여기서 3개월은 Cafe24 전체 주문 보관기간을 의미하는 것이 아니라, **한 요청에서 지정할 수 있는 검색기간 제한**이다.

따라서 프로젝트에서는 다음처럼 구분한다.

* 단일 요청 검색기간: 최대 3개월
* 전체 과거 주문 조회 가능 기간: `VERIFY`

#### 반품 관련 근거

Cafe24 주문 API에는 `return` 관련 하위 Resource를 포함하여 조회할 수 있는 구조가 존재한다.

하지만 현재 공통 `CommerceProvider`에는 별도 `read_returns()` 메서드가 존재하지 않는다.

따라서 D05-BE-01에서 공통 계약에 `read_returns()`를 임의 추가하지 않는다.

기존 `read_orders()`의 주문 데이터에서 필요한 반품 정보를 얻을 수 있는지 이후 Mapper 단계에서 먼저 검증한다.

#### 현재 판단

공식 주문 Read API가 존재하므로 `orders_read=SUPPORTED`로 판단한다.

실제 Credential과 Scope 검증 전까지 실제 연결 수준은 `CONTRACT_ONLY`로 유지한다.

---

### 3.3 고객문의 Inquiries

* 프로젝트 계약 메서드: `CommerceProvider.read_inquiries()`
* Capability 상태: `VERIFY`
* 연결 방식: `CONTRACT_ONLY`
* 실제 API 검증: `NOT_DONE`

#### 공식 근거

Cafe24에는 게시판/커뮤니티 글을 조회할 수 있는 공식 Read API가 존재한다.

확인한 예:

`GET /boards/{board_no}/articles`

관련 Read Scope:

`read_community`

확인된 호출 제한:

* `40 calls/sec`

확인한 Endpoint의 요청당 최대 item 수:

* `100 items`

#### 미확정 사항

이 프로젝트의 Canonical `Inquiry`가 Cafe24의 일반 게시판 글과 완전히 동일하다고 가정하지 않는다.

실제 사업에서 사용하는 문의가 다음 중 무엇인지 확인해야 한다.

* 상품 문의
* 일반 게시판
* 1:1 문의
* 기타 Cafe24 문의 Resource

#### 현재 판단

Cafe24에서 문의 성격의 Read API는 존재하지만 프로젝트 `Inquiry`와의 정확한 Mapping이 확정되지 않았다.

따라서:

`inquiries_read=VERIFY`

상태를 유지한다.

실제 문의 API 호출과 Adapter 구현은 아직 수행하지 않는다.

---

### 3.4 재고 Inventory

* 프로젝트 계약 메서드: `CommerceProvider.read_inventory()`
* Capability 상태: `VERIFY`
* 연결 방식: `CONTRACT_ONLY`
* 실제 API 검증: `NOT_DONE`

#### 미확정 사항

현재 이 결정기록에서는 프로젝트가 사용할 Cafe24 재고 Snapshot의 정확한 공식 Endpoint와 최소 Read Scope를 아직 확정하지 않았다.

Endpoint나 Scope를 추측하여 구현하지 않는다.

#### 현재 판단

`inventory_read=VERIFY`

실제 공식 Resource와 Scope가 확인되기 전에는 Live Adapter에 연결하지 않는다.

---

### 3.5 입고예정 Incoming Stock

* 프로젝트 계약 메서드: `CommerceProvider.read_incoming_stock()`
* Capability 상태: `UNKNOWN`
* 연결 방식: `CONTRACT_ONLY`
* 실제 API 검증: `NOT_DONE`

현재 프로젝트 요구사항을 만족하는 Cafe24 입고예정 데이터 Resource가 공식적으로 확정되지 않았다.

숫자나 Endpoint를 추측하지 않는다.

따라서:

`incoming_stock_read=UNKNOWN`

으로 유지한다.

---

### 3.6 반품 Returns

현재 공통 `CommerceProvider`에는 `read_returns()`가 없다.

현재 존재하는 공통 Read 메서드는 다음과 같다.

* `read_products()`
* `read_orders()`
* `read_inventory()`
* `read_inquiries()`
* `read_incoming_stock()`

Cafe24 주문 API에서 `return` 관련 정보를 조회할 수 있는 근거가 있기 때문에 별도 Provider Contract를 추가하기 전에 기존 `read_orders()`를 통해 필요한 정보를 얻을 수 있는지 우선 확인한다.

#### 현재 판단

* 별도 Return Capability: `VERIFY`
* 공통 Contract 변경: `NOT_APPROVED`
* D05-BE-01에서는 Finding으로만 기록

---

## 4. Pagination과 조회 제한

확인된 Cafe24 Resource는 각 API별로 Pagination과 요청 제한이 존재한다.

주문 목록의 경우 다음 파라미터를 사용한다.

* `limit`
* `offset`

상품/커뮤니티 등 확인한 일부 Endpoint는 요청당 최대 `100 items` 제한이 존재한다.

그러나 Provider 자체 최대 허용치와 프로젝트의 실제 연결 시험 제한은 다르다.

### D05-BE-05 프로젝트 Smoke 제한

실제 Read가 승인된 경우에도 다음을 넘지 않는다.

* `max_pages = 2`
* `max_items = 50`

Cafe24 공식 API가 더 많은 데이터를 허용하더라도 Day 5 Smoke에서는 프로젝트 안전 제한을 우선한다.

---

## 5. Credential 및 안전 결정

실제 Cafe24 API를 호출하기 전에 다음 조건을 모두 확인해야 한다.

* 실제 사업 Owner의 Read 승인
* Credential은 Git/문서/로그 밖에서 관리
* 필요한 Read Scope가 존재하는지 확인
* 불명확한 Scope가 없는지 확인
* Write Scope가 포함되어 있지 않은지 확인
* HTTP Method가 `GET`인지 확인
* 요청 Path가 프로젝트 Read Allowlist에 있는지 확인
* Authorization Token을 로그에 출력하지 않음
* 실제 Request/Response Body를 일반 로그에 저장하지 않음
* 외부 Write Call Count가 항상 `0`

하나라도 만족하지 못하면 Provider HTTP 호출 전에 차단한다.

---

## 6. 현재 Capability Matrix 결정

| Resource        | Capability      | 현재 연결 수준        | Live 검증 |
| --------------- | --------------- | --------------- | ------- |
| Products        | `SUPPORTED`     | `CONTRACT_ONLY` | NO      |
| Orders          | `SUPPORTED`     | `CONTRACT_ONLY` | NO      |
| Inventory       | `VERIFY`        | `CONTRACT_ONLY` | NO      |
| Inquiries       | `VERIFY`        | `CONTRACT_ONLY` | NO      |
| Incoming Stock  | `UNKNOWN`       | `CONTRACT_ONLY` | NO      |
| Inventory Write | `DISABLED_CORE` | 사용 금지           | NO      |

현재 Provider 전체 연결 수준:

`CONTRACT_ONLY`

공식 문서만으로 API 존재 여부를 확인한 상태이며 실제 Credential/Scope/승인/제한 Read Smoke는 수행하지 않았다.

따라서 현재 상태를 `LIVE_READ`로 표시하지 않는다.

---

## 7. 열린 Finding

### D05-BE-FINDING-001 — Return Contract 불일치

현재 공유 `CommerceProvider`에는 `read_returns()`가 없다.

Cafe24 주문 API에서는 Return 관련 데이터를 주문 Resource의 일부로 읽을 가능성이 있으므로 새로운 공유 Contract가 필요하다고 아직 판단할 수 없다.

#### 조치

* `contracts/providers.py` 수정 금지
* `CommerceProvider`에 `read_returns()` 임의 추가 금지
* Cafe24 Order Mapper에서 기존 구조로 충족 가능한지 이후 확인

---

### D05-BE-FINDING-002 — Inquiry Resource Mapping 미확정

Cafe24 커뮤니티/게시판 Read API는 존재한다.

하지만 실제 사업의 문의 채널과 프로젝트 Canonical `Inquiry`가 해당 Resource와 정확히 대응하는지는 확인되지 않았다.

#### 조치

* `inquiries_read=VERIFY` 유지
* 실제 문의 Read 호출 금지
* 실제 문의 Resource 확인 후 재판정

---

### D05-BE-FINDING-003 — Inventory / Incoming Resource 미확정

공통 Provider 계약에는 `read_inventory()`와 `read_incoming_stock()`이 존재한다.

하지만 이 프로젝트에서 사용할 Cafe24의 정확한 공식 Resource/Scope는 아직 확정되지 않았다.

#### 조치

* `inventory_read=VERIFY`
* `incoming_stock_read=UNKNOWN`
* Endpoint 추측 금지
* 공식 근거 확보 후 다시 판단

---
## 8. D05-BE-01 최종 상태

상태:

`PASS`

Provider 검증 수준:

`CONTRACT_ONLY`

실제 Cafe24 Live Read:

`NOT_EXECUTED`

### 완료

* 기존 `ProviderReadPage` 계약 확인
* 기존 `CommerceProvider` Interface 확인
* 기존 Cafe24 Mock 구조 확인
* Provider Contract Test 확인
* Cafe24 상품 Read 공식 근거 확인
* Cafe24 주문 Read 공식 근거 확인
* Cafe24 문의 관련 공식 Read 근거 확인
* Return Contract 차이 Finding 기록
* `.env.example`에 Cafe24 설정 Key 추가
* `Settings`에 Cafe24 환경설정 구조 추가
* Cafe24 설정값이 없어도 Local/Mock 환경이 정상 실행되는 것을 확인
* 실제 Credential 값은 저장소·문서·로그에 기록하지 않음

### Credential 확인 결과

2026-09-04 로컬 환경 확인 결과:

* `CAFE24_MALL_ID`: 미설정
* `CAFE24_ACCESS_TOKEN`: 미설정
* `CAFE24_API_VERSION`: 미설정
* 실제 부여 Scope: 미확인
* Owner 승인 기반 Live Read: 미실행

### 판정

Cafe24 공식 Read API와 프로젝트 연결 구조는 확인했지만 실제 Credential과 Scope가 준비되지 않았으므로 실제 Provider Read는 수행하지 않았다.

따라서 D05-BE-01은 공식 근거와 Contract 결정까지 완료한 `PASS / CONTRACT_ONLY`로 판정한다.

이 상태를 `LIVE_READ`로 표시하지 않는다.

---

## 9. D05-BE-02 — Cafe24 Read Adapter 결과

상태:

`PASS / FIXTURE_VERIFIED`

### 구현 결과

실제 Cafe24용 `Cafe24Adapter`를 기존 `CommerceProvider` Interface에 맞춰 추가했다.

현재 확정된 Resource만 실제 Read 경계를 구현했다.

* Products
* Orders

미확정 Resource는 외부 호출 없이 차단한다.

* Inventory: `VERIFY`
* Inquiries: `VERIFY`
* Incoming Stock: `UNKNOWN`

### ProviderReadPage 연결

Cafe24 상품/주문 Fixture 응답을 기존 공통 계약인 `ProviderReadPage`로 변환하도록 구현했다.

확인 항목:

* `provider=CAFE24`
* `resource`
* `items`
* `next_cursor`
* `watermark`
* `has_more`
* `request_count`
* `source_as_of`
* `schema_version=provider-read-page.v1`

Pagination은 Day 5 최소 구현에서 `offset` 기반 Cursor를 사용한다.

예:

`offset:25`

### 검증 결과

Cafe24 Adapter 단위시험:

`11 passed`

실제 Cafe24 Network Call:

`0`

---

## 10. D05-BE-03 — Credential Scope / HTTP Read-Only Guard 결과

상태:

`PASS`

### 구현한 안전 경계

실제 Provider Transport 전에 다음을 검사한다.

1. 필요한 Read Scope 존재 여부
2. HTTP Method가 `GET`인지 확인
3. Path가 Read Allowlist에 포함되는지 확인

현재 Cafe24 Read Allowlist:

* `/api/v2/admin/products`
* `/api/v2/admin/orders`

현재 Guard 기준 Scope:

* Products: `mall.read_product`
* Orders: `mall.read_order`

### 차단 대상

다음 Method는 실제 HTTP Transport 전에 차단한다.

* `POST`
* `PUT`
* `PATCH`
* `DELETE`

다음 경우도 외부 호출 전에 차단한다.

* 필요한 Scope 없음
* Scope 확인 불가
* Allowlist에 없는 Path
* 잘못된 Cursor

### 검증 결과

Read Guard 단위시험:

`9 passed`

Provider + Safety 관련 시험:

`44 passed`

Write-like Method 차단 시 Transport 호출:

`0`

---

## 11. D05-BE-04 — Raw 보호 참조 / Sanitized Staging 결과

상태:

`PASS`

### 구현 경계

Cafe24 Raw Record를 일반 Pipeline에 바로 전달하지 않고 다음 경계를 적용한다.

`Cafe24 raw item`

→ `ProtectedRawReference`

→ `raw SHA-256`

→ 민감 필드 제거

→ `SanitizedStagingRecord`

→ `ProviderReadPage`

### 일반 Pipeline에서 제거하는 대표 민감 필드

* 고객 이름
* 수령인 이름
* 전화번호
* 휴대전화번호
* 이메일
* 주소
* 우편번호
* Password
* Secret
* Access Token
* API Key
* Authorization

중첩 `dict`와 `list` 내부의 민감 필드도 동일하게 제거한다.

### Raw 추적 방식

일반 Pipeline에는 Raw 원문을 저장하지 않는다.

대신 다음만 유지한다.

* `raw_sha256`
* 보호 저장소 Reference

Day 5에서는 실제 보호 Object Storage 전체를 구현하지 않고 `protected://...` 형태의 보호 참조 경계를 검증한다.

### 검증 결과

Staging 단위시험:

`5 passed`

Cafe24 Staging Boundary:

`3 passed`

Privacy 전체:

`8 passed`

Secret/PII Safety Scanner:

`PASS`

---

## 12. D05-BE-05 — 제한 Read Smoke

상태:

`BLOCKED_BY_CREDENTIAL`

검증 수준:

`CONTRACT_ONLY`

### 실행 전 확인 결과

로컬 환경 설정 확인:

* `CAFE24_MALL_ID=False`
* `CAFE24_ACCESS_TOKEN=False`
* `CAFE24_API_VERSION=False`

따라서 다음 조건을 확인할 수 없었다.

* 실제 Cafe24 Credential
* 실제 부여된 최소 Read Scope
* 실제 Cafe24 App API Version
* Owner 승인 기반 Live Read

### 결정

실제 Credential과 Scope가 준비되지 않았으므로 Cafe24 실제 HTTP Read Smoke를 실행하지 않는다.

D05-BE-05의 최대 제한:

* 최대 2 page
* 최대 50 item

은 Live Read 승인 후에만 사용한다.

### 실제 Provider 영향

* 실제 Cafe24 Read Call: `0`
* 실제 Cafe24 Write Call: `0`
* Cafe24 원본 변경: `0`
* 실제 Credential 로그 노출: `0`

Fixture 시험만 통과한 상태이므로 `LIVE_READ`로 표시하지 않는다.

---

## 13. Day 5 Backend 관련 최종 시험

### Provider / Privacy / Safety / Integration

실행:

`pytest backend\tests\providers backend\tests\privacy backend\tests\safety backend\tests\integration -q`

결과:

`65 passed in 1.25s`

### 전체 저장소 pytest

실행:

`pytest -q`

결과:

`COLLECTION ERROR`

발생 위치:

`ai/tests/privacy/test_redaction.py`

오류:

`ModuleNotFoundError: No module named 'privacy.test_redaction'`

### 판정

이 오류는 Backend Day 5 코드 또는 Backend 시험에서 발생한 것이 아니다.

AI 트랙 소유 테스트의 import/collection 문제이므로 Backend 질문지에서 해당 AI 파일을 수정하지 않는다.

Backend Day 5 관련 범위에서는:

* Provider
* Privacy
* Safety
* Integration

시험이 모두 통과했으며 현재 Backend Day 5 blocking implementation defect는 확인되지 않았다.

---

## 14. Day 5 최종 Provider 판정

| 항목                      | 결과               |
| ----------------------- | ---------------- |
| Cafe24 공식 Capability 조사 | PASS             |
| Provider Contract       | PASS             |
| Products Adapter        | FIXTURE_VERIFIED |
| Orders Adapter          | FIXTURE_VERIFIED |
| Inventory               | VERIFY           |
| Inquiries               | VERIFY           |
| Incoming Stock          | UNKNOWN          |
| Read Scope Guard        | PASS             |
| GET-only Guard          | PASS             |
| Path Allowlist          | PASS             |
| Privacy/Staging         | PASS             |
| PII/Secret Scanner      | PASS             |
| 실제 Cafe24 Read          | NOT_EXECUTED     |
| 실제 Cafe24 Write         | 0                |
| 최종 Verification Level   | CONTRACT_ONLY    |

Day 5는 실제 Provider Credential 부재로 `LIVE_READ`까지 승격하지 않는다.

실제 Credential과 최소 Read Scope가 준비되면 D05-BE-05 제한 Smoke만 다시 수행하여 `LIVE_READ` 승격 여부를 재검증한다.
