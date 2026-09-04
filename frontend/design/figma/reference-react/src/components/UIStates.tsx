import React from "react";
import { AIBadge, RuleBadge, ProviderBadge } from "./Badges";

// ── 1. 로딩 ─────────────────────────────────────────────────
export function LoadingSkeleton({ rows = 4, cols = 5 }: { rows?: number; cols?: number }) {
  return (
    <div style={{ padding: "16px", display: "flex", flexDirection: "column", gap: 8 }}>
      {/* Table header skeleton */}
      <div style={{ display: "flex", gap: 8, marginBottom: 4 }}>
        {Array.from({ length: cols }).map((_, i) => (
          <div key={i} className="skeleton" style={{ height: 20, flex: i === 0 ? 2 : 1, borderRadius: "var(--radius-sm)" }} />
        ))}
      </div>
      {/* Table rows skeleton */}
      {Array.from({ length: rows }).map((_, ri) => (
        <div key={ri} style={{ display: "flex", gap: 8 }}>
          {Array.from({ length: cols }).map((_, ci) => (
            <div key={ci} className="skeleton" style={{ height: 32, flex: ci === 0 ? 2 : 1, borderRadius: "var(--radius-sm)", opacity: 1 - ri * 0.15 }} />
          ))}
        </div>
      ))}
      <p style={{ fontSize: 11, color: "var(--text-tertiary)", marginTop: 4, textAlign: "center" }}>데이터 불러오는 중...</p>
    </div>
  );
}

export function LoadingCard() {
  return (
    <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-lg)", padding: "16px", display: "flex", flexDirection: "column", gap: 10 }}>
      <div className="skeleton" style={{ height: 14, width: "40%", borderRadius: "var(--radius-sm)" }} />
      <div className="skeleton" style={{ height: 32, width: "60%", borderRadius: "var(--radius-sm)" }} />
      <div className="skeleton" style={{ height: 10, width: "80%", borderRadius: "var(--radius-sm)" }} />
    </div>
  );
}

// ── 2. 빈 상태 ───────────────────────────────────────────────
export function EmptyState({
  icon = "📭",
  title,
  description,
  action,
  onAction,
}: {
  icon?: string;
  title: string;
  description: string;
  action?: string;
  onAction?: () => void;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "48px 24px", gap: 12, textAlign: "center" }}>
      <span style={{ fontSize: 36 }}>{icon}</span>
      <p style={{ fontSize: 15, fontWeight: 700, color: "var(--text-primary)", margin: 0 }}>{title}</p>
      <p style={{ fontSize: 13, color: "var(--text-secondary)", margin: 0, lineHeight: 1.6, maxWidth: 320 }}>{description}</p>
      {action && onAction && (
        <button
          onClick={onAction}
          style={{ marginTop: 8, background: "var(--rule-accent)", color: "white", border: "none", borderRadius: "var(--radius)", padding: "8px 20px", fontSize: 13, fontWeight: 600, cursor: "pointer" }}
        >
          {action}
        </button>
      )}
    </div>
  );
}

// ── 3. 데이터 지연(Stale) ────────────────────────────────────
export function StaleDataBanner({
  source,
  lastUpdated,
  message,
}: {
  source: string;
  lastUpdated: string;
  message?: string;
}) {
  return (
    <div style={{ background: "var(--warn-bg)", border: "1px solid var(--warn-border)", borderRadius: "var(--radius)", padding: "10px 14px", display: "flex", gap: 10, alignItems: "flex-start" }}>
      <span style={{ fontSize: 16, flexShrink: 0 }}>⚠</span>
      <div>
        <div style={{ fontSize: 12, fontWeight: 700, color: "var(--warn-text)", marginBottom: 2 }}>
          데이터 지연 · 최신 정보가 아닐 수 있습니다
        </div>
        <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.5 }}>
          소스: <strong>{source}</strong> · 마지막 갱신: <span style={{ fontFamily: "var(--font-mono)" }}>{lastUpdated}</span>
        </div>
        {message && <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginTop: 3 }}>{message}</div>}
        <div style={{ fontSize: 11, color: "var(--warn-text)", marginTop: 4 }}>
          이 데이터를 기반으로 한 위험 판단의 신뢰도가 낮을 수 있습니다. 직접 확인 후 결정하세요.
        </div>
      </div>
    </div>
  );
}

// ── 4. 일부 연동 오류 (Partial Provider Failure) ─────────────
export function PartialFailureBanner({
  failedProviders,
  workingProviders,
}: {
  failedProviders: string[];
  workingProviders: string[];
}) {
  return (
    <div style={{ background: "var(--warn-bg)", border: "1px solid var(--warn-border)", borderRadius: "var(--radius)", padding: "12px 14px" }}>
      <div style={{ fontSize: 12, fontWeight: 700, color: "var(--warn-text)", marginBottom: 8 }}>
        ⚠ 일부 연동 오류
      </div>
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginBottom: 8 }}>
        <div>
          <div style={{ fontSize: 10, fontWeight: 600, color: "var(--text-tertiary)", marginBottom: 4 }}>오류 중인 연동</div>
          <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
            {failedProviders.map(p => <ProviderBadge key={p} name={p} status="error" />)}
          </div>
        </div>
        <div>
          <div style={{ fontSize: 10, fontWeight: 600, color: "var(--text-tertiary)", marginBottom: 4 }}>정상 연동</div>
          <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
            {workingProviders.map(p => <ProviderBadge key={p} name={p} status="ok" />)}
          </div>
        </div>
      </div>
      <div style={{ fontSize: 11, color: "var(--text-secondary)", lineHeight: 1.5 }}>
        {workingProviders.join(", ")} 데이터는 정상 표시됩니다. {failedProviders.join(", ")} 관련 수치는 오류로 인해 표시되지 않습니다. 전체 시스템 오류가 아닙니다.
      </div>
    </div>
  );
}

// ── 5. 차단됨 (Denied) ──────────────────────────────────────
export function DeniedState({
  action,
  reason,
  reasonCode,
}: {
  action: string;
  reason: string;
  reasonCode?: string;
}) {
  return (
    <div style={{ background: "var(--crit-bg)", border: "1px solid var(--crit-border)", borderRadius: "var(--radius)", padding: "12px 14px", display: "flex", gap: 10 }}>
      <span style={{ fontSize: 16, flexShrink: 0 }}>🚫</span>
      <div>
        <div style={{ fontSize: 12, fontWeight: 700, color: "var(--crit-text)", marginBottom: 4 }}>
          안전 정책으로 실행 차단됨
        </div>
        <div style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 4 }}>
          <strong>요청:</strong> {action}
        </div>
        <div style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 4 }}>
          <strong>사유:</strong> {reason}
        </div>
        {reasonCode && (
          <div style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--text-tertiary)" }}>사유 코드: {reasonCode}</div>
        )}
        <div style={{ fontSize: 11, color: "var(--human-text)", marginTop: 6, fontWeight: 600 }}>
          ✓ 외부 연동 시스템에 아무런 변경이 실행되지 않았습니다.
        </div>
      </div>
    </div>
  );
}

// ── 6. 상품 연결 확인 필요 (Ambiguous Mapping) ───────────────
export function AmbiguousMappingBadge() {
  return (
    <span style={{ background: "var(--warn-bg)", color: "var(--warn-text)", border: "1px solid var(--warn-border)", borderRadius: "var(--radius-sm)", padding: "1px 7px", fontSize: 10, fontWeight: 700, whiteSpace: "nowrap" }}>
      🔗 상품 연결 확인 필요
    </span>
  );
}

export function AmbiguousMappingState({ productName }: { productName: string }) {
  return (
    <div style={{ background: "var(--warn-bg)", border: "1px solid var(--warn-border)", borderRadius: "var(--radius)", padding: "10px 14px" }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 6 }}>
        <AmbiguousMappingBadge />
        <span style={{ fontSize: 12, fontWeight: 600 }}>{productName}</span>
      </div>
      <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.5 }}>
        이 상품의 Cafe24 항목이 eCount 품목과 자동으로 연결되지 않았습니다. 후보 2개가 제안됩니다. 담당자가 올바른 항목을 선택해야 재고가 정확하게 집계됩니다.
      </div>
      <div style={{ fontSize: 11, color: "var(--warn-text)", marginTop: 6 }}>
        자동 연결이 적용되지 않습니다. 담당자 선택 후 승인이 필요합니다.
      </div>
    </div>
  );
}

// ── 7. AI 판단 신뢰도 낮음 (Low AI Confidence) ───────────────
export function LowConfidenceBanner({
  confidence,
  context,
}: {
  confidence: number;
  context?: string;
}) {
  return (
    <div style={{ background: "var(--warn-bg)", border: "1px solid var(--warn-border)", borderLeft: "3px solid var(--warn-accent)", borderRadius: "var(--radius)", padding: "10px 14px", display: "flex", gap: 10 }}>
      <span style={{ fontSize: 16, flexShrink: 0 }}>⚠</span>
      <div>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
          <span style={{ fontSize: 12, fontWeight: 700, color: "var(--warn-text)" }}>AI 판단 신뢰도 낮음</span>
          <span style={{ background: "var(--warn-bg)", color: "var(--warn-text)", border: "1px solid var(--warn-border)", borderRadius: "var(--radius-sm)", padding: "1px 6px", fontSize: 10, fontWeight: 700, fontFamily: "var(--font-mono)" }}>{confidence}%</span>
        </div>
        <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.5 }}>
          {context || "AI가 충분한 근거를 찾지 못했습니다."} 담당자가 직접 확인하고 판단해야 합니다.
        </div>
        <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
          <span style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", padding: "3px 8px", fontSize: 11, color: "var(--text-secondary)" }}>
            📋 담당자 검토 필요
          </span>
          <span style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", padding: "3px 8px", fontSize: 11, color: "var(--text-secondary)" }}>
            💬 근거 부족
          </span>
        </div>
      </div>
    </div>
  );
}

// ── 8. 담당자 확인 대기 (Agent Waiting) ─────────────────────
export function AgentWaitingState({
  step,
  checkpoint,
  requiredAction,
}: {
  step: string;
  checkpoint: string;
  requiredAction: string;
}) {
  return (
    <div style={{ background: "var(--ai-bg)", border: "1px solid var(--ai-border)", borderRadius: "var(--radius)", padding: "12px 14px", display: "flex", gap: 10 }}>
      <span style={{ fontSize: 16, flexShrink: 0 }}>⏸</span>
      <div>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
          <span style={{ fontSize: 12, fontWeight: 700, color: "var(--ai-text)" }}>담당자 확인 대기</span>
          <span style={{ background: "var(--ai-bg)", color: "var(--ai-text)", border: "1px solid var(--ai-border)", borderRadius: "var(--radius-sm)", padding: "1px 6px", fontSize: 10, fontWeight: 600 }}>일시 중단</span>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.5 }}>
          <div><strong>현재 단계:</strong> {step}</div>
          <div><strong>확인 지점:</strong> {checkpoint}</div>
          <div><strong>필요 조치:</strong> {requiredAction}</div>
        </div>
        <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginTop: 6 }}>
          ℹ 내부 처리 과정은 표시되지 않습니다. 담당자 승인 또는 검토 후 다음 단계가 진행됩니다.
        </div>
      </div>
    </div>
  );
}
