import React, { useState } from "react";
import { AIBadge, ConfidenceBadge, FreshnessBadge, RuleBadge } from "../components/Badges";
import WorkCreationModal, { WorkItem } from "../components/WorkCreationModal";

// ── Insight data ─────────────────────────────────────────────
// Each insight clearly answers: 무슨 문제 / 왜 중요 / 어떤 데이터 / 신뢰도 / 지금 무엇을
// Rule/SQL results vs AI explanations are kept distinguishable

type InsightType =
  | "재고소진위험"
  | "예약주문부족"
  | "반복문의증가"
  | "반품이상증가"
  | "입고지연영향"
  | "판매급증신호"
  | "반복재고불일치"
  | "업무병목";

interface Insight {
  id: string;
  type: InsightType;
  severity: "critical" | "warning" | "info";
  title: string;
  // 5 operator questions
  problem: string;        // 무슨 문제가 발견됐나요?
  importance: string;     // 왜 중요한가요?
  dataSource: { label: string; value: string; isRule: boolean }[];  // 어떤 데이터로 판단?
  confidence: number;     // 신뢰도
  asOf: string;           // 데이터 기준 시각
  nextAction: string;     // 지금 무엇을 확인하면 되나요?
  tags: string[];
  workDefaults: Partial<WorkItem>;
}

const insights: Insight[] = [
  {
    id: "i001",
    type: "재고소진위험",
    severity: "critical",
    title: "이번 주 토요일 전 레드벨벳·말차 케이크 재고 소진 예상",
    problem: "현재 판매 속도로 계속 판매되면 9월 7일(토) 이전에 재고가 완전히 소진될 것으로 예측됩니다.",
    importance: "재고 소진 후에도 Cafe24에 판매 가능 상태로 표시되면 과판매가 발생해 고객 불만과 취소 대응 업무가 급증합니다.",
    dataSource: [
      { label: "최근 7일 일평균 판매량", value: "레드벨벳 4.1개/일, 말차 3.8개/일", isRule: true },
      { label: "현재 eCount 실재고", value: "레드벨벳 3개, 말차 0개", isRule: true },
      { label: "확정 입고 예정", value: "레드벨벳 9/6, 말차 9/7", isRule: true },
      { label: "소진 예측 시점", value: "레드벨벳 9/5, 말차 즉시", isRule: false },
    ],
    confidence: 94,
    asOf: "5분 전",
    nextAction: "eCount 실재고 직접 확인 → Cafe24 진열수량 조정 또는 일시 품절 처리 검토",
    tags: ["재고", "소진위험", "레드벨벳", "말차"],
    workDefaults: {
      title: "재고 소진 위험 상품 진열 조정 검토",
      summary: "레드벨벳·말차 케이크 9/7 전 재고 소진 예측. Cafe24 진열수량 조정 필요.",
      cause: "판매 속도 대비 실재고 부족, 입고 지연 겹침",
      priority: "높음",
      deadline: new Date().toISOString().slice(0, 10),
    },
  },
  {
    id: "i002",
    type: "예약주문부족",
    severity: "critical",
    title: "9/7 예약 주문 6건 충족 불가 — 사전 안내 필요",
    problem: "9월 7일(토) 배송 예약 주문 24건 중 6건을 생산할 원자재(생크림)가 부족합니다.",
    importance: "배송 당일 고객에게 취소 통보가 이루어지면 고객 신뢰도와 재구매율에 큰 영향을 미칩니다. 미리 안내할수록 피해가 줄어듭니다.",
    dataSource: [
      { label: "9/7 예약 주문 수", value: "24건", isRule: true },
      { label: "생크림 현재고 기반 생산 가능", value: "18개", isRule: true },
      { label: "생크림 입고 예정일", value: "9/7 (배송 당일)", isRule: true },
      { label: "입고 당일 생산 가능 여부", value: "불가 (당일 생산 리드타임 부족)", isRule: false },
    ],
    confidence: 91,
    asOf: "12분 전",
    nextAction: "긴급 원자재 확보 가능 여부 확인 → 불가 시 고객 6명 사전 안내 초안 작성",
    tags: ["예약", "부족", "생크림", "9/7"],
    workDefaults: {
      title: "9/7 예약 주문 미충족 고객 6명 사전 안내",
      summary: "생크림 부족으로 티라미수 케이크 9/7 예약 6건 생산 불가.",
      cause: "생크림 입고 9/7로 지연, 당일 생산 불가",
      priority: "높음",
      deadline: new Date().toISOString().slice(0, 10),
    },
  },
  {
    id: "i003",
    type: "반복문의증가",
    severity: "warning",
    title: "배송 지연 문의 오늘 23건 — 동일 원인 클러스터 감지",
    problem: "오늘 오후 강남구 배송 지연 관련 문의가 23건 접수되었습니다. 이는 전일 동일 유형 5건 대비 +340% 증가입니다.",
    importance: "동일 원인으로 반복되는 문의가 방치되면 담당자 응대 업무가 과부하 상태가 되고, 개별 대응 품질이 낮아집니다. 원인을 파악해 일괄 안내하면 업무량을 크게 줄일 수 있습니다.",
    dataSource: [
      { label: "오늘 배송지연 문의 수", value: "23건 (오후 12시~현재)", isRule: true },
      { label: "전일 동일 유형", value: "5건", isRule: true },
      { label: "공통 지역", value: "강남구 집중", isRule: true },
      { label: "단일 원인 가능성", value: "동일 지역·동일 시간대 집중으로 단일 물류 지연 추정", isRule: false },
    ],
    confidence: 88,
    asOf: "8분 전",
    nextAction: "물류사 강남구 배송 지연 여부 확인 → 원인 확인 시 해당 고객 일괄 안내 초안 작성",
    tags: ["문의", "배송지연", "강남구", "클러스터"],
    workDefaults: {
      title: "강남구 배송 지연 원인 확인 및 고객 안내",
      summary: "오늘 배송지연 문의 23건 집중 (강남구). 물류사 확인 및 일괄 안내 필요.",
      cause: "특정 지역 물류 지연 추정",
      priority: "보통",
      deadline: new Date().toISOString().slice(0, 10),
    },
  },
  {
    id: "i004",
    type: "반복재고불일치",
    severity: "warning",
    title: "레드벨벳 케이크 재고 불일치 3일 연속 반복",
    problem: "레드벨벳 케이크의 Cafe24-eCount 재고 차이가 9월 2일부터 오늘까지 3일 연속으로 감지되고 있습니다.",
    importance: "단순 데이터 지연 이상의 구조적 원인(Toss POS 반영 누락, 수동 재고 조정 미적용 등)이 있을 수 있습니다. 방치 시 재고 데이터 신뢰도가 지속적으로 하락합니다.",
    dataSource: [
      { label: "9/2 재고 차이", value: "+6개", isRule: true },
      { label: "9/3 재고 차이", value: "+8개", isRule: true },
      { label: "9/4 재고 차이", value: "+9개 (현재)", isRule: true },
      { label: "반복 패턴 판단", value: "단순 지연이 아닌 구조적 누락 가능성", isRule: false },
    ],
    confidence: 82,
    asOf: "5분 전",
    nextAction: "Toss POS ↔ eCount 재고 반영 경로 확인 → 수동 조정 내역 검토",
    tags: ["재고불일치", "반복", "구조적원인"],
    workDefaults: {
      title: "레드벨벳 케이크 반복 재고 불일치 원인 조사",
      summary: "3일 연속 재고 차이 반복. 구조적 누락 가능성 확인 필요.",
      cause: "Toss POS ↔ eCount 반영 경로 오류 추정",
      priority: "보통",
      deadline: new Date(Date.now() + 86400000).toISOString().slice(0, 10),
    },
  },
  {
    id: "i005",
    type: "입고지연영향",
    severity: "warning",
    title: "생크림 입고 지연 → 9/5~6 생산 2개 배치 연쇄 영향",
    problem: "생크림 원자재 입고가 9/4에서 9/7로 3일 지연됨에 따라 9/5, 9/6 생산 배치 2개가 취소되거나 연기되어야 합니다.",
    importance: "생산 배치 취소는 9/7 주말 배송 재고 부족으로 이어지고, 예약 주문 미충족 → 고객 취소 안내 → 문의 급증으로 연쇄됩니다.",
    dataSource: [
      { label: "예정 입고일", value: "9/4 (수)", isRule: true },
      { label: "변경 입고일", value: "9/7 (토)", isRule: true },
      { label: "영향 생산 배치", value: "9/5 AM 18개, 9/6 AM 12개", isRule: true },
      { label: "연쇄 영향 예측", value: "9/7 배송 재고 부족 6개, 고객 안내 필요", isRule: false },
    ],
    confidence: 87,
    asOf: "1시간 전",
    nextAction: "공급사에 9/6 이전 부분 입고 가능 여부 확인 → 불가 시 생산 일정 재배치 검토",
    tags: ["입고지연", "생크림", "연쇄영향"],
    workDefaults: {
      title: "생크림 입고 지연 — 공급사 부분 입고 협의",
      summary: "입고 3일 지연으로 9/5~6 생산 2배치 취소 위기.",
      cause: "공급사 납기 변경",
      priority: "높음",
      deadline: new Date().toISOString().slice(0, 10),
    },
  },
  {
    id: "i006",
    type: "판매급증신호",
    severity: "info",
    title: "추석 시즌 선물 세트 조기 예약 급증 — 재고 사전 확보 검토",
    problem: "9월 14~17일 추석 연휴를 앞두고 선물 세트 예약 주문이 이번 주 들어 전주 대비 +180% 증가했습니다.",
    importance: "추석 수요는 일반적으로 연휴 1주 전에 정점에 도달합니다. 지금 재고를 확보하지 않으면 연휴 기간 품절로 매출 기회를 잃을 수 있습니다.",
    dataSource: [
      { label: "이번 주 선물 세트 예약 증가율", value: "+180% (전주 대비)", isRule: true },
      { label: "전년 동기 추석 주문 수", value: "312건 (기록적 수요)", isRule: true },
      { label: "현재 선물 세트 재고", value: "47세트", isRule: true },
      { label: "추석 기간 수요 예측", value: "약 280~320건", isRule: false },
    ],
    confidence: 85,
    asOf: "1시간 전",
    nextAction: "선물 세트 재고 현황 확인 → 추가 생산 또는 원자재 선주문 검토",
    tags: ["추석", "시즌", "판매급증", "선물세트"],
    workDefaults: {
      title: "추석 시즌 선물 세트 재고 사전 확보 계획",
      summary: "추석 예약 급증. 현재 재고 47세트로 예상 수요 280건 충족 불가.",
      cause: "시즌 수요 급증",
      priority: "보통",
      deadline: new Date(Date.now() + 3 * 86400000).toISOString().slice(0, 10),
    },
  },
  {
    id: "i007",
    type: "업무병목",
    severity: "info",
    title: "문의 AI 초안 검토 대기 14건 — 평균 대기 2.4시간 초과",
    problem: "현재 AI 초안이 생성되었으나 담당자 검토를 기다리는 문의가 14건이며, 평균 대기 시간이 2.4시간을 넘었습니다.",
    importance: "고객 응대 지연이 길어질수록 재문의 발생률이 높아지고 고객 만족도가 하락합니다. 단순 문의는 빠른 검토만으로 처리가 가능합니다.",
    dataSource: [
      { label: "AI 초안 대기 문의", value: "14건", isRule: true },
      { label: "평균 대기 시간", value: "2.4시간", isRule: true },
      { label: "긴급 문의 포함 여부", value: "3건 포함", isRule: true },
      { label: "처리 병목 구간", value: "담당자 검토 단계", isRule: false },
    ],
    confidence: 96,
    asOf: "3분 전",
    nextAction: "고객 문의 화면에서 AI 초안 완료 상태 14건 우선 검토",
    tags: ["업무병목", "문의대기", "AI초안"],
    workDefaults: {
      title: "AI 초안 대기 문의 14건 우선 처리",
      summary: "평균 2.4시간 초과 대기 중. 긴급 3건 포함.",
      cause: "담당자 검토 인력 부족 추정",
      priority: "보통",
      deadline: new Date().toISOString().slice(0, 10),
    },
  },
];

// ── Component ─────────────────────────────────────────────────
type Filter = "전체" | "위험" | "주의" | "참고";

export default function Insights() {
  const [filter, setFilter] = useState<Filter>("전체");
  const [feedbacks, setFeedbacks] = useState<Record<string, "긍정" | "부정">>({});
  const [expandedIds, setExpandedIds] = useState<string[]>([]);
  const [showTech, setShowTech] = useState(false);
  const [workModal, setWorkModal] = useState<{ insight: Insight } | null>(null);
  const [createdIds, setCreatedIds] = useState<string[]>([]);
  const [toast, setToast] = useState<string | null>(null);

  const showToast = (msg: string) => { setToast(msg); setTimeout(() => setToast(null), 3000); };

  const filtered = insights.filter(i => {
    if (filter === "전체") return true;
    if (filter === "위험") return i.severity === "critical";
    if (filter === "주의") return i.severity === "warning";
    if (filter === "참고") return i.severity === "info";
    return true;
  });

  const toggleExpand = (id: string) =>
    setExpandedIds(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);

  return (
    <div style={{ height: "100%", overflow: "auto", padding: "20px 24px" }}>
      {/* Purpose banner */}
      <div style={{ background: "var(--ai-bg)", border: "1px solid var(--ai-border)", borderRadius: "var(--radius-lg)", padding: "14px 18px", marginBottom: 20, display: "flex", gap: 12, alignItems: "flex-start" }}>
        <span style={{ fontSize: 20, flexShrink: 0 }}>✦</span>
        <div>
          <div style={{ fontSize: 13, fontWeight: 700, color: "var(--ai-text)", marginBottom: 4 }}>AI 인사이트 — 운영 패턴 자동 감지</div>
          <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.7 }}>
            AI가 Cafe24·Toss POS·eCount 데이터를 실시간으로 분석하여 담당자가 수동으로 발견하기 어려운 <strong>재고 위험·예약 부족·반복 패턴·운영 병목</strong>을 자동으로 감지합니다.
            모든 인사이트는 판단 근거와 함께 제공되며, 자동 실행되지 않습니다.
          </div>
        </div>
      </div>

      {/* KPI strip */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 20 }}>
        {[
          { label: "오늘 분석 건수", value: String(insights.length), sub: "인사이트 유형", color: "var(--ai-text)" },
          { label: "검토 필요 항목", value: String(insights.filter(i => i.severity !== "info").length), sub: "위험+주의", color: "var(--crit-text)" },
          { label: "평균 신뢰도", value: Math.round(insights.reduce((a, i) => a + i.confidence, 0) / insights.length) + "%", sub: "오늘 기준", color: "var(--human-text)" },
          { label: "자동 실행", value: "0건", sub: "정책상 자동 실행 없음", color: "var(--text-secondary)" },
        ].map((m, i) => (
          <div key={i} style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-lg)", padding: "12px 16px" }}>
            <div style={{ fontSize: 10, fontWeight: 600, color: "var(--text-tertiary)", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 4 }}>{m.label}</div>
            <div style={{ fontSize: 24, fontWeight: 700, color: m.color, lineHeight: 1.2, marginBottom: 2 }}>{m.value}</div>
            <div style={{ fontSize: 11, color: "var(--text-tertiary)" }}>{m.sub}</div>
          </div>
        ))}
      </div>

      {/* Data as-of + tech toggle */}
      <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 14, flexWrap: "wrap" }}>
        <span style={{ fontSize: 11, color: "var(--text-secondary)" }}>
          <strong>데이터 기준 시각:</strong> 2024-09-04 11:42 KST
        </span>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {([["전체", undefined], ["위험", "critical"], ["주의", "warning"], ["참고", "info"]] as const).map(([label]) => (
            <button key={label} onClick={() => setFilter(label as Filter)} style={{ background: filter === label ? "var(--rule-accent)" : "var(--surface)", color: filter === label ? "white" : "var(--text-secondary)", border: `1px solid ${filter === label ? "var(--rule-accent)" : "var(--border)"}`, borderRadius: "var(--radius)", padding: "4px 12px", fontSize: 12, cursor: "pointer" }}>{label}</button>
          ))}
        </div>
        <button onClick={() => setShowTech(!showTech)} style={{ marginLeft: "auto", background: "none", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", padding: "3px 10px", fontSize: 11, cursor: "pointer", color: "var(--text-tertiary)" }}>
          {showTech ? "처리 기록 숨기기" : "처리 기록 보기"}
        </button>
      </div>

      {/* Tech panel (collapsed by default) */}
      {showTech && (
        <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: "12px 16px", marginBottom: 16 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-secondary)", marginBottom: 8 }}>처리 기록 — 담당자 전용 · 기술 상세</div>
          <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
            {[
              { label: "재고·수요 예측", value: "ops-forecast-v2.3" },
              { label: "문의 분류", value: "inquiry-cls-v1.8" },
              { label: "답변 초안 생성", value: "draft-gen-v1.5" },
              { label: "검색 방식", value: "하이브리드 RAG" },
            ].map(m => (
              <div key={m.label}>
                <div style={{ fontSize: 10, color: "var(--text-tertiary)", marginBottom: 2 }}>{m.label}</div>
                <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--ai-text)", fontWeight: 600 }}>{m.value}</div>
              </div>
            ))}
          </div>
          <p style={{ fontSize: 10, color: "var(--text-tertiary)", margin: "8px 0 0" }}>
            ※ 내부 처리 사고과정(Chain-of-Thought)은 표시되지 않습니다 · 최종 버전은 배포 환경 기준
          </p>
        </div>
      )}

      {/* Insight cards */}
      <div style={{ display: "flex", flexDirection: "column", gap: 14, marginBottom: 24 }}>
        {filtered.map(insight => (
          <InsightCard
            key={insight.id}
            insight={insight}
            expanded={expandedIds.includes(insight.id)}
            onToggleExpand={() => toggleExpand(insight.id)}
            feedback={feedbacks[insight.id]}
            onFeedback={(id, fb) => { setFeedbacks(prev => ({ ...prev, [id]: fb })); showToast("피드백 감사합니다."); }}
            workCreated={createdIds.includes(insight.id)}
            onCreateWork={() => setWorkModal({ insight })}
          />
        ))}
        {filtered.length === 0 && (
          <div style={{ textAlign: "center", padding: "40px", color: "var(--text-tertiary)", fontSize: 13 }}>
            해당 유형의 인사이트가 없습니다.
          </div>
        )}
      </div>

      {/* Work creation modal */}
      {workModal && (
        <WorkCreationModal
          initialData={workModal.insight.workDefaults}
          onClose={() => setWorkModal(null)}
          onSubmit={() => {
            setCreatedIds(prev => [...prev, workModal.insight.id]);
            setWorkModal(null);
            showToast("✅ 확인 업무가 생성되었습니다.");
          }}
        />
      )}

      {toast && (
        <div className="toast-container">
          <div className="toast">{toast}</div>
        </div>
      )}
    </div>
  );
}

// ── Insight card ──────────────────────────────────────────────
interface CardProps {
  insight: Insight;
  expanded: boolean;
  onToggleExpand: () => void;
  feedback?: "긍정" | "부정";
  onFeedback: (id: string, fb: "긍정" | "부정") => void;
  workCreated: boolean;
  onCreateWork: () => void;
}

function InsightCard({ insight, expanded, onToggleExpand, feedback, onFeedback, workCreated, onCreateWork }: CardProps) {
  const severityConfig = {
    critical: { borderColor: "var(--crit-accent)", bg: "var(--crit-bg)", label: "🔴 즉시 확인", textColor: "var(--crit-text)" },
    warning: { borderColor: "var(--warn-accent)", bg: "var(--warn-bg)", label: "🟡 확인 권장", textColor: "var(--warn-text)" },
    info: { borderColor: "var(--rule-accent)", bg: "var(--rule-bg)", label: "🔵 참고", textColor: "var(--rule-text)" },
  }[insight.severity];

  const typeLabel: Record<InsightType, string> = {
    재고소진위험: "재고 소진 위험",
    예약주문부족: "예약 주문 부족",
    반복문의증가: "반복 문의 증가",
    반품이상증가: "반품/문의 이상",
    입고지연영향: "입고 지연 영향",
    판매급증신호: "판매 급증 신호",
    반복재고불일치: "반복 재고 불일치",
    업무병목: "운영 업무 병목",
  };

  return (
    <div style={{ background: "var(--surface)", border: `1px solid var(--border)`, borderLeft: `4px solid ${severityConfig.borderColor}`, borderRadius: "var(--radius-lg)", overflow: "hidden" }}>
      {/* Header row */}
      <div style={{ padding: "12px 16px", borderBottom: expanded ? "1px solid var(--border)" : "none", display: "flex", alignItems: "flex-start", gap: 12 }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 5, flexWrap: "wrap" }}>
            <span style={{ fontSize: 11, fontWeight: 700, color: severityConfig.textColor, background: severityConfig.bg, padding: "1px 7px", borderRadius: "var(--radius-sm)", border: `1px solid ${severityConfig.borderColor}` }}>
              {severityConfig.label}
            </span>
            <span style={{ fontSize: 10, color: "var(--text-secondary)", background: "var(--surface-2)", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", padding: "1px 6px" }}>
              {typeLabel[insight.type]}
            </span>
            <ConfidenceBadge value={insight.confidence} />
            <FreshnessBadge asOf={insight.asOf} stale={insight.asOf.includes("시간")} />
          </div>
          <h3 style={{ margin: 0, fontSize: 14, fontWeight: 700, color: "var(--text-primary)", lineHeight: 1.4 }}>{insight.title}</h3>
        </div>
        <button
          onClick={onToggleExpand}
          aria-expanded={expanded}
          style={{ background: "none", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", padding: "4px 8px", fontSize: 11, cursor: "pointer", color: "var(--text-secondary)", flexShrink: 0 }}
        >
          {expanded ? "▲ 접기" : "▼ 자세히"}
        </button>
      </div>

      {expanded && (
        <div style={{ padding: "14px 16px", display: "flex", flexDirection: "column", gap: 14 }}>

          {/* Q1: 무슨 문제 */}
          <QARow
            q="무슨 문제가 발견됐나요?"
            a={insight.problem}
            type="problem"
            isSeverity={insight.severity}
          />

          {/* Q2: 왜 중요 */}
          <QARow
            q="왜 중요한가요?"
            a={insight.importance}
            type="importance"
          />

          {/* Q3: 어떤 데이터 — rule vs AI clearly separated */}
          <div>
            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-secondary)", marginBottom: 6 }}>어떤 데이터로 판단했나요?</div>
            <div style={{ border: "1px solid var(--border)", borderRadius: "var(--radius)", overflow: "hidden" }}>
              {insight.dataSource.map((d, i) => (
                <div
                  key={i}
                  style={{
                    display: "flex", justifyContent: "space-between", alignItems: "center",
                    padding: "8px 12px", gap: 10,
                    borderBottom: i < insight.dataSource.length - 1 ? "1px solid var(--border)" : "none",
                    background: d.isRule ? "var(--surface)" : "var(--ai-bg)",
                  }}
                >
                  <div style={{ display: "flex", gap: 7, alignItems: "center", flexShrink: 0 }}>
                    {d.isRule ? <RuleBadge label="데이터" /> : <AIBadge label="AI 분석" />}
                    <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>{d.label}</span>
                  </div>
                  <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: d.isRule ? "var(--text-primary)" : "var(--ai-text)", fontWeight: 600, textAlign: "right" }}>{d.value}</span>
                </div>
              ))}
            </div>
            <div style={{ fontSize: 10, color: "var(--text-tertiary)", marginTop: 4 }}>
              데이터 행 = 실제 집계/계산 결과 · AI 분석 행 = 패턴 해석 및 예측
            </div>
          </div>

          {/* Q5: 지금 무엇을 */}
          <div style={{ background: "var(--human-bg)", border: "1px solid var(--human-border)", borderRadius: "var(--radius)", padding: "10px 14px" }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--human-text)", marginBottom: 4 }}>지금 무엇을 확인하면 되나요?</div>
            <p style={{ fontSize: 13, color: "var(--text-secondary)", margin: 0, lineHeight: 1.6 }}>{insight.nextAction}</p>
          </div>

          {/* Action row */}
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            {/* Tags */}
            <div style={{ display: "flex", gap: 4, flexWrap: "wrap", flex: 1 }}>
              {insight.tags.map(t => (
                <span key={t} style={{ background: "var(--surface-2)", color: "var(--text-secondary)", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", padding: "1px 6px", fontSize: 10 }}>#{t}</span>
              ))}
            </div>

            {/* Work creation */}
            {workCreated ? (
              <span style={{ fontSize: 12, color: "var(--human-text)", fontWeight: 600 }}>✅ 업무 생성됨</span>
            ) : (
              <button
                onClick={onCreateWork}
                style={{ background: "var(--rule-accent)", color: "white", border: "none", borderRadius: "var(--radius-sm)", padding: "6px 12px", fontSize: 12, fontWeight: 600, cursor: "pointer" }}
              >
                📋 후속 조치 제안
              </button>
            )}

            {/* Feedback */}
            <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
              <span style={{ fontSize: 11, color: "var(--text-tertiary)" }}>정확도:</span>
              <button
                onClick={() => onFeedback(insight.id, "긍정")}
                aria-label="정확함"
                aria-pressed={feedback === "긍정"}
                style={{ background: feedback === "긍정" ? "var(--human-bg)" : "none", border: `1px solid ${feedback === "긍정" ? "var(--human-border)" : "var(--border)"}`, borderRadius: "var(--radius-sm)", padding: "2px 8px", fontSize: 12, cursor: "pointer" }}
              >👍</button>
              <button
                onClick={() => onFeedback(insight.id, "부정")}
                aria-label="부정확함"
                aria-pressed={feedback === "부정"}
                style={{ background: feedback === "부정" ? "var(--crit-bg)" : "none", border: `1px solid ${feedback === "부정" ? "var(--crit-border)" : "var(--border)"}`, borderRadius: "var(--radius-sm)", padding: "2px 8px", fontSize: 12, cursor: "pointer" }}
              >👎</button>
            </div>
          </div>
        </div>
      )}

      {/* Collapsed quick summary */}
      {!expanded && (
        <div style={{ padding: "10px 16px 12px", display: "flex", gap: 12, alignItems: "center" }}>
          <p style={{ fontSize: 12, color: "var(--text-secondary)", margin: 0, flex: 1, lineHeight: 1.5 }}>{insight.problem}</p>
          <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
            {workCreated ? (
              <span style={{ fontSize: 11, color: "var(--human-text)", fontWeight: 600 }}>✅ 업무 생성됨</span>
            ) : (
              <button
                onClick={onCreateWork}
                style={{ background: "var(--surface-2)", color: "var(--text-secondary)", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", padding: "4px 10px", fontSize: 11, cursor: "pointer" }}
              >
                📋 후속 조치
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function QARow({ q, a, type, isSeverity }: { q: string; a: string; type: string; isSeverity?: string }) {
  const bgColor = type === "problem" && isSeverity === "critical" ? "var(--crit-bg)"
    : type === "problem" && isSeverity === "warning" ? "var(--warn-bg)"
    : "var(--surface-2)";
  const borderColor = type === "problem" && isSeverity === "critical" ? "var(--crit-border)"
    : type === "problem" && isSeverity === "warning" ? "var(--warn-border)"
    : "var(--border)";

  return (
    <div style={{ background: bgColor, border: `1px solid ${borderColor}`, borderRadius: "var(--radius)", padding: "10px 14px" }}>
      <div style={{ fontSize: 10, fontWeight: 700, color: "var(--text-tertiary)", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 5 }}>{q}</div>
      <p style={{ fontSize: 13, color: "var(--text-primary)", margin: 0, lineHeight: 1.7 }}>{a}</p>
    </div>
  );
}
