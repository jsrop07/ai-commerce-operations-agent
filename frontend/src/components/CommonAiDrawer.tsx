import { useEffect, useRef, useState } from "react";
import {
  appendAnalysis, contextIdentity, createConversation, getConversations, reopenConversation,
  type ConversationContext, type ConversationView, type MessageView,
} from "../api/conversations";

export type AiPanelContext = ConversationContext;

interface CommonAiDrawerProps {
  open: boolean;
  context: AiPanelContext | null;
  onClose: () => void;
}

type DrawerStatus = "idle" | "loading" | "creating" | "analyzing" | "loaded" | "error";

function isBootstrapMessage(message: MessageView): boolean {
  return message.role === "USER" && message.analysis_kind === "NONE" &&
    message.request_message_id === null;
}

function latestLinkedAssistant(messages: MessageView[], revision: number, key: string): MessageView | null {
  const ordered = [...messages].sort((a, b) => a.message_order - b.message_order);
  return [...ordered].reverse().find((message) => message.role === "ASSISTANT" &&
    message.request_message_id !== null && message.context.context_revision === revision &&
    contextIdentity(message.context) === key && ordered.some((request) =>
      request.message_id === message.request_message_id && request.role === "USER" &&
      request.message_order < message.message_order && request.context.context_revision === revision &&
      contextIdentity(request.context) === key)) ?? null;
}

function latestSavedAssistant(messages: MessageView[]): MessageView | null {
  return [...messages].sort((a, b) => b.message_order - a.message_order).find((message) =>
    message.role === "ASSISTANT" &&
    (message.response_status === "ANSWER" || message.response_status === "HOLD" ||
      message.response_status === "NO_EDGE")) ?? null;
}

export default function CommonAiDrawer({ open, context, onClose }: CommonAiDrawerProps) {
  const visible = open && context !== null;
  const dialogRef = useRef<HTMLElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  const [status, setStatus] = useState<DrawerStatus>("idle");
  const [conversation, setConversation] = useState<ConversationView | null>(null);
  const [result, setResult] = useState<MessageView | null>(null);
  const [error, setError] = useState("");
  const [recent, setRecent] = useState<ConversationView[]>([]);
  const [recentLoading, setRecentLoading] = useState(false);
  const [recentError, setRecentError] = useState("");
  const operationRef = useRef(0);
  const key = context ? contextIdentity(context) : null;
  const activeRef = useRef({ key, open, conversationId: null as string | null, revision: 0 });
  activeRef.current.key = key;
  activeRef.current.open = open;

  useEffect(() => {
    operationRef.current += 1;
    activeRef.current.conversationId = null;
    activeRef.current.revision = 0;
    setRecent([]);
    setRecentError("");
    setConversation(null);
    setResult(null);
    setStatus("idle");
    setError("");
  }, [key]);

  useEffect(() => {
    if (!visible || !key) return;
    const controller = new AbortController();
    setRecentLoading(true);
    setRecentError("");
    void getConversations(controller.signal).then(({ data }) => {
      if (!controller.signal.aborted) setRecent(data.filter((item) => item.context !== null &&
        contextIdentity(item.context) === key));
    }).catch((cause) => {
      if (!controller.signal.aborted) setRecentError(cause instanceof Error ? cause.message : "최근 대화 조회에 실패했습니다.");
    }).finally(() => {
      if (!controller.signal.aborted) setRecentLoading(false);
    });
    return () => controller.abort();
  }, [visible, key]);

  useEffect(() => {
    if (!visible) operationRef.current += 1;
  }, [visible]);

  useEffect(() => () => { operationRef.current += 1; }, []);

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

  async function runAnalysis() {
    if (!context || !key || status === "loading" || status === "creating" || status === "analyzing") return;
    const requestSnapshot = {
      sequence: ++operationRef.current,
      context,
      key,
      conversationId: conversation?.conversation_id ?? null,
      revision: conversation?.current_context_revision ?? 0,
    };
    if (conversation && (!conversation.context || contextIdentity(conversation.context) !== requestSnapshot.key)) {
      setError("선택된 대화의 분석 범위가 현재 화면과 일치하지 않습니다.");
      setStatus("error");
      return;
    }
    let analysisSnapshot = requestSnapshot;
    activeRef.current.conversationId = requestSnapshot.conversationId;
    activeRef.current.revision = requestSnapshot.revision;
    const isCurrent = (snapshot: typeof requestSnapshot) =>
      operationRef.current === snapshot.sequence && activeRef.current.open && activeRef.current.key === snapshot.key &&
      activeRef.current.conversationId === snapshot.conversationId && activeRef.current.revision === snapshot.revision;
    setError("");
    try {
      if (!requestSnapshot.conversationId) {
        setStatus("creating");
        const created = (await createConversation(requestSnapshot.context)).data;
        if (!created.context || contextIdentity(created.context) !== requestSnapshot.key ||
          created.current_context_revision < 1) throw new Error("생성된 대화의 분석 범위가 일치하지 않습니다.");
        if (isCurrent(requestSnapshot)) {
          activeRef.current.conversationId = created.conversation_id;
          activeRef.current.revision = created.current_context_revision;
          setConversation(created);
        }
        analysisSnapshot = { ...requestSnapshot, conversationId: created.conversation_id,
          revision: created.current_context_revision };
      }
      if (!analysisSnapshot.conversationId) throw new Error("분석 요청 대화가 없습니다.");
      if (isCurrent(analysisSnapshot)) setStatus("analyzing");
      const analyzed = (await appendAnalysis(
        analysisSnapshot.conversationId, analysisSnapshot.context, analysisSnapshot.revision,
        "INSPECT_TARGET", "DETERMINISTIC",
      )).data;
      if (!isCurrent(analysisSnapshot)) return;
      const assistant = latestLinkedAssistant(analyzed.messages, analysisSnapshot.revision, analysisSnapshot.key);
      if (analyzed.conversation_id !== analysisSnapshot.conversationId || !assistant ||
        !analyzed.context || contextIdentity(analyzed.context) !== analysisSnapshot.key ||
        analyzed.current_context_revision !== analysisSnapshot.revision) {
        throw new Error("분석 응답의 대화·요청 identity가 일치하지 않습니다.");
      }
      setConversation(analyzed);
      setResult(assistant);
      setStatus("loaded");
      setRecent((items) => [analyzed, ...items.filter((item) => item.conversation_id !== analyzed.conversation_id)]);
    } catch (cause) {
      if (!isCurrent(analysisSnapshot)) return;
      setError(cause instanceof Error ? cause.message : "분석 요청에 실패했습니다.");
      setStatus("error");
    }
  }

  async function selectConversation(item: ConversationView) {
    if (!key) return;
    const operation = ++operationRef.current;
    setStatus("loading");
    setError("");
    try {
      const restored = (await reopenConversation(item.conversation_id)).data;
      if (operationRef.current !== operation || !activeRef.current.open || activeRef.current.key !== key) return;
      if (restored.conversation_id !== item.conversation_id || !restored.context ||
        restored.context.context_revision !== restored.current_context_revision ||
        contextIdentity(restored.context) !== key) throw new Error("재열기 응답의 대화 범위가 일치하지 않습니다.");
      activeRef.current.conversationId = restored.conversation_id;
      activeRef.current.revision = restored.current_context_revision;
      setConversation(restored);
      const assistant = latestSavedAssistant(restored.messages);
      setResult(assistant);
      setStatus(assistant ? "loaded" : "idle");
      setRecent((items) => items.map((current) => current.conversation_id === restored.conversation_id ? restored : current));
    } catch (cause) {
      if (operationRef.current !== operation || !activeRef.current.open || activeRef.current.key !== key) return;
      setError(cause instanceof Error ? cause.message : "대화 재열기에 실패했습니다.");
      setStatus("error");
    }
  }

  function startNewConversation() {
    operationRef.current += 1;
    activeRef.current.conversationId = null;
    activeRef.current.revision = 0;
    setConversation(null);
    setResult(null);
    setError("");
    setStatus("idle");
  }

  if (!visible) return null;

  const isEntity = "targetType" in context;
  const history = (conversation?.messages ?? [])
    .filter((message) => !isBootstrapMessage(message))
    .sort((a, b) => a.message_order - b.message_order);
  const synthetic = result?.evidence_ids.some((id) => id.startsWith("product-demand:SYNTHETIC_DEMO:")) ?? false;
  const statusLabel = result?.response_status === "ANSWER" ? "정상 분석 결과" :
    result?.response_status === "NO_EDGE" ? "확인된 관계 없음" : "판단 근거 부족 · 현재 분석 불가";

  return (
    <>
      <button type="button" className="common-ai-backdrop" aria-label="운영 AI 패널 배경 닫기" onClick={onClose} />
      <aside ref={dialogRef} className="common-ai-drawer" role="dialog" aria-modal="true" aria-labelledby="common-ai-title">
        <header className="common-ai-header">
          <h2 id="common-ai-title">운영 AI</h2>
          <button ref={closeButtonRef} type="button" aria-label="운영 AI 패널 닫기" onClick={onClose}>×</button>
        </header>
        <div className="common-ai-body">
          <section aria-labelledby="common-ai-recent-title">
            <h3 id="common-ai-recent-title">최근 대화</h3>
            {recentLoading && <p role="status">최근 대화 조회 중입니다.</p>}
            {recentError && <p role="alert">{recentError}</p>}
            {!recentLoading && !recentError && recent.length === 0 && <p>이 범위의 최근 대화가 없습니다.</p>}
            {recent.length > 0 && <ul className="common-ai-recent">{recent.map((item) =>
              <li key={item.conversation_id}><button type="button"
                aria-pressed={conversation?.conversation_id === item.conversation_id}
                onClick={() => void selectConversation(item)}>
                {item.context?.target_label ?? item.context?.page} · {item.conversation_status} · revision {item.current_context_revision}
                <small>{item.conversation_id}</small>
              </button></li>)}</ul>}
            <button type="button" onClick={startNewConversation}>새 대화</button>
          </section>
          <section aria-labelledby="common-ai-target-title">
            <h3 id="common-ai-target-title">현재 분석 범위</h3>
            <strong>{isEntity ? context.targetLabel : context.page}</strong>
            <dl className="common-ai-context">
              <div><dt>페이지</dt><dd>{isEntity ? "상품 Catalog" : context.page}</dd></div>
              {isEntity ? <>
                <div><dt>대상 유형</dt><dd>{context.targetType}</dd></div>
                <div><dt>대상 ID</dt><dd>{context.targetId}</dd></div>
                <div><dt>자료 출처</dt><dd>{context.source}</dd></div>
                <div><dt>데이터 기준 시각</dt><dd>{context.asOf === null ? "기준 시각 미확인" : <time dateTime={context.asOf}>{context.asOf}</time>}</dd></div>
              </> : <>
                <div><dt>적용 필터</dt><dd>{Object.keys(context.filters).length === 0 ? "없음" :
                  Object.entries(context.filters).map(([name, value]) => `${name}: ${value}`).join(" · ")}</dd></div>
                {context.search && <div><dt>검색</dt><dd>{context.search}</dd></div>}
                {context.date_range && <div><dt>기간</dt><dd>{context.date_range.from_date} ~ {context.date_range.to_date}</dd></div>}
                {context.sort && <div><dt>정렬</dt><dd>{context.sort.by} · {context.sort.direction}</dd></div>}
              </>}
            </dl>
            {isEntity && <p>상품정보 · 실제 Catalog</p>}
          </section>
          <section aria-labelledby="common-ai-result-title">
            <h3 id="common-ai-result-title">분석 결과</h3>
            {status === "idle" && <p>아직 분석을 실행하지 않았습니다.</p>}
            {status === "creating" && <p role="status">대화 생성 중입니다.</p>}
            {status === "loading" && <p role="status">대화 재열기 중입니다.</p>}
            {status === "analyzing" && <p role="status">분석 중입니다.</p>}
            {status === "error" && <p role="alert">{error}</p>}
            {status === "loaded" && result && <>
              <p role="status">{statusLabel}</p>
              {synthetic && <p>주문/판매 분석 · Demo synthetic data</p>}
              <p className="common-ai-answer">{result.content}</p>
            </>}
            <button type="button" onClick={() => void runAnalysis()}
              disabled={status === "loading" || status === "creating" || status === "analyzing"}>분석 실행</button>
          </section>
          <section aria-labelledby="common-ai-evidence-title">
            <h3 id="common-ai-evidence-title">근거</h3>
            {result?.evidence_ids.length ? <ul>{result.evidence_ids.map((id) => <li key={id}>{id}</li>)}</ul> :
              <p>연결된 근거 없음</p>}
          </section>
          <section aria-labelledby="common-ai-next-title">
            <h3 id="common-ai-next-title">다음 확인</h3>
            <p>{result ? "분석 본문의 다음 확인/조치를 참고하세요." : "현재 context 기준 후속 확인 없음"}</p>
          </section>
          <section aria-labelledby="common-ai-history-title">
            <h3 id="common-ai-history-title">대화 History</h3>
            {history.length ? <ol>{history.map((message) => <li key={message.message_id}>
              <strong>{message.role === "USER" ? "요청" : "분석"} · {message.response_status}</strong>
              <p>{message.content}</p>
              {message.role === "ASSISTANT" && message.evidence_ids.length > 0 &&
                <ul aria-label="메시지 근거">{message.evidence_ids.map((id) => <li key={id}>{id}</li>)}</ul>}
            </li>)}</ol> : <p>저장된 대화가 없습니다.</p>}
          </section>
          <section aria-labelledby="common-ai-followup-title">
            <h3 id="common-ai-followup-title">후속 질문</h3>
            <p>C09 자유 입력은 아직 연결되지 않았습니다. 같은 범위는 분석 실행으로 다시 확인할 수 있습니다.</p>
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
