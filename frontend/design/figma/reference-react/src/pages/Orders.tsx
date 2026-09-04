import React, { useState } from "react";
import { orders, OrderRow } from "../data/mockData";
import { SourceChip, StatusBadge, FreshnessBadge } from "../components/Badges";
import WorkCreationModal, { WorkItem } from "../components/WorkCreationModal";

export default function Orders() {
  const [filterSource, setFilterSource] = useState<"전체" | "Cafe24" | "Toss POS">("전체");
  const [filterStatus, setFilterStatus] = useState("전체");
  const [selectedOrder, setSelectedOrder] = useState<OrderRow | null>(null);

  const statuses = ["전체", "완료", "준비중", "배송중", "보류", "취소"];
  const filtered = orders.filter(o => {
    const srcOk = filterSource === "전체" || o.source === filterSource;
    const stOk = filterStatus === "전체" || o.status === filterStatus;
    return srcOk && stOk;
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Summary strip */}
      <div style={{ padding: "10px 24px", borderBottom: "1px solid var(--border)", background: "var(--surface)", display: "flex", gap: 16, alignItems: "center" }}>
        {[
          { label: "전체 주문", value: orders.length + "건", color: "var(--text-primary)" },
          { label: "Cafe24", value: orders.filter(o => o.source === "Cafe24").length + "건", color: "var(--rule-text)" },
          { label: "Toss POS", value: orders.filter(o => o.source === "Toss POS").length + "건", color: "var(--ai-text)" },
          { label: "위험 플래그", value: orders.filter(o => o.riskFlag).length + "건", color: "var(--crit-text)" },
        ].map(s => (
          <div key={s.label} style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <span style={{ fontSize: 11, color: "var(--text-tertiary)" }}>{s.label}</span>
            <span style={{ fontSize: 14, fontWeight: 700, color: s.color }}>{s.value}</span>
          </div>
        ))}
        <span style={{ marginLeft: "auto", fontSize: 11, color: "var(--text-tertiary)" }}>소스: Cafe24 + Toss POS · 필드명 API 계약 기준</span>
      </div>

      {/* Filters */}
      <div style={{ padding: "10px 24px", background: "var(--surface)", borderBottom: "1px solid var(--border)", display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <span style={{ fontSize: 11, fontWeight: 600, color: "var(--text-secondary)" }}>소스:</span>
        {(["전체", "Cafe24", "Toss POS"] as const).map(s => (
          <button key={s} onClick={() => setFilterSource(s)} style={{ background: filterSource === s ? "var(--rule-accent)" : "var(--surface-2)", color: filterSource === s ? "white" : "var(--text-secondary)", border: `1px solid ${filterSource === s ? "var(--rule-accent)" : "var(--border)"}`, borderRadius: "var(--radius)", padding: "4px 10px", fontSize: 12, cursor: "pointer" }}>{s}</button>
        ))}
        <span style={{ fontSize: 11, fontWeight: 600, color: "var(--text-secondary)", marginLeft: 8 }}>상태:</span>
        {statuses.map(s => (
          <button key={s} onClick={() => setFilterStatus(s)} style={{ background: filterStatus === s ? "var(--rule-accent)" : "var(--surface-2)", color: filterStatus === s ? "white" : "var(--text-secondary)", border: `1px solid ${filterStatus === s ? "var(--rule-accent)" : "var(--border)"}`, borderRadius: "var(--radius)", padding: "4px 10px", fontSize: 12, cursor: "pointer" }}>{s}</button>
        ))}
        {orders.some(o => o.riskFlag) && (
          <span style={{ fontSize: 11, color: "var(--text-tertiary)", marginLeft: 8 }}>⚑ 위험 플래그 행 클릭 시 상세 설명 확인</span>
        )}
      </div>

      <div style={{ flex: 1, overflow: "hidden", display: "flex" }}>
        {/* Table */}
        <div style={{ flex: 1, overflow: "auto", padding: "16px 24px" }}>
          <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-lg)", overflow: "hidden" }}>
            <div style={{ overflowX: "auto" }}>
              <table className="dense-table">
                <thead>
                  <tr>
                    <th>주문번호</th>
                    <th>소스</th>
                    <th>고객</th>
                    <th>상품</th>
                    <th style={{ textAlign: "right" }}>수량</th>
                    <th style={{ textAlign: "right" }}>금액</th>
                    <th>상태</th>
                    <th>배송 예정일</th>
                    <th>주문 일시</th>
                    <th>위험</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map(o => (
                    <tr
                      key={o.id}
                      onClick={() => setSelectedOrder(selectedOrder?.id === o.id ? null : o)}
                      style={{ cursor: "pointer", background: o.riskFlag ? "var(--crit-bg)" : selectedOrder?.id === o.id ? "var(--rule-bg)" : undefined }}
                    >
                      <td style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--rule-text)" }}>{o.orderId}</td>
                      <td><SourceChip source={o.source} /></td>
                      <td style={{ fontWeight: 500 }}>{o.customer}</td>
                      <td style={{ maxWidth: 180 }}>{o.product}</td>
                      <td style={{ textAlign: "right", fontFamily: "var(--font-mono)" }}>{o.qty}</td>
                      <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", fontWeight: 600 }}>{o.amount}</td>
                      <td><StatusBadge status={o.status} /></td>
                      <td style={{ fontSize: 11, color: "var(--text-secondary)" }}>{o.deliveryDate || "—"}</td>
                      <td><FreshnessBadge asOf={o.orderedAt} stale={false} /></td>
                      <td>
                        {o.riskFlag && (
                          <span style={{ background: "var(--crit-bg)", color: "var(--crit-text)", border: "1px solid var(--crit-border)", borderRadius: "var(--radius-sm)", padding: "1px 6px", fontSize: 10, fontWeight: 700, cursor: "pointer" }}>
                            ⚑ {o.riskFlag}
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {filtered.length === 0 && (
              <div style={{ padding: "40px", textAlign: "center", color: "var(--text-tertiary)", fontSize: 13 }}>해당하는 주문이 없습니다.</div>
            )}
          </div>
        </div>

        {/* Right: stock shortage detail panel */}
        {selectedOrder && selectedOrder.riskFlag && (
          <StockShortagePanel order={selectedOrder} onClose={() => setSelectedOrder(null)} />
        )}
      </div>
    </div>
  );
}

function StockShortagePanel({ order, onClose }: { order: OrderRow; onClose: () => void }) {
  const [showWorkModal, setShowWorkModal] = useState(false);
  const [workCreated, setWorkCreated] = useState(false);
  // Synthetic shortage data per order
  const detail = order.riskFlag === "재고부족" ? {
    ordered: 1, available: 0, reserved: 0, incoming: 6, incomingDate: "9/6",
    shortage: 1, impact: "배송 예정일 9/6 지연 가능성",
    reason: "eCount 실재고 0개. 9/6 입고 예정이나 당일 생산 시간 필요.",
    nextStep: "입고 확인 후 배송 일정 재안내",
  } : {
    ordered: 1, available: 0, reserved: 0, incoming: 15, incomingDate: "9/7",
    shortage: 1, impact: "9/7 픽업 불가 — 재고 없음",
    reason: "말차 라떼 케이크 현재 재고 0개. 9/7 입고 예정이나 픽업 당일과 겹쳐 준비 불가.",
    nextStep: "고객에게 9/8 이후 픽업 안내 초안 작성",
  };

  return (
    <div style={{ width: 320, borderLeft: "1px solid var(--border)", background: "var(--surface)", display: "flex", flexDirection: "column", flexShrink: 0 }}>
      {/* Header */}
      <div style={{ padding: "12px 14px", borderBottom: "1px solid var(--border)", background: "var(--crit-bg)", flexShrink: 0, display: "flex", alignItems: "flex-start", gap: 8 }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: "var(--crit-text)", marginBottom: 4 }}>🔴 재고 부족 상세</div>
          <div style={{ fontSize: 12, fontWeight: 600 }}>{order.product}</div>
          <div style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--text-tertiary)", marginTop: 2 }}>{order.orderId}</div>
        </div>
        <button onClick={onClose} aria-label="닫기" style={{ background: "none", border: "1px solid var(--crit-border)", borderRadius: "var(--radius-sm)", padding: "3px 7px", fontSize: 11, cursor: "pointer", color: "var(--crit-text)" }}>✕</button>
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflowY: "auto", padding: "14px" }}>
        {/* Numbers */}
        <div style={{ border: "1px solid var(--border)", borderRadius: "var(--radius)", overflow: "hidden", marginBottom: 14 }}>
          {[
            { label: "주문 수량", value: `${detail.ordered}개` },
            { label: "현재 확보 재고", value: `${detail.available}개`, warn: true },
            { label: "예약 재고", value: `${detail.reserved}개` },
            { label: "확정 입고", value: `${detail.incoming}개 / ${detail.incomingDate}` },
            { label: "부족 수량", value: `${detail.shortage}개`, warn: true },
          ].map((r, i, arr) => (
            <div key={r.label} style={{ display: "flex", justifyContent: "space-between", padding: "8px 12px", fontSize: 12, background: r.warn ? "var(--crit-bg)" : "var(--surface)", borderBottom: i < arr.length - 1 ? "1px solid var(--border)" : "none" }}>
              <span style={{ color: "var(--text-secondary)" }}>{r.label}</span>
              <span style={{ fontFamily: "var(--font-mono)", fontWeight: 600, color: r.warn ? "var(--crit-text)" : "var(--text-primary)" }}>{r.value}</span>
            </div>
          ))}
        </div>

        {/* Impact */}
        <div style={{ background: "var(--warn-bg)", border: "1px solid var(--warn-border)", borderRadius: "var(--radius)", padding: "10px 12px", marginBottom: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: "var(--warn-text)", marginBottom: 4 }}>예상 배송 영향</div>
          <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>{detail.impact}</div>
        </div>

        {/* Reason */}
        <div style={{ background: "var(--surface-2)", borderRadius: "var(--radius)", padding: "10px 12px", marginBottom: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-secondary)", marginBottom: 4 }}>원인</div>
          <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.6 }}>{detail.reason}</div>
        </div>

        {/* Next step */}
        <div style={{ background: "var(--human-bg)", border: "1px solid var(--human-border)", borderRadius: "var(--radius)", padding: "10px 12px" }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: "var(--human-text)", marginBottom: 4 }}>다음 확인 항목</div>
          <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.5 }}>{detail.nextStep}</div>
        </div>
      </div>

      {/* CTA */}
      <div style={{ padding: "12px 14px", borderTop: "1px solid var(--border)", flexShrink: 0 }}>
        {workCreated ? (
          <div style={{ background: "var(--human-bg)", border: "1px solid var(--human-border)", borderRadius: "var(--radius)", padding: "8px 10px", fontSize: 12, color: "var(--human-text)", fontWeight: 600 }}>
            ✅ 업무 생성됨 · 외부 시스템 변경 없음
          </div>
        ) : (
          <button
            onClick={() => setShowWorkModal(true)}
            style={{ width: "100%", background: "var(--rule-accent)", color: "white", border: "none", borderRadius: "var(--radius)", padding: "9px", fontSize: 12, fontWeight: 600, cursor: "pointer" }}
          >
            📋 확인 업무 만들기
          </button>
        )}
        <p style={{ fontSize: 10, color: "var(--text-tertiary)", margin: "5px 0 0", textAlign: "center" }}>
          재고 자동 수정 없음 · 주문 자동 취소 없음
        </p>
      </div>

      {showWorkModal && (
        <WorkCreationModal
          initialData={{
            title: `재고 부족 확인 — ${order.product}`,
            summary: `주문 ${order.orderId} 재고 부족. ${order.riskFlag === "재고없음" ? "현재 재고 0개." : "확보 재고 부족."}`,
            cause: order.riskFlag === "재고없음" ? "현재 실재고 없음, 입고 일정 확인 필요" : "예약 재고로 인해 가용 재고 부족",
            relatedOrder: order.orderId,
            relatedProduct: order.product,
            priority: "높음",
            deadline: new Date().toISOString().slice(0, 10),
          }}
          onClose={() => setShowWorkModal(false)}
          onSubmit={() => { setWorkCreated(true); setShowWorkModal(false); }}
        />
      )}
    </div>
  );
}
