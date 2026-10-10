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
          <div className="muted">재고 기록 상세</div>
            <h2 id={titleId} className="inventory-detail-title">
              {item.sku_id}
            </h2>

            <div className="inventory-detail-freshness">
              <span className="inventory-freshness-chip">
                {item.freshness === "STALE"
                  ? "최신성 확인 필요"
                  : item.freshness === "FRESH"
                    ? "최신성 기준 충족"
                    : "최신성 미확인"}
              </span>
            </div>
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
            <span>기록된 재고</span>
            <strong>{item.on_hand}개</strong>
          </div>
          <div className="inventory-detail-quantity-card">
            <span>Snapshot 예약</span>
            <strong>{item.reserved}개</strong>
          </div>
        </section>

        <section
          className="inventory-detail-status"
          aria-labelledby="inventory-detail-status-title"
        >
          <h3 id="inventory-detail-status-title">
            데이터 확인 상태
          </h3>

          <div className="inventory-detail-status-row">
            <span>최신성</span>
            <strong>
              {item.freshness === "FRESH"
                ? "최신성 기준 충족"
                : item.freshness === "STALE"
                  ? "오래된 자료"
                  : "확인 필요"}
            </strong>
          </div>

          <div className="inventory-detail-status-row">
            <span>기준 시각</span>
            <time dateTime={item.as_of}>
              {item.as_of
                ? new Date(item.as_of).toLocaleString("ko-KR", {
                    timeZone: "Asia/Seoul",
                  })
                : "미확인"}
            </time>
          </div>

          <div className="inventory-detail-status-row">
            <span>재고 합계 반영</span>
            <strong>
              {item.confirmed_for_total === true
                ? "반영 가능"
                : "확정 합계에서 제외"}
            </strong>
          </div>

          <p className="muted inventory-detail-status-note">
            {item.freshness === "STALE"
              ? "최신 재고가 확인되지 않아 현재 재고 위험을 확정할 수 없습니다."
              : "재고 수량은 원천의 품질 및 확인 조건에 따라 판단해야 합니다."}
          </p>
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
              <strong>
                {item.risk_level === "UNKNOWN" || item.risk_level == null
                  ? "판정 불가"
                  : item.risk_level === "HIGH"
                    ? "높음"
                    : item.risk_level === "MEDIUM"
                      ? "보통"
                      : item.risk_level === "LOW"
                        ? "낮음"
                        : item.risk_level === "PROHIBITED"
                          ? "사용 제한"
                          : "확인 필요"}
              </strong>
            </div>
            <div className="inventory-evidence-notes">
  <div>
    <strong>재고 수량 기준</strong>
    <p>
      기록된 재고는 과거 Snapshot 기준입니다.
      최신 재고가 확인되기 전까지 현재 보유 수량으로 확정하지 않습니다.
    </p>
  </div>

  <div>
    <strong>예약 수량 기준</strong>
    <p>
      표시된 예약 {item.reserved}개는 Snapshot에 기록된 값입니다.
      별도로 관리되는 예약주문 필요 수량과는 다릅니다.
    </p>
  </div>

  <div>
    <strong>예정 입고 기준</strong>
    <p>
      입고예정 미제공은 입고 일정이 없다는 뜻이 아닙니다.
      운영 일정의 입고 정보와 자동 합산하지 않습니다.
    </p>
  </div>
</div>
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