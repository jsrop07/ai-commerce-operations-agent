import React, { useState } from "react";
import { inquiries, InquiryRow } from "../data/mockData";
import { SourceChip, StatusBadge, ConfidenceBadge, AIBadge, FreshnessBadge } from "../components/Badges";
import { LowConfidenceBanner } from "../components/UIStates";

type DraftAction = "수정중" | "승인대기" | "보류" | "근거부족" | "거절";

const urgencyColor = (u: string) =>
  u === "높음" ? "var(--crit-text)" : u === "보통" ? "var(--warn-text)" : "var(--text-secondary)";

export default function Inquiry() {
  const [selected, setSelected] = useState<InquiryRow | null>(inquiries[0]);
  const [draftEdits, setDraftEdits] = useState<Record<string, string>>({});
  const [draftActions, setDraftActions] = useState<Record<string, DraftAction>>({});
  const [expandedDraft, setExpandedDraft] = useState(false);
  const [showSources, setShowSources] = useState<Record<string, boolean>>({});
  const [toast, setToast] = useState<string | null>(null);

  const showToast = (msg: string) => { setToast(msg); setTimeout(() => setToast(null), 3000); };

  const currentDraft = selected ? (draftEdits[selected.id] ?? selected.draftText ?? "") : "";
  const currentAction = selected ? draftActions[selected.id] : undefined;

  const handleAction = (action: DraftAction) => {
    if (!selected) return;
    setDraftActions(prev => ({ ...prev, [selected.id]: action }));
    const msgs: Record<DraftAction, string> = {
      "수정중": "수정 모드로 전환됩니다.",
      "승인대기": "승인 대기 상태로 변경되었습니다. 실제 발송은 담당자가 직접 처리해야 합니다.",
      "보류": "문의가 보류 처리되었습니다.",
      "근거부족": "근거 부족으로 표시되었습니다.",
      "거절": "초안이 거절되었습니다.",
    };
    showToast(msgs[action]);
  };

  return (
    <div style={{ display: "flex", height: "100%", overflow: "hidden" }}>

      {/* ── 왼쪽: 문의 목록 (240px) ── */}
      <div style={{ width: 240, borderRight: "1px solid var(--border)", background: "var(--surface)", display: "flex", flexDirection: "column", flexShrink: 0 }}>
        <div style={{ padding: "10px 14px", borderBottom: "1px solid var(--border)", background: "var(--surface-2)" }}>
          <div style={{ fontSize: 12, fontWeight: 700 }}>문의 목록</div>
          <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginTop: 2 }}>
            전체 {inquiries.length}건 · 긴급 {inquiries.filter(q => q.urgency === "높음").length}건
          </div>
        </div>
        <div style={{ flex: 1, overflow: "auto" }}>
          {inquiries.map(q => (
            <button
              key={q.id}
              onClick={() => setSelected(q)}
              style={{
                display: "block", width: "100%", textAlign: "left",
                background: selected?.id === q.id ? "var(--rule-bg)" : "none",
                border: "none", borderBottom: "1px solid var(--border)", padding: "10px 14px", cursor: "pointer",
                borderLeft: selected?.id === q.id ? "3px solid var(--rule-accent)" : "3px solid transparent",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 4, marginBottom: 3 }}>
                <span style={{ fontSize: 10, fontWeight: 700, color: urgencyColor(q.urgency) }}>
                  {q.urgency === "높음" ? "🔴" : q.urgency === "보통" ? "🟡" : "⚪"}
                </span>
                <StatusBadge status={q.draftStatus} />
                <span style={{ marginLeft: "auto", fontSize: 10, color: "var(--text-tertiary)", fontFamily: "var(--font-mono)" }}>{q.receivedAt}</span>
              </div>
              <div style={{ fontSize: 12, fontWeight: 500, color: "var(--text-primary)", lineHeight: 1.4, marginBottom: 2 }}>{q.subject}</div>
              <div style={{ fontSize: 11, color: "var(--text-tertiary)" }}>{q.customer}</div>
            </button>
          ))}
        </div>
      </div>

      {selected ? (
        <>
          {/* ── 가운데: 문의 내용 + AI 분류 + 답변 참고 (340px) ── */}
          <div style={{ width: 340, borderRight: "1px solid var(--border)", background: "var(--surface)", display: "flex", flexDirection: "column", flexShrink: 0, overflow: "hidden" }}>
            <div style={{ padding: "10px 14px", borderBottom: "1px solid var(--border)", background: "var(--surface-2)", flexShrink: 0 }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-primary)", lineHeight: 1.4, marginBottom: 2 }}>{selected.subject}</div>
              <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: urgencyColor(selected.urgency) }}>
                  {selected.urgency === "높음" ? "🔴 긴급" : selected.urgency === "보통" ? "🟡 보통" : "⚪ 낮음"}
                </span>
                <SourceChip source={selected.source} />
                <FreshnessBadge asOf={selected.receivedAt} stale={false} />
              </div>
            </div>

            <div style={{ flex: 1, overflowY: "auto", padding: "12px 14px", display: "flex", flexDirection: "column", gap: 14 }}>
              {/* 문의 정보 */}
              <div style={{ background: "var(--surface-2)", borderRadius: "var(--radius)", padding: "10px 12px", display: "flex", flexDirection: "column", gap: 6 }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-secondary)", marginBottom: 2 }}>문의 정보</div>
                {[
                  { label: "티켓 ID", value: selected.ticketId, mono: true },
                  { label: "고객", value: selected.customer },
                  { label: "소스", value: selected.source },
                  { label: "접수", value: selected.receivedAt },
                ].map(r => (
                  <div key={r.label} style={{ display: "flex", justifyContent: "space-between", fontSize: 11, gap: 6 }}>
                    <span style={{ color: "var(--text-tertiary)", flexShrink: 0 }}>{r.label}</span>
                    <span style={{ fontFamily: r.mono ? "var(--font-mono)" : undefined, fontWeight: 500, textAlign: "right", fontSize: r.mono ? 10 : 11 }}>{r.value}</span>
                  </div>
                ))}
              </div>

              {/* AI 분류 */}
              <div style={{ background: "var(--ai-bg)", border: "1px solid var(--ai-border)", borderRadius: "var(--radius)", padding: "10px 12px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
                  <AIBadge label="AI 분류" />
                  <ConfidenceBadge value={selected.confidence} />
                </div>
                <div style={{ marginBottom: 8 }}>
                  <div style={{ fontSize: 10, fontWeight: 700, color: "var(--text-tertiary)", marginBottom: 4, textTransform: "uppercase" }}>문의 유형</div>
                  <span style={{ background: "var(--ai-accent)", color: "white", borderRadius: "var(--radius-sm)", padding: "2px 8px", fontSize: 12, fontWeight: 600 }}>
                    {selected.intent}
                  </span>
                </div>
                <div>
                  <div style={{ fontSize: 10, fontWeight: 700, color: "var(--text-tertiary)", marginBottom: 4, textTransform: "uppercase" }}>파악된 정보</div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
                    {selected.entities.map(e => (
                      <div key={e} style={{ background: "var(--surface)", border: "1px solid var(--ai-border)", borderRadius: "var(--radius-sm)", padding: "3px 7px", fontSize: 11, color: "var(--ai-text)" }}>
                        {e}
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* 신뢰도 경고 */}
              {selected.confidence < 80 && (
                <LowConfidenceBanner
                  confidence={selected.confidence}
                  context="관련 정보가 충분하지 않거나 의도 파악이 불명확합니다."
                />
              )}

              {/* 답변 참고 정보 */}
              {selected.citations && selected.citations.length > 0 && (
                <div style={{ border: "1px solid var(--rule-border)", borderRadius: "var(--radius)", overflow: "hidden" }}>
                  <div style={{ background: "var(--rule-bg)", padding: "8px 10px", borderBottom: "1px solid var(--rule-border)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                      <RuleBadge />
                      <span style={{ fontSize: 11, fontWeight: 700, color: "var(--rule-text)" }}>답변 참고 정보</span>
                    </div>
                    <button
                      onClick={() => setShowSources(prev => ({ ...prev, [selected.id]: !prev[selected.id] }))}
                      style={{ background: "none", border: "none", fontSize: 10, color: "var(--text-tertiary)", cursor: "pointer" }}
                    >
                      {showSources[selected.id] ? "상세 출처 숨기기" : "상세 출처 보기"}
                    </button>
                  </div>
                  <div style={{ padding: "8px 10px", display: "flex", flexDirection: "column", gap: 5 }}>
                    {selected.citations.map((c, i) => (
                      <div key={i} style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.5, padding: "3px 0", borderBottom: i < selected.citations!.length - 1 ? "1px solid var(--rule-border)" : "none" }}>
                        {c}
                      </div>
                    ))}
                    {showSources[selected.id] && (
                      <div style={{ marginTop: 6, padding: "6px 8px", background: "var(--surface-2)", borderRadius: "var(--radius-sm)", fontSize: 10, color: "var(--text-tertiary)", fontFamily: "var(--font-mono)", lineHeight: 1.6 }}>
                        <div>검색 엔진: RAG 하이브리드 검색</div>
                        <div>문서 DB: 정책·상품·주문 데이터</div>
                        <div>기준 시각: {selected.receivedAt}</div>
                        <div style={{ marginTop: 4, color: "var(--text-tertiary)" }}>※ 내부 기술 상세 — 운영자 참고용</div>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* ── 오른쪽: AI 초안 (나머지 전체) ── */}
          <div style={{ flex: 1, display: "flex", flexDirection: "column", background: "var(--bg)", overflow: "hidden" }}>
            {/* Header */}
            <div style={{ padding: "10px 16px", borderBottom: "1px solid var(--border)", background: "var(--surface)", display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
              <AIBadge label="AI 초안" />
              <span style={{ fontSize: 12, fontWeight: 700 }}>AI 답변 초안</span>
              <span style={{ background: "var(--crit-bg)", color: "var(--crit-text)", border: "1px solid var(--crit-border)", borderRadius: "var(--radius-sm)", padding: "1px 7px", fontSize: 10, fontWeight: 700 }}>
                실제 전송 아님
              </span>
              <StatusBadge status={currentAction ?? selected.draftStatus} />
              <button
                onClick={() => setExpandedDraft(!expandedDraft)}
                style={{ marginLeft: "auto", background: "var(--surface-2)", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", padding: "3px 8px", fontSize: 11, cursor: "pointer", color: "var(--text-secondary)" }}
                title="확대 편집"
              >
                {expandedDraft ? "⊡ 축소" : "⊞ 확대 편집"}
              </button>
            </div>

            {/* Draft-only notice */}
            <div style={{ padding: "8px 16px", background: "#FFFBEB", borderBottom: "1px solid #FDE68A", flexShrink: 0 }}>
              <span style={{ fontSize: 11, color: "var(--warn-text)", fontWeight: 600 }}>
                ⚠ AI 답변 초안 · 실제 전송 아님 — 담당자 검토 후 Cafe24에서 직접 발송해야 합니다
              </span>
            </div>

            {/* Draft area */}
            <div style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column", padding: "14px 16px 0" }}>
              {selected.draftText ? (
                <textarea
                  value={currentDraft}
                  onChange={e => setDraftEdits(prev => ({ ...prev, [selected.id]: e.target.value }))}
                  style={{
                    flex: 1,
                    width: "100%",
                    border: "1px solid var(--border)",
                    borderRadius: "var(--radius)",
                    padding: "14px 16px",
                    fontSize: expandedDraft ? 14 : 13,
                    lineHeight: 1.8,
                    fontFamily: "var(--font-sans)",
                    color: "var(--text-primary)",
                    background: "var(--surface)",
                    resize: "none",
                    outline: "none",
                    boxSizing: "border-box",
                  }}
                />
              ) : (
                <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", border: "1px solid var(--border)", borderRadius: "var(--radius)", background: "var(--surface)" }}>
                  {selected.confidence < 75 ? (
                    <LowConfidenceBanner
                      confidence={selected.confidence}
                      context="AI가 이 문의에 대한 초안을 생성할 수 없습니다. 담당자가 직접 작성해야 합니다."
                    />
                  ) : (
                    <div style={{ textAlign: "center", color: "var(--text-tertiary)", fontSize: 12 }}>
                      <div style={{ marginBottom: 8 }}>⏳</div>
                      <div>초안 생성 중입니다...</div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Action buttons — fixed at bottom */}
            <div style={{ padding: "12px 16px", borderTop: "1px solid var(--border)", background: "var(--surface)", flexShrink: 0 }}>
              <div style={{ marginBottom: 8, fontSize: 11, fontWeight: 600, color: "var(--text-secondary)" }}>초안 검토 결과</div>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {(["수정중", "승인대기", "보류", "근거부족", "거절"] as DraftAction[]).map(a => (
                  <button
                    key={a}
                    onClick={() => handleAction(a)}
                    style={{
                      background: currentAction === a ? "var(--rule-accent)" : "var(--surface)",
                      color: currentAction === a ? "white" : "var(--text-secondary)",
                      border: `1px solid ${currentAction === a ? "var(--rule-accent)" : "var(--border)"}`,
                      borderRadius: "var(--radius-sm)",
                      padding: "5px 12px", fontSize: 12, fontWeight: currentAction === a ? 600 : 400,
                      cursor: "pointer",
                    }}
                  >
                    {a}
                  </button>
                ))}
              </div>
              <p style={{ fontSize: 11, color: "var(--text-tertiary)", margin: "8px 0 0", lineHeight: 1.5 }}>
                이 초안은 외부로 자동 발송되지 않습니다. 환불·취소·재고 변경·결제는 이 화면에서 처리할 수 없습니다.
              </p>
            </div>
          </div>
        </>
      ) : (
        <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-tertiary)", fontSize: 13 }}>
          왼쪽에서 문의를 선택하세요
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

function RuleBadge() {
  return (
    <span style={{ background: "var(--rule-bg)", color: "var(--rule-text)", border: "1px solid var(--rule-border)", borderRadius: "var(--radius-sm)", padding: "1px 6px", fontSize: 10, fontWeight: 600 }}>데이터</span>
  );
}
