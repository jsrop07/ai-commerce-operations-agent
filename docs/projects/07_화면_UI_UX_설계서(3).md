# 07. 화면 UI·UX 설계서

> **이 문서는 무엇인가:** 운영자가 어떤 화면에서 어떤 근거를 보고 무엇을 판단하는지 정한다.  
> **언제 읽는가:** 화면·컴포넌트·상태 표시를 만들기 전, 통합 확인일의 사용자 흐름을 준비할 때 읽는다.  
> **핵심 판단:** 화려한 AI 문장보다 데이터 시점, 근거, 신뢰도, 위험, 다음 행동을 먼저 보여준다.

## 0. Figma AI → 통합 구현 묶음 절차

### 0.1 역할 분리

Figma AI는 디자인 시스템·화면 구성·상태 Variant를 한 번에 만든다. 프론트 질문지는 Figma 결과 검수와 `frontend/design/figma/handoff.md` 작성까지 수행한다. 실제 코드는 화면마다 Codex를 호출하지 않고, Day 5~8 이후의 통합 Codex 묶음에서 Token·Component Mapping과 `05_데이터_API_명세서.md`의 데이터 계약을 기준으로 `frontend/`에 화면군 단위로 구현한다. Figma 이미지나 자동 생성 코드를 그대로 Production에 배포하지 않는다.

Codex 실행 전에는 다음 네 가지가 모두 준비되어야 한다.

1. 승인된 Figma Frame 이름과 링크
2. Token·Component Mapping
3. 연결할 OpenAPI/JSON Schema와 Mock 응답
4. 구현할 화면군의 작업 ID와 E2E 완료 기준

하나라도 없으면 Codex를 추가 호출하지 않고 프론트 질문지에서 인계 자료를 먼저 보완한다.

Figma 파일 페이지 구조는 다음으로 고정한다.

```text
00_Foundations
01_Components
02_Screens
03_States
04_Prototype
```

프레임 이름은 `Screen/{영역}/{상태}/Desktop` 형식을 사용한다. 예: `Screen/Inventory/Stale/Desktop`.

### 0.2 Figma AI Master Prompt

아래 Prompt를 한 번에 입력하여 최초 디자인을 만든다.

```text
Create a desktop-first Korean B2B operations dashboard named “AI Commerce Operations Agent”.

Purpose:
Unify Cafe24 online orders, Toss POS offline sales, and eCount inventory/incoming-stock data. Help operators detect inventory mismatch, reservation shortage, incoming/launch delay, and customer-inquiry risk. This is a decision-support tool, not an autonomous commerce controller.

Canvas and style:
- Desktop 1280px minimum width
- Dense but readable professional operations UI
- Neutral gray/white base
- Rule/source data: blue
- AI result: violet
- Human decision: gray/green
- Warning: amber with text/icon
- Critical: red with text/icon
- Demo environment: blue banner
- Production Read-Only: persistent red-outline banner
- Use an 8px spacing system, clear typography hierarchy, compact tables, accessible contrast and visible keyboard focus

Create these pages:
00_Foundations, 01_Components, 02_Screens, 03_States, 04_Prototype.

Create reusable components and variants:
Navigation, top header, environment banner, provider health badge, freshness badge, risk badge, confidence badge, rule/AI/human badge, dense data table, filter bar, KPI card, evidence card, right-side evidence drawer, timeline, before/after diff, mapping-review row, task-proposal card, modal, toast, skeleton and empty-state panel.

Create seven desktop screens:
1. Home / Operations Dashboard
2. Products & Inventory
3. Orders & Sales
4. Customer Inquiry / AI Draft
5. Operations Schedule
6. AI Insights & Evaluation
7. Integrations & Settings

Every relevant record must display source/provider, as_of timestamp, freshness, confidence or reason, and an evidence entry point.

Create explicit variants for:
Loading, Empty, Stale, Partial Provider Failure, Denied, Ambiguous Mapping, Low AI Confidence and Agent Waiting.

Safety rules:
- Never create actions that automatically refund, cancel orders, change prices, change real inventory, make payments or settle money.
- Customer replies are Draft only.
- Schedule changes are Proposal/Before-After review only.
- Production is Read-Only.
- Demo event simulator appears only in Demo mode.
- Do not use real personal information, real store identifiers or real credentials. Use Korean synthetic data.

Prototype these flows:
A. Dashboard risk → inventory evidence drawer → task proposal
B. Reservation shortage → calculation evidence → review task
C. Inquiry → intent/entity → citations → answer draft → hold/review
D. Incoming delay → impact → before/after replan proposal
E. Ambiguous product mapping → candidate review

Do not invent backend field names. Label data regions semantically and add a note that final field names come from the OpenAPI/JSON Schema contract.
```

### 0.3 Figma 결과 검수표

| 구분 | 필수 결과 | 불합격 조건 |
|---|---|---|
| 화면 | 7개 Desktop 화면 | 화면 누락 또는 이름 불명확 |
| 공통요소 | Navigation/Header/Table/Card/Badge/Drawer/Filter/Modal/Toast | 화면별로 중복 복사되고 Component가 아님 |
| 상태 | Loading/Empty/Stale/Partial/Denied/Ambiguous/Low Confidence/Waiting | 성공 화면만 존재 |
| 근거 | source/as_of/freshness/evidence 진입점 | AI 문장만 있고 근거 없음 |
| 안전 | Read-Only·Draft·Proposal 표현 | 환불·취소·가격·실재고 변경 실행 CTA 존재 |
| 접근성 | 텍스트+아이콘 상태, focus, 대비 | 색상만으로 상태 구분 |
| 데이터 | 합성 한국어 예시 | 실제 PII·실제 사업 ID 포함 |

### 0.4 `frontend/design/figma/handoff.md` 필수 내용

```text
Figma file URL 또는 파일 식별자
확정 frame 목록
색상·타이포·간격·radius·shadow token
공통 component와 variant 목록
화면 → React route 매핑
Figma component → 코드 component 매핑
화면별 사용 API/Mock Contract
상태별 Fixture 이름
금지 CTA 검수 결과
미결 디자인 항목과 담당자
확정일·디자인 버전
```

Figma 자동 생성 React 코드는 참고만 한다. 코드의 완료 기준은 Figma 유사도가 아니라 Contract Test, 상태 처리, 접근성, E2E와 안전 시험이다.

## 1. UX 목표

운영자가 30초 안에 `무슨 문제인가 → 왜 그런가 → 지금 무엇을 해야 하는가 → 실행 위험은 무엇인가`를 판단하도록 한다. AI 결과는 화려한 문장보다 상태·근거·신뢰도·다음 행동을 우선한다.

### 원칙

- AI/Rule/사람 입력의 출처를 구분
- live data의 `as_of`와 stale 상태를 항상 표시
- Suggestion/Draft/Approved/Executed 상태를 시각·텍스트로 구분
- 고위험 행동은 UI shortcut으로 실행할 수 없음
- 값 변화는 before/after diff와 영향 범위 제공
- 색상만으로 위험/상태를 표현하지 않음
- Demo Mode를 화면 전체에서 명확히 표시

## 2. 화면 정보 구조

| # | 영역 | 핵심 질문 |
|---:|---|---|
| 1 | Home / Operations Dashboard | 오늘 가장 먼저 처리할 것은? |
| 2 | Products & Inventory | 어떤 SKU가 왜 위험하며 데이터가 최신인가? |
| 3 | Orders & Sales | 채널별 판매·예약·반품 상태는? |
| 4 | Customer Inquiry / AI CS | 어떤 문의이며 어떤 근거로 답할까? |
| 5 | Operations Schedule | 지연이 어떤 Task/출시에 영향을 주는가? |
| 6 | AI Insights | AI/Rule이 발견한 패턴과 근거는? |
| 7 | 외부 연동·설정 | 연동·상품 연결·권한·비용·긴급 차단 상태는? |

## 3. 공통 화면 틀

- 좌측 Navigation: 7개 영역, badge는 critical count만
- 상단: tenant/environment, provider health, global freshness, AI budget, Kill Switch status
- 검색: 상품명/SKU/주문/Task; PII 검색 권한 별도
- 우측 Trace Drawer: Source, calculation, retrieval citation, model/prompt/index version, timing
- Notification Center: stale/mapping/agent failure/safety deny
- Demo Control: Synthetic event simulator는 Demo에서만 노출

## 4. 홈·운영 현황판

### 화면 배치

1. 상태바: Provider 연결, 마지막 sync, stale 경고
2. 긴급 Queue: 예약 부족, 재고 불일치, 일정 충돌, 중요 문의
3. 오늘의 업무: Priority score와 이유, deadline, 영향
4. 채널 KPI: 온라인/오프라인 판매와 데이터 시점
5. AI 발견: anomaly/반복 이슈/운영 병목
6. 자동 준비: 생성된 Task/Draft/재계획 제안

각 카드에는 `severity`, `source`, `as_of`, `confidence`, `why`, `open evidence`, `create/review task`가 있어야 한다. 매출은 AI Insight보다 원천 집계임을 표시한다.

## 5. 상품·재고

### 목록 화면

컬럼: Product/SKU, Brand, 채널별 Snapshot, Expected, Reserved, Incoming, Days of Cover, Risk, Mapping, Freshness.

필터: brand/category/language/base game/expansion/channel/risk/mapping/freshness. Ambiguous mapping과 stale inventory는 상단 고정 filter 제공.

### 상세 화면

- Inventory equation과 source snapshot/ledger timeline
- Reservation demand와 Incoming Stock
- Product relation: BaseGame/Expansion/Component/Compatibility
- Inquiry/Return signal
- Risk feature contribution
- 제안 Task와 과거 operator feedback

실재고 수정 CTA는 Core Build Production에 존재하지 않는다. Demo/Pilot에서도 `Proposal → Diff → Approval` 경로만 제공한다.

## 6. 주문·판매

- channel/type/status/date 필터
- online/offline event timeline과 dedupe 상태
- reservation shortage/aging
- cancellation/return은 분석용 표시; 자동 처리 버튼 없음
- 주문 Detail의 고객정보는 기본 마스킹, 권한과 목적이 있을 때만 protected view
- reconciliation mismatch와 source record link

## 7. 고객문의·AI 답변 초안

### 세 영역 화면 구성

1. Inbox: intent/risk/status/age
2. Conversation: sanitized content, related product/order reference
3. AI Workbench: structured intent/entity, retrieved evidence, Draft, confidence, warnings

Draft actions: `수정`, `승인 대기`, `보류`, `근거 부족`, `거절`. Core Build에서 실제 전송은 비활성화하거나 DemoProvider만 사용한다. 고위험 유형은 붉은 경고와 “운영 시스템에서 사람이 처리” 안내를 표시한다.

Citation을 클릭하면 문서/상품 field와 updated_at을 보여준다. 서로 충돌하는 근거는 하나를 숨기지 않고 conflict state로 제시한다.

## 8. 운영 일정

- Calendar + Dependency list/graph를 토글
- Launch Event 생성 시 Flow A/B와 Task Template 미리보기
- Deadline 역산, owner, duration, predecessor
- Incoming delay Event 입력 시 impacted task 강조
- Replan panel: original vs proposed dates, reason, downstream impact, confidence
- 승인 전에는 기존 일정이 유지되고 proposed overlay만 표시

오늘의 Task 정렬에는 `deadline/risk/business impact/aging` 구성 점수를 열어볼 수 있어야 한다.

## 9. AI 분석 결과

Insight 유형: inventory risk, reservation risk, repeated inquiry/return, schedule bottleneck, sales signal.

목록과 Detail 모두 다음을 제공한다.

- Rule/Model badge
- summary와 operational impact
- evidence count/source freshness
- confidence와 calibration band
- calculation 또는 retrieval path
- proposed action/task
- operator feedback(correct/useful/not useful/reason)
- model/prompt/rule/index version

Insight가 LLM 문장일 뿐이면 표시하지 않는다. evidence가 없으면 `Evidence unavailable`과 no-action 상태다.

Rule/Model badge는 응답 계약이 출처를 명시한 경우에만 표시한다. `model_run_id=null`만으로 Rule이라고 추론하지 않으며, provenance가 미확정이면 `출처 확인 불가`로 표시한다. AI Raw Response를 `InsightSummary`로 강제 변환하거나 Backend에 없는 evidence/proposal을 화면에서 생성하지 않는다.

## 10. 외부 연동·설정

### 설정 영역

- Provider capability/health/last sync/rate limit
- SKU Mapping Review Queue
- 자동화 단계: 읽기, 제안, 그림자 계산, 승인형 시범운영(환경 진입 조건 연동)
- Approval policy와 role
- Global/provider/AI Kill Switch
- AI model route/budget/cache metric
- data retention/PII scan status
- Demo seed/reset

Production Core Build에서 automation level은 UI 조작으로 Shadow/Write로 올릴 수 없다. 서버 정책이 source of truth다.

## 11. 데모 이벤트 발생기

Demo 전용 고정 시나리오:

| Event | 조작 | 기대 표시 |
|---|---|---|
| Online Order | SKU/qty | order, expected stock, risk update |
| Offline Sale | SKU/qty + duplicate toggle | dedupe, ledger, task |
| Reservation | qty/promised date | shortage/aging/task |
| Inquiry | template/free text | NLU, retrieval, Draft/citation |
| Stock Shortage | snapshot delta | discrepancy/risk |
| Incoming Delay | delay days | impacted schedule/replan |

`Run Scenario` 후 Event→Service→AI/Rule→Output을 단계별 Trace로 재생한다. Production 연결 상태에서는 Simulator를 숨기고 API도 거부한다.

## 12. 핵심 사용자 흐름

### 12.1 예약주문

Dashboard Alert → Reservation Detail → 부족 계산 근거 → Incoming 확인 → Task 제안 검토 → owner/deadline 수정 → 승인 → Audit.

### 12.2 입고 지연

Delay notification → Launch Event → 영향 Task → original/proposed diff → conflict 확인 → 일정 승인/거절 → Task 갱신.

### 12.3 고객문의 답변 초안

Inquiry open → intent/entity 검토 → citation 확인 → Draft 수정 → 승인 대기/보류. 고위험이면 자동으로 manual instruction.

## 13. 상태와 오류 표시

| 상태 | UI 처리 |
|---|---|
| Loading | 영역 skeleton, 전체 화면 block 금지 |
| Empty | 원인과 다음 수집/Simulator action |
| Stale | timestamp badge, action 제한 |
| Partial Provider Failure | 성공 source 유지, 실패 source 명시 |
| Ambiguous Mapping | 후보와 근거, manual resolution |
| Low AI Confidence | human review, alternative/clarify |
| Agent Waiting | checkpoint/node/필요 승인 표시 |
| Policy Denied | 숨기지 않고 reason code와 안전 설명 |
| Budget Exceeded | degraded route와 영향 기능 표시 |

## 14. 시각 표현 기준

- Neutral base + Track/status accent
- 위험: Critical red, Warning amber, Safe green에 아이콘/텍스트 병행
- AI: violet, Rule: blue, Human: gray/green badge
- Production: 고정 red outline/label, Demo: blue label
- 표는 dense하지만 row detail drawer로 근거를 분리
- 숫자는 단위·channel·as_of가 없으면 표시하지 않음

## 15. 접근성과 반응형 화면

- WCAG AA 대비 목표, focus indicator, keyboard table navigation
- icon-only action 금지, aria label
- Desktop-first(운영 도구), 1280px 기준; 핵심 Alert/Task는 tablet 대응
- 대형 relation graph는 대체 list/table 제공

## 16. 화면 개발 합격 조건

- OpenAPI mock과 실제 Backend response의 contract test 통과
- 6개 Demo Scenario가 mock→실제 pipeline으로 교체되어 동일 UI에서 동작
- stale/partial/denied/ambiguous/low-confidence 상태 screenshot test
- 실제 PII/production identifiers가 build artifact에 0건
- Insight detail에서 source와 pipeline trace까지 2단계 이내 접근
- 승인 전/후/실행 상태를 혼동시키는 UI 결함 0건
