import type {
  InventorySnapshot,
  TaskSummary,
} from "../../types/contracts";
import {
  useEffect,
  useRef,
} from "react";
import FreshnessLabel from "../../components/FreshnessLabel";
import QualityStatus from "../integrations/QualityStatus";

interface InventoryDetailPanelProps {
  item: InventorySnapshot | null;
  open: boolean;
  taskProposals: TaskSummary[];
  onClose: () => void;
}

export default function InventoryDetailPanel({
  item,
  open,
  taskProposals,
  onClose,
}: InventoryDetailPanelProps) {
  const panelRef = useRef<HTMLElement | null>(null);
  const closeButtonRef =
    useRef<HTMLButtonElement | null>(null);
useEffect(() => {
  if (!open) return;

  closeButtonRef.current?.focus();

  function handleKeyDown(event: KeyboardEvent) {
    if (event.key === "Escape") {
      onClose();
    }
  }

  window.addEventListener("keydown", handleKeyDown);

  return () => {
    window.removeEventListener("keydown", handleKeyDown);
  };
}, [open, onClose]);

  if (!open || !item) {
    return null;
  }

    const titleId = "inventory-detail-title";

  return (
    <aside
      id="inventory-detail-panel"
      ref={panelRef}
      className="inventory-detail-panel"
      role="dialog"
      aria-modal="false"
      aria-labelledby={titleId}
      data-testid="inventory-detail-panel"
    >
      <div className="inventory-detail-header">
        <div>
          <div className="muted">
            재고 상세 · {item.provider}
          </div>
          <h2 id={titleId} className="inventory-detail-title">
            {item.sku_id}
          </h2>
        </div>

        <button
          ref={closeButtonRef}
          type="button"
          className="filter"
          aria-label="재고 상세 닫기"
          onClick={onClose}
        >
          닫기
        </button>
      </div>

      <div className="inventory-detail-body">
        <section
          className="inventory-detail-quantity-grid"
          aria-label="재고 수량 요약"
        >
          <div className="inventory-detail-quantity-card">
            <span>현재 수량</span>
            <strong>{item.on_hand}</strong>
          </div>
          <div className="inventory-detail-quantity-card">
            <span>예약 수량</span>
            <strong>{item.reserved}</strong>
          </div>
        </section>

        <section
          className="inventory-detail-status"
          aria-labelledby="inventory-detail-status-title"
        >
          <h3 id="inventory-detail-status-title">
            데이터 상태
          </h3>

          <div className="inventory-detail-status-row">
            <span>최신성</span>
            <FreshnessLabel
              freshness={item.freshness}
              source={item.provider}
              asOf={item.as_of}
              showMetadata={false}
            />
          </div>

          <div className="inventory-detail-status-row">
            <span>기준 시각</span>
            <time dateTime={item.as_of}>
              {item.as_of
                ? new Date(item.as_of).toLocaleString("ko-KR")
                : "미확인"}
            </time>
          </div>

          <div className="inventory-detail-status-row">
            <span>품질 상태</span>
            {item.quality_status ? (
              <QualityStatus
                status={item.quality_status}
                provider={item.provider}
                confirmedForTotal={item.confirmed_for_total}
              />
            ) : (
              <span>미제공</span>
            )}
          </div>
        </section>

        <details className="inventory-detail-disclosure">
          <summary>계산 근거 및 판단 제한</summary>
          <div className="inventory-detail-disclosure-body">
            <div className="inventory-detail-status-row">
              <span>현재 수량</span>
              <strong>{item.on_hand}</strong>
            </div>
            <div className="inventory-detail-status-row">
              <span>예약 수량</span>
              <strong>{item.reserved}</strong>
            </div>
            <div className="inventory-detail-status-row">
              <span>예상재고</span>
              <strong>{item.expected_inventory ?? "미제공"}</strong>
            </div>
            <div className="inventory-detail-status-row">
              <span>입고예정</span>
              <strong>{item.confirmed_incoming ?? "미제공"}</strong>
            </div>
            <div className="inventory-detail-status-row">
              <span>위험</span>
              <strong>{item.risk_level ?? "미제공"}</strong>
            </div>
            <p className="muted">
              제공되지 않은 계산값이나 위험값은 화면에서
              임의로 생성하지 않습니다.
            </p>
          </div>
        </details>

        <details className="inventory-detail-disclosure">
          <summary>
            확인 업무 제안 ({taskProposals.length})
          </summary>

          <div className="inventory-detail-disclosure-body">
            {taskProposals.length === 0 ? (
              <p className="muted">
                현재 제안된 재고 확인 업무가 없습니다.
              </p>
            ) : (
              taskProposals.map((task) => (
                <article
                  key={task.id}
                  className="inventory-task-proposal"
                >
                  <strong>{task.title}</strong>
                  <div className="muted">
                    우선순위: {task.priority}
                  </div>
                  <div className="muted">
                    상태: {task.status}
                  </div>
                  <div className="muted">
                    제안 이유: {task.source_reason}
                  </div>
                </article>
              ))
            )}

            <p className="muted">
              Task 계약에는 SKU 직접 연결 정보가 없어
              선택한 SKU와의 관련성을 확정하지 않습니다.
            </p>
          </div>
        </details>
      </div>
    </aside>
  );
}