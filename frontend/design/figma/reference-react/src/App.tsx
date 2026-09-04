import React, { useState } from "react";
import { ENV, Env } from "./data/mockData";
import Dashboard from "./pages/Dashboard";
import Inventory from "./pages/Inventory";
import Orders from "./pages/Orders";
import Inquiry from "./pages/Inquiry";
import Schedule from "./pages/Schedule";
import Insights from "./pages/Insights";
import Settings from "./pages/Settings";

type Page = "대시보드" | "상품·재고" | "주문·매출" | "고객문의" | "운영일정" | "AI인사이트" | "연동·설정";

const navItems: { id: Page; icon: string; label: string; badge?: string }[] = [
  { id: "대시보드", icon: "⬡", label: "홈 / 대시보드", badge: "5" },
  { id: "상품·재고", icon: "📦", label: "상품 & 재고" },
  { id: "주문·매출", icon: "🛒", label: "주문 & 매출" },
  { id: "고객문의", icon: "💬", label: "고객 문의 / AI 초안", badge: "31" },
  { id: "운영일정", icon: "📅", label: "운영 일정" },
  { id: "AI인사이트", icon: "✦", label: "AI 인사이트 & 평가" },
  { id: "연동·설정", icon: "⚙", label: "연동 & 설정" },
];

const pageTitles: Record<Page, string> = {
  "대시보드": "홈 / 운영 대시보드",
  "상품·재고": "상품 & 재고",
  "주문·매출": "주문 & 매출",
  "고객문의": "고객 문의 / AI 초안",
  "운영일정": "운영 일정",
  "AI인사이트": "AI 인사이트 & 평가",
  "연동·설정": "연동 & 설정",
};

// Demo: allow toggling between env modes for prototype demonstration
function EnvironmentBanner({ env, onToggle }: { env: Env; onToggle: () => void }) {
  if (env === "demo") {
    return (
      <div
        role="banner"
        aria-label="데모 환경 배너"
        style={{ background: "var(--rule-accent)", color: "white", padding: "5px 20px", fontSize: 11, fontWeight: 600, display: "flex", alignItems: "center", gap: 12, zIndex: 60, flexShrink: 0 }}
      >
        <span aria-label="데모 환경 아이콘">🔵</span>
        <span>데모 환경</span>
        <span style={{ fontWeight: 400, opacity: 0.9 }}>합성 데이터만 표시 · 실제 주문·재고·고객 정보 없음 · 모든 조치는 가상 시뮬레이션</span>
        <button
          onClick={onToggle}
          style={{ marginLeft: "auto", background: "rgba(255,255,255,0.2)", border: "1px solid rgba(255,255,255,0.4)", borderRadius: "var(--radius-sm)", padding: "2px 10px", fontSize: 10, cursor: "pointer", color: "white" }}
        >
          Production 배너 미리보기
        </button>
      </div>
    );
  }

  return (
    <div
      role="banner"
      aria-label="운영 환경 읽기 전용 배너"
      style={{ background: "white", color: "var(--crit-text)", border: "2px solid var(--crit-accent)", padding: "5px 20px", fontSize: 11, display: "flex", alignItems: "center", gap: 10, zIndex: 60, flexShrink: 0 }}
    >
      <span aria-label="경고 아이콘">🔴</span>
      <span style={{ fontWeight: 700 }}>Production Read-Only · 운영환경 읽기 전용</span>
      <span style={{ color: "var(--text-secondary)", fontWeight: 400 }}>실제 데이터 표시 중 · 자동 실행 없음 · 외부 시스템 변경 불가</span>
      <button
        onClick={onToggle}
        style={{ marginLeft: "auto", background: "none", border: "1px solid var(--crit-border)", borderRadius: "var(--radius-sm)", padding: "2px 10px", fontSize: 10, cursor: "pointer", color: "var(--crit-text)" }}
      >
        Demo 배너로 전환
      </button>
    </div>
  );
}

export default function App() {
  const [page, setPage] = useState<Page>("대시보드");
  const [envOverride, setEnvOverride] = useState<Env>(ENV);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", minWidth: 1280, fontFamily: "var(--font-sans)" }}>
      {/* Environment banner */}
      <EnvironmentBanner env={envOverride} onToggle={() => setEnvOverride(e => e === "demo" ? "production" : "demo")} />

      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        {/* Navigation sidebar */}
        <nav aria-label="주 탐색" style={{ width: 224, background: "var(--nav-bg)", display: "flex", flexDirection: "column", flexShrink: 0, overflow: "hidden" }}>
          {/* Logo */}
          <div style={{ padding: "14px 16px 12px", borderBottom: "1px solid rgba(255,255,255,0.08)" }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: "white", lineHeight: 1.3 }}>AI Commerce</div>
            <div style={{ fontSize: 12, fontWeight: 700, color: "white", lineHeight: 1.3 }}>Operations Agent</div>
            <div style={{ fontSize: 10, color: "var(--nav-text)", marginTop: 2 }}>운영 지원 시스템</div>
          </div>

          {/* Nav items */}
          <div style={{ flex: 1, padding: "6px 0", overflow: "auto" }}>
            {navItems.map(item => (
              <button
                key={item.id}
                onClick={() => setPage(item.id)}
                aria-current={page === item.id ? "page" : undefined}
                aria-label={item.label}
                style={{
                  display: "flex", alignItems: "center", gap: 10, width: "100%", textAlign: "left",
                  background: page === item.id ? "var(--nav-active)" : "none",
                  border: "none", cursor: "pointer",
                  padding: "9px 16px", fontSize: 12.5,
                  color: page === item.id ? "var(--nav-text-active)" : "var(--nav-text)",
                  fontWeight: page === item.id ? 600 : 400,
                  transition: "background 0.1s",
                  outline: "none",
                }}
                onMouseEnter={e => { if (page !== item.id) e.currentTarget.style.background = "var(--nav-hover)"; }}
                onMouseLeave={e => { if (page !== item.id) e.currentTarget.style.background = "none"; }}
                onFocus={e => { e.currentTarget.style.outline = "2px solid rgba(255,255,255,0.4)"; e.currentTarget.style.outlineOffset = "-2px"; }}
                onBlur={e => { e.currentTarget.style.outline = "none"; }}
              >
                <span style={{ fontSize: 14, width: 18, textAlign: "center", flexShrink: 0 }} aria-hidden="true">{item.icon}</span>
                <span style={{ lineHeight: 1.3, flex: 1 }}>{item.label}</span>
                {item.badge && (
                  <span style={{ background: item.id === "대시보드" ? "var(--crit-accent)" : "var(--warn-accent)", color: "white", borderRadius: 8, padding: "0 5px", fontSize: 10, fontWeight: 700, flexShrink: 0 }}>
                    {item.badge}
                  </span>
                )}
              </button>
            ))}
          </div>

          {/* Safety badge */}
          <div style={{ padding: "10px 12px", borderTop: "1px solid rgba(255,255,255,0.08)" }}>
            <div style={{ background: "rgba(255,255,255,0.06)", borderRadius: "var(--radius)", padding: "8px 10px" }}>
              <div style={{ fontSize: 10, color: "rgba(255,255,255,0.5)", fontWeight: 700, marginBottom: 2 }}>🛡 안전 원칙</div>
              <div style={{ fontSize: 10, color: "rgba(255,255,255,0.35)", lineHeight: 1.6 }}>환불·취소·가격변경 자동 없음</div>
              <div style={{ fontSize: 10, color: "rgba(255,255,255,0.35)", lineHeight: 1.6 }}>모든 조치 담당자 직접 실행</div>
            </div>
          </div>
        </nav>

        {/* Main area */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", background: "var(--bg)" }}>
          {/* Top header */}
          <header style={{ background: "var(--surface)", borderBottom: "1px solid var(--border)", padding: "0 24px", height: 48, display: "flex", alignItems: "center", gap: 14, flexShrink: 0 }}>
            <h1 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: "var(--text-primary)" }}>{pageTitles[page]}</h1>

            {/* Provider health pills */}
            <div style={{ display: "flex", gap: 5, marginLeft: 12 }} role="status" aria-label="연동 상태">
              {[
                { name: "Cafe24", ok: true },
                { name: "Toss POS", ok: true },
                { name: "eCount", ok: false, note: "지연" },
              ].map(p => (
                <div
                  key={p.name}
                  title={p.ok ? `${p.name}: 정상` : `${p.name}: ${p.note}`}
                  style={{ display: "flex", alignItems: "center", gap: 4, padding: "2px 8px", background: "var(--surface-2)", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", fontSize: 11, color: p.ok ? "var(--human-text)" : "var(--warn-text)" }}
                >
                  <span aria-hidden="true" style={{ width: 5, height: 5, borderRadius: "50%", background: p.ok ? "var(--human-accent)" : "var(--warn-accent)", display: "inline-block" }} />
                  {p.name}
                  {!p.ok && <span style={{ fontSize: 9, fontWeight: 700 }}>({p.note})</span>}
                </div>
              ))}
            </div>

            {/* Right */}
            <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 16 }}>
              <time style={{ fontSize: 11, color: "var(--text-tertiary)", fontFamily: "var(--font-mono)" }}>
                2024-09-04 (수) 11:42 KST
              </time>
              <div
                role="img"
                aria-label="로그인 사용자: 운영 담당자"
                style={{ width: 28, height: 28, borderRadius: "50%", background: "var(--rule-accent)", color: "white", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, fontWeight: 700 }}
              >
                운
              </div>
            </div>
          </header>

          {/* Page content */}
          <main style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }} role="main">
            {page === "대시보드" && <Dashboard />}
            {page === "상품·재고" && <Inventory />}
            {page === "주문·매출" && <Orders />}
            {page === "고객문의" && <Inquiry />}
            {page === "운영일정" && <Schedule />}
            {page === "AI인사이트" && <Insights />}
            {page === "연동·설정" && <Settings />}
          </main>
        </div>
      </div>
    </div>
  );
}
