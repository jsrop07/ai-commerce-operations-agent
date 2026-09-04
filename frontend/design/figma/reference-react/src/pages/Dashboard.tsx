import React, { useState } from "react";
import { riskItems, kpiData, providers, RiskItem } from "../data/mockData";
import { RiskBadge, ConfidenceBadge, FreshnessBadge, SourceChip, ProviderBadge } from "../components/Badges";
import EvidenceDrawer from "../components/EvidenceDrawer";
import TaskProposalCard from "../components/TaskProposalCard";

export default function Dashboard() {
  const [selectedRisk, setSelectedRisk] = useState<RiskItem | null>(null);
  const [proposalItem, setProposalItem] = useState<RiskItem | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 0, height: "100%" }}>
      {/* KPI strip */}
      <div style={{ padding: "16px 24px", borderBottom: "1px solid var(--border)", background: "var(--surface)" }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 12 }}>
          {kpiData.map((kpi, i) => (
            <div key={i} style={{
              background: kpi.status === "crit" ? "var(--crit-bg)" : kpi.status === "warn" ? "var(--warn-bg)" : "var(--surface-2)",
              border: `1px solid ${kpi.status === "crit" ? "var(--crit-border)" : kpi.status === "warn" ? "var(--warn-border)" : "var(--border)"}`,
              borderRadius: "var(--radius)", padding: "12px 14px"
            }}>
              <div style={{ fontSize: 10, fontWeight: 600, color: "var(--text-tertiary)", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 4 }}>{kpi.label}</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: kpi.status === "crit" ? "var(--crit-text)" : kpi.status === "warn" ? "var(--warn-text)" : "var(--text-primary)", lineHeight: 1.2, marginBottom: 2 }}>{kpi.value}</div>
              {kpi.sub && <div style={{ fontSize: 11, color: "var(--text-secondary)", marginBottom: 4 }}>{kpi.sub}</div>}
              <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                {kpi.trend && (
                  <span style={{ fontSize: 11, color: kpi.trend === "up" ? "var(--human-text)" : "var(--crit-text)", fontWeight: 600 }}>
                    {kpi.trend === "up" ? "▲" : "▼"} {kpi.trendValue}
                  </span>
                )}
                <span style={{ fontSize: 10, color: "var(--text-tertiary)", fontFamily: "var(--font-mono)" }}>{kpi.asOf}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div style={{ flex: 1, overflow: "auto", padding: "20px 24px", display: "grid", gridTemplateColumns: "1fr 320px", gap: 20, alignContent: "start" }}>
        {/* Left: Risk feed */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <h2 style={{ margin: 0, fontSize: 14, fontWeight: 700, color: "var(--text-primary)" }}>위험 피드</h2>
            <span style={{ background: "var(--crit-bg)", color: "var(--crit-text)", border: "1px solid var(--crit-border)", borderRadius: "var(--radius-sm)", padding: "1px 7px", fontSize: 11, fontWeight: 700 }}>
              위험 {riskItems.filter(r => r.severity === "critical").length}
            </span>
            <span style={{ background: "var(--warn-bg)", color: "var(--warn-text)", border: "1px solid var(--warn-border)", borderRadius: "var(--radius-sm)", padding: "1px 7px", fontSize: 11, fontWeight: 700 }}>
              주의 {riskItems.filter(r => r.severity === "warning").length}
            </span>
            <span style={{ fontSize: 11, color: "var(--text-tertiary)", marginLeft: "auto" }}>실시간 업데이트 · 클릭하여 근거 확인</span>
          </div>

          {riskItems.map(risk => (
            <RiskCard
              key={risk.id}
              risk={risk}
              onClick={() => setSelectedRisk(risk)}
            />
          ))}

          {/* Proposal card inline */}
          {proposalItem && (
            <TaskProposalCard
              item={proposalItem}
              onDismiss={() => setProposalItem(null)}
              onApprove={(note) => {
                setProposalItem(null);
                setSelectedRisk(null);
                showToast("✅ 작업 제안이 목록에 추가되었습니다.");
              }}
            />
          )}
        </div>

        {/* Right: Provider status + recent activity */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Provider health */}
          <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-lg)", overflow: "hidden" }}>
            <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--border)", background: "var(--surface-2)", fontSize: 12, fontWeight: 700, color: "var(--text-secondary)" }}>
              연동 상태
            </div>
            <div style={{ padding: "12px 16px", display: "flex", flexDirection: "column", gap: 10 }}>
              {providers.map(p => (
                <div key={p.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                  <ProviderBadge name={p.name} status={p.status} />
                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontSize: 10, color: "var(--text-tertiary)", fontFamily: "var(--font-mono)" }}>{p.lastSync}</div>
                    {p.note && <div style={{ fontSize: 10, color: "var(--warn-text)" }}>{p.note}</div>}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* eCount stale warning */}
          <div style={{ background: "var(--warn-bg)", border: "1px solid var(--warn-border)", borderRadius: "var(--radius)", padding: "10px 14px" }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: "var(--warn-text)", marginBottom: 4 }}>⚠ eCount 데이터 지연</div>
            <div style={{ fontSize: 11, color: "var(--text-secondary)", lineHeight: 1.5 }}>
              마지막 동기화 47분 전. 재고 수치가 실제와 다를 수 있습니다. 실시간 재고 확인 후 의사결정하세요.
            </div>
          </div>

          {/* AI activity */}
          <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-lg)", overflow: "hidden" }}>
            <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--border)", background: "var(--surface-2)", fontSize: 12, fontWeight: 700, color: "var(--text-secondary)" }}>
              AI 처리 현황 (오늘)
            </div>
            <div style={{ padding: "12px 16px", display: "flex", flexDirection: "column", gap: 8 }}>
              {[
                { label: "문의 자동분류", value: "128건", pct: 92 },
                { label: "재고 위험 감지", value: "5건", pct: 100 },
                { label: "초안 생성", value: "47건", pct: 88 },
              ].map(item => (
                <div key={item.label}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, marginBottom: 3 }}>
                    <span style={{ color: "var(--text-secondary)" }}>{item.label}</span>
                    <span style={{ color: "var(--text-primary)", fontWeight: 600, fontFamily: "var(--font-mono)" }}>{item.value}</span>
                  </div>
                  <div style={{ height: 4, background: "var(--surface-2)", borderRadius: 2, overflow: "hidden" }}>
                    <div style={{ height: "100%", width: `${item.pct}%`, background: "var(--ai-accent)", borderRadius: 2 }} />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Safety notice */}
          <div style={{ background: "var(--surface-2)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: "10px 14px" }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-secondary)", marginBottom: 4 }}>🛡 안전 원칙</div>
            <div style={{ fontSize: 11, color: "var(--text-tertiary)", lineHeight: 1.6 }}>
              이 시스템은 <strong>의사결정 지원 도구</strong>입니다. 환불·취소·가격변경·결제는 자동으로 실행되지 않습니다. 모든 조치는 담당자 검토 후 수동 실행됩니다.
            </div>
          </div>
        </div>
      </div>

      {/* Evidence Drawer */}
      <EvidenceDrawer
        item={selectedRisk}
        onClose={() => setSelectedRisk(null)}
        onPropose={(item) => {
          setSelectedRisk(null);
          setProposalItem(item);
        }}
      />

      {/* Toast */}
      {toast && (
        <div className="toast-container">
          <div className="toast">{toast}</div>
        </div>
      )}
    </div>
  );
}

function RiskCard({ risk, onClick }: { risk: RiskItem; onClick: () => void }) {
  const isCrit = risk.severity === "critical";
  return (
    <button
      onClick={onClick}
      style={{
        background: "var(--surface)",
        border: `1px solid ${isCrit ? "var(--crit-border)" : "var(--warn-border)"}`,
        borderLeft: `4px solid ${isCrit ? "var(--crit-accent)" : "var(--warn-accent)"}`,
        borderRadius: "var(--radius)",
        padding: "14px 16px",
        textAlign: "left",
        cursor: "pointer",
        width: "100%",
        transition: "box-shadow 0.15s ease",
      }}
      onMouseEnter={e => (e.currentTarget.style.boxShadow = "0 2px 8px rgba(0,0,0,0.08)")}
      onMouseLeave={e => (e.currentTarget.style.boxShadow = "none")}
    >
      <div style={{ display: "flex", alignItems: "flex-start", gap: 12, justifyContent: "space-between" }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
            <RiskBadge severity={risk.severity} />
            <span style={{ fontSize: 11, color: "var(--text-tertiary)", fontFamily: "var(--font-mono)" }}>{risk.id}</span>
            <span style={{ fontSize: 10, background: "var(--surface-2)", color: "var(--text-secondary)", borderRadius: "var(--radius-sm)", padding: "1px 5px", border: "1px solid var(--border)" }}>{risk.type}</span>
          </div>
          <div style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)", marginBottom: 4 }}>{risk.title}</div>
          <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.5 }}>{risk.description}</div>
          <div style={{ marginTop: 8, display: "flex", flexWrap: "wrap", gap: 6, alignItems: "center" }}>
            {risk.sources.map(s => <SourceChip key={s} source={s} />)}
            <FreshnessBadge asOf={risk.asOf} stale={risk.asOf.includes("시간")} />
            {risk.confidence !== undefined && <ConfidenceBadge value={risk.confidence} />}
          </div>
        </div>
        <div style={{ fontSize: 18, color: "var(--text-tertiary)", flexShrink: 0 }}>→</div>
      </div>
    </button>
  );
}
