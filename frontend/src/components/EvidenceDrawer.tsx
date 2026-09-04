import { useEffect, useRef } from "react";
import type { InsightSummary } from "../types/contracts";
import { getInsightTypeLabel } from "./statusLabels";

type EvidenceDrawerProps = {
  open: boolean;
  insight: InsightSummary | null;
  onClose: () => void;
};

const sourceTypeLabels: Record<string, string> = {
  order: "주문",
  inventory_snapshot: "재고 스냅샷",
  inquiry: "고객 문의",
  task: "내부 확인 업무",
};

function getSourceTypeLabel(sourceType: string): string {
  return sourceTypeLabels[sourceType] ?? "기타 근거";
}

function formatCalculation(calculation?: Record<string, number>) {
  if (!calculation || Object.keys(calculation).length === 0) {
    return null;
  }

  return Object.entries(calculation);
}

export default function EvidenceDrawer({
  open,
  insight,
  onClose,
}: EvidenceDrawerProps) {
  const dialogRef = useRef<HTMLElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const previouslyFocusedRef = useRef<HTMLElement | null>(null);
  const onCloseRef = useRef(onClose);

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (!open || !insight) return;

    previouslyFocusedRef.current =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    closeButtonRef.current?.focus();

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onCloseRef.current();
        return;
      }

      if (event.key !== "Tab" || !dialogRef.current) return;

      const focusableElements = Array.from(
        dialogRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ),
      );

      if (focusableElements.length === 0) {
        event.preventDefault();
        return;
      }

      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];
      const focusIsOutsideDialog = !dialogRef.current.contains(
        document.activeElement,
      );

      if (
        event.shiftKey &&
        (document.activeElement === firstElement || focusIsOutsideDialog)
      ) {
        event.preventDefault();
        lastElement.focus();
      } else if (
        !event.shiftKey &&
        (document.activeElement === lastElement || focusIsOutsideDialog)
      ) {
        event.preventDefault();
        firstElement.focus();
      }
    }

    window.addEventListener("keydown", handleKeyDown);

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      previouslyFocusedRef.current?.focus();
    };
  }, [open, insight]);

  if (!open || !insight) {
    return null;
  }

  const calculation = formatCalculation(insight.calculation);
  const hasModelRunId = insight.model_run_id !== null;

  return (
    <>
      <button
        className="drawer-backdrop"
        type="button"
        aria-label="판단 근거 닫기"
        onClick={onClose}
      />

      <aside
        ref={dialogRef}
        className="evidence-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="evidence-drawer-title"
      >
        <div className="evidence-drawer-header">
          <div>
            <div className="tertiary">판단 근거</div>
            <h2 id="evidence-drawer-title">
              {getInsightTypeLabel(insight.type)}
            </h2>
          </div>

          <button
            ref={closeButtonRef}
            type="button"
            className="drawer-close-button"
            onClick={onClose}
            aria-label="판단 근거 패널 닫기"
          >
            ×
          </button>
        </div>

        <div className="evidence-drawer-body">
          <section className="evidence-section">
            <h3>1. 원천 근거</h3>

            <div className="stack">
              {insight.evidence.length > 0 ? (
                insight.evidence.map((evidence, index) => (
                  <article
                    className="evidence-item"
                    key={`${evidence.source_type}-${evidence.source_id}-${index}`}
                  >
                    <div className="toolbar">
                      <strong>{getSourceTypeLabel(evidence.source_type)}</strong>
                      <span className="badge source">
                        근거 {index + 1}
                      </span>
                    </div>

                    <dl className="evidence-details">
                      <div>
                        <dt>source_id</dt>
                        <dd className="mono">{evidence.source_id}</dd>
                      </div>

                      <div>
                        <dt>기준 시각</dt>
                        <dd>{evidence.as_of}</dd>
                      </div>
                    </dl>
                  </article>
                ))
              ) : (
                <div className="notice">
                  연결된 원천 근거가 없습니다.
                </div>
              )}
            </div>
          </section>

          <section className="evidence-section">
            <h3>2. 계산 근거</h3>

            {calculation ? (
              <dl className="calculation-list">
                {calculation.map(([key, value]) => (
                  <div key={key}>
                    <dt className="mono">{key}</dt>
                    <dd>{value}</dd>
                  </div>
                ))}
              </dl>
            ) : (
              <div className="notice">
                별도의 수치 계산식이 없는 판단입니다.
              </div>
            )}

            <div className="evidence-rule">
              <span className="tertiary">규칙 버전</span>
              <strong className="mono">{insight.rule_version}</strong>
            </div>
          </section>

          <section className="evidence-section">
            <h3>3. 처리·버전 정보</h3>

            <dl className="evidence-details">
              <div>
                <dt>판단 방식</dt>
                <dd>
                  {hasModelRunId ? "AI 모델 기반 판단" : "현재 계약으로 확인 불가"}
                </dd>
              </div>

              <div>
                <dt>model_run_id</dt>
                <dd className="mono">
                  {insight.model_run_id ?? "제공되지 않음"}
                </dd>
              </div>

              <div>
                <dt>Model Version</dt>
                <dd>
                  현재 계약에서 제공되지 않음
                </dd>
              </div>

              <div>
                <dt>Prompt Version</dt>
                <dd>
                  현재 계약에서 제공되지 않음
                </dd>
              </div>

              <div>
                <dt>Index Version</dt>
                <dd>
                  현재 계약에서 제공되지 않음
                </dd>
              </div>
            </dl>

            {!hasModelRunId && (
              <div className="notice">
                model_run_id가 없어도 규칙 또는 AI Mock 결과일 수 있어,
                현재 계약만으로 판단 출처를 확정할 수 없습니다.
              </div>
            )}
          </section>
        </div>
      </aside>
    </>
  );
}
