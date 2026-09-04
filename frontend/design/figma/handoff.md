# AI Commerce Operations Agent — Figma → Frontend Handoff

- 상태: D01-FE-01 Figma 결과 동결본 인계
- 디자인 소스: Figma Make 생성 React 소스 아카이브 `AI Commerce Operations Dashboard.zip`
- 디자인 버전: Figma Make 최종 수정본 (2026-09-02 인계 기준)
- Figma URL: 미제공
- 공식 구현 루트: `frontend/`
- 공식 인계 위치: `frontend/design/figma/handoff.md`
- 중요: Figma Make React 코드는 시각/상호작용 참고본이다. Production 구현의 데이터 필드와 API 계약은 `05_데이터_API_명세서.md`를 단일 기준으로 사용한다.

## 1. 확정 화면

| 화면 | Figma Make 소스 | 권장 React route | 핵심 목적 |
|---|---|---|---|
| 홈 / 운영 대시보드 | `src/pages/Dashboard.tsx` | `/` | 긴급 위험, KPI, 판단 근거, 확인 업무 생성 |
| 상품 & 재고 | `src/pages/Inventory.tsx` | `/inventory` | 채널별 재고 비교, stale 경고, 상품 상세, 상품 연결 검토 |
| 주문 & 매출 | `src/pages/Orders.tsx` | `/orders` | 채널별 주문/판매, 주문별 재고 부족 상세 |
| 고객 문의 / AI 초안 | `src/pages/Inquiry.tsx` | `/inquiries` | 문의 목록, 문의 정보/분류/참고정보, AI 답변 Draft 검토 |
| 운영 일정 | `src/pages/Schedule.tsx` | `/schedule` | 입고 지연 영향, Before/After 재계획 제안, 승인 대기 |
| AI 인사이트 & 평가 | `src/pages/Insights.tsx` | `/insights` | 운영 패턴/위험/병목 설명, 판단 근거, 후속 조치 제안 |
| 연동 & 설정 | `src/pages/Settings.tsx` | `/settings` | Provider 상태, 알림, 팀 권한, 안전 차단 표현 |

현재 `src/App.tsx`는 React state로 화면을 전환하는 프로토타입이며 실제 Router는 없다. 통합 구현 시 공식 route를 구성한다.

## 2. 디자인 토큰 — 현재 소스에서 추출

### Typography

- Sans: `'Noto Sans KR', system-ui, sans-serif`
- Mono: `'JetBrains Mono', 'Courier New', monospace`
- 기본 본문: 13px / line-height 1.5
- 페이지 제목: 약 15px / 700
- Section/Modal 제목: 약 16px / 700
- Table: header 11px / body 12.5px
- Badge/Caption: 약 10~12px

### Color

| Token | Value | 용도 |
|---|---|---|
| `--bg` | `#F5F6F8` | 앱 배경 |
| `--surface` | `#FFFFFF` | 카드/패널 |
| `--surface-2` | `#F0F2F5` | 보조 surface |
| `--border` | `#E2E5EA` | 기본 border |
| `--border-strong` | `#C9CDD6` | 강한 border |
| `--text-primary` | `#111827` | 기본 텍스트 |
| `--text-secondary` | `#4B5563` | 보조 텍스트 |
| `--text-tertiary` | `#9CA3AF` | 비활성/메타 |
| `--rule-bg` | `#EFF6FF` | Rule/source 배경 |
| `--rule-border` | `#BFDBFE` | Rule/source border |
| `--rule-text` | `#1D4ED8` | Rule/source 텍스트 |
| `--rule-accent` | `#2563EB` | Primary/Rule accent |
| `--ai-bg` | `#F5F3FF` | AI 배경 |
| `--ai-border` | `#DDD6FE` | AI border |
| `--ai-text` | `#6D28D9` | AI 텍스트 |
| `--ai-accent` | `#7C3AED` | AI accent |
| `--human-bg` | `#F0FDF4` | 사람 판단 배경 |
| `--human-border` | `#BBF7D0` | 사람 판단 border |
| `--human-text` | `#15803D` | 사람 판단 텍스트 |
| `--human-accent` | `#16A34A` | 사람 판단 accent |
| `--warn-bg` | `#FFFBEB` | Warning 배경 |
| `--warn-border` | `#FDE68A` | Warning border |
| `--warn-text` | `#B45309` | Warning 텍스트 |
| `--warn-accent` | `#D97706` | Warning accent |
| `--crit-bg` | `#FEF2F2` | Critical 배경 |
| `--crit-border` | `#FECACA` | Critical border |
| `--crit-text` | `#B91C1C` | Critical 텍스트 |
| `--crit-accent` | `#DC2626` | Critical accent |
| `--nav-bg` | `#1E2433` | Navigation |
| `--nav-active` | `#2563EB` | Active nav |
| `--nav-hover` | `#2A3348` | Hover nav |
| `--nav-text` | `#94A3B8` | Nav text |

### Radius / Shadow / Density

- `--radius-sm`: 4px
- `--radius`: 6px
- `--radius-lg`: 10px
- Drawer shadow: 구현 시 현재 패널 계층과 동일한 중간 강도 사용
- Modal shadow: `0 12px 48px rgba(0,0,0,0.18)`
- Toast shadow: `0 4px 16px rgba(0,0,0,0.2)`
- Dense table: header 6px 10px, cell 6px 10px
- Desktop minimum width: 1280px
- 기본 spacing은 4/8px 계열을 유지한다.

## 3. 공통 Component Mapping

| Figma/UX 개념 | 현재 참고 코드 | 실제 코드 권장명 |
|---|---|---|
| Navigation | `src/App.tsx` | `AppSidebar` |
| Top Header | `src/App.tsx` | `AppHeader` |
| Environment Banner | `src/App.tsx` | `EnvironmentBanner` |
| Provider Health | `Badges.tsx` / `App.tsx` | `ProviderHealthBadge` |
| Risk Badge | `Badges.tsx` | `RiskBadge` |
| Freshness Badge | `Badges.tsx` | `FreshnessBadge` |
| Confidence Badge | `Badges.tsx` | `ConfidenceBadge` |
| Rule/AI/Human Badge | `Badges.tsx` | `OriginBadge` 또는 개별 Badge |
| Data Table | page inline table + `.dense-table` | `DataTable` |
| 판단 근거 Drawer | `EvidenceDrawer.tsx` | `EvidenceDrawer` |
| 확인 업무 Modal | `WorkCreationModal.tsx` | `WorkCreationModal` |
| 작업 제안 Card | `TaskProposalCard.tsx` | `TaskProposalCard` |
| Before/After Diff | `Schedule.tsx` | `BeforeAfterDiff` |
| 상품 연결 검토 Row | `Inventory.tsx` | `MappingReviewRow` |
| Loading | `UIStates.tsx` | `LoadingSkeleton` |
| Empty | `UIStates.tsx` | `EmptyState` |
| Stale | `UIStates.tsx` | `StaleDataBanner` |
| Partial Provider Failure | `UIStates.tsx` | `PartialFailureBanner` |
| Denied | `UIStates.tsx` | `DeniedState` |
| Ambiguous Mapping | `UIStates.tsx` | `AmbiguousMappingState` |
| Low AI Confidence | `UIStates.tsx` | `LowConfidenceBanner` |
| Agent Waiting | `UIStates.tsx` | `AgentWaitingState` |
| Toast | page별 local 구현/CSS | `Toast` / `ToastProvider` |

공통 컴포넌트를 화면마다 복사하지 않고 `frontend/src/components/`에 통합한다.

## 4. 필수 상태 Variant

Figma Make 소스에서 다음 8종의 상태 구현이 확인되었다.

1. Loading → `LoadingSkeleton`, `LoadingCard`
2. Empty → `EmptyState`
3. Stale → `StaleDataBanner`
4. Partial Provider Failure → `PartialFailureBanner`
5. Denied / Policy Denied → `DeniedState`
6. Ambiguous Mapping → `AmbiguousMappingBadge`, `AmbiguousMappingState`
7. Low AI Confidence → `LowConfidenceBanner`
8. Agent Waiting → `AgentWaitingState`

실제 구현에서는 Fixture로 각 상태를 재현 가능하게 만들고 screenshot/interaction test를 연결한다.

권장 Fixture 명:

```text
ui_loading.json
ui_empty.json
ui_stale_inventory.json
ui_partial_provider_failure.json
ui_policy_denied.json
ui_ambiguous_mapping.json
ui_low_ai_confidence.json
ui_agent_waiting.json
```

## 5. 화면 → API / Mock Contract Mapping

실제 필드는 OpenAPI/JSON Schema만 사용한다. 아래는 화면과 공식 API의 연결 관계다.

| 화면 | 공식 조회 API | 내부/Demo action 후보 |
|---|---|---|
| Dashboard | `GET /api/v1/dashboard`, `GET /api/v1/tasks`, `GET /api/v1/insights` | Task decision은 내부 계약에 따라 연결 |
| Inventory | `GET /api/v1/products`, `GET /api/v1/inventory` | `POST /api/v1/reconciliation/run`; mapping review는 확정 Contract에 맞춰 구현 |
| Orders | `GET /api/v1/orders`, `GET /api/v1/reservations` | 없음 — Core Production Read-Only |
| Inquiry | `GET /api/v1/inquiries` | `POST /api/v1/inquiries/{id}/draft`; 실제 전송 없음 |
| Schedule | `GET /api/v1/launch-events`, `GET /api/v1/tasks` | Task/Proposal decision은 내부 계약으로 연결, Provider Write 없음 |
| Insights | `GET /api/v1/insights`, `GET /api/v1/traces/{trace_id}` | Task 생성/검토 계약으로 연결 |
| Settings | `GET /api/v1/health` 및 Provider 상태 Contract | Production 자격증명/Write 변경 없음 |

공통 응답은 `request_id`, `trace_id`, `evidence_ids`, `warnings`, `as_of`를 소비한다.

## 6. 핵심 UX 결정

### Dashboard

- 위험 Card 클릭 → `판단 근거` Drawer
- 운영자 기본 근거는 사람이 이해할 수 있는 수량/시점/이유 중심
- 기술 상세는 별도 접힘 영역
- `확인 업무 만들기`는 내부 Task 생성만 의미한다.

### Products & Inventory

- 상품 Row 클릭 → 우측 재고 상세 Panel
- Cafe24 / eCount / Toss POS 판매 반영 / 예약 / 확정 입고 / 예상 가용재고 / 시스템 차이를 표시
- stale source는 명확히 경고
- 실제 재고 변경 CTA 금지
- `상품연결` 탭은 모호한 SKU를 사람이 검토하고 승인/거절하는 UI다.

### Orders & Sales

- `재고부족` badge 클릭/row 선택 → 필요수량, 확보재고, 예약재고, 확정입고, 부족수량, 배송영향, 원인을 표시
- 확인 업무 생성은 허용
- 실제 재고 수정·주문 취소 없음

### Customer Inquiry / AI Draft

- 3열 구조 유지
  - 좌측: 문의 목록
  - 중앙: 문의 정보, AI 분류, 답변 참고정보
  - 우측: 가장 넓은 AI 답변 초안 편집 영역
- `AI 답변 초안 · 실제 전송 아님` 고정
- actions: 수정 / 승인대기 / 보류 / 근거부족 / 거절
- 상세 출처는 secondary detail로만 노출

### Operations Schedule

- 입고 지연 → 영향 요약 → Before/After 일정 제안
- 승인/검토 전 기존 일정은 변경되지 않음
- Agent Waiting 상태를 노출하되 내부 Chain-of-Thought는 표시하지 않는다.

### AI Insights

- 운영자 기본 화면에서 모델명/Prompt/Index/BM25를 강조하지 않는다.
- Card가 반드시 답해야 하는 질문:
  1. 무슨 문제가 발견됐는가
  2. 왜 중요한가
  3. 어떤 데이터로 판단했는가
  4. 신뢰도는 얼마인가
  5. 지금 무엇을 확인해야 하는가
- Rule/SQL/통계 계산을 AI가 계산한 것처럼 표현하지 않는다.
- 기술정보는 `처리 기록 보기`에서만 노출한다.

### Integrations & Settings

- Provider health / last sync / degraded 상태 표시
- Production에서는 자격증명·외부 Write 조작이 차단됨을 명시
- 역할 표기는 조회/내부 업무 승인/AI 제안 검토/설정 관리처럼 오해 없이 사용

## 7. 안전 UI 고정 규칙

- Demo: 파란 배너 + 합성 데이터 명시
- Production: `Production Read-Only · 운영환경 읽기 전용` 지속 표시
- 금지 CTA:
  - 환불 실행
  - 주문 취소 실행
  - 가격 변경 실행
  - 실재고 직접 변경
  - 결제/정산 실행
  - 고객 답변 자동 전송
- CS는 Draft-only
- 일정 변경은 Proposal/Before-After/검토 흐름
- 모호한 SKU는 자동 병합 금지
- 낮은 신뢰도/stale/unsupported는 Human Review 또는 No Action
- 내부 Chain-of-Thought 표시 금지. 단계/도구/근거/결과/오류만 노출한다.

## 8. 현재 Figma Make 코드에서 재사용 가능한 부분

### 재사용 권장

- `src/index.css`의 색상/타이포/radius/focus/dense table 토큰
- 화면 레이아웃 및 정보 우선순위
- `Badges.tsx`의 시각 규칙
- `UIStates.tsx`의 8개 상태 UX
- `EvidenceDrawer.tsx`의 운영자 근거/기술상세 분리 방식
- `WorkCreationModal.tsx`의 안전 문구와 내부 Task form UX
- `Inventory.tsx`의 상품 상세/상품연결 검토 레이아웃
- `Orders.tsx`의 재고부족 상세 Panel
- `Inquiry.tsx`의 3열 Draft workbench
- `Schedule.tsx`의 Before/After 제안 레이아웃
- `Insights.tsx`의 운영자 질문 중심 Insight 구조

### 그대로 Production에 사용 금지 / 재구현 필요

- `src/data/mockData.ts`의 Type과 필드명: Figma 생성 필드이며 공식 계약이 아님
- `App.tsx`의 state 기반 page navigation: Router로 재구현 필요
- 모든 local `useState` 기반 저장/승인/업무생성: API/Mock adapter 계층으로 교체 필요
- Figma 내 하드코딩 timestamp/Provider 상태
- API 이름/모델 버전 등 합성 문구
- 화면별 중복 inline style: 실제 구현 시 공통 component/token으로 정리 권장
- Figma Make runtime/deploy 파일 (`.figma/make/*`): Production build 기준으로 사용하지 않음
- `src/imports/pasted_text/*`: 개발 참고 Prompt이며 Production source에서 제외 권장

## 9. 발견된 코드 레벨 주의사항

1. React Router가 없다. 7개 화면 전환이 `App.tsx` local state에 의존한다.
2. 실제 API 호출(`fetch`, axios 등)이 없다. 현재는 `mockData.ts`만 사용한다.
3. `mockData.ts`에는 `BM25 텍스트 유사도`, `AI 분석 엔진 v2.3` 등 개발자용 합성 문자열이 남아 있다. 일부는 UI에서 친화적인 문구로 치환되지만 공식 구현에서는 Contract/Trace 데이터로 대체한다.
4. CSS가 Google Fonts URL을 import한다. 공개/배포 환경 정책에 따라 self-host/system font fallback 여부를 결정한다.
5. 일부 상태/Toast는 페이지 local state로 구현되어 있어 전역 상태/공통 feedback component로 정리할 수 있다.
6. Build 검증은 현재 압축본에 `node_modules`가 포함되지 않아 별도 dependency install이 필요하다. 소스 구조 검수는 완료됐지만 이 인계 단계에서 실행 빌드 성공을 완료 증거로 간주하지 않는다.

## 10. 권장 실제 Frontend 구조

```text
frontend/
├─ design/figma/
│  └─ handoff.md
├─ src/
│  ├─ app/
│  ├─ pages/
│  ├─ components/
│  ├─ api/
│  ├─ contracts/
│  ├─ fixtures/
│  ├─ hooks/
│  └─ styles/
└─ tests/
```

실제 구조는 기존 repo 상태와 통합 Codex 묶음의 결정을 우선하며, 위 구조는 논리적 mapping 기준이다.

## 11. 구현 시 우선 검증

- OpenAPI/JSON Schema 기반 Type 생성/검증
- Mock Fixture → 화면 상태 분기
- `stale`, `partial`, `denied`, `ambiguous`, `low-confidence`, `agent-waiting` screenshot/interaction test
- keyboard/focus/aria 검증
- Demo/Production Banner 분기
- 금지 CTA 및 Provider Write 요청 0건 검증
- 실제 PII/Production identifier 0건 검증
- 판단 근거 → Trace까지 2단계 이내 접근

## 12. 미결 항목과 담당

| 항목 | 현재 상태 | 처리 시점/담당 |
|---|---|---|
| Figma URL/Frame ID | 미제공 | 사용자 또는 포트폴리오 정리 시 기록 |
| 실제 API Type | 미구현 | Backend OpenAPI 확정 후 통합 Codex |
| 실제 Router | 미구현 | Frontend 통합 구현 |
| API/Mock Handler | 미구현 | Frontend 통합 구현 |
| Task 생성 실제 저장 | Prototype local state | Backend Task Contract 연결 시 구현 |
| Mapping approval Contract | UI 존재, 실제 endpoint 미확정 | 05 계약 우선으로 통합 시 확정 |
| 8개 상태 E2E | Component 존재 | 실제 Fixture 연결 후 T-UI-01 |
| Production Read-Only enforcement | UI 표현 존재 | 서버 deny 정책 + frontend safety test로 확인 |
| Demo Simulator | 현재 7개 메인 화면에 독립 노출 없음 | 해당 일정 작업에서 Demo-only 구현 |
| Agent Trace | 기술상세 일부 존재 | Agent/Trace 계약 구현 시 확장 |

## 13. D01-FE-01 판정 메모

현재 Figma Make 결과는 다음 핵심 디자인 자산을 제공한다.

- 7개 핵심 화면
- 공통 Badge/Drawer/Modal/Task Proposal/상태 컴포넌트
- Demo / Production Read-Only 환경 표현
- 상품 재고 상세 및 상품 연결 검토
- 주문 재고 부족 상세
- 고객문의 Draft-only 3열 workbench
- 일정 Before/After 및 Agent Waiting
- 운영자 중심 AI Insight 설명
- 내부 확인 업무 생성 Modal

Figma 자동 생성 코드 자체는 Production 완료 증거가 아니다. 이후 완료 기준은 공식 Contract, Mock/API 연결, 상태 시험, 접근성, E2E, 안전 시험으로 판정한다.
