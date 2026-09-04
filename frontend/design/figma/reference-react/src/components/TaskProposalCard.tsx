import React, { useState } from "react";
import { RiskItem } from "../data/mockData";
import { RiskBadge, AIBadge } from "./Badges";

interface Props {
  item: RiskItem;
  onDismiss: () => void;
  onApprove: (note: string) => void;
}

export default function TaskProposalCard({ item, onDismiss, onApprove }: Props) {
  const [note, setNote] = useState("");
  const [assignee, setAssignee] = useState("");
  const [done, setDone] = useState(false);

  const proposals: Record<string, { title: string; priority: string; deadline: string; reason: string; checklist: string[] }> = {
    "재고불일치": {
      title: "재고 차이 확인 필요",
      priority: "높음",
      deadline: "오늘",
      reason: "Cafe24와 eCount 재고 차이 9개 감지 (eCount 데이터 47분 전 기준)",
      checklist: ["eCount 실재고 직접 확인", "Cafe24 진열수량 조정 여부 결정", "Toss POS 판매 반영 지연 여부 확인"],
    },
    "예약부족": {
      title: "예약 주문 재고 부족 대응",
      priority: "높음",
      deadline: "오늘 (9/7 배송 전)",
      reason: "9/7 예약 주문 24건 중 6건 생산 원자재 부족",
      checklist: ["추가 원자재 긴급 확보 가능 여부 확인", "미충족 6건 고객 안내 초안 작성", "배송 일정 변경 가능 여부 확인"],
    },
    "입고지연": {
      title: "입고 지연 일정 조정 검토",
      priority: "보통",
      deadline: "9/5 오전 전",
      reason: "생크림 입고 9/4 → 9/7로 3일 지연",
      checklist: ["9/5 생산 배치 조정 여부 결정", "영향 주문 3건 배송 안내 검토", "공급사 재확인 및 대체 조달 검토"],
    },
    "문의위험": {
      title: "배송 지연 고객 일괄 안내 준비",
      priority: "보통",
      deadline: "오늘 중",
      reason: "배송 지연 문의 23건 급증 (+340%)",
      checklist: ["물류사 배송 현황 확인", "강남구 지연 원인 파악", "해당 고객 안내 초안 작성 (실제 발송은 담당자 직접)"],
    },
    "매핑모호": {
      title: "상품 연결 확인 필요",
      priority: "보통",
      deadline: "오늘 중",
      reason: "Cafe24 신규 상품 3개 eCount 미연결 — 재고 집계 오류 가능",
      checklist: ["상품 & 재고 > 상품 연결 탭에서 후보 확인", "3건 각각 올바른 항목 선택 또는 수동 지정", "연결 완료 후 재고 수치 재확인"],
    },
  };

  const p = proposals[item.type] || proposals["재고불일치"];

  if (done) {
    return (
      <div style={{ border: "1px solid var(--human-border)", borderRadius: "var(--radius-lg)", background: "var(--human-bg)", padding: "20px", display: "flex", flexDirection: "column", gap: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 18 }}>✅</span>
          <span style={{ fontSize: 14, fontWeight: 700, color: "var(--human-text)" }}>업무가 목록에 추가됨</span>
        </div>
        <p style={{ fontSize: 12, color: "var(--text-secondary)", margin: 0 }}>담당자가 검토 후 직접 실행합니다. 외부 시스템은 자동으로 변경되지 않습니다.</p>
        <button onClick={onDismiss} style={{ alignSelf: "flex-start", background: "none", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: "5px 12px", fontSize: 12, cursor: "pointer", color: "var(--text-secondary)", marginTop: 4 }}>닫기</button>
      </div>
    );
  }

  return (
    <div style={{ border: "1px solid var(--border)", borderRadius: "var(--radius-lg)", background: "var(--surface)", overflow: "hidden", boxShadow: "0 4px 16px rgba(0,0,0,0.08)" }}>
      {/* Header */}
      <div style={{ background: "var(--surface-2)", padding: "10px 16px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ fontSize: 14 }}>📋</span>
        <span style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)" }}>후속 조치 제안</span>
        <RiskBadge severity={item.severity} />
        <button onClick={onDismiss} style={{ marginLeft: "auto", background: "none", border: "none", cursor: "pointer", color: "var(--text-tertiary)", fontSize: 16, lineHeight: 1 }}>✕</button>
      </div>

      <div style={{ padding: "16px" }}>
        {/* Title and details */}
        <div style={{ marginBottom: 14 }}>
          <h3 style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)", margin: "0 0 10px" }}>{p.title}</h3>
          <div style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: "4px 16px", fontSize: 12 }}>
            <span style={{ color: "var(--text-tertiary)" }}>상품</span>
            <span style={{ fontWeight: 500 }}>{item.product || "해당 항목"}</span>
            <span style={{ color: "var(--text-tertiary)" }}>우선순위</span>
            <span style={{ fontWeight: 600, color: p.priority === "높음" ? "var(--crit-text)" : "var(--warn-text)" }}>{p.priority}</span>
            <span style={{ color: "var(--text-tertiary)" }}>기한</span>
            <span style={{ fontWeight: 500 }}>{p.deadline}</span>
            <span style={{ color: "var(--text-tertiary)" }}>이유</span>
            <span style={{ color: "var(--text-secondary)", lineHeight: 1.5 }}>{p.reason}</span>
          </div>
        </div>

        {/* Checklist */}
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 6 }}>확인 항목</div>
          {p.checklist.map((c, i) => (
            <div key={i} style={{ display: "flex", gap: 8, fontSize: 12, color: "var(--text-secondary)", padding: "3px 0", lineHeight: 1.5 }}>
              <span style={{ color: "var(--text-tertiary)", flexShrink: 0 }}>{i + 1}.</span>
              <span>{c}</span>
            </div>
          ))}
        </div>

        {/* Safety notice */}
        <div style={{ background: "#FFFBEB", border: "1px solid #FDE68A", borderRadius: "var(--radius)", padding: "8px 12px", marginBottom: 14, display: "flex", gap: 8 }}>
          <span style={{ fontSize: 13, flexShrink: 0 }}>🛡</span>
          <span style={{ fontSize: 11, color: "var(--warn-text)", lineHeight: 1.6 }}>
            이 제안은 외부 시스템(Cafe24·Toss POS·eCount)을 자동으로 변경하지 않습니다. 담당자가 직접 확인하고 실행해야 합니다.
          </span>
        </div>

        {/* Assignee + note */}
        <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
          <div style={{ flex: 1 }}>
            <label style={{ fontSize: 11, fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>담당자 지정 (선택)</label>
            <input
              value={assignee}
              onChange={e => setAssignee(e.target.value)}
              placeholder="이름 입력..."
              style={{ width: "100%", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", padding: "6px 8px", fontSize: 12, fontFamily: "var(--font-sans)", outline: "none", background: "var(--surface)" }}
            />
          </div>
        </div>
        <div style={{ marginBottom: 14 }}>
          <label style={{ fontSize: 11, fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>메모 (선택)</label>
          <textarea
            value={note}
            onChange={e => setNote(e.target.value)}
            placeholder="추가 메모를 입력하세요..."
            style={{ width: "100%", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", padding: "6px 8px", fontSize: 12, fontFamily: "var(--font-sans)", resize: "vertical", minHeight: 52, outline: "none", background: "var(--surface)", color: "var(--text-primary)" }}
          />
        </div>

        {/* CTAs */}
        <div style={{ display: "flex", gap: 8 }}>
          <button
            onClick={() => { onApprove(note); setDone(true); }}
            style={{ flex: 1, background: "var(--human-accent)", color: "white", border: "none", borderRadius: "var(--radius)", padding: "10px", fontSize: 13, fontWeight: 600, cursor: "pointer" }}
          >
            확인 업무 만들기
          </button>
          <button
            onClick={onDismiss}
            style={{ background: "none", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: "10px 14px", fontSize: 12, cursor: "pointer", color: "var(--text-secondary)" }}
          >
            무시
          </button>
        </div>
      </div>
    </div>
  );
}
