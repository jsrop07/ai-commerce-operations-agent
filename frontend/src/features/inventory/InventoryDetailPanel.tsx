import type {
  InventorySnapshot,
  TaskSummary,
} from "../../types/contracts";
import {
  useEffect,
  useRef,
} from "react";
import FreshnessLabel from "../../components/FreshnessLabel";

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
    if (!open) {
      return;
    }

    closeButtonRef.current?.focus();

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
        return;
      }

      if (event.key !== "Tab" || !panelRef.current) {
        return;
      }

      const focusableElements = Array.from(
        panelRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ),
      );

      if (focusableElements.length === 0) {
        event.preventDefault();
        return;
      }

      const firstElement = focusableElements[0];
      const lastElement =
        focusableElements[focusableElements.length - 1];
      const activeElement = document.activeElement;

      if (
        event.shiftKey &&
        (activeElement === firstElement ||
          !panelRef.current.contains(activeElement))
      ) {
        event.preventDefault();
        lastElement.focus();
      } else if (
        !event.shiftKey &&
        (activeElement === lastElement ||
          !panelRef.current.contains(activeElement))
      ) {
        event.preventDefault();
        firstElement.focus();
      }
    }

    window.addEventListener("keydown", handleKeyDown);

    return () => {
      window.removeEventListener(
        "keydown",
        handleKeyDown,
      );
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
      aria-modal="true"
      aria-labelledby={titleId}
      data-testid="inventory-detail-panel"
    >
      <div className="inventory-detail-header">
        <div>
          <div className="muted">
            재고 상세
          </div>

          <h2
            id={titleId}
            className="inventory-detail-title"
          >
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
          className="card"
          aria-labelledby="inventory-snapshot-title"
        >
          <div
            className="card-header"
            id="inventory-snapshot-title"
          >
            현재 Snapshot
          </div>

          <div className="card-body">
            <table className="dense-table">
              <tbody>
                <tr>
                  <th>SKU</th>
                  <td className="mono">
                    {item.sku_id}
                  </td>
                </tr>

                <tr>
                  <th>채널</th>
                  <td>
                    {item.provider}
                  </td>
                </tr>

                <tr>
                  <th>현재 수량</th>
                  <td className="number">
                    {item.on_hand}
                  </td>
                </tr>

                <tr>
                  <th>예약 수량</th>
                  <td className="number">
                    {item.reserved}
                  </td>
                </tr>

                <tr>
                  <th>최신성</th>
                  <td>
                    <FreshnessLabel
                      freshness={item.freshness}
                      source={item.provider}
                      asOf={item.as_of}
                      showMetadata={false}
                    />
                  </td>
                </tr>

                <tr>
                  <th>기준 시각</th>
                  <td>
                    <time dateTime={item.as_of}>
                      {new Date(
                        item.as_of,
                      ).toLocaleString("ko-KR")}
                    </time>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section
          className="card"
          aria-labelledby="inventory-calculation-title"
        >
          <div
            className="card-header"
            id="inventory-calculation-title"
          >
            계산 근거
          </div>

          <div className="card-body stack">
            <div className="dashboard-summary-row">
              <span>현재 Snapshot</span>
              <strong>계약 제공</strong>
            </div>

            <div className="dashboard-summary-row">
              <span>예약 수량</span>
              <strong>계약 제공</strong>
            </div>

            <div className="dashboard-summary-row">
              <span>예상재고</span>
              <span className="muted">
                계약 미제공
              </span>
            </div>

            <div className="dashboard-summary-row">
              <span>입고예정</span>
              <span className="muted">
                계약 미제공
              </span>
            </div>

            <div className="dashboard-summary-row">
              <span>위험</span>
              <span className="muted">
                계약 미제공
              </span>
            </div>

            <p className="muted">
              현재 상세 패널은 InventorySnapshot 계약에 포함된 값만 표시합니다.
              없는 계산값이나 위험값은 화면에서 생성하지 않습니다.
            </p>
          </div>
        </section>

        <section
          className="card"
          aria-labelledby="inventory-task-title"
        >
          <div
            className="card-header"
            id="inventory-task-title"
          >
            확인 업무 제안
          </div>

          <div className="card-body stack">
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
              현재 Task 계약에는 SKU 직접 연결 정보가 없어
              선택한 SKU와의 관련성을 확정하지 않습니다.
            </p>
          </div>
        </section>
      </div>
    </aside>
  );
}
