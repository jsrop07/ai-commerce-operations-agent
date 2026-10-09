import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  ArrowLeft, History, SquarePen, X, Sparkles, Send,
  ChevronDown, FileText, Maximize2, Minimize2,
} from "lucide-react";
import "./CommonAiDrawerChat.css";

import {
  appendAnalysis, appendNaturalQuestion, appendProductSearch,
  contextIdentity, createConversation,

  createProductSearchConversation, getConversation, getConversations, reopenConversation,

  type AnalysisKind, type ContextView, type ConversationContext, type ConversationView, type MessageView,

} from "../api/conversations";

import { BackendHttpError } from "../api/backendHttp";

import type { SessionState } from "../app/CommonAiDrawerContext";



export type AiPanelContext = ConversationContext;



interface CommonAiDrawerProps {

  open: boolean;

  context: AiPanelContext | null;

  onClose: () => void;

  sessionState?: SessionState;

  onStartNewSession?: () => void;

  onSessionExpired?: () => void;

  publicMode?: boolean;

}



type DrawerStatus = "idle" | "loading" | "creating" | "analyzing" | "loaded" | "error";

const AI_CONVERSATION_STORAGE_KEY = "commerce-ai-active-conversation";

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



export function aiProblem(cause: unknown): { message: string; sessionExpired: boolean } {

  if (cause instanceof BackendHttpError) {

    if (cause.code === "C09_TRUSTED_ACTOR_REQUIRED" || cause.code === "DEMO_SESSION_REQUIRED")

      return { message: "Demo Session이 만료되었습니다. 새 세션을 시작해 주세요.", sessionExpired: true };

    if (cause.code === "C24_QUOTA_EXCEEDED")

      return { message: "이 세션의 AI 모델 사용 한도에 도달했습니다. 검증된 업무 결과는 계속 확인할 수 있습니다.", sessionExpired: false };

    if (cause.code?.startsWith("C24_QUOTA_UNCONFIGURED") || cause.code === "C24_QUOTA_UNAVAILABLE" ||

      cause.code === "C24_OPENAI_CREDENTIAL_REQUIRED")

      return { message: "Public Demo의 AI 모델 호출이 현재 중지되어 있습니다. 검증된 업무 결과는 계속 확인할 수 있습니다.", sessionExpired: false };

    if (cause.status === 429)

      return { message: "요청이 잠시 제한되었습니다. 잠시 후 다시 시도해 주세요.", sessionExpired: false };

    if (cause.code === "PRODUCT_SEARCH_AMBIGUOUS")

      return { message: "일치하는 상품이 여러 개입니다. 상품명이나 코드를 더 구체적으로 입력해 주세요.", sessionExpired: false };

    if (cause.code === "PRODUCT_SEARCH_NOT_FOUND")

      return { message: "일치하는 상품을 찾지 못했습니다. 기존 분석 범위는 유지됩니다.", sessionExpired: false };

    if (cause.code === "PRODUCT_SEARCH_INPUT_FORBIDDEN")

      return { message: "이 검색어는 Demo Product 검색에 사용할 수 없습니다.", sessionExpired: false };

    if (cause.status >= 500)

      return { message: "AI 서비스 또는 Backend를 일시적으로 사용할 수 없습니다. 저장된 분석은 계속 볼 수 있습니다.", sessionExpired: false };

  }

  return { message: cause instanceof Error ? cause.message : "요청에 실패했습니다.", sessionExpired: false };

}



function evidenceType(message: MessageView): string {

  if (message.analysis_kind === "RELATION_DOCUMENT") return "관계 근거";

  if (message.analysis_kind === "HYBRID") return "검색·문서 근거";

  return "규칙·권위 근거";

}



function displayContent(content: string, publicMode: boolean): string {

  return publicMode ? content.split("\n").filter((line) => !line.startsWith("근거:")).join("\n") : content;

}

function AnalysisContent({
  content,
  publicMode,
}: {
  content: string;
  publicMode: boolean;
}) {
  const lines = displayContent(content, publicMode)
    .split("\n")
    .filter(Boolean);

  return (
    <div className="common-ai-analysis-content">
      {lines.map((line, index) => {
        const separator = line.indexOf(":");

        if (separator < 0) {
          return <p key={index}>{line}</p>;
        }

        const title = line.slice(0, separator).trim();
        const value = line.slice(separator + 1).trim();

        if (![
          "결론",
          "핵심 수치/상태",
          "근거",
          "다음 확인/조치",
        ].includes(title)) {
          return <p key={index}>{line}</p>;
        }

        return (
          <section
            key={index}
            className="common-ai-analysis-section"
          >
            <strong>{title}</strong>
            {title === "핵심 수치/상태" ? (
              <ul className="common-ai-facts">
                {value.split("; ").filter(Boolean).map((fact, i) => (
                  <li key={i}>{fact}</li>
                ))}
              </ul>
            ) : (
              <p>{value}</p>
            )}
          </section>
        );
      })}
    </div>
  );
}

function contextInput(view: ContextView): ConversationContext | null {

  if (view.scope !== "ENTITY" || view.target_type !== "PRODUCT" || !view.target_id || !view.target_label || !view.source)

    return null;

  return { targetType: "PRODUCT", targetId: view.target_id, targetLabel: view.target_label,

    source: view.source, asOf: view.source_as_of };

}



export default function CommonAiDrawer({ open, context, onClose,

  sessionState = "ready", onStartNewSession, onSessionExpired, publicMode = false }: CommonAiDrawerProps) {

  const visible = open;

  const dialogRef = useRef<HTMLElement>(null);
  const chatScrollRef = useRef<HTMLDivElement>(null);
  const shouldAutoScrollRef = useRef(true);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  const onCloseRef = useRef(onClose);

  onCloseRef.current = onClose;

  const [status, setStatus] = useState<DrawerStatus>("idle");

  const [conversation, setConversation] = useState<ConversationView | null>(null);

  const [result, setResult] = useState<MessageView | null>(null);

  const [error, setError] = useState("");

  const [panelScreen, setPanelScreen] = useState<"chat" | "history">("chat");

  const [expanded, setExpanded] = useState(false);

  const [recent, setRecent] = useState<ConversationView[]>([]);

  const [recentLoading, setRecentLoading] = useState(false);

  const [recentError, setRecentError] = useState("");

  const [searchDraft, setSearchDraft] = useState("");

  const [resolvedContext, setResolvedContext] = useState<ContextView | null>(null);

  const [analysisKind, setAnalysisKind] = useState<AnalysisKind>("DETERMINISTIC");

  const operationRef = useRef(0);

  const key = context ? contextIdentity(context) : null;

  const activeRef = useRef({ key, open, conversationId: null as string | null, revision: 0 });

  activeRef.current.key = key;

  activeRef.current.open = open;

  useEffect(() => {
  if (!conversation?.conversation_id || !conversation.context) return;

  try {
    sessionStorage.setItem(
      AI_CONVERSATION_STORAGE_KEY,
      JSON.stringify({
        contextKey: key,
        conversationId: conversation.conversation_id,
      }),
    );
  } catch {
    // 저장소를 사용할 수 없는 환경에서는 메모리 상태로 동작
  }
}, [conversation, key]);


  useEffect(() => {

    operationRef.current += 1;

    activeRef.current.conversationId = null;

    activeRef.current.revision = 0;


    setRecentError("");

    setConversation(null);

    setResult(null);

    setStatus("idle");

    setError("");

    setResolvedContext(null);

    setAnalysisKind("DETERMINISTIC");

  }, [key]);



  useEffect(() => {

    if (!visible || sessionState !== "ready") return;

    const controller = new AbortController();

    setRecentLoading(true);

    setRecentError("");

    void getConversations(controller.signal).then(({ data }) => {
      if (!controller.signal.aborted) {
        setRecent(data.filter((item) => item.context !== null));
      }
    }).catch((cause) => {

      if (!controller.signal.aborted) {

        const problem = aiProblem(cause);

        if (problem.sessionExpired) onSessionExpired?.();

        setRecentError(problem.message);

      }

    }).finally(() => {

      if (!controller.signal.aborted) setRecentLoading(false);

    });

    return () => controller.abort();

  }, [visible, key, sessionState]);



  useEffect(() => {

    if (sessionState === "ready" || sessionState === "loading") return;

    operationRef.current += 1;

    setRecent([]);

    setConversation(null);

    setResult(null);

    setResolvedContext(null);

    setStatus("idle");

  }, [sessionState]);



  useEffect(() => {

    if (!visible) operationRef.current += 1;

  }, [visible]);



  useEffect(() => () => { operationRef.current += 1; }, []);

useEffect(() => {
  if (!open || panelScreen !== "chat") return;

  const element = chatScrollRef.current;
  if (!element) return;

  if (shouldAutoScrollRef.current) {
    element.scrollTop = element.scrollHeight;
  }
}, [
  open,
  panelScreen,
  conversation,
  result,
  status,
  error,
]);

  useEffect(() => {

    if (!visible) return;



    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onCloseRef.current();
      }
    }



    window.addEventListener("keydown", handleKeyDown);



    return () => {

      window.removeEventListener("keydown", handleKeyDown);

    };

  }, [visible]);

useEffect(() => {
  if (!open || sessionState !== "ready") return;

  let stored: {
    contextKey: string | null;
    conversationId: string;
  };

  try {
    const raw = sessionStorage.getItem(
      AI_CONVERSATION_STORAGE_KEY,
    );

    if (!raw) return;

    stored = JSON.parse(raw);

    if (
      typeof stored.conversationId !== "string" ||
      stored.contextKey !== key
    ) {
      return;
    }
  } catch {
    return;
  }

  const operation = ++operationRef.current;
  let cancelled = false;

  setStatus("loading");

  void getConversation(stored.conversationId)
    .then(({ data }) => {
      if (
        cancelled ||
        operationRef.current !== operation ||
        !activeRef.current.open
      ) {
        return;
      }

      if (
        data.conversation_id !== stored.conversationId ||
        !data.context ||
        data.current_context_revision !== data.context.context_revision
      ) {
        throw new Error("저장된 대화의 식별 정보가 일치하지 않습니다.");
      }

      activeRef.current.conversationId = data.conversation_id;
      activeRef.current.revision = data.current_context_revision;

      setConversation(data);
      setResolvedContext(data.context);
      setResult(latestSavedAssistant(data.messages));
      setStatus("loaded");
      shouldAutoScrollRef.current = true;
    })
    .catch((cause: unknown) => {
      if (cancelled || operationRef.current !== operation) return;

      const problem = aiProblem(cause);

      if (problem.sessionExpired) {
        onSessionExpired?.();
      }

      setError(problem.message);
      setStatus("error");
    });

  return () => {
    cancelled = true;
  };
}, [open, key, sessionState]);

  async function runAnalysis(question?: string) {

    const targetContext = resolvedContext ? contextInput(resolvedContext) : context;

    if (!targetContext || sessionState !== "ready" || status === "loading" || status === "creating" || status === "analyzing") return;

    const targetKey = contextIdentity(targetContext);

    const requestSnapshot = {

      sequence: ++operationRef.current,

      context: targetContext,

      key,

      targetKey,

      conversationId: conversation?.conversation_id ?? null,

      revision: conversation?.current_context_revision ?? 0,

    };

    if (conversation && (!conversation.context || contextIdentity(conversation.context) !== requestSnapshot.targetKey)) {

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

        if (!created.context || contextIdentity(created.context) !== requestSnapshot.targetKey ||

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

      const naturalQuestion = question?.trim();

      const analyzed = (
        await (
          naturalQuestion
            ? appendNaturalQuestion(
                analysisSnapshot.conversationId,
                analysisSnapshot.context as Extract<
                  ConversationContext,
                  { targetType: "PRODUCT" }
                >,
                analysisSnapshot.revision,
                naturalQuestion,
              )
            : appendAnalysis(
                analysisSnapshot.conversationId,
                analysisSnapshot.context,
                analysisSnapshot.revision,
                "INSPECT_TARGET",
                analysisKind,
              )
        )
      ).data;

      if (!isCurrent(analysisSnapshot)) return;

      const assistant = latestLinkedAssistant(analyzed.messages, analysisSnapshot.revision, analysisSnapshot.targetKey);

      if (analyzed.conversation_id !== analysisSnapshot.conversationId || !assistant ||

        !analyzed.context || contextIdentity(analyzed.context) !== analysisSnapshot.targetKey ||

        analyzed.current_context_revision !== analysisSnapshot.revision) {

        throw new Error("분석 응답의 대화·요청 identity가 일치하지 않습니다.");

      }

      setConversation(analyzed);
      setResult(assistant);
      setStatus("loaded");

      if (naturalQuestion) {
        setSearchDraft("");
        shouldAutoScrollRef.current = true;
      }

      setRecent((items) => [analyzed, ...items.filter((item) => item.conversation_id !== analyzed.conversation_id)]);

    } catch (cause) {

      if (!isCurrent(analysisSnapshot)) return;

      const problem = aiProblem(cause);

      if (problem.sessionExpired) onSessionExpired?.();

      setError(problem.message);

      setStatus("error");

    }

  }



  async function runProductSearch(event: FormEvent<HTMLFormElement>) {

    event.preventDefault();

    const query = searchDraft.trim();

    if (!query || sessionState !== "ready" || status === "analyzing" || status === "creating") return;

    const operation = ++operationRef.current;

    const originalConversation = conversation?.context?.target_type === "PRODUCT" ? conversation : null;

    setStatus("analyzing");

    setError("");

    try {

      const response = originalConversation ?

        await appendProductSearch(originalConversation.conversation_id, query,

          originalConversation.current_context_revision) :

        await createProductSearchConversation(query);

      if (operationRef.current !== operation || !activeRef.current.open || activeRef.current.key !== key) return;

      const found = response.data;

      if (!found.context || found.context.target_type !== "PRODUCT" ||

        (originalConversation && found.conversation_id !== originalConversation.conversation_id)) {

        throw new Error("Product 검색 응답의 대상이 일치하지 않습니다.");

      }

      activeRef.current.conversationId = found.conversation_id;

      activeRef.current.revision = found.current_context_revision;

      setResolvedContext(found.context);

      setConversation(found);

      setResult(latestSavedAssistant(found.messages));

      setStatus("loaded");

      setSearchDraft("");

      setRecent((items) => [found, ...items.filter((item) => item.conversation_id !== found.conversation_id)]);

    } catch (cause) {

      if (operationRef.current !== operation || !activeRef.current.open || activeRef.current.key !== key) return;

      const problem = aiProblem(cause);

      if (problem.sessionExpired) onSessionExpired?.();

      setError(problem.message);

      setStatus("error");

    }

  }

async function openRecentConversations() {
  if (sessionState !== "ready") return;

  setPanelScreen("history");
  setRecentLoading(true);
  setRecentError("");

  try {
    const response = await getConversations();

    if (!activeRef.current.open) return;

    setRecent(
      response.data.filter((item) => item.context !== null),
    );
  } catch (cause) {
    if (!activeRef.current.open) return;

    const problem = aiProblem(cause);
    if (problem.sessionExpired) onSessionExpired?.();
    setRecentError(problem.message);
  } finally {
    if (activeRef.current.open) {
      setRecentLoading(false);
    }
  }
}

  async function selectConversation(item: ConversationView) {

    if (sessionState !== "ready") return;

    const operation = ++operationRef.current;

    setStatus("loading");

    setError("");

    try {

      const restored = (await reopenConversation(item.conversation_id)).data;

      if (operationRef.current !== operation || !activeRef.current.open || activeRef.current.key !== key) return;

      if (
        restored.conversation_id !== item.conversation_id ||
        !restored.context ||
        restored.context.context_revision !== restored.current_context_revision
      ) {
        throw new Error("재열기 응답의 대화 범위가 일치하지 않습니다.");
      }

      activeRef.current.conversationId = restored.conversation_id;

      activeRef.current.revision = restored.current_context_revision;

      setConversation(restored);

      setResolvedContext(restored.context);

      const assistant = latestSavedAssistant(restored.messages);

      setResult(assistant);

      setStatus(assistant ? "loaded" : "idle");
      shouldAutoScrollRef.current = true;
      setPanelScreen("chat");

      setRecent((items) => items.map((current) => current.conversation_id === restored.conversation_id ? restored : current));

    } catch (cause) {

      if (operationRef.current !== operation || !activeRef.current.open || activeRef.current.key !== key) return;

      const problem = aiProblem(cause);

      if (problem.sessionExpired) onSessionExpired?.();

      setError(problem.message);

      setStatus("error");

    }

  }

function handleChatScroll() {
  const element = chatScrollRef.current;
  if (!element) return;

  const distanceFromBottom =
    element.scrollHeight -
    element.scrollTop -
    element.clientHeight;

  shouldAutoScrollRef.current = distanceFromBottom < 80;
}

  function startNewConversation() {
    try {
      sessionStorage.removeItem(AI_CONVERSATION_STORAGE_KEY);
    } catch {
      // 저장소를 사용할 수 없는 환경은 무시
    }
    operationRef.current += 1;

    activeRef.current.conversationId = null;

    activeRef.current.revision = 0;

    setConversation(null);

    setResolvedContext(null);

    setResult(null);

    setError("");

    setStatus("idle");

    setPanelScreen("chat");

  }



  if (!visible) return null;



  const displayContext = resolvedContext ? contextInput(resolvedContext) : context;

  const isEntity = displayContext !== null && "targetType" in displayContext;

  const history = (conversation?.messages ?? [])

    .filter((message) => !isBootstrapMessage(message))

    .sort((a, b) => a.message_order - b.message_order);

  const synthetic = result?.evidence_ids.some((id) => id.startsWith("product-demand:SYNTHETIC_DEMO:")) ?? false;

  const statusLabel = result?.response_status === "ANSWER" ? "정상 분석 결과" :

    result?.response_status === "NO_EDGE" ? "확인된 관계 없음" : "판단 근거 부족 · 현재 분석 불가";



  const busy = status === "loading" || status === "creating" || status === "analyzing";
  const canAnalyze = displayContext !== null && sessionState === "ready" && !busy;
  const latestInHistory = result && history.some((message) => message.message_id === result.message_id);

  return (
    <aside
      ref={dialogRef}
      className={`common-ai-drawer common-ai-chat-shell${expanded ? " is-expanded" : ""}`}
      role="dialog"
      aria-modal="false"
      aria-labelledby="common-ai-title"
    >
      <header className="common-ai-header common-ai-chat-header">
        <div className="common-ai-header-main">
          {panelScreen === "history" ? (
            <button type="button" className="common-ai-icon-button" aria-label="채팅으로 돌아가기"
              onClick={() => setPanelScreen("chat")}><ArrowLeft size={19} /></button>
          ) : (
            <span className="common-ai-brand-icon" aria-hidden="true"><Sparkles size={18} /></span>
          )}
          <div className="common-ai-heading">
            <h2 id="common-ai-title">{panelScreen === "history" ? "최근 대화" : "운영 AI"}</h2>
            <span className="common-ai-subtitle">{panelScreen === "history" ? "저장된 업무 대화" : "업무 분석 어시스턴트"}</span>
          </div>
        </div>
        <div className="common-ai-header-actions">
          <button
            type="button"
            className="common-ai-icon-button"
            aria-label={expanded ? "AI 패널 축소" : "AI 패널 확대"}
            title={expanded ? "축소" : "확대"}
            onClick={() => setExpanded((value) => !value)}
          >
            {expanded ? <Minimize2 size={19} /> : <Maximize2 size={19} />}
          </button>
          {panelScreen === "chat" && (
            <button type="button" className="common-ai-icon-button" aria-label="최근 대화 보기" title="최근 대화"
              onClick={() => void openRecentConversations()}><History size={19} /></button>
          )}
          <button type="button" className="common-ai-icon-button" aria-label="새 대화" title="새 대화"
            disabled={sessionState !== "ready"} onClick={startNewConversation}><SquarePen size={19} /></button>
          <button type="button" className="common-ai-icon-button" ref={closeButtonRef}
            aria-label="운영 AI 닫기" title="닫기" onClick={onClose}><X size={19} /></button>
        </div>
      </header>

      {sessionState !== "ready" ? (
        <div className="common-ai-chat-scroll" role="status">
          <div className="common-ai-session-notice">
            {sessionState === "loading" ? "Demo Session을 준비하는 중입니다." :
              sessionState === "needs-new" ? "Demo Session이 만료되었습니다." : "Demo Session을 사용할 수 없습니다."}
            {sessionState !== "loading" && onStartNewSession &&
              <button type="button" onClick={onStartNewSession}>새 Demo Session 시작</button>}
          </div>
        </div>
      ) : panelScreen === "history" ? (
        <div className="common-ai-chat-scroll common-ai-history-screen" aria-label="저장된 대화 목록">
          {recentLoading && <p role="status" className="common-ai-muted">최근 대화 조회 중입니다.</p>}
          {recentError && <p role="alert" className="common-ai-error">{recentError}</p>}
          {!recentLoading && !recentError && recent.length === 0 && (
            <div className="common-ai-empty"><History size={26} /><strong>저장된 대화가 없습니다</strong>
              <p>분석을 실행하거나 상품을 검색하면 기록을 이곳에서 확인할 수 있습니다.</p></div>
          )}
          {recent.length > 0 && (
            <ul className="common-ai-conversation-list">
              {recent.map((item) => (
                <li key={item.conversation_id}>
                  <button type="button" className="common-ai-conversation-row"
                    aria-current={conversation?.conversation_id === item.conversation_id ? "true" : undefined}
                    onClick={() => void selectConversation(item)}>
                    <span className="common-ai-conversation-name">{item.context?.target_label ?? item.context?.page ?? "업무 대화"}</span>
                    <span className="common-ai-conversation-meta">{item.conversation_status} · revision {item.current_context_revision}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : (
        <>
          <div
            ref={chatScrollRef}
            className="common-ai-chat-scroll"
            aria-label="운영 AI 대화 내용"
            onScroll={handleChatScroll}
          >
            {displayContext ? (
              <section className="common-ai-context-card" aria-label="현재 분석 범위">
                <div className="common-ai-context-kicker">현재 업무 Context</div>
                <strong>{isEntity ? displayContext.targetLabel : displayContext.page}</strong>
                <p>{isEntity
                  ? `${displayContext.targetType} · ${displayContext.source} · ${displayContext.asOf ?? "기준 시각 미확인"}`
                  : `적용 필터 ${Object.keys(displayContext.filters).length}개${displayContext.search ? ` · 검색 ${displayContext.search}` : ""}`}</p>
                {!isEntity && displayContext.date_range && <p>기간: {displayContext.date_range.from_date} ~ {displayContext.date_range.to_date}</p>}
              </section>
            ) : (
              <div className="common-ai-welcome"><span className="common-ai-welcome-icon"><Sparkles size={25} /></span>
                <h3>무엇을 확인할까요?</h3>
                <p>상품을 검색하거나 업무 화면에서 분석할 대상을 선택하세요.</p>
              </div>
            )}

            {history.length > 0 && (
              <ol className="common-ai-message-list">
                {history.map((message) => (
                  <li key={message.message_id} className={`common-ai-message ${message.role === "USER" ? "is-user" : "is-assistant"}`}>
                    {message.role === "ASSISTANT" && <div className="common-ai-message-author"><Sparkles size={14} /> 운영 AI</div>}
                    <div className="common-ai-bubble">
                      {message.role === "ASSISTANT" ? (
                        <AnalysisContent
                          content={message.content}
                          publicMode={publicMode}
                        />
                      ) : (
                        <p>{message.content}</p>
                      )}
                      {message.role === "ASSISTANT" && (
                        <>
                          <span className="common-ai-response-status">{message.response_status === "ANSWER" ? "분석 완료" : message.response_status === "NO_EDGE" ? "확인된 관계 없음" : "근거 부족 · 판단 보류"}</span>
                          <details className="common-ai-evidence-details">
                            <summary><FileText size={14} /> 근거 보기 <ChevronDown size={14} /></summary>
                            <div>{evidenceType(message)} · {message.evidence_ids.length}건</div>
                            {message.evidence_ids.length === 0 ? <p>연결된 근거 없음</p> :
                              publicMode ? <p>Demo의 근거 세부정보는 일부 제한됩니다.</p> :
                              <ul>{message.evidence_ids.map((id) => <li key={id}>{id}</li>)}</ul>}
                            {publicMode && message.analysis_kind === "RELATION_DOCUMENT" && <p>관계 경로 세부정보는 현재 Conversation API에서 제공하지 않습니다.</p>}
                          </details>
                        </>
                      )}
                    </div>
                  </li>
                ))}
              </ol>
            )}
            {result && !latestInHistory && (
              <div className="common-ai-message is-assistant" role="status">
                <div className="common-ai-message-author"><Sparkles size={14} /> 운영 AI</div>
                <div className="common-ai-bubble">
                  <AnalysisContent
                    content={result.content}
                    publicMode={publicMode}
                  />
                  <span className="common-ai-response-status">{statusLabel}</span>
                  {synthetic && <span className="common-ai-response-status">주문/판매 분석 · SYNTHETIC_DEMO</span>}
                  <details className="common-ai-evidence-details">
                    <summary><FileText size={14} /> 근거 보기 <ChevronDown size={14} /></summary>
                    <div>{evidenceType(result)} · {result.evidence_ids.length}건</div>
                    {result.evidence_ids.length === 0 ? <p>연결된 근거 없음</p> :
                      publicMode ? <p>Demo의 근거 세부정보는 일부 제한됩니다.</p> :
                      <ul>{result.evidence_ids.map((id) => <li key={id}>{id}</li>)}</ul>}
                    {publicMode && result.analysis_kind === "RELATION_DOCUMENT" && <p>관계 경로 세부정보는 현재 Conversation API에서 제공하지 않습니다.</p>}
                  </details>
                </div>
              </div>
            )}
            {status === "creating" && <p role="status" className="common-ai-muted">대화 생성 중입니다.</p>}
            {status === "loading" && <p role="status" className="common-ai-muted">대화 불러오는 중입니다.</p>}
            {status === "analyzing" && <p role="status" className="common-ai-muted">분석 중입니다.</p>}
            {status === "error" && <p role="alert" className="common-ai-error">{error}</p>}
          </div>
          <footer className="common-ai-chat-footer">
            {displayContext && (
              <div className="common-ai-analysis-tools">
                {isEntity && displayContext.targetType === "PRODUCT" && (
                  <label>분석 방식
                    <select aria-label="분석 방식" value={analysisKind} onChange={(event) => setAnalysisKind(event.target.value as AnalysisKind)}>
                      <option value="DETERMINISTIC">규칙 기반</option>
                      <option value="HYBRID">상품 근거 검색</option>
                      <option value="RELATION_DOCUMENT">관계 조회</option>
                    </select>
                  </label>
                )}
                <button type="button" className="common-ai-analysis-button" onClick={() => void runAnalysis()} disabled={!canAnalyze}>분석 실행</button>
              </div>
            )}
            {publicMode ? (
              <form
                className="common-ai-chat-composer"
                onSubmit={(event) => {
                  if (isEntity && displayContext.targetType === "PRODUCT") {
                    event.preventDefault();
                    if (searchDraft.trim() && !busy) {
                      shouldAutoScrollRef.current = true;
                      void runAnalysis(searchDraft.trim());
                    }
                  } else {
                    void runProductSearch(event);
                  }
                }}
              >
                <label className="common-ai-sr-only" htmlFor="common-ai-search-input">Demo 상품 검색</label>
                <input
                  id="common-ai-search-input"
                  aria-label={
                    isEntity && displayContext.targetType === "PRODUCT"
                      ? "운영 AI 질문"
                      : "Product 검색 질문"
                  }
                  placeholder={
                    isEntity && displayContext.targetType === "PRODUCT"
                      ? "이 상품 주문량이 어떻게 돼?"
                      : "상품명 또는 상품 코드를 입력하세요..."
                  }
                  value={searchDraft}
                  maxLength={isEntity && displayContext.targetType === "PRODUCT" ? 500 : 200}
                  onChange={(event) => setSearchDraft(event.target.value)}
                  disabled={sessionState !== "ready" || busy}
                />
                <button
                  type="submit"
                  aria-label={
                    isEntity && displayContext.targetType === "PRODUCT"
                      ? "질문 전송"
                      : "상품 검색 전송"
                  }
                  title="전송"
                  disabled={!searchDraft.trim() || busy}
                >
                  <Send size={18} />
                </button>
              </form>
            ) : (
              <div className="common-ai-chat-composer is-disabled">
                <input aria-label="후속 질문 입력" placeholder="자유 입력은 아직 연결되지 않았습니다" disabled />
                <button type="button" aria-label="전송 불가" disabled><Send size={18} /></button>
              </div>
            )}
            <p className="common-ai-composer-note">{publicMode
                ? isEntity && displayContext.targetType === "PRODUCT"
                  ? "현재 상품 질문 · 고객 개인정보와 주문 원문은 입력하지 마세요."
                  : "상품 검색 · 상품명 또는 상품 코드를 입력하세요."
              : "자유 입력은 미지원 · 분석 실행으로 현재 범위를 확인할 수 있습니다."}</p>
          </footer>
        </>
      )}
    </aside>
  );
}
