import { useEffect, useRef, useState } from "react";
import { BackendGetError, getC04Lookup, type C04Key, type C04Document } from "../api/day04";
import type { InsightSummary } from "../types/contracts";
import { getInsightTypeLabel } from "./statusLabels";

type EvidenceDrawerProps = {
  open: boolean;
  insight: InsightSummary | null;
  onClose: () => void;
  c04Key?: C04Key;
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
  c04Key,
}: EvidenceDrawerProps) {
  const sourceId = c04Key?.source_id;
  const version = c04Key?.version;
  const chunkId = c04Key?.chunk_id;
  const target = c04Key ? JSON.stringify([sourceId, version, chunkId]) : null;
  const [lookup, setLookup] = useState<{ target: string; document?: C04Document; error?: string } | null>(null);
  const requestRef = useRef(0);
  const visible = open && (!!insight || !!c04Key);

  useEffect(() => {
    const request = ++requestRef.current;
    setLookup(null);
    if (!open || sourceId === undefined || version === undefined || target === null) return;
    const controller = new AbortController();
    getC04Lookup({ source_id: sourceId, version, ...(chunkId !== undefined ? { chunk_id: chunkId } : {}) }, controller.signal)
      .then((document) => {
        if (request === requestRef.current && !controller.signal.aborted) setLookup({ target, document });
      })
      .catch((error: unknown) => {
        if (request !== requestRef.current || controller.signal.aborted) return;
        const messages: Record<number, string> = {
          403: "접근/안전 정책으로 근거 조회가 차단되었습니다.",
          404: "근거가 없거나 version/chunk가 일치하지 않습니다.",
          422: "잘못된 근거 조회 요청입니다.",
          503: "근거 registry를 사용할 수 없습니다.",
        };
        setLookup({ target, error: error instanceof BackendGetError
          ? messages[error.status] ?? "근거를 불러오지 못했습니다."
          : "근거 응답 또는 연결 상태를 확인할 수 없습니다." });
      });
    return () => { requestRef.current += 1; controller.abort(); };
  }, [open, sourceId, version, chunkId, target]);
  const dialogRef = useRef<HTMLElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const previouslyFocusedRef = useRef<HTMLElement | null>(null);
  const onCloseRef = useRef(onClose);

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (!visible) return;

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
  }, [visible]);

  if (!visible) {
    return null;
  }

  const calculation = formatCalculation(insight?.calculation);
  const hasModelRunId = insight?.model_run_id != null;
  const currentLookup = lookup?.target === target ? lookup : null;
  const c04Document = currentLookup?.document;

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
              {c04Key ? "C04 원문 근거" : getInsightTypeLabel(insight!.type)}
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
          {c04Key ? (
            currentLookup?.error ? <div className="notice" role="alert">{currentLookup.error}</div> :
            c04Document ? <section className="evidence-section" data-testid="c04-document">
              <h3>{c04Document.title}</h3>
              <div className="notice">합성 Demo 근거 (SYNTHETIC_DEMO)</div>
              {c04Document.stale && <div className="notice" role="alert">오래된 자료입니다. 최신 자료를 확인하세요.</div>}
              {!c04Document.definitive_answer_allowed && <div className="notice">원문은 조회됐지만 이 자료 하나만으로 현재 상태를 확정할 수 없습니다.</div>}
              <p>{c04Document.excerpt}</p>
              <dl className="evidence-details">
                {(["source_id", "source_type", "version", "as_of", "stale", "data_mode", "visibility", "chunk_id", "definitive_answer_allowed"] as const).map((field) =>
                  <div key={field}><dt>{field}</dt><dd>{String(c04Document[field])}</dd></div>,
                )}
                <div><dt>warnings</dt><dd>{c04Document.warnings.length ? c04Document.warnings.join(" / ") : "없음"}</dd></div>
              </dl>
            </section> : <p role="status">근거를 불러오는 중입니다.</p>
          ) : insight ? <>
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
          </> : null}
        </div>
      </aside>
    </>
  );
}
