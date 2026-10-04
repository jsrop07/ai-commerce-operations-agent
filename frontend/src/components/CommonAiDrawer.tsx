import { useEffect, useRef } from "react";

export interface AiPanelContext {
  targetType: string;
  targetId: string;
  targetLabel: string;
  source: string;
  asOf: string | null;
}

interface CommonAiDrawerProps {
  open: boolean;
  context: AiPanelContext | null;
  onClose: () => void;
}

export default function CommonAiDrawer({ open, context, onClose }: CommonAiDrawerProps) {
  const visible = open && context !== null;
  const dialogRef = useRef<HTMLElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!visible) return;
    previousFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    closeButtonRef.current?.focus();

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onCloseRef.current();
        return;
      }
      if (event.key !== "Tab" || !dialogRef.current) return;

      const focusable = Array.from(dialogRef.current.querySelectorAll<HTMLElement>(
        'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      ));
      if (focusable.length === 0) {
        event.preventDefault();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const focusOutside = !dialogRef.current.contains(document.activeElement);
      if (event.shiftKey && (document.activeElement === first || focusOutside)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && (document.activeElement === last || focusOutside)) {
        event.preventDefault();
        first.focus();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      previousFocusRef.current?.focus();
    };
  }, [visible]);

  if (!visible) return null;

  return (
    <>
      <button type="button" className="common-ai-backdrop" aria-label="운영 AI 패널 배경 닫기" onClick={onClose} />
      <aside ref={dialogRef} className="common-ai-drawer" role="dialog" aria-modal="true" aria-labelledby="common-ai-title">
        <header className="common-ai-header">
          <h2 id="common-ai-title">운영 AI</h2>
          <button ref={closeButtonRef} type="button" aria-label="운영 AI 패널 닫기" onClick={onClose}>×</button>
        </header>
        <div className="common-ai-body">
          <section aria-labelledby="common-ai-target-title">
            <h3 id="common-ai-target-title">선택 대상</h3>
            <strong>{context.targetLabel}</strong>
            <dl className="common-ai-context">
              <div><dt>대상 유형</dt><dd>{context.targetType}</dd></div>
              <div><dt>대상 ID</dt><dd>{context.targetId}</dd></div>
              <div><dt>자료 출처</dt><dd>{context.source}</dd></div>
              <div><dt>데이터 기준 시각</dt><dd>{context.asOf === null ? "기준 시각 미확인" : <time dateTime={context.asOf}>{context.asOf}</time>}</dd></div>
            </dl>
          </section>
          <section aria-labelledby="common-ai-result-title">
            <h3 id="common-ai-result-title">분석 결과</h3>
            <p>아직 분석을 실행하지 않았습니다.</p>
          </section>
          <section aria-labelledby="common-ai-evidence-title">
            <h3 id="common-ai-evidence-title">근거</h3>
            <p>연결된 근거 없음</p>
          </section>
          <section aria-labelledby="common-ai-next-title">
            <h3 id="common-ai-next-title">다음 확인</h3>
            <p>현재 context 기준 후속 확인 없음</p>
          </section>
          <section aria-labelledby="common-ai-followup-title">
            <h3 id="common-ai-followup-title">후속 질문</h3>
            <p>C09 대화 연결 전입니다.</p>
            <div className="common-ai-followup">
              <input aria-label="후속 질문 입력" disabled />
              <button type="button" disabled>전송</button>
            </div>
          </section>
        </div>
      </aside>
    </>
  );
}
