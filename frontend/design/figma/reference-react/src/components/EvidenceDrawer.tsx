import React, { useState } from "react";
import { RiskItem } from "../data/mockData";
import { RiskBadge, SourceChip, FreshnessBadge, ConfidenceBadge, AIBadge } from "./Badges";
import WorkCreationModal, { WorkItem } from "./WorkCreationModal";

interface Props {
  item: RiskItem | null;
  onClose: () => void;
  onPropose: (item: RiskItem) => void;
}

export default function EvidenceDrawer({ item, onClose, onPropose }: Props) {
  const [showTechDetail, setShowTechDetail] = useState(false);
  const [showWorkModal, setShowWorkModal] = useState(false);
  const [workCreated, setWorkCreated] = useState(false);

  if (!item) return null;

  const workDefaults = buildWorkDefaults(item);

  const handleWorkSubmit = (_w: WorkItem) => {
    setWorkCreated(true);
    setShowWorkModal(false);
  };

  return (
    <>
      {/* Overlay */}
      <div
        style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.3)", zIndex: 40 }}
        onClick={onClose}
      />

      {/* Panel */}
      <div
        role="complementary"
        aria-label="판단 근거"
        style={{
          position: "fixed", right: 0, top: 0, bottom: 0, width: 480,
          background: "var(--surface)", borderLeft: "1px solid var(--border)",
          zIndex: 50, display: "flex", flexDirection: "column",
          boxShadow: "-4px 0 24px rgba(0,0,0,0.12)",
          animation: "slideIn 0.2s ease",
        }}
      >
        {/* Fixed header */}
        <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--border)", flexShrink: 0 }}>
          <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
            <div style={{ flex: 1 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                <RiskBadge severity={item.severity} />
                <span style={{ fontSize: 10, color: "var(--text-tertiary)", fontFamily: "var(--font-mono)" }}>{item.id}</span>
              </div>
              <h2 style={{ fontSize: 15, fontWeight: 700, color: "var(--text-primary)", margin: 0 }}>
                판단 근거
              </h2>
              <p style={{ fontSize: 13, color: "var(--text-secondary)", margin: "4px 0 0", lineHeight: 1.4 }}>{item.title}</p>
            </div>
            <button
              onClick={onClose}
              aria-label="닫기"
              style={{ background: "var(--surface-2)", border: "1px solid var(--border)", cursor: "pointer", padding: "6px 10px", color: "var(--text-secondary)", fontSize: 14, lineHeight: 1, borderRadius: "var(--radius-sm)", flexShrink: 0 }}
            >✕ 닫기</button>
          </div>
        </div>

        {/* Scrollable middle */}
        <div style={{ flex: 1, overflowY: "auto", padding: "16px 20px", display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ background: "var(--surface-2)", borderRadius: "var(--radius)", padding: "12px 14px", fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.7 }}>
            {item.description}
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, alignItems: "center" }}>
            {item.sources.map(s => <SourceChip key={s} source={s} />)}
            <FreshnessBadge asOf={item.asOf} stale={item.asOf.includes("시간")} />
            {item.confidence !== undefined && <ConfidenceBadge value={item.confidence} />}
          </div>

          <OperatorEvidence item={item} />

          {/* Technical detail toggle */}
          <div>
            <button
              onClick={() => setShowTechDetail(!showTechDetail)}
              style={{ background: "none", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: "6px 12px", fontSize: 11, cursor: "pointer", color: "var(--text-tertiary)", width: "100%", textAlign: "left", display: "flex", justifyContent: "space-between" }}
            >
              <span>상세 기술정보 보기</span>
              <span>{showTechDetail ? "▲" : "▼"}</span>
            </button>
            {showTechDetail && <TechDetailPanel item={item} />}
          </div>
        </div>

        {/* Fixed bottom action */}
        <div style={{ padding: "14px 20px", borderTop: "1px solid var(--border)", background: "var(--surface)", flexShrink: 0, display: "flex", flexDirection: "column", gap: 8 }}>
          {workCreated ? (
            <div style={{ background: "var(--human-bg)", border: "1px solid var(--human-border)", borderRadius: "var(--radius)", padding: "10px 14px", display: "flex", gap: 8, alignItems: "center" }}>
              <span>✅</span>
              <div>
                <div style={{ fontSize: 12, fontWeight: 700, color: "var(--human-text)" }}>업무가 생성되었습니다</div>
                <div style={{ fontSize: 11, color: "var(--text-secondary)" }}>외부 시스템 변경 없음 · 담당자 확인 후 실행</div>
              </div>
            </div>
          ) : (
            <button
              onClick={() => setShowWorkModal(true)}
              style={{ background: "var(--rule-accent)", color: "white", border: "none", borderRadius: "var(--radius)", padding: "11px 16px", fontSize: 13, fontWeight: 600, cursor: "pointer", width: "100%", display: "flex", alignItems: "center", gap: 8 }}
            >
              <span>📋</span>
              <span>확인 업무 만들기</span>
            </button>
          )}
          <p style={{ fontSize: 11, color: "var(--text-tertiary)", margin: 0, lineHeight: 1.5, textAlign: "center" }}>
            내부 확인 업무만 생성 · 외부 주문·재고 변경 없음
          </p>
        </div>
      </div>

      {/* Work creation modal */}
      {showWorkModal && (
        <WorkCreationModal
          initialData={workDefaults}
          onClose={() => setShowWorkModal(false)}
          onSubmit={handleWorkSubmit}
        />
      )}
    </>
  );
}

// ── Build default form values from risk item ─────────────────
function buildWorkDefaults(item: RiskItem): Partial<WorkItem> {
  const base: Record<string, Partial<WorkItem>> = {
    "재고불일치": {
      title: `재고 차이 확인 — ${item.product ?? "해당 상품"}`,
      summary: "Cafe24 진열재고와 eCount 실재고 간 차이가 감지되었습니다. 과판매 방지를 위해 실재고를 직접 확인해야 합니다.",
      cause: "eCount 데이터가 47분 전 기준으로 지연되어 있거나, Toss POS 판매가 아직 반영되지 않았을 가능성이 있습니다.",
      relatedProduct: item.product ?? "",
      priority: "높음",
      deadline: new Date().toISOString().slice(0, 10),
    },
    "예약부족": {
      title: `예약 주문 재고 부족 대응 — ${item.product ?? "해당 상품"}`,
      summary: "9/7 예약 주문 24건 중 6건을 생산할 원자재가 부족합니다.",
      cause: "생크림 입고 지연으로 인해 생산 가능 수량이 예약 수량에 미치지 못합니다.",
      relatedProduct: item.product ?? "",
      priority: "높음",
      deadline: new Date().toISOString().slice(0, 10),
    },
    "입고지연": {
      title: "생크림 원자재 입고 지연 일정 조정",
      summary: "생크림 원자재 입고가 9/4 → 9/7로 3일 지연됩니다. 9/5 생산 배치에 영향이 있습니다.",
      cause: "공급사 사정으로 인한 납기 변경",
      priority: "보통",
      deadline: new Date(Date.now() + 86400000).toISOString().slice(0, 10),
    },
    "문의위험": {
      title: "배송 지연 고객 안내 초안 작성",
      summary: "강남구 배송 지연 관련 문의가 오늘 23건으로 급증(+340%)했습니다.",
      cause: "특정 지역 물류 지연으로 인한 동일 유형 문의 집중 발생",
      priority: "보통",
      deadline: new Date().toISOString().slice(0, 10),
    },
    "매핑모호": {
      title: "신규 상품 eCount 연결 확인",
      summary: "Cafe24 신규 상품 3개가 eCount 품목과 자동으로 연결되지 않아 재고 집계가 정확하지 않을 수 있습니다.",
      cause: "상품명 또는 코드 불일치로 인한 자동 연결 실패",
      priority: "보통",
      deadline: new Date().toISOString().slice(0, 10),
    },
  };

  return base[item.type] ?? {
    title: item.title,
    summary: item.description,
    priority: item.severity === "critical" ? "높음" : "보통",
    deadline: new Date().toISOString().slice(0, 10),
  };
}

// ── Operator-friendly evidence display ───────────────────────
function OperatorEvidence({ item }: { item: RiskItem }) {
  const byType: Record<string, {
    rows: { label: string; value: string; warn?: boolean }[];
    summary: string;
    recommend: string;
  }> = {
    "재고불일치": {
      rows: [
        { label: "Cafe24 재고", value: "12개" },
        { label: "eCount 재고", value: "3개", warn: true },
        { label: "차이", value: "9개 (eCount 기준 부족)", warn: true },
        { label: "Cafe24 마지막 확인", value: "3분 전" },
        { label: "eCount 마지막 확인", value: "47분 전", warn: true },
        { label: "Toss POS 판매 반영", value: "-2개 (반영 지연 가능)" },
      ],
      summary: "eCount 정보가 47분 전 기준이라 실제 차이가 아닐 가능성이 있습니다. 최신 재고를 직접 확인한 후 판단하세요.",
      recommend: "재고 상태 직접 확인 후 Cafe24 진열수량 조정 검토",
    },
    "예약부족": {
      rows: [
        { label: "예약 주문 수", value: "24개 (9/7 배송)" },
        { label: "생산 가능 수량", value: "18개", warn: true },
        { label: "부족 수량", value: "6개", warn: true },
        { label: "원자재 입고 예정", value: "9/7 (배송 당일)" },
        { label: "데이터 기준", value: "12분 전" },
      ],
      summary: "9/7 배송 예약 24건 중 6건을 생산할 원자재가 부족합니다. 입고 당일 생산이 어려울 수 있습니다.",
      recommend: "고객 6명 사전 안내 또는 대체 입고 긴급 확보 검토",
    },
    "입고지연": {
      rows: [
        { label: "원자재", value: "생크림" },
        { label: "예정 입고일", value: "9/4 (수)" },
        { label: "변경된 입고일", value: "9/7 (토)", warn: true },
        { label: "지연 일수", value: "3일", warn: true },
        { label: "영향 생산 배치", value: "9/5 오전 배치 위험" },
        { label: "영향 주문 수", value: "3건" },
      ],
      summary: "생크림 입고가 3일 지연됩니다. 9/5 생산 배치에 필요한 원자재가 부족할 수 있습니다.",
      recommend: "9/5 생산 일정 조정 및 영향 고객 안내 검토",
    },
    "문의위험": {
      rows: [
        { label: "오늘 배송지연 문의", value: "23건", warn: true },
        { label: "전일 동일 문의", value: "5건" },
        { label: "증가율", value: "+340%", warn: true },
        { label: "주요 지역", value: "강남구 집중" },
        { label: "데이터 기준", value: "8분 전" },
      ],
      summary: "강남구 배송 지연 관련 문의가 급격히 증가했습니다. 단일 배송 지연 사유가 있을 가능성이 높습니다.",
      recommend: "물류사 배송 현황 확인 후 해당 고객 일괄 안내 초안 작성",
    },
    "매핑모호": {
      rows: [
        { label: "상품 연결 미완료", value: "3개", warn: true },
        { label: "자동 연결 실패 이유", value: "상품명/코드 불일치" },
        { label: "담당자 확인 필요", value: "매핑 후보 선택" },
        { label: "데이터 기준", value: "2시간 전" },
      ],
      summary: "Cafe24 신규 상품 3개가 eCount 품목과 자동으로 연결되지 않았습니다. 재고 집계가 정확하지 않을 수 있습니다.",
      recommend: "상품 연결 탭에서 후보 확인 후 수동 선택",
    },
  };

  const d = byType[item.type] ?? byType["재고불일치"];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ border: "1px solid var(--border)", borderRadius: "var(--radius)", overflow: "hidden" }}>
        <div style={{ background: "var(--surface-2)", padding: "8px 12px", fontSize: 11, fontWeight: 700, color: "var(--text-secondary)", borderBottom: "1px solid var(--border)" }}>
          현재 재고 / 데이터 비교
        </div>
        {d.rows.map((row, i) => (
          <div
            key={i}
            style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 12px", fontSize: 13, borderBottom: i < d.rows.length - 1 ? "1px solid var(--border)" : "none", background: row.warn ? "var(--warn-bg)" : "var(--surface)" }}
          >
            <span style={{ color: "var(--text-secondary)" }}>{row.label}</span>
            <span style={{ fontWeight: 600, color: row.warn ? "var(--warn-text)" : "var(--text-primary)", fontFamily: "var(--font-mono)", fontSize: 12 }}>{row.value}</span>
          </div>
        ))}
      </div>

      <div style={{ background: "var(--ai-bg)", border: "1px solid var(--ai-border)", borderLeft: "3px solid var(--ai-accent)", borderRadius: "var(--radius)", padding: "10px 14px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
          <AIBadge label="AI 판단" />
          {item.confidence !== undefined && <ConfidenceBadge value={item.confidence} />}
        </div>
        <p style={{ fontSize: 13, color: "var(--text-secondary)", margin: 0, lineHeight: 1.6 }}>{d.summary}</p>
      </div>

      <div style={{ background: "var(--human-bg)", border: "1px solid var(--human-border)", borderRadius: "var(--radius)", padding: "10px 14px" }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: "var(--human-text)", marginBottom: 4 }}>권장 확인 사항</div>
        <p style={{ fontSize: 13, color: "var(--text-secondary)", margin: 0, lineHeight: 1.5 }}>{d.recommend}</p>
      </div>

      {(item.product || item.sku) && (
        <div style={{ border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: "10px 12px", display: "flex", flexDirection: "column", gap: 4 }}>
          {item.product && <Row label="상품명" value={item.product} />}
          {item.sku && <Row label="SKU" value={item.sku} mono />}
          {item.affectedCount !== undefined && <Row label="영향 수량" value={`${item.affectedCount}개`} />}
        </div>
      )}
    </div>
  );
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 8, fontSize: 12 }}>
      <span style={{ color: "var(--text-tertiary)", flexShrink: 0 }}>{label}</span>
      <span style={{ fontFamily: mono ? "var(--font-mono)" : undefined, fontWeight: 500, textAlign: "right", fontSize: mono ? 11 : 12 }}>{value}</span>
    </div>
  );
}

function TechDetailPanel({ item }: { item: RiskItem }) {
  return (
    <div style={{ marginTop: 8, border: "1px solid var(--border)", borderRadius: "var(--radius)", overflow: "hidden" }}>
      <div style={{ background: "var(--surface-2)", padding: "8px 12px", fontSize: 11, fontWeight: 600, color: "var(--text-tertiary)", borderBottom: "1px solid var(--border)" }}>
        기술 상세 — 담당자 전용 · 최종 필드명은 OpenAPI/JSON Schema 계약 기준
      </div>
      <div style={{ padding: "10px 12px", display: "flex", flexDirection: "column", gap: 6 }}>
        {[
          { label: "위험 ID", value: item.id },
          { label: "유형", value: item.type },
          { label: "소스", value: item.sources.join(", ") },
          { label: "신뢰도 점수", value: item.confidence !== undefined ? `${item.confidence}%` : "—" },
          { label: "기준 시각", value: item.asOf },
          { label: "분석 엔진", value: "ops-risk-v2.3 (내부 식별자)" },
        ].map(r => (
          <div key={r.label} style={{ display: "flex", justifyContent: "space-between", fontSize: 11, gap: 8 }}>
            <span style={{ color: "var(--text-tertiary)", flexShrink: 0 }}>{r.label}</span>
            <span style={{ fontFamily: "var(--font-mono)", color: "var(--text-secondary)", textAlign: "right" }}>{r.value}</span>
          </div>
        ))}
        <p style={{ fontSize: 10, color: "var(--text-tertiary)", margin: "4px 0 0", lineHeight: 1.5 }}>
          ℹ 내부 처리 사고과정(Chain-of-Thought)은 표시되지 않습니다.
        </p>
      </div>
    </div>
  );
}
