import React, { useState } from "react";
import { providers } from "../data/mockData";
import { ProviderBadge } from "../components/Badges";
import { DeniedState } from "../components/UIStates";

export default function Settings() {
  const [tab, setTab] = useState<"연동" | "알림" | "팀">("연동");
  const [showDenied, setShowDenied] = useState(false);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Tabs */}
      <div style={{ padding: "0 24px", borderBottom: "1px solid var(--border)", background: "var(--surface)", display: "flex" }}>
        {(["연동", "알림", "팀"] as const).map(t => (
          <button key={t} onClick={() => setTab(t)} style={{ background: "none", border: "none", cursor: "pointer", padding: "14px 20px", fontSize: 13, fontWeight: tab === t ? 700 : 400, color: tab === t ? "var(--rule-accent)" : "var(--text-secondary)", borderBottom: tab === t ? "2px solid var(--rule-accent)" : "2px solid transparent", marginBottom: -1 }}>
            {t}
          </button>
        ))}
      </div>

      <div style={{ flex: 1, overflow: "auto", padding: "24px" }}>
        {tab === "연동" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            {/* Read-only safety notice */}
            <div style={{ background: "var(--warn-bg)", border: "1px solid var(--warn-border)", borderRadius: "var(--radius)", padding: "10px 16px", fontSize: 12, color: "var(--warn-text)", lineHeight: 1.6, display: "flex", gap: 8 }}>
              <span>⚠</span>
              <div>
                <strong>연동 상태 확인 및 수동 동기화만 가능합니다.</strong><br />
                자격증명 변경은 보안 관리자에게 문의하세요. API 키·비밀번호는 표시되지 않습니다.
              </div>
            </div>

            {/* Demo denied state example */}
            {showDenied && (
              <DeniedState
                action="eCount API 자격증명 직접 변경"
                reason="Production Read-Only 환경에서는 자격증명 변경이 차단됩니다."
                reasonCode="POLICY_READONLY_ENV"
              />
            )}

            {providers.map(p => (
              <div key={p.id} style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-lg)", overflow: "hidden" }}>
                <div style={{ padding: "12px 16px", background: "var(--surface-2)", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", gap: 12 }}>
                  <ProviderBadge name={p.name} status={p.status} />
                  <span style={{ fontSize: 14, fontWeight: 700 }}>{p.name}</span>
                  <span style={{ marginLeft: "auto", fontSize: 11, color: "var(--text-tertiary)", fontFamily: "var(--font-mono)" }}>마지막 동기화: {p.lastSync}</span>
                  {p.latencyMs > 0 && <span style={{ fontSize: 11, color: "var(--text-tertiary)", fontFamily: "var(--font-mono)" }}>응답 {p.latencyMs}ms</span>}
                </div>
                <div style={{ padding: "12px 16px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                  {[
                    { label: "연동 방식", value: "REST API" },
                    { label: "인증 방식", value: "OAuth 2.0 (자격증명 미표시)" },
                    { label: "데이터 범위", value: p.id === "cafe24" ? "주문, 상품, 재고" : p.id === "toss" ? "POS 매출, 재고" : "재고, 입고, 품목" },
                    { label: "갱신 주기", value: p.id === "ecount" ? "30분 (현재 지연)" : "5분" },
                  ].map(r => (
                    <div key={r.label}>
                      <div style={{ fontSize: 10, color: "var(--text-tertiary)", marginBottom: 2 }}>{r.label}</div>
                      <div style={{ fontSize: 12, fontWeight: 500 }}>{r.value}</div>
                    </div>
                  ))}
                </div>
                {p.note && <div style={{ padding: "6px 16px 12px", fontSize: 12, color: "var(--warn-text)" }}>⚠ {p.note}</div>}
                <div style={{ padding: "10px 16px", borderTop: "1px solid var(--border)", display: "flex", gap: 8 }}>
                  <button style={{ background: "var(--rule-bg)", color: "var(--rule-text)", border: "1px solid var(--rule-border)", borderRadius: "var(--radius)", padding: "6px 14px", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>수동 동기화</button>
                  <button style={{ background: "none", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: "6px 12px", fontSize: 12, cursor: "pointer", color: "var(--text-secondary)" }}>연결 테스트</button>
                  <button onClick={() => setShowDenied(true)} style={{ background: "none", border: "1px solid var(--crit-border)", borderRadius: "var(--radius)", padding: "6px 12px", fontSize: 12, cursor: "pointer", color: "var(--crit-text)" }}>자격증명 변경 (차단됨)</button>
                </div>
              </div>
            ))}

            <div style={{ background: "var(--surface-2)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: "10px 14px", fontSize: 11, color: "var(--text-tertiary)", lineHeight: 1.7 }}>
              📋 최종 API 필드명은 Cafe24 / Toss POS / eCount OpenAPI 계약 및 JSON Schema에서 확정됩니다. 이 화면의 레이블은 시맨틱 식별자입니다.
            </div>
          </div>
        )}

        {tab === "알림" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 4 }}>위험 알림 설정</div>
            {[
              { label: "재고 불일치 감지", desc: "Cafe24와 eCount 재고 차이 발생 시", enabled: true, level: "critical" },
              { label: "예약 부족 경고", desc: "예약 수량 > 생산 가능 수량", enabled: true, level: "critical" },
              { label: "입고 지연 알림", desc: "예정 입고일 초과 시", enabled: true, level: "warning" },
              { label: "문의 급증 감지", desc: "전일 대비 +200% 초과", enabled: true, level: "warning" },
              { label: "AI 판단 신뢰도 낮음", desc: "신뢰도 75% 미만 초안 발생 시", enabled: false, level: "warning" },
            ].map((item, i) => (
              <div key={i} style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: "12px 16px", display: "flex", alignItems: "center", gap: 12 }}>
                <input type="checkbox" defaultChecked={item.enabled} style={{ width: 16, height: 16, accentColor: "var(--rule-accent)" }} aria-label={item.label} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 600 }}>{item.label}</div>
                  <div style={{ fontSize: 11, color: "var(--text-tertiary)" }}>{item.desc}</div>
                </div>
                <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 6px", borderRadius: "var(--radius-sm)", background: item.level === "critical" ? "var(--crit-bg)" : "var(--warn-bg)", color: item.level === "critical" ? "var(--crit-text)" : "var(--warn-text)", border: `1px solid ${item.level === "critical" ? "var(--crit-border)" : "var(--warn-border)"}` }}>
                  {item.level === "critical" ? "🔴 위험" : "🟡 주의"}
                </span>
              </div>
            ))}
          </div>
        )}

        {tab === "팀" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 4 }}>역할 및 권한 관리</div>
            <div style={{ background: "var(--warn-bg)", border: "1px solid var(--warn-border)", borderRadius: "var(--radius)", padding: "10px 14px", fontSize: 12, color: "var(--warn-text)", lineHeight: 1.6 }}>
              ⚠ 실제 사용자 정보는 표시되지 않습니다 (합성 데이터 환경). 실제 사용자 관리는 관리자 시스템에서 처리합니다.
            </div>

            {/* Production read-only rule */}
            <div style={{ background: "var(--crit-bg)", border: "2px solid var(--crit-border)", borderRadius: "var(--radius)", padding: "10px 14px", fontSize: 12, color: "var(--crit-text)", lineHeight: 1.6, display: "flex", gap: 8 }}>
              <span style={{ fontSize: 16 }}>🔴</span>
              <div>
                <strong>Production Read-Only 정책:</strong> 모든 역할에서 외부 주문·재고·가격·결제 변경 권한은 제공되지 않습니다. 이 시스템은 의사결정 지원 도구이며 자동 실행되지 않습니다.
              </div>
            </div>

            <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-lg)", overflow: "hidden" }}>
              <table className="dense-table">
                <thead>
                  <tr>
                    <th>역할</th>
                    <th>데이터 조회</th>
                    <th>AI 제안 검토</th>
                    <th>내부 업무 승인</th>
                    <th>알림 관리</th>
                    <th>설정 관리</th>
                    <th>외부 시스템 변경</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    { role: "운영 관리자", view: "✓", aiReview: "✓", workApprove: "✓", alert: "✓", config: "✓", external: "✗" },
                    { role: "운영 담당자", view: "✓", aiReview: "✓", workApprove: "✓", alert: "✗", config: "✗", external: "✗" },
                    { role: "CS 담당자", view: "문의만", aiReview: "✓ (문의)", workApprove: "✗", alert: "✗", config: "✗", external: "✗" },
                    { role: "조회 전용", view: "✓", aiReview: "✗", workApprove: "✗", alert: "✗", config: "✗", external: "✗" },
                  ].map((r, i) => {
                    const green = "var(--human-text)";
                    const red = "var(--crit-text)";
                    const neutral = "var(--text-secondary)";
                    const c = (v: string) => v === "✓" || v.includes("✓") ? green : v === "✗" ? red : neutral;
                    return (
                      <tr key={i}>
                        <td style={{ fontWeight: 600 }}>{r.role}</td>
                        <td style={{ color: c(r.view), fontWeight: 600 }}>{r.view}</td>
                        <td style={{ color: c(r.aiReview), fontWeight: 600 }}>{r.aiReview}</td>
                        <td style={{ color: c(r.workApprove), fontWeight: 600 }}>{r.workApprove}</td>
                        <td style={{ color: c(r.alert), fontWeight: 600 }}>{r.alert}</td>
                        <td style={{ color: c(r.config), fontWeight: 600 }}>{r.config}</td>
                        <td style={{ color: red, fontWeight: 700 }}>✗ (정책상 차단)</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <p style={{ fontSize: 11, color: "var(--text-tertiary)", margin: 0 }}>
              ※ 외부 시스템 변경(주문취소·환불·재고변경·가격변경·결제·정산)은 어떤 역할에서도 이 시스템을 통해 실행되지 않습니다.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
