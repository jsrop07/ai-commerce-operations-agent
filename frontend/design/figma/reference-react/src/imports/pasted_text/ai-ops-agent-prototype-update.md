Continue from the existing AI Commerce Operations Agent prototype.

IMPORTANT:
Do NOT redesign the existing seven primary screens from scratch.
Preserve the current visual style, navigation structure, tables, cards, spacing hierarchy and overall Korean B2B operations dashboard look.

This request is to COMPLETE and CORRECT the existing prototype for the D01 frontend design handoff.

All visible operator-facing UI text must be Korean.
English may remain only for unavoidable technical names such as:
AI, API, SKU, Cafe24, Toss POS, eCount, RAG and version identifiers in technical-detail views.

==================================================
1. PRESERVE THE SEVEN PRIMARY SCREENS
==================================================

Keep exactly these seven primary navigation areas:

1. 홈 / 운영 대시보드
2. 상품 & 재고
3. 주문 & 매출
4. 고객 문의 / AI 초안
5. 운영 일정
6. AI 인사이트 & 평가
7. 연동 & 설정

Do not add new primary navigation sections.

==================================================
2. OPERATOR-FIRST LANGUAGE
==================================================

The main UI is for store/business operators, not AI engineers.

Do not expose technical terminology in the default operator view when a simpler Korean explanation is possible.

Examples:

- Evidence Drawer → 판단 근거 / 상세 근거
- Task Proposal → 작업 제안 / 후속 조치 제안
- Confidence → 신뢰도
- Stale → 최신 정보 아님 / 데이터 지연
- Mapping → 상품 연결
- Ambiguous Mapping → 상품 연결 확인 필요
- Partial Provider Failure → 일부 연동 오류
- Agent Waiting → 담당자 확인 대기

Do not show terms such as:
BM25, vector similarity, model_run_id, prompt version, index version, retrieval score
in the normal operator-facing view.

Technical information may be available only in:
“상세 기술정보”
or
“처리 기록 보기”.

==================================================
3. AI INSIGHTS SCREEN — REMOVE ENGINEERING INFO FROM MAIN VIEW
==================================================

On the existing “AI 인사이트 & 평가” screen:

Remove the large “현재 사용 모델” section from the main operator view.

Do not prominently show:
- ops-forecast-v2.3
- inquiry-cls-v1.8
- draft-gen-v1.5
- BM25 + vector hybrid
- prompt/index/model versions

Instead, use that space for operator-relevant information such as:

- 오늘 분석 건수
- 검토 필요한 항목
- 평균 신뢰도
- 자동 실행 0건
- 데이터 기준 시각
- 주요 분석 유형

Each insight card should prioritize:

1. 무슨 문제가 발견됐는지
2. 운영에 어떤 영향이 있는지
3. 신뢰도
4. 데이터 기준 시각
5. 판단 근거 보기
6. 후속 조치 제안

Technical information should move to “상세 기술정보” or the detailed trace/evidence view.

==================================================
4. JUDGMENT EVIDENCE / DETAIL DRAWER
==================================================

Keep the existing right-side evidence/detail drawer behavior.

Rename the operator-facing concept to:
“판단 근거”
or
“상세 근거”.

Fix the current clipping issue:
- the drawer must not be visually cut off at the top or bottom
- header remains fixed
- bottom action area remains fixed
- middle content area scrolls internally
- close button must always remain visible

The operator-facing content must be easy to understand.

For inventory mismatch, show information such as:

- Cafe24 재고: 12개
- eCount 재고: 3개
- 차이: 9개
- Cafe24 마지막 확인: 3분 전
- eCount 마지막 확인: 47분 전
- 판단: eCount 정보가 오래되어 실제 차이가 아닐 가능성 있음
- 권장 조치: 재고 상태 확인 필요

Do not prioritize raw API terminology.

A secondary “상세 기술정보” section may show:
- source/provider
- calculation
- retrieval citation
- model/rule version
- prompt/index version
- timing
- tool/result/error
- trace ID

Never expose internal Chain-of-Thought.
Only show step, tool, evidence, result and error information.

==================================================
5. TASK PROPOSAL → OPERATOR-FRIENDLY WORK PROPOSAL
==================================================

Keep the task proposal functionality, but use operator-friendly wording.

Use:
“작업 제안”
or
“후속 조치 제안”.

Example:

재고 차이 확인 필요
- 상품: 레드벨벳 케이크 500g
- 우선순위: 높음
- 담당자: 미지정
- 기한: 오늘
- 이유: Cafe24와 eCount 재고 차이 9개

Safe CTA examples:
- 확인 업무 만들기
- 작업 제안 검토
- 담당자 지정

Do not create buttons that directly modify external provider data.

==================================================
6. PRODUCTS & INVENTORY — ROW CLICK MUST OPEN DETAIL
==================================================

The current product rows do nothing when clicked.
Fix this.

Clicking a product row in “상품 & 재고” must open a right-side inventory detail panel.

The detail must show operator-friendly inventory information.

Include:

- 상품명
- SKU
- 상품 연결 상태
- Cafe24 재고
- eCount 재고
- Toss POS 판매 반영 기반 예상 수량
- 예약 수량
- 확정 입고 수량
- 확정 입고 예정일
- 예상 가용재고
- 시스템 간 재고 차이
- 각 데이터의 마지막 갱신 시각
- freshness / 데이터 지연 여부
- 차이가 발생했을 가능성이 높은 이유
- 관련 위험
- 안전한 후속 조치

Example:

현재 재고 비교

Cafe24 재고        12개
eCount 재고         3개
Toss 판매 반영      -2개
예약 수량            4개
확정 입고            6개 / 9월 6일

예상 가용재고        12개
시스템 간 차이        7개

Possible explanation:
“Toss POS 판매 일부가 eCount에 아직 반영되지 않았거나,
eCount 데이터가 오래되어 차이가 발생했을 수 있습니다.”

Safe CTA:
“확인 업무 만들기”

DO NOT add:
- 재고 맞추기
- 재고 수정
- eCount에 반영
- Cafe24 재고 변경
- automatic inventory synchronization write action

Production Core Build is read-only.

==================================================
7. ORDERS & SALES — EXPLAIN STOCK SHORTAGE
==================================================

When an order has a “재고부족” risk badge, the operator must be able to understand WHY.

Do not display only a red badge.

Provide an easy detail entry point and show information such as:

“주문 필요 2개 / 확보 1개 / 부족 1개”

or:

- 주문 수량
- 현재 확보 재고
- 예약 재고
- 확정 입고
- 부족 수량
- 예상 배송 영향
- 다음 확인 항목

The purpose is to help the operator decide the next action.

Do not directly modify real inventory.

==================================================
8. PRODUCT MAPPING REVIEW
==================================================

Keep the existing “매핑검토” workflow.

Purpose:
Help a human determine whether products from Cafe24, Toss POS and eCount represent the same real product/SKU.

Do not display technical text such as:
“BM25 텍스트 유사도”.

Replace it with operator-friendly matching reasons such as:

- 이름이 매우 유사함
- 옵션 일부 일치
- 상품코드 불일치
- 용량이 다름
- 후보가 2개 있어 확인 필요
- 기존 연결 정보 없음

Show candidate confidence in an easy format if useful.

Keep:
- candidate selection
- human approval
- manual rejection / manual specification

Never automatically merge ambiguous products.

==================================================
9. CUSTOMER INQUIRY SCREEN — MAJOR LAYOUT CHANGE
==================================================

Redesign ONLY the layout of the existing “고객 문의 / AI 초안” screen.

Keep the same overall visual design.

Use a three-column layout:

LEFT COLUMN
- 문의 목록

MIDDLE COLUMN
- 문의 내용
- 문의 정보
- AI 분류
- 신뢰도
- 경고
- 답변 참고 정보

RIGHT COLUMN
- AI 답변 초안
- occupy the full vertical working area
- make this the largest and most prominent work area
- large editable draft area
- internal scrolling
- “확대 편집” control
- review actions fixed near the bottom

Move the current “문의 정보” into the middle column,
roughly where the small answer draft is currently located.

The AI draft must occupy the entire right-side column vertically.

==================================================
10. CUSTOMER INQUIRY — SIMPLIFY EVIDENCE
==================================================

Replace:

“인용 근거 (RAG 검색 결과)”

with:

“답변 참고 정보”

The operator should see easy-to-understand facts such as:

- 주문 상태: 준비중
- 배송 예정일: 9월 6일
- 상품: 레드벨벳 케이크 500g
- 배송 정책: 출고 후 평균 2~3영업일
- 관련 정책: 예약 상품은 입고 후 순차 발송

Do not show retrieval-engine terminology by default.

If necessary, provide a small secondary action:
“상세 출처 보기”

Only that detailed view may show technical source/citation information.

==================================================
11. CUSTOMER INQUIRY — DRAFT-ONLY SAFETY
==================================================

Remove any wording or CTA that implies actual sending.

Remove:
“검토 완료 → 발송 준비”

The AI response must remain Draft-only.

Clearly display:

“AI 답변 초안 · 실제 전송 아님”

Use only review actions such as:

- 수정
- 승인 대기
- 보류
- 근거 부족
- 거절

Do not add:
- 보내기
- 전송
- 자동 발송
- 환불 실행
- 주문 취소
- 가격 변경
- 재고 변경
- 결제
- 정산

==================================================
12. OPERATIONS SCHEDULE
==================================================

Keep the existing schedule and Before/After replan design.

Replace technical or unclear wording with operator-friendly language.

For example:

Instead of:
“AI 제안입니다.”

Use:
“일정 변경 제안입니다. 승인 전 실제 일정은 변경되지 않습니다.”

For incoming delay analysis, show:

- 무엇이 지연됐는지
- 며칠 지연됐는지
- 어떤 작업에 영향이 있는지
- 기존 일정
- 제안 일정
- 변경 이유
- 영향 범위
- 신뢰도
- 담당자 확인 필요 여부

Do not directly change the real schedule without approval.

==================================================
13. INTEGRATIONS & SETTINGS — ROLE LANGUAGE
==================================================

Keep the existing:
- 연동
- 알림
- 팀

tabs.

Clarify role/permission wording.

Avoid vague permissions such as:
“운영 실행”

if they could be misunderstood as permission to modify external commerce systems.

Prefer clear permission labels such as:

- 조회
- 내부 업무 승인
- AI 제안 검토
- 설정 관리
- 알림 관리

Clearly state:

“Production에서는 외부 주문·재고·가격·결제 변경 권한이 제공되지 않습니다.”

==================================================
14. ENVIRONMENT BANNER VARIANTS
==================================================

Keep the existing Demo banner.

Add a reusable Production Read-Only environment variant.

Text:

“Production Read-Only · 운영환경 읽기 전용”

Style:
- persistent
- red-outline warning treatment
- visible icon and text
- not color-only

Production Read-Only must never expose executable CTAs for:

- refund
- order cancellation
- price change
- real inventory modification
- payment
- settlement
- customer-message sending

==================================================
15. COMPLETE REQUIRED UI STATES
==================================================

Create reusable examples/variants for ALL of the following:

1. Loading
2. Empty
3. Stale
4. Partial Provider Failure
5. Denied
6. Ambiguous Mapping
7. Low AI Confidence
8. Agent Waiting

Use Korean operator-friendly labels.

LOADING
- section-level skeleton
- do not block the entire application

EMPTY
- explain why data is empty
- provide safe next action or Demo guidance

STALE
Operator text example:
“데이터 지연 · 최신 정보가 아닐 수 있습니다”
- show source
- show last updated/as_of
- downgrade risky recommendations

PARTIAL PROVIDER FAILURE
Operator text:
“일부 연동 오류”
- preserve successful provider data
- identify failed provider
- do not treat entire system as failed

DENIED
Operator text:
“안전 정책으로 실행 차단됨”
- show reason
- show reason code if useful
- show that no external provider change occurred

AMBIGUOUS MAPPING
Operator text:
“상품 연결 확인 필요”
- show candidates
- show easy matching reasons
- require human review

LOW AI CONFIDENCE
Operator text:
“AI 판단 신뢰도 낮음”
- human review required
- allow clarification / insufficient evidence handling

AGENT WAITING
Operator text:
“담당자 확인 대기”
- show workflow status
- current step/checkpoint
- required approval/review
- do not expose Chain-of-Thought

==================================================
16. COMMON COMPONENT COMPLETION
==================================================

Preserve existing reusable components.

Verify or add reusable components for:

- Navigation
- Header
- EnvironmentBanner
- Table
- Card
- Badge
- Judgment/Evidence Drawer
- Filter
- Modal
- Toast
- Skeleton
- Empty State
- Before/After Diff
- Mapping Review Row
- Task Proposal / Work Proposal Card

Do not duplicate components per screen when a reusable component can be shared.

==================================================
17. DESIGN TOKENS
==================================================

Do not redesign the UI.

Extract and normalize a design-token reference from the CURRENT design.

Document:

COLORS
- neutral background
- surface
- text
- muted text
- border
- primary
- rule/source
- AI
- human
- warning
- critical
- success
- Demo
- Production Read-Only

TYPOGRAPHY
- font family
- page title
- section title
- body
- caption
- table
- badge

SPACING
- 4px / 8px based scale

RADIUS
- small
- medium
- large

SHADOW
- card
- drawer
- modal

ALSO DOCUMENT
- table density
- icon sizing
- keyboard focus style

==================================================
18. ACCESSIBILITY
==================================================

Do not communicate status by color alone.

Use:
- text
- icon
- color

together.

Maintain:
- readable contrast
- visible keyboard focus
- keyboard-friendly table interactions
- no icon-only critical actions without labels

==================================================
19. SYNTHETIC DATA ONLY
==================================================

All displayed example data must be synthetic Korean demo data.

Do not use:
- real customer information
- real business identifiers
- real store IDs
- real credentials
- API secrets

Prefer clearly synthetic customer labels such as:

- 데모고객 001
- 데모고객 002

rather than realistic masked names.

==================================================
20. DATA CONTRACT SAFETY
==================================================

Do NOT invent backend API field names.

Semantic labels in the prototype are allowed.

Final implementation field names will come ONLY from the OpenAPI / JSON Schema contract.

Do not treat Figma-generated mock field names as backend contract fields.

==================================================
21. SAFETY RULES
==================================================

This product is a decision-support system.

Production is Read-Only.

Never create executable UI actions for:

- automatic refund
- order cancellation
- price changes
- real inventory changes
- payment
- settlement
- automatic customer message sending

Customer response:
Draft only.

Schedule:
Proposal + Before/After + human review.

Inventory:
analysis / comparison / work proposal only.

Ambiguous product mapping:
human decision required.

==================================================
22. FINAL HANDOFF SUMMARY
==================================================

After completing the changes, provide a concise handoff summary containing:

- final seven screen list
- major layout changes
- reusable component list
- component variants
- all required UI states
- design token names and values
- operator-facing terminology rules
- Production Read-Only rules
- Draft/Proposal safety rules
- unresolved design items
- files/components changed

Do not expose internal Chain-of-Thought.

The result should help a store operator understand within about 30 seconds:

1. 무슨 문제가 있는가
2. 왜 문제가 발생했는가
3. 데이터가 얼마나 최신인가
4. 지금 무엇을 확인하거나 처리해야 하는가
5. 시스템이 실제 운영 데이터를 자동으로 변경하는지 여부