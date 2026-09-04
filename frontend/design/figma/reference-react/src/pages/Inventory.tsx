import React, { useState } from "react";
import { products, mappingCandidates, MappingCandidate, ProductRow } from "../data/mockData";
import { RiskBadge, SourceChip, FreshnessBadge, AIBadge, HumanBadge } from "../components/Badges";
import { StaleDataBanner, AmbiguousMappingBadge } from "../components/UIStates";
import WorkCreationModal, { WorkItem } from "../components/WorkCreationModal";

export default function Inventory() {
  const [tab, setTab] = useState<"재고현황" | "상품연결">("재고현황");
  const [mappings, setMappings] = useState(mappingCandidates);
  const [filter, setFilter] = useState<"전체" | "위험" | "주의" | "정상">("전체");
  const [selectedProduct, setSelectedProduct] = useState<ProductRow | null>(null);

  const filtered = products.filter(p => {
    if (filter === "전체") return true;
    if (filter === "위험") return p.status === "crit";
    if (filter === "주의") return p.status === "warn";
    if (filter === "정상") return p.status === "ok";
    return true;
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Tabs */}
      <div style={{ padding: "0 24px", borderBottom: "1px solid var(--border)", background: "var(--surface)", display: "flex" }}>
        {(["재고현황", "상품연결"] as const).map(t => (
          <button key={t} onClick={() => setTab(t)} style={{ background: "none", border: "none", cursor: "pointer", padding: "14px 20px", fontSize: 13, fontWeight: tab === t ? 700 : 400, color: tab === t ? "var(--rule-accent)" : "var(--text-secondary)", borderBottom: tab === t ? "2px solid var(--rule-accent)" : "2px solid transparent", marginBottom: -1 }}>
            {t}
            {t === "상품연결" && (
              <span style={{ marginLeft: 6, background: "var(--warn-bg)", color: "var(--warn-text)", border: "1px solid var(--warn-border)", borderRadius: "var(--radius-sm)", padding: "0 5px", fontSize: 10, fontWeight: 700 }}>
                {mappings.filter(m => m.status === "미검토").length}
              </span>
            )}
          </button>
        ))}
      </div>

      {tab === "재고현황" && (
        <div style={{ flex: 1, overflow: "hidden", display: "flex" }}>
          {/* Main table area */}
          <div style={{ flex: 1, overflow: "auto", padding: "16px 24px" }}>
            {/* Filters */}
            <div style={{ display: "flex", gap: 8, marginBottom: 12, alignItems: "center" }}>
              {(["전체", "위험", "주의", "정상"] as const).map(f => (
                <button key={f} onClick={() => setFilter(f)} style={{ background: filter === f ? "var(--rule-accent)" : "var(--surface)", color: filter === f ? "white" : "var(--text-secondary)", border: `1px solid ${filter === f ? "var(--rule-accent)" : "var(--border)"}`, borderRadius: "var(--radius)", padding: "5px 12px", fontSize: 12, fontWeight: 500, cursor: "pointer" }}>
                  {f}
                </button>
              ))}
              <span style={{ marginLeft: "auto", fontSize: 11, color: "var(--text-tertiary)" }}>행을 클릭하면 상세 재고 현황을 볼 수 있습니다</span>
            </div>

            <StaleDataBanner source="eCount" lastUpdated="47분 전" message="재고 수치가 현재 실제와 다를 수 있습니다. 중요 의사결정 전 직접 확인하세요." />

            <div style={{ height: 12 }} />

            <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-lg)", overflow: "hidden" }}>
              <div style={{ overflowX: "auto" }}>
                <table className="dense-table">
                  <thead>
                    <tr>
                      <th>상품명</th>
                      <th>SKU</th>
                      <th style={{ textAlign: "right" }}>Cafe24 재고</th>
                      <th style={{ textAlign: "right" }}>eCount 재고</th>
                      <th style={{ textAlign: "right" }}>차이</th>
                      <th style={{ textAlign: "right" }}>입고 예정</th>
                      <th>입고 예정일</th>
                      <th>상태</th>
                      <th>최종 갱신</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map(p => {
                      const diffColor = p.diff < -5 ? "var(--crit-text)" : p.diff < 0 ? "var(--warn-text)" : "var(--human-text)";
                      const isSelected = selectedProduct?.id === p.id;
                      return (
                        <tr
                          key={p.id}
                          onClick={() => setSelectedProduct(isSelected ? null : p)}
                          style={{ cursor: "pointer", background: isSelected ? "var(--rule-bg)" : undefined, outline: isSelected ? "2px solid var(--rule-accent)" : undefined, outlineOffset: -2 }}
                        >
                          <td style={{ fontWeight: 600, color: isSelected ? "var(--rule-text)" : "var(--text-primary)" }}>{p.name}</td>
                          <td style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-secondary)" }}>{p.sku}</td>
                          <td style={{ textAlign: "right" }}>
                            <div style={{ display: "flex", alignItems: "center", gap: 4, justifyContent: "flex-end" }}>
                              <SourceChip source="Cafe24" />
                              <span style={{ fontWeight: 600, fontFamily: "var(--font-mono)" }}>{p.cafe24Stock}</span>
                            </div>
                          </td>
                          <td style={{ textAlign: "right" }}>
                            <div style={{ display: "flex", alignItems: "center", gap: 4, justifyContent: "flex-end" }}>
                              <SourceChip source="eCount" />
                              <span style={{ fontWeight: 600, fontFamily: "var(--font-mono)" }}>{p.ecountStock}</span>
                            </div>
                          </td>
                          <td style={{ textAlign: "right", fontWeight: 700, color: diffColor, fontFamily: "var(--font-mono)" }}>
                            {p.diff > 0 ? "+" : ""}{p.diff}
                          </td>
                          <td style={{ textAlign: "right", fontFamily: "var(--font-mono)" }}>{p.incoming > 0 ? p.incoming : "—"}</td>
                          <td style={{ color: p.incomingDate ? "var(--rule-text)" : "var(--text-tertiary)", fontSize: 11 }}>{p.incomingDate || "—"}</td>
                          <td><RiskBadge severity={p.status === "crit" ? "critical" : p.status === "warn" ? "warning" : "ok"} /></td>
                          <td><FreshnessBadge asOf={p.lastUpdated} stale={p.lastUpdated.includes("시간") || p.lastUpdated === "47분 전"} /></td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
            <p style={{ fontSize: 10, color: "var(--text-tertiary)", marginTop: 8 }}>
              ※ 최종 필드명은 OpenAPI/JSON Schema 계약에서 확정됩니다 · 이 화면의 레이블은 시맨틱 식별자입니다
            </p>
          </div>

          {/* Right: Product detail panel */}
          {selectedProduct && (
            <ProductDetailPanel
              product={selectedProduct}
              onClose={() => setSelectedProduct(null)}
            />
          )}
        </div>
      )}

      {tab === "상품연결" && (
        <MappingReview mappings={mappings} setMappings={setMappings} />
      )}
    </div>
  );
}

function ProductDetailPanel({ product, onClose }: { product: ProductRow; onClose: () => void }) {
  const [showWorkModal, setShowWorkModal] = useState(false);
  const [workCreated, setWorkCreated] = useState(false);
  const tosPosEstimate = -2;
  const reservation = 4;
  const availableEstimate = product.ecountStock + (product.incoming || 0) + tosPosEstimate;

  return (
    <div style={{ width: 340, borderLeft: "1px solid var(--border)", background: "var(--surface)", display: "flex", flexDirection: "column", flexShrink: 0 }}>
      {/* Header */}
      <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--border)", background: "var(--surface-2)", flexShrink: 0, display: "flex", alignItems: "flex-start", gap: 8 }}>
        <div style={{ flex: 1 }}>
          <RiskBadge severity={product.status === "crit" ? "critical" : product.status === "warn" ? "warning" : "ok"} />
          <div style={{ fontSize: 13, fontWeight: 700, marginTop: 4, lineHeight: 1.3 }}>{product.name}</div>
          <div style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--text-tertiary)", marginTop: 2 }}>{product.sku}</div>
        </div>
        <button onClick={onClose} aria-label="닫기" style={{ background: "none", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", padding: "4px 8px", fontSize: 12, cursor: "pointer", color: "var(--text-secondary)", flexShrink: 0 }}>✕</button>
      </div>

      {/* Scrollable content */}
      <div style={{ flex: 1, overflowY: "auto", padding: "14px 16px", display: "flex", flexDirection: "column", gap: 14 }}>

        {/* 현재 재고 비교 */}
        <section>
          <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-secondary)", marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.04em" }}>현재 재고 비교</div>
          <div style={{ border: "1px solid var(--border)", borderRadius: "var(--radius)", overflow: "hidden" }}>
            {[
              { label: "Cafe24 재고", value: `${product.cafe24Stock}개`, source: "Cafe24", warn: false },
              { label: "eCount 재고", value: `${product.ecountStock}개`, source: "eCount", warn: product.ecountStock < product.cafe24Stock },
              { label: "Toss POS 판매 반영", value: `${tosPosEstimate}개 (반영 지연 가능)`, source: "Toss POS", warn: true },
              { label: "예약 수량", value: `${reservation}개`, source: "Cafe24", warn: false },
              ...(product.incoming > 0 ? [{ label: "확정 입고 수량", value: `${product.incoming}개`, source: "eCount", warn: false }] : []),
              ...(product.incomingDate ? [{ label: "확정 입고 예정일", value: product.incomingDate, source: "eCount", warn: false }] : []),
            ].map((row, i, arr) => (
              <div key={row.label} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 12px", background: row.warn ? "var(--warn-bg)" : "var(--surface)", borderBottom: i < arr.length - 1 ? "1px solid var(--border)" : "none", fontSize: 12 }}>
                <div>
                  <span style={{ color: "var(--text-secondary)" }}>{row.label}</span>
                  <SourceChip source={row.source} />
                </div>
                <span style={{ fontFamily: "var(--font-mono)", fontWeight: 600, color: row.warn ? "var(--warn-text)" : "var(--text-primary)" }}>{row.value}</span>
              </div>
            ))}

            {/* Divider */}
            <div style={{ height: 1, background: "var(--border-strong)" }} />

            {/* Summary rows */}
            <div style={{ display: "flex", justifyContent: "space-between", padding: "8px 12px", background: "var(--surface-2)", fontSize: 12 }}>
              <span style={{ fontWeight: 700 }}>예상 가용재고</span>
              <span style={{ fontFamily: "var(--font-mono)", fontWeight: 700, color: availableEstimate <= 0 ? "var(--crit-text)" : "var(--text-primary)" }}>{availableEstimate}개</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", padding: "8px 12px", background: product.diff !== 0 ? "var(--warn-bg)" : "var(--surface-2)", borderTop: "1px solid var(--border)", fontSize: 12 }}>
              <span style={{ fontWeight: 700 }}>시스템 간 차이</span>
              <span style={{ fontFamily: "var(--font-mono)", fontWeight: 700, color: product.diff !== 0 ? "var(--warn-text)" : "var(--human-text)" }}>{Math.abs(product.diff)}개</span>
            </div>
          </div>
        </section>

        {/* 데이터 갱신 시각 */}
        <section>
          <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-secondary)", marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.04em" }}>데이터 갱신 시각</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {[
              { label: "Cafe24", asOf: "3분 전", stale: false },
              { label: "eCount", asOf: "47분 전", stale: true },
              { label: "Toss POS", asOf: "5분 전", stale: false },
            ].map(r => (
              <div key={r.label} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 12 }}>
                <span style={{ color: "var(--text-secondary)" }}>{r.label}</span>
                <FreshnessBadge asOf={r.asOf} stale={r.stale} />
              </div>
            ))}
          </div>
        </section>

        {/* 차이 발생 원인 */}
        {product.diff !== 0 && (
          <section>
            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-secondary)", marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.04em" }}>차이 발생 가능한 이유</div>
            <div style={{ background: "var(--ai-bg)", border: "1px solid var(--ai-border)", borderRadius: "var(--radius)", padding: "10px 12px", fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.7 }}>
              <AIBadge label="AI 분석" />
              <p style={{ margin: "6px 0 0" }}>
                Toss POS 판매 일부가 eCount에 아직 반영되지 않았거나, eCount 데이터(47분 전 기준)가 오래되어 실제 재고와 차이가 생겼을 수 있습니다. 정확한 확인을 위해 eCount를 직접 조회하세요.
              </p>
            </div>
          </section>
        )}

        {/* 관련 위험 */}
        {product.status !== "ok" && (
          <section>
            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-secondary)", marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.04em" }}>관련 위험</div>
            <div style={{ background: product.status === "crit" ? "var(--crit-bg)" : "var(--warn-bg)", border: `1px solid ${product.status === "crit" ? "var(--crit-border)" : "var(--warn-border)"}`, borderRadius: "var(--radius)", padding: "10px 12px", fontSize: 12 }}>
              <div style={{ fontWeight: 700, color: product.status === "crit" ? "var(--crit-text)" : "var(--warn-text)", marginBottom: 4 }}>
                {product.status === "crit" ? "🔴 즉시 확인 필요" : "🟡 주의 필요"}
              </div>
              <div style={{ color: "var(--text-secondary)", lineHeight: 1.5 }}>
                {product.status === "crit" ? "재고 부족으로 과판매가 발생할 수 있습니다. 즉시 재고를 확인하고 판매 수량을 조정하세요." : "재고 수량 차이가 있습니다. 확인 후 필요시 조정하세요."}
              </div>
            </div>
          </section>
        )}
      </div>

      {/* Fixed bottom action */}
      <div style={{ padding: "12px 16px", borderTop: "1px solid var(--border)", flexShrink: 0 }}>
        {workCreated ? (
          <div style={{ background: "var(--human-bg)", border: "1px solid var(--human-border)", borderRadius: "var(--radius)", padding: "8px 12px", fontSize: 12, color: "var(--human-text)", fontWeight: 600 }}>
            ✅ 업무가 생성되었습니다 · 외부 시스템 변경 없음
          </div>
        ) : (
          <button
            onClick={() => setShowWorkModal(true)}
            style={{ width: "100%", background: "var(--rule-accent)", color: "white", border: "none", borderRadius: "var(--radius)", padding: "10px", fontSize: 13, fontWeight: 600, cursor: "pointer" }}
          >
            📋 확인 업무 만들기
          </button>
        )}
        <p style={{ fontSize: 10, color: "var(--text-tertiary)", margin: "6px 0 0", textAlign: "center" }}>
          재고 자동 수정 없음 · 담당자 직접 확인 및 실행
        </p>
      </div>

      {showWorkModal && (
        <WorkCreationModal
          initialData={{
            title: `재고 차이 확인 — ${product.name}`,
            summary: `Cafe24 재고(${product.cafe24Stock}개)와 eCount 재고(${product.ecountStock}개) 간 ${Math.abs(product.diff)}개 차이 발생.`,
            cause: "eCount 데이터 지연 또는 Toss POS 판매 미반영 가능성",
            relatedProduct: `${product.name} (${product.sku})`,
            priority: product.status === "crit" ? "높음" : "보통",
            deadline: new Date().toISOString().slice(0, 10),
          }}
          onClose={() => setShowWorkModal(false)}
          onSubmit={() => { setWorkCreated(true); setShowWorkModal(false); }}
        />
      )}
    </div>
  );
}

function MappingReview({ mappings, setMappings }: { mappings: MappingCandidate[]; setMappings: React.Dispatch<React.SetStateAction<MappingCandidate[]>> }) {
  const [toast, setToast] = useState<string | null>(null);

  const approve = (id: string, candidateCode: string) => {
    setMappings(prev => prev.map(m => m.id === id ? { ...m, status: "승인" } : m));
    setToast(`상품 연결 승인 완료: ${candidateCode}`);
    setTimeout(() => setToast(null), 2500);
  };

  const reject = (id: string) => {
    setMappings(prev => prev.map(m => m.id === id ? { ...m, status: "거부" } : m));
  };

  // Operator-friendly matching reason labels (replaces BM25)
  const friendlyReason = (similarity: number): string => {
    if (similarity >= 85) return "이름이 매우 유사함";
    if (similarity >= 75) return "이름이 유사함";
    if (similarity >= 65) return "옵션 일부 일치";
    return "상품코드 불일치 · 추가 확인 필요";
  };

  return (
    <div style={{ flex: 1, overflow: "auto", padding: "20px 24px" }}>
      <div style={{ background: "var(--warn-bg)", border: "1px solid var(--warn-border)", borderRadius: "var(--radius)", padding: "12px 16px", marginBottom: 20 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
          <AmbiguousMappingBadge />
          <span style={{ fontSize: 13, fontWeight: 700 }}>상품 연결 확인 필요</span>
        </div>
        <p style={{ fontSize: 12, color: "var(--text-secondary)", margin: 0, lineHeight: 1.5 }}>
          아래 Cafe24 신규 상품이 eCount 품목과 자동으로 연결되지 않았습니다. 올바른 항목을 직접 선택해 주세요. 재고 집계가 정확하지 않을 수 있습니다.
        </p>
        <p style={{ fontSize: 11, color: "var(--text-tertiary)", margin: "6px 0 0" }}>
          선택 후 승인해야 연결이 적용됩니다. 자동 연결이 실행되지 않습니다.
        </p>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        {mappings.map(m => (
          <MappingRow key={m.id} m={m} onApprove={approve} onReject={reject} friendlyReason={friendlyReason} />
        ))}
      </div>

      {toast && (
        <div className="toast-container">
          <div className="toast">✅ {toast}</div>
        </div>
      )}
    </div>
  );
}

function MappingRow({ m, onApprove, onReject, friendlyReason }: {
  m: MappingCandidate;
  onApprove: (id: string, code: string) => void;
  onReject: (id: string) => void;
  friendlyReason: (s: number) => string;
}) {
  const [selected, setSelected] = useState<string | null>(null);
  const isDone = m.status !== "미검토";

  return (
    <div style={{ background: "var(--surface)", border: `1px solid ${isDone ? "var(--border)" : "var(--warn-border)"}`, borderRadius: "var(--radius-lg)", overflow: "hidden", opacity: isDone ? 0.7 : 1 }}>
      <div style={{ padding: "10px 14px", background: "var(--surface-2)", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", gap: 10 }}>
        <SourceChip source="Cafe24" />
        <span style={{ fontSize: 13, fontWeight: 700 }}>{m.cafe24Name}</span>
        <span style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--text-tertiary)" }}>{m.cafe24Sku}</span>
        {!isDone && <AmbiguousMappingBadge />}
        {isDone && (
          <span style={{ marginLeft: "auto", fontWeight: 700, fontSize: 12, color: m.status === "승인" ? "var(--human-text)" : "var(--crit-text)" }}>
            {m.status === "승인" ? "✓ 연결 승인됨" : "✕ 거부"}
          </span>
        )}
      </div>

      {!isDone && (
        <div style={{ padding: "12px 14px" }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-tertiary)", marginBottom: 8, textTransform: "uppercase" }}>eCount 연결 후보</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 14 }}>
            {m.candidates.map(c => (
              <label key={c.ecountCode} style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 12px", border: `1px solid ${selected === c.ecountCode ? "var(--rule-accent)" : "var(--border)"}`, borderRadius: "var(--radius)", cursor: "pointer", background: selected === c.ecountCode ? "var(--rule-bg)" : "var(--surface)" }}>
                <input type="radio" name={m.id} value={c.ecountCode} checked={selected === c.ecountCode} onChange={() => setSelected(c.ecountCode)} style={{ accentColor: "var(--rule-accent)" }} />
                <div style={{ flex: 1 }}>
                  <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 2 }}>
                    <SourceChip source="eCount" />
                    <span style={{ fontSize: 13, fontWeight: 600 }}>{c.ecountName}</span>
                    <span style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--text-tertiary)" }}>{c.ecountCode}</span>
                  </div>
                  <div style={{ fontSize: 11, color: c.similarity >= 80 ? "var(--human-text)" : "var(--warn-text)", fontWeight: 500 }}>
                    {friendlyReason(c.similarity)}
                    {c.similarity < 70 && " · 후보가 2개 있어 확인 필요"}
                  </div>
                </div>
              </label>
            ))}
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button onClick={() => selected && onApprove(m.id, selected)} disabled={!selected} style={{ background: selected ? "var(--human-accent)" : "var(--surface-2)", color: selected ? "white" : "var(--text-tertiary)", border: "none", borderRadius: "var(--radius)", padding: "8px 16px", fontSize: 13, fontWeight: 600, cursor: selected ? "pointer" : "not-allowed" }}>
              선택 연결 승인
            </button>
            <button onClick={() => onReject(m.id)} style={{ background: "none", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: "8px 12px", fontSize: 12, cursor: "pointer", color: "var(--text-secondary)" }}>
              거부 (수동 지정)
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
