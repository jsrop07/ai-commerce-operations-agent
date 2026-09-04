import React, { useState } from "react";
import { RuleBadge, AIBadge } from "./Badges";

export interface WorkItem {
  title: string;
  summary: string;
  cause: string;
  relatedProduct?: string;
  relatedOrder?: string;
  priority: "높음" | "보통" | "낮음";
  assignee: string;
  deadline: string;
  memo: string;
}

interface Props {
  initialData: Partial<WorkItem>;
  onClose: () => void;
  onSubmit: (item: WorkItem) => void;
}

export default function WorkCreationModal({ initialData, onClose, onSubmit }: Props) {
  const [form, setForm] = useState<WorkItem>({
    title: initialData.title ?? "",
    summary: initialData.summary ?? "",
    cause: initialData.cause ?? "",
    relatedProduct: initialData.relatedProduct ?? "",
    relatedOrder: initialData.relatedOrder ?? "",
    priority: initialData.priority ?? "보통",
    assignee: initialData.assignee ?? "",
    deadline: initialData.deadline ?? "",
    memo: initialData.memo ?? "",
  });
  const [submitted, setSubmitted] = useState(false);

  const set = <K extends keyof WorkItem>(k: K, v: WorkItem[K]) =>
    setForm(prev => ({ ...prev, [k]: v }));

  const handleSubmit = () => {
    if (!form.title.trim()) return;
    onSubmit(form);
    setSubmitted(true);
  };

  const priorityColor: Record<string, string> = {
    높음: "var(--crit-text)", 보통: "var(--warn-text)", 낮음: "var(--text-secondary)",
  };

  if (submitted) {
    return (
      <ModalShell onClose={onClose}>
        <div style={{ textAlign: "center", padding: "32px 0" }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>✅</div>
          <div style={{ fontSize: 16, fontWeight: 700, color: "var(--human-text)", marginBottom: 8 }}>
            업무가 생성되었습니다
          </div>
          <div style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.7, maxWidth: 320, margin: "0 auto" }}>
            내부 확인 업무 목록에 추가되었습니다.<br />
            외부 주문·재고·가격·결제는 변경되지 않았습니다.
          </div>
          <button
            onClick={onClose}
            style={{ marginTop: 20, background: "var(--human-accent)", color: "white", border: "none", borderRadius: "var(--radius)", padding: "10px 28px", fontSize: 13, fontWeight: 600, cursor: "pointer" }}
          >
            닫기
          </button>
        </div>
      </ModalShell>
    );
  }

  return (
    <ModalShell onClose={onClose}>
      {/* Header */}
      <div style={{ padding: "18px 24px 14px", borderBottom: "1px solid var(--border)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
          <span style={{ fontSize: 16 }}>📋</span>
          <h2 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: "var(--text-primary)" }}>
            확인 업무 만들기
          </h2>
        </div>
        {/* Safety notice */}
        <div style={{ background: "#FFFBEB", border: "1px solid #FDE68A", borderRadius: "var(--radius)", padding: "7px 12px", display: "flex", gap: 7, alignItems: "flex-start" }}>
          <span style={{ fontSize: 13, flexShrink: 0 }}>🛡</span>
          <span style={{ fontSize: 11, color: "var(--warn-text)", lineHeight: 1.5 }}>
            내부 확인 업무만 생성되며 외부 주문·재고는 변경되지 않습니다.
          </span>
        </div>
      </div>

      {/* Form */}
      <div style={{ padding: "16px 24px", display: "flex", flexDirection: "column", gap: 14, overflowY: "auto", flex: 1 }}>

        {/* 업무 제목 */}
        <Field label="업무 제목" required>
          <input
            value={form.title}
            onChange={e => set("title", e.target.value)}
            placeholder="예: 레드벨벳 케이크 재고 불일치 확인"
            style={inputStyle}
          />
        </Field>

        {/* 발견된 문제 요약 */}
        <Field label="발견된 문제 요약">
          <textarea
            value={form.summary}
            onChange={e => set("summary", e.target.value)}
            placeholder="어떤 문제가 감지됐는지 간략히 적어주세요."
            rows={2}
            style={{ ...inputStyle, resize: "vertical" }}
          />
        </Field>

        {/* 문제 원인 */}
        <Field label="문제 원인">
          <textarea
            value={form.cause}
            onChange={e => set("cause", e.target.value)}
            placeholder="왜 이 문제가 발생했을 가능성이 높은지 기록하세요."
            rows={2}
            style={{ ...inputStyle, resize: "vertical" }}
          />
        </Field>

        {/* 관련 정보 2컬럼 */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <Field label="관련 상품">
            <input
              value={form.relatedProduct}
              onChange={e => set("relatedProduct", e.target.value)}
              placeholder="상품명 또는 SKU"
              style={inputStyle}
            />
          </Field>
          <Field label="관련 주문">
            <input
              value={form.relatedOrder}
              onChange={e => set("relatedOrder", e.target.value)}
              placeholder="주문번호 (선택)"
              style={inputStyle}
            />
          </Field>
        </div>

        {/* 우선순위 / 기한 */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <Field label="우선순위">
            <div style={{ display: "flex", gap: 6 }}>
              {(["높음", "보통", "낮음"] as const).map(p => (
                <button
                  key={p}
                  type="button"
                  onClick={() => set("priority", p)}
                  style={{
                    flex: 1, padding: "6px 0", fontSize: 12, fontWeight: form.priority === p ? 700 : 400,
                    border: `1px solid ${form.priority === p ? "var(--rule-accent)" : "var(--border)"}`,
                    borderRadius: "var(--radius-sm)",
                    background: form.priority === p ? "var(--rule-bg)" : "var(--surface)",
                    color: form.priority === p ? priorityColor[p] : "var(--text-secondary)",
                    cursor: "pointer",
                  }}
                >
                  {p}
                </button>
              ))}
            </div>
          </Field>
          <Field label="기한">
            <input
              type="date"
              value={form.deadline}
              onChange={e => set("deadline", e.target.value)}
              style={inputStyle}
            />
          </Field>
        </div>

        {/* 담당자 */}
        <Field label="담당자">
          <input
            value={form.assignee}
            onChange={e => set("assignee", e.target.value)}
            placeholder="담당자 이름 (선택)"
            style={inputStyle}
          />
        </Field>

        {/* 메모 */}
        <Field label="메모">
          <textarea
            value={form.memo}
            onChange={e => set("memo", e.target.value)}
            placeholder="추가로 기록할 내용이 있으면 입력하세요."
            rows={3}
            style={{ ...inputStyle, resize: "vertical" }}
          />
        </Field>
      </div>

      {/* Footer actions */}
      <div style={{ padding: "14px 24px", borderTop: "1px solid var(--border)", display: "flex", gap: 10 }}>
        <button
          onClick={handleSubmit}
          disabled={!form.title.trim()}
          style={{
            flex: 1, background: form.title.trim() ? "var(--human-accent)" : "var(--surface-2)",
            color: form.title.trim() ? "white" : "var(--text-tertiary)",
            border: "none", borderRadius: "var(--radius)", padding: "11px", fontSize: 14,
            fontWeight: 700, cursor: form.title.trim() ? "pointer" : "not-allowed",
            transition: "background 0.15s",
          }}
        >
          업무 생성
        </button>
        <button
          onClick={onClose}
          style={{ background: "none", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: "11px 20px", fontSize: 13, cursor: "pointer", color: "var(--text-secondary)" }}
        >
          취소
        </button>
      </div>
    </ModalShell>
  );
}

// ── Helpers ──────────────────────────────────────────────────
function ModalShell({ children, onClose }: { children: React.ReactNode; onClose: () => void }) {
  return (
    <>
      <div
        style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", zIndex: 60 }}
        onClick={onClose}
        aria-hidden
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label="확인 업무 만들기"
        style={{
          position: "fixed", top: "50%", left: "50%",
          transform: "translate(-50%, -50%)",
          background: "var(--surface)", borderRadius: "var(--radius-lg)",
          width: 560, maxWidth: "calc(100vw - 48px)",
          maxHeight: "calc(100vh - 80px)",
          display: "flex", flexDirection: "column",
          boxShadow: "0 12px 48px rgba(0,0,0,0.18)",
          zIndex: 70,
          overflow: "hidden",
        }}
        onClick={e => e.stopPropagation()}
      >
        {children}
      </div>
    </>
  );
}

function Field({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <div>
      <label style={{ display: "block", fontSize: 11, fontWeight: 700, color: "var(--text-secondary)", marginBottom: 5, letterSpacing: "0.03em" }}>
        {label}{required && <span style={{ color: "var(--crit-text)", marginLeft: 3 }}>*</span>}
      </label>
      {children}
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  width: "100%",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius-sm)",
  padding: "7px 10px",
  fontSize: 13,
  fontFamily: "var(--font-sans)",
  color: "var(--text-primary)",
  background: "var(--surface)",
  outline: "none",
  boxSizing: "border-box",
};
