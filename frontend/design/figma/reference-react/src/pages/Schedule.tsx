import React, { useState } from "react";
import { scheduleItems, ScheduleItem } from "../data/mockData";
import { StatusBadge, AIBadge, ConfidenceBadge } from "../components/Badges";
import { AgentWaitingState } from "../components/UIStates";

export default function Schedule() {
  const [items, setItems] = useState(scheduleItems);
  const [showImpactModal, setShowImpactModal] = useState(false);
  const [approvedIds, setApprovedIds] = useState<string[]>([]);
  const [toast, setToast] = useState<string | null>(null);

  const showToast = (msg: string) => { setToast(msg); setTimeout(() => setToast(null), 3500); };

  const typeIcon: Record<string, string> = { "생산": "🏭", "배송": "🚚", "입고": "📦", "픽업": "🛍", "점검": "🔧" };
  const typeColor: Record<string, string> = { "생산": "var(--rule-text)", "배송": "var(--ai-text)", "입고": "var(--human-text)", "픽업": "var(--warn-text)", "점검": "var(--text-secondary)" };

  const grouped = items.reduce((acc, item) => {
    if (!acc[item.date]) acc[item.date] = [];
    acc[item.date].push(item);
    return acc;
  }, {} as Record<string, ScheduleItem[]>);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Header */}
      <div style={{ padding: "12px 24px", background: "var(--surface)", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", gap: 12 }}>
        <h2 style={{ margin: 0, fontSize: 14, fontWeight: 700 }}>운영 일정</h2>
        <span style={{ fontSize: 11, color: "var(--text-tertiary)" }}>2024년 9월 4일 (수) ~ 9월 8일 (일)</span>
        <button onClick={() => setShowImpactModal(true)} style={{ marginLeft: "auto", background: "var(--warn-bg)", color: "var(--warn-text)", border: "1px solid var(--warn-border)", borderRadius: "var(--radius)", padding: "6px 14px", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>
          ⚠ 입고 지연 영향 검토
        </button>
      </div>

      <div style={{ flex: 1, overflow: "auto", padding: "20px 24px", display: "grid", gridTemplateColumns: "1fr 340px", gap: 20, alignContent: "start" }}>
        {/* Timeline */}
        <div>
          {Object.entries(grouped).map(([date, dateItems]) => (
            <div key={date} style={{ marginBottom: 20 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: "var(--text-secondary)", marginBottom: 10, padding: "4px 0", borderBottom: "1px solid var(--border)" }}>{date}</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {dateItems.map(item => (
                  <div key={item.id} style={{
                    display: "flex", gap: 12, alignItems: "flex-start", padding: "10px 14px",
                    background: "var(--surface)",
                    border: `1px solid ${item.isProposal ? "var(--ai-border)" : item.status === "지연" ? "var(--crit-border)" : "var(--border)"}`,
                    borderLeft: `3px solid ${item.isProposal ? "var(--ai-accent)" : item.status === "지연" ? "var(--crit-accent)" : item.status === "완료" ? "var(--human-accent)" : item.status === "진행중" ? "var(--rule-accent)" : "var(--border-strong)"}`,
                    borderRadius: "var(--radius)",
                    opacity: item.status === "취소" ? 0.5 : 1,
                  }}>
                    <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-tertiary)", width: 44, flexShrink: 0, paddingTop: 2 }}>{item.time}</div>
                    <div style={{ width: 6, height: 6, borderRadius: "50%", background: typeColor[item.type], marginTop: 5, flexShrink: 0 }} />
                    <div style={{ flex: 1 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 3, flexWrap: "wrap" }}>
                        <span style={{ fontSize: 11, color: typeColor[item.type] }}>{typeIcon[item.type]} {item.type}</span>
                        {item.isProposal && <AIBadge label="일정 변경 제안" />}
                        <StatusBadge status={item.status} />
                        {item.originalDate && (
                          <span style={{ fontSize: 10, color: "var(--warn-text)", background: "var(--warn-bg)", border: "1px solid var(--warn-border)", borderRadius: "var(--radius-sm)", padding: "1px 5px" }}>
                            원래 {item.originalDate}
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>{item.title}</div>
                      {item.note && (
                        <div style={{ fontSize: 11, color: item.note.startsWith("⚠") ? "var(--warn-text)" : "var(--text-secondary)", marginTop: 3, lineHeight: 1.5 }}>
                          {item.note}
                        </div>
                      )}
                      {item.isProposal && !approvedIds.includes(item.id) && (
                        <div style={{ marginTop: 10 }}>
                          <div style={{ fontSize: 11, color: "var(--ai-text)", marginBottom: 6, lineHeight: 1.5 }}>
                            📋 일정 변경 제안입니다. 승인 전 실제 일정은 변경되지 않습니다.
                          </div>
                          <div style={{ display: "flex", gap: 6 }}>
                            <button
                              onClick={() => { setApprovedIds(prev => [...prev, item.id]); showToast("✅ 일정 변경 제안 검토 완료 — 운영팀이 직접 일정을 수정해야 합니다. 외부 시스템 자동 변경 없음."); }}
                              style={{ background: "var(--human-accent)", color: "white", border: "none", borderRadius: "var(--radius-sm)", padding: "5px 12px", fontSize: 11, fontWeight: 600, cursor: "pointer" }}
                            >
                              검토 후 승인
                            </button>
                            <button style={{ background: "none", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", padding: "5px 8px", fontSize: 11, cursor: "pointer", color: "var(--text-secondary)" }}>
                              거부
                            </button>
                          </div>
                        </div>
                      )}
                      {approvedIds.includes(item.id) && (
                        <div style={{ fontSize: 11, color: "var(--human-text)", marginTop: 4, fontWeight: 600 }}>✓ 검토 승인됨 — 운영팀 실행 대기</div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Right panel: impact + before/after */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Impact summary */}
          <div style={{ background: "var(--crit-bg)", border: "1px solid var(--crit-border)", borderRadius: "var(--radius-lg)", padding: "14px 16px" }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: "var(--crit-text)", marginBottom: 8 }}>🔴 입고 지연 영향 요약</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.6 }}>
              <div>• <strong>무엇이 지연됐는지:</strong> 생크림 원자재</div>
              <div>• <strong>며칠 지연:</strong> 3일 (9/4 → 9/7)</div>
              <div>• <strong>영향 작업:</strong> 9/5 오전 생산 배치</div>
              <div>• <strong>영향 주문:</strong> 3건 배송 지연 가능</div>
              <div>• <strong>담당자 확인 필요:</strong> 예</div>
            </div>
          </div>

          {/* Before/After proposal */}
          <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-lg)", overflow: "hidden" }}>
            <div style={{ padding: "10px 14px", borderBottom: "1px solid var(--border)", background: "var(--surface-2)", display: "flex", alignItems: "center", gap: 8 }}>
              <AIBadge label="AI 일정 재배치 제안" />
              <ConfidenceBadge value={85} />
            </div>
            <div style={{ padding: "12px 14px" }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-secondary)", marginBottom: 10 }}>기존 일정 vs. 제안 일정</div>
              {[
                { label: "생산 배치 (9/5 AM)", before: "예정", after: "9/8로 재배정 제안", warn: true, reason: "생크림 미입고" },
                { label: "말차 픽업 (9/5)", before: "예정", after: "9/8 이후 가능", warn: true, reason: "재고 없음" },
                { label: "주말 배송 (9/7 2차)", before: "24건", after: "18건 확정 / 6건 지연", warn: true, reason: "생산 수량 부족" },
              ].map(row => (
                <div key={row.label} style={{ marginBottom: 12, paddingBottom: 12, borderBottom: "1px solid var(--border)" }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-secondary)", marginBottom: 6 }}>{row.label}</div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 18px 1fr", gap: 6, alignItems: "center", marginBottom: 3 }}>
                    <div style={{ background: "var(--surface-2)", borderRadius: "var(--radius-sm)", padding: "5px 8px", fontSize: 11, color: "var(--text-tertiary)", textDecoration: "line-through" }}>{row.before}</div>
                    <span style={{ textAlign: "center", color: "var(--ai-accent)", fontWeight: 700, fontSize: 14 }}>→</span>
                    <div style={{ background: "var(--warn-bg)", borderRadius: "var(--radius-sm)", padding: "5px 8px", fontSize: 11, color: "var(--warn-text)", fontWeight: 600 }}>{row.after}</div>
                  </div>
                  <div style={{ fontSize: 10, color: "var(--text-tertiary)" }}>변경 이유: {row.reason}</div>
                </div>
              ))}
              <p style={{ fontSize: 11, color: "var(--text-tertiary)", margin: 0, lineHeight: 1.5 }}>
                ⚠ 일정 변경 제안입니다. 승인 전 실제 일정은 변경되지 않습니다. 운영팀이 직접 적용해야 합니다.
              </p>
            </div>
          </div>

          {/* Agent waiting example */}
          <AgentWaitingState
            step="영향 주문 3건 안내 초안 대기"
            checkpoint="담당자 승인 필요"
            requiredAction="입고 지연 영향 고객 안내 초안 검토 및 승인"
          />
        </div>
      </div>

      {/* Impact detail modal */}
      {showImpactModal && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", zIndex: 50, display: "flex", alignItems: "center", justifyContent: "center" }} onClick={() => setShowImpactModal(false)}>
          <div style={{ background: "var(--surface)", borderRadius: "var(--radius-lg)", padding: "24px", width: 540, maxWidth: "90vw", boxShadow: "0 8px 32px rgba(0,0,0,0.15)" }} onClick={e => e.stopPropagation()}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
              <AIBadge label="AI 분석" />
              <h3 style={{ margin: 0, fontSize: 15, fontWeight: 700 }}>입고 지연 영향 상세 분석</h3>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 20, fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.8 }}>
              {[
                { q: "무엇이 지연됐는지", a: "생크림 원자재" },
                { q: "며칠 지연됐는지", a: "3일 (9/4 예정 → 9/7 변경)" },
                { q: "어떤 작업에 영향이 있는지", a: "9/5 오전 생산 배치 전면 취소 예상" },
                { q: "기존 일정", a: "9/5 AM 생산 18개, 9/7 배송 24건" },
                { q: "제안 일정", a: "9/8 생산 시작, 9/7 배송 18건 확정·6건 지연" },
                { q: "영향 범위", a: "주문 3건 배송 지연, 고객 6명 사전 안내 필요" },
                { q: "신뢰도", a: "85% — 담당자 최종 확인 필요" },
              ].map(r => (
                <div key={r.q} style={{ display: "flex", gap: 8 }}>
                  <span style={{ color: "var(--text-tertiary)", flexShrink: 0, minWidth: 170 }}>{r.q}</span>
                  <span style={{ fontWeight: 500, color: "var(--text-primary)" }}>{r.a}</span>
                </div>
              ))}
            </div>
            <p style={{ fontSize: 11, color: "var(--text-tertiary)", margin: "0 0 16px", lineHeight: 1.5 }}>
              이 분석은 제안입니다. 실제 일정 변경은 운영팀이 직접 실행해야 합니다. 외부 시스템 자동 변경 없음.
            </p>
            <div style={{ display: "flex", gap: 8 }}>
              <button onClick={() => { setShowImpactModal(false); showToast("재배치 제안이 일정 화면에 표시됩니다."); }} style={{ background: "var(--rule-accent)", color: "white", border: "none", borderRadius: "var(--radius)", padding: "10px 20px", fontSize: 13, fontWeight: 600, cursor: "pointer" }}>
                재배치 제안 검토
              </button>
              <button onClick={() => setShowImpactModal(false)} style={{ background: "none", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: "10px 14px", fontSize: 12, cursor: "pointer", color: "var(--text-secondary)" }}>닫기</button>
            </div>
          </div>
        </div>
      )}

      {toast && (
        <div className="toast-container">
          <div className="toast">{toast}</div>
        </div>
      )}
    </div>
  );
}
