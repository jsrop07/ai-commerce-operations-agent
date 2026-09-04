import React from "react";

// ── Source type badge ───────────────────────────────────────
export function RuleBadge({ label = "규칙" }: { label?: string }) {
  return (
    <span style={{ background: "var(--rule-bg)", color: "var(--rule-text)", border: "1px solid var(--rule-border)", borderRadius: "var(--radius-sm)", padding: "1px 6px", fontSize: 10, fontWeight: 600, letterSpacing: "0.03em", whiteSpace: "nowrap" }}>
      {label}
    </span>
  );
}

export function AIBadge({ label = "AI" }: { label?: string }) {
  return (
    <span style={{ background: "var(--ai-bg)", color: "var(--ai-text)", border: "1px solid var(--ai-border)", borderRadius: "var(--radius-sm)", padding: "1px 6px", fontSize: 10, fontWeight: 600, letterSpacing: "0.03em", whiteSpace: "nowrap" }}>
      {label}
    </span>
  );
}

export function HumanBadge({ label = "담당자" }: { label?: string }) {
  return (
    <span style={{ background: "var(--human-bg)", color: "var(--human-text)", border: "1px solid var(--human-border)", borderRadius: "var(--radius-sm)", padding: "1px 6px", fontSize: 10, fontWeight: 600, letterSpacing: "0.03em", whiteSpace: "nowrap" }}>
      {label}
    </span>
  );
}

// ── Risk severity badge ─────────────────────────────────────
export function RiskBadge({ severity }: { severity: "critical" | "warning" | "ok" }) {
  if (severity === "critical") return (
    <span style={{ background: "var(--crit-bg)", color: "var(--crit-text)", border: "1px solid var(--crit-border)", borderRadius: "var(--radius-sm)", padding: "1px 7px", fontSize: 10, fontWeight: 700, whiteSpace: "nowrap" }}>
      ● 위험
    </span>
  );
  if (severity === "warning") return (
    <span style={{ background: "var(--warn-bg)", color: "var(--warn-text)", border: "1px solid var(--warn-border)", borderRadius: "var(--radius-sm)", padding: "1px 7px", fontSize: 10, fontWeight: 700, whiteSpace: "nowrap" }}>
      ▲ 주의
    </span>
  );
  return (
    <span style={{ background: "var(--human-bg)", color: "var(--human-text)", border: "1px solid var(--human-border)", borderRadius: "var(--radius-sm)", padding: "1px 7px", fontSize: 10, fontWeight: 600, whiteSpace: "nowrap" }}>
      ✓ 정상
    </span>
  );
}

// ── Freshness badge ─────────────────────────────────────────
export function FreshnessBadge({ asOf, stale = false }: { asOf: string; stale?: boolean }) {
  return (
    <span style={{
      background: stale ? "var(--warn-bg)" : "var(--surface-2)",
      color: stale ? "var(--warn-text)" : "var(--text-tertiary)",
      border: `1px solid ${stale ? "var(--warn-border)" : "var(--border)"}`,
      borderRadius: "var(--radius-sm)",
      padding: "1px 6px", fontSize: 10, fontWeight: 500, whiteSpace: "nowrap", fontFamily: "var(--font-mono)"
    }}>
      {stale ? "⚠ " : "⏱ "}{asOf}
    </span>
  );
}

// ── Provider health badge ───────────────────────────────────
export function ProviderBadge({ name, status }: { name: string; status: "ok" | "degraded" | "error" | "stale" }) {
  const cfg = {
    ok: { dot: "#16A34A", bg: "#F0FDF4", border: "#BBF7D0", text: "#15803D" },
    degraded: { dot: "#D97706", bg: "#FFFBEB", border: "#FDE68A", text: "#B45309" },
    error: { dot: "#DC2626", bg: "#FEF2F2", border: "#FECACA", text: "#B91C1C" },
    stale: { dot: "#9CA3AF", bg: "#F5F6F8", border: "#E2E5EA", text: "#6B7280" },
  }[status];
  return (
    <span style={{ background: cfg.bg, color: cfg.text, border: `1px solid ${cfg.border}`, borderRadius: "var(--radius-sm)", padding: "2px 8px", fontSize: 11, fontWeight: 600, display: "inline-flex", alignItems: "center", gap: 4, whiteSpace: "nowrap" }}>
      <span style={{ width: 6, height: 6, borderRadius: "50%", background: cfg.dot, display: "inline-block" }} />
      {name}
    </span>
  );
}

// ── Confidence badge ────────────────────────────────────────
export function ConfidenceBadge({ value }: { value: number }) {
  const color = value >= 90 ? "var(--human-text)" : value >= 75 ? "var(--warn-text)" : "var(--crit-text)";
  const bg = value >= 90 ? "var(--human-bg)" : value >= 75 ? "var(--warn-bg)" : "var(--crit-bg)";
  const border = value >= 90 ? "var(--human-border)" : value >= 75 ? "var(--warn-border)" : "var(--crit-border)";
  return (
    <span style={{ background: bg, color, border: `1px solid ${border}`, borderRadius: "var(--radius-sm)", padding: "1px 6px", fontSize: 10, fontWeight: 600, fontFamily: "var(--font-mono)", whiteSpace: "nowrap" }}>
      신뢰도 {value}%
    </span>
  );
}

// ── Status badge for orders/schedule ───────────────────────
export function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { bg: string; color: string; border: string }> = {
    "완료": { bg: "#F0FDF4", color: "#15803D", border: "#BBF7D0" },
    "준비중": { bg: "#EFF6FF", color: "#1D4ED8", border: "#BFDBFE" },
    "배송중": { bg: "#F5F3FF", color: "#6D28D9", border: "#DDD6FE" },
    "취소": { bg: "#F5F6F8", color: "#6B7280", border: "#E2E5EA" },
    "보류": { bg: "#FFFBEB", color: "#B45309", border: "#FDE68A" },
    "예정": { bg: "#F5F6F8", color: "#4B5563", border: "#E2E5EA" },
    "진행중": { bg: "#EFF6FF", color: "#1D4ED8", border: "#BFDBFE" },
    "지연": { bg: "#FEF2F2", color: "#B91C1C", border: "#FECACA" },
    "대기": { bg: "#F5F6F8", color: "#6B7280", border: "#E2E5EA" },
    "초안완료": { bg: "#F5F3FF", color: "#6D28D9", border: "#DDD6FE" },
    "검토중": { bg: "#FFFBEB", color: "#B45309", border: "#FDE68A" },
    "발송완료": { bg: "#F0FDF4", color: "#15803D", border: "#BBF7D0" },
  };
  const cfg = map[status] || { bg: "#F5F6F8", color: "#4B5563", border: "#E2E5EA" };
  return (
    <span style={{ background: cfg.bg, color: cfg.color, border: `1px solid ${cfg.border}`, borderRadius: "var(--radius-sm)", padding: "1px 7px", fontSize: 11, fontWeight: 600, whiteSpace: "nowrap" }}>
      {status}
    </span>
  );
}

// ── Source chip ─────────────────────────────────────────────
export function SourceChip({ source }: { source: string }) {
  const colors: Record<string, { bg: string; text: string }> = {
    "Cafe24": { bg: "#EFF6FF", text: "#1D4ED8" },
    "Toss POS": { bg: "#F5F3FF", text: "#6D28D9" },
    "eCount": { bg: "#ECFDF5", text: "#065F46" },
  };
  const cfg = colors[source] || { bg: "#F5F6F8", text: "#4B5563" };
  return (
    <span style={{ background: cfg.bg, color: cfg.text, borderRadius: "var(--radius-sm)", padding: "1px 6px", fontSize: 10, fontWeight: 600 }}>
      {source}
    </span>
  );
}
