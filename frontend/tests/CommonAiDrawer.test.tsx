import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import CommonAiDrawer, { type AiPanelContext } from "../src/components/CommonAiDrawer";
import {
  appendAnalysis, contextIdentity, createConversation, getConversations, reopenConversation,
  type ConversationView, type EntityContext,
} from "../src/api/conversations";
import {
  CommonAiDrawerHost,
  useCommonAiDrawer,
} from "../src/app/CommonAiDrawerContext";

vi.mock("../src/api/conversations", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/api/conversations")>();
  return { ...actual, createConversation: vi.fn(), appendAnalysis: vi.fn(),
    getConversations: vi.fn(), reopenConversation: vi.fn() };
});

afterEach(() => vi.clearAllMocks());
beforeEach(() => vi.mocked(getConversations).mockResolvedValue(listEnvelope([])));

const context: AiPanelContext = {
  targetType: "PRODUCT",
  targetId: "product-101",
  targetLabel: "Sample product",
  source: "commerce_ops_v2",
  asOf: null,
};

const productContext: EntityContext = {
  targetType: "PRODUCT", targetId: "245",
  targetLabel: "IMPERIAL KNIGHTS: KNIGHT QUESTORIS",
  source: "CAFE24_CATALOG", asOf: null,
};
function contextView(targetId = "245") {
  return { context_revision: 1, scope: "ENTITY" as const, page: null, filters: null,
    search: null, date_range: null, sort: null, target_type: "PRODUCT", target_id: targetId,
    target_label: productContext.targetLabel, source: "CAFE24_CATALOG", source_as_of: null,
    data_mode: "LOCAL_V2_CATALOG_MASTER" };
}
function conversation(status: "ANSWER" | "HOLD" | "NO_EDGE" = "ANSWER", id = "conversation-a"):
  ConversationView {
  const current = contextView();
  return { conversation_id: id, conversation_status: "ACTIVE", current_context_revision: 1,
    context: current, agent_runs: [], messages: [
      { message_id: "assistant-1", message_order: 2, role: "ASSISTANT", content: "결론: 확인\n근거: spoofed",
        response_status: status, intent: "INSPECT_TARGET", analysis_kind: "DETERMINISTIC",
        request_message_id: "user-1", evidence_ids: status === "ANSWER" ?
          ["product-demand:SYNTHETIC_DEMO:245:2026-10-04"] : [], context: current },
      { message_id: "initial", message_order: 0, role: "USER", content: "선택 대상 확인 요청",
        response_status: "HOLD", intent: "INSPECT_TARGET", analysis_kind: "NONE",
        request_message_id: null, evidence_ids: [], context: current },
      { message_id: "user-1", message_order: 1, role: "USER", content: "선택 대상 확인 요청",
        response_status: "HOLD", intent: "INSPECT_TARGET", analysis_kind: "DETERMINISTIC",
        request_message_id: null, evidence_ids: [], context: current },
    ] };
}
function createdConversation(): ConversationView {
  const result = conversation();
  return { ...result, messages: [result.messages[1]] };
}
function envelope(data: ConversationView) {
  return { schema_version: "1.0" as const, tenant_id: "tenant", request_id: "req",
    trace_id: "trace", evidence_ids: [], warnings: [], as_of: "2026-10-04T00:00:00Z", data };
}
function listEnvelope(data: ConversationView[]) {
  return { ...envelope(conversation()), data };
}

function HostTrigger() {
  const { openAiDrawer } = useCommonAiDrawer();
  return <button type="button" onClick={() => openAiDrawer(context)}>대상 열기</button>;
}

describe("Common AI Drawer shell", () => {
  it("does not render in CLOSED state", () => {
    render(<CommonAiDrawer open={false} context={null} onClose={() => {}} />);
    expect(screen.queryByRole("dialog", { name: "운영 AI" })).not.toBeInTheDocument();
  });

  it("shows only context and idle shell, preserving unknown time", () => {
    const extended = { ...context, request_id: "internal-request", trace_id: "internal-trace" };
    render(<CommonAiDrawer open context={extended} onClose={() => {}} />);
    const dialog = screen.getByRole("dialog", { name: "운영 AI" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    for (const value of ["Sample product", "PRODUCT", "product-101", "commerce_ops_v2", "기준 시각 미확인",
      "아직 분석을 실행하지 않았습니다.", "연결된 근거 없음", "현재 context 기준 후속 확인 없음",
      "C09 자유 입력은 아직 연결되지 않았습니다. 같은 범위는 분석 실행으로 다시 확인할 수 있습니다."]) {
      expect(within(dialog).getByText(value)).toBeInTheDocument();
    }
    expect(within(dialog).getByRole("textbox", { name: "후속 질문 입력" })).toBeDisabled();
    expect(within(dialog).getByRole("button", { name: "전송" })).toBeDisabled();
    expect(dialog).not.toHaveTextContent("internal-request");
    expect(dialog).not.toHaveTextContent("internal-trace");
    expect(dialog).not.toHaveTextContent("request_id");
    expect(dialog).not.toHaveTextContent("trace_id");
  });

  it("shows a provided data timestamp without replacing it", () => {
    render(<CommonAiDrawer open context={{ ...context, asOf: "2026-09-11T06:00:00Z" }} onClose={() => {}} />);
    expect(screen.getByText("2026-09-11T06:00:00Z")).toHaveAttribute("datetime", "2026-09-11T06:00:00Z");
  });

  it("uses one App-level host, traps focus, and restores the opener after Escape", () => {
    render(<CommonAiDrawerHost><HostTrigger /></CommonAiDrawerHost>);
    const opener = screen.getByRole("button", { name: "대상 열기" });
    opener.focus();
    fireEvent.click(opener);
    const dialog = screen.getByRole("dialog", { name: "운영 AI" });
    expect(screen.getAllByRole("dialog")).toHaveLength(1);
    const close = within(dialog).getByRole("button", { name: "운영 AI 패널 닫기" });
    expect(close).toHaveFocus();
    fireEvent.keyDown(window, { key: "Tab" });
    expect(close).toHaveFocus();
    fireEvent.keyDown(window, { key: "Tab", shiftKey: true });
    expect(within(dialog).getByRole("button", { name: "분석 실행" })).toHaveFocus();
    opener.focus();
    fireEvent.keyDown(window, { key: "Tab" });
    expect(close).toHaveFocus();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("dialog", { name: "운영 AI" })).not.toBeInTheDocument();
    expect(opener).toHaveFocus();
  });

  it("closes through backdrop and returns focus", () => {
    render(<CommonAiDrawerHost><HostTrigger /></CommonAiDrawerHost>);
    const opener = screen.getByRole("button", { name: "대상 열기" });
    opener.focus();
    fireEvent.click(opener);
    fireEvent.click(screen.getByRole("button", { name: "운영 AI 패널 배경 닫기" }));
    expect(screen.queryByRole("dialog", { name: "운영 AI" })).not.toBeInTheDocument();
    expect(opener).toHaveFocus();
    fireEvent.click(opener);
    fireEvent.click(screen.getByRole("button", { name: "운영 AI 패널 닫기" }));
    expect(screen.queryByRole("dialog", { name: "운영 AI" })).not.toBeInTheDocument();
    expect(opener).toHaveFocus();
  });
});

describe("C09 conversation drawer", () => {
  it("keeps PRODUCT number and opens without creating or analyzing", () => {
    render(<CommonAiDrawer open context={productContext} onClose={() => {}} />);
    expect(screen.getByText("245")).toBeInTheDocument();
    expect(contextIdentity(productContext)).toBe(contextIdentity(contextView()));
    expect(createConversation).not.toHaveBeenCalled();
    expect(appendAnalysis).not.toHaveBeenCalled();
  });

  it("lists multiple conversations for one product and reopens one without analysis", async () => {
    const first = conversation("ANSWER", "conversation-a");
    const second = conversation("HOLD", "conversation-b");
    vi.mocked(getConversations).mockResolvedValue(listEnvelope([first, second]));
    vi.mocked(reopenConversation).mockResolvedValue(envelope(second));
    render(<CommonAiDrawer open context={productContext} onClose={() => {}} />);
    const recent = screen.getByRole("region", { name: "최근 대화" });
    await waitFor(() => expect(within(recent).getAllByRole("button", { name: /conversation-/ })).toHaveLength(2));
    fireEvent.click(within(recent).getByRole("button", { name: /conversation-b/ }));
    await waitFor(() => expect(reopenConversation).toHaveBeenCalledWith("conversation-b"));
    expect(createConversation).not.toHaveBeenCalled();
    expect(appendAnalysis).not.toHaveBeenCalled();
    const history = screen.getByRole("region", { name: "대화 History" });
    await waitFor(() => expect(history.querySelectorAll("ol > li")).toHaveLength(2));
    expect(within(history).getAllByText("선택 대상 확인 요청")).toHaveLength(1);
    expect(history.querySelectorAll("ol > li")[1]).toHaveTextContent("분석 · HOLD");
    expect(screen.getByText("판단 근거 부족 · 현재 분석 불가")).toBeInTheDocument();
  });

  it("appends to the selected conversation, then creates a new one after explicit reset", async () => {
    const first = conversation("ANSWER", "conversation-a");
    const second = conversation("NO_EDGE", "conversation-b");
    vi.mocked(getConversations).mockResolvedValue(listEnvelope([first, second]));
    vi.mocked(reopenConversation).mockResolvedValue(envelope(first));
    vi.mocked(appendAnalysis).mockResolvedValue(envelope(first));
    vi.mocked(createConversation).mockResolvedValue(envelope(createdConversation()));
    render(<CommonAiDrawer open context={productContext} onClose={() => {}} />);
    const recent = screen.getByRole("region", { name: "최근 대화" });
    fireEvent.click(await within(recent).findByRole("button", { name: /conversation-a/ }));
    await waitFor(() => expect(screen.getByText("정상 분석 결과")).toBeInTheDocument());
    expect(screen.getByRole("region", { name: "대화 History" })).toHaveTextContent("product-demand:SYNTHETIC_DEMO:245:2026-10-04");
    fireEvent.click(screen.getByRole("button", { name: "분석 실행" }));
    await waitFor(() => expect(appendAnalysis).toHaveBeenCalledWith(
      "conversation-a", productContext, 1, "INSPECT_TARGET", "DETERMINISTIC",
    ));
    expect(createConversation).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "새 대화" }));
    expect(screen.getByText("아직 분석을 실행하지 않았습니다.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "분석 실행" }));
    await waitFor(() => expect(createConversation).toHaveBeenCalledWith(productContext));
  });

  it("restores a NO_EDGE result and its ordered history", async () => {
    const saved = conversation("NO_EDGE");
    vi.mocked(getConversations).mockResolvedValue(listEnvelope([saved]));
    vi.mocked(reopenConversation).mockResolvedValue(envelope(saved));
    render(<CommonAiDrawer open context={productContext} onClose={() => {}} />);
    fireEvent.click(await screen.findByRole("button", { name: /conversation-a/ }));
    expect(await screen.findByText("확인된 관계 없음")).toBeInTheDocument();
    expect(appendAnalysis).not.toHaveBeenCalled();
    const turns = screen.getByRole("region", { name: "대화 History" }).querySelectorAll("ol > li");
    expect(Array.from(turns, (turn) => turn.querySelector("strong")?.textContent)).toEqual(["요청 · HOLD", "분석 · NO_EDGE"]);
  });

  it.each(["ANSWER", "HOLD", "NO_EDGE"] as const)(
    "restores a saved %s assistant from an older valid revision", async (responseStatus) => {
      const old = conversation(responseStatus);
      const current = { ...contextView(), context_revision: 2 };
      const saved = { ...old, context: current, current_context_revision: 2 };
      vi.mocked(getConversations).mockResolvedValue(listEnvelope([saved]));
      vi.mocked(reopenConversation).mockResolvedValue(envelope(saved));
      render(<CommonAiDrawer open context={productContext} onClose={() => {}} />);
      fireEvent.click(await screen.findByRole("button", { name: /conversation-a/ }));
      const result = screen.getByRole("region", { name: "분석 결과" });
      const label = responseStatus === "ANSWER" ? "정상 분석 결과" : responseStatus === "HOLD" ?
        "판단 근거 부족 · 현재 분석 불가" : "확인된 관계 없음";
      expect(await within(result).findByText(label)).toBeInTheDocument();
      expect(within(result).getByText(/결론: 확인/)).toBeInTheDocument();
      expect(screen.getByRole("region", { name: "대화 History" })).toHaveTextContent("결론: 확인");
      if (responseStatus === "ANSWER") {
        expect(screen.getByRole("region", { name: "근거" })).toHaveTextContent(
          "product-demand:SYNTHETIC_DEMO:245:2026-10-04",
        );
        expect(within(result).getByText("주문/판매 분석 · Demo synthetic data")).toBeInTheDocument();
      }
      expect(appendAnalysis).not.toHaveBeenCalled();
    },
  );

  it("uses the highest message_order assistant, not response array order or bootstrap USER", async () => {
    const saved = conversation();
    const newest = { ...saved.messages[0], message_id: "assistant-2", message_order: 4,
      content: "최신 판단 보류", response_status: "HOLD" as const,
      request_message_id: "user-2", evidence_ids: ["latest-evidence"] };
    saved.messages = [newest, ...saved.messages, { ...saved.messages[2], message_id: "user-2", message_order: 3 }];
    vi.mocked(getConversations).mockResolvedValue(listEnvelope([saved]));
    vi.mocked(reopenConversation).mockResolvedValue(envelope(saved));
    render(<CommonAiDrawer open context={productContext} onClose={() => {}} />);
    fireEvent.click(await screen.findByRole("button", { name: /conversation-a/ }));
    const result = screen.getByRole("region", { name: "분석 결과" });
    expect(await within(result).findByText("최신 판단 보류")).toBeInTheDocument();
    expect(within(result).getByText("판단 근거 부족 · 현재 분석 불가")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "근거" })).toHaveTextContent("latest-evidence");
    expect(within(result).queryByText("주문/판매 분석 · Demo synthetic data")).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: "대화 History" }).querySelectorAll("ol > li")).toHaveLength(4);
  });

  it("does not restore the bootstrap USER as an analysis result", async () => {
    const saved = createdConversation();
    vi.mocked(getConversations).mockResolvedValue(listEnvelope([saved]));
    vi.mocked(reopenConversation).mockResolvedValue(envelope(saved));
    render(<CommonAiDrawer open context={productContext} onClose={() => {}} />);
    fireEvent.click(await screen.findByRole("button", { name: /conversation-a/ }));
    expect(await screen.findByText("아직 분석을 실행하지 않았습니다.")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "대화 History" })).toHaveTextContent("저장된 대화가 없습니다.");
  });

  it("rejects a reopen response whose context revision conflicts with its conversation revision", async () => {
    const saved = conversation();
    vi.mocked(getConversations).mockResolvedValue(listEnvelope([saved]));
    vi.mocked(reopenConversation).mockResolvedValue(envelope({ ...saved, current_context_revision: 2 }));
    render(<CommonAiDrawer open context={productContext} onClose={() => {}} />);
    fireEvent.click(await screen.findByRole("button", { name: /conversation-a/ }));
    expect(await screen.findByRole("alert", { name: "" })).toHaveTextContent("재열기 응답의 대화 범위가 일치하지 않습니다.");
    expect(screen.getByRole("region", { name: "대화 History" })).toHaveTextContent("저장된 대화가 없습니다.");
  });

  it("does not apply a late reopen after choosing a new conversation", async () => {
    const saved = conversation();
    let finish!: (value: ReturnType<typeof envelope>) => void;
    vi.mocked(getConversations).mockResolvedValue(listEnvelope([saved]));
    vi.mocked(reopenConversation).mockReturnValue(new Promise((resolve) => { finish = resolve; }));
    render(<CommonAiDrawer open context={productContext} onClose={() => {}} />);
    fireEvent.click(await screen.findByRole("button", { name: /conversation-a/ }));
    fireEvent.click(screen.getByRole("button", { name: "새 대화" }));
    await act(async () => finish(envelope(saved)));
    expect(screen.getByText("아직 분석을 실행하지 않았습니다.")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "대화 History" })).toHaveTextContent("저장된 대화가 없습니다.");
  });

  it("keeps conversation B selected when conversation A analysis finishes late", async () => {
    const first = conversation("ANSWER", "conversation-a");
    const second = conversation("NO_EDGE", "conversation-b");
    let finish!: (value: ReturnType<typeof envelope>) => void;
    vi.mocked(getConversations).mockResolvedValue(listEnvelope([first, second]));
    vi.mocked(reopenConversation).mockImplementation(async (id) => envelope(id === "conversation-a" ? first : second));
    vi.mocked(appendAnalysis).mockReturnValue(new Promise((resolve) => { finish = resolve; }));
    render(<CommonAiDrawer open context={productContext} onClose={() => {}} />);
    const recent = screen.getByRole("region", { name: "최근 대화" });
    fireEvent.click(await within(recent).findByRole("button", { name: /conversation-a/ }));
    await waitFor(() => expect(screen.getByText("정상 분석 결과")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "분석 실행" }));
    await waitFor(() => expect(appendAnalysis).toHaveBeenCalled());
    fireEvent.click(within(recent).getByRole("button", { name: /conversation-b/ }));
    await waitFor(() => expect(within(recent).getByRole("button", { name: /conversation-b/ })).toHaveAttribute("aria-pressed", "true"));
    await act(async () => finish(envelope(first)));
    expect(screen.getByText("확인된 관계 없음")).toBeInTheDocument();
    expect(within(recent).getByRole("button", { name: /conversation-a/ })).toHaveAttribute("aria-pressed", "false");
  });

  it("reopens A after A to B to A and appends to A despite its older late response", async () => {
    const targetA = { ...productContext, targetId: "1757", targetLabel: "A" };
    const targetB = { ...productContext, targetId: "1614", targetLabel: "B" };
    const forTarget = (id: string, targetId: string) => {
      const saved = conversation("ANSWER", id);
      const scoped = { ...contextView(targetId), target_label: targetId === "1757" ? "A" : "B" };
      return { ...saved, context: scoped, messages: saved.messages.map((message) =>
        ({ ...message, content: message.role === "ASSISTANT" ? `${targetId} 분석 결과` : message.content,
          context: scoped })) };
    };
    const savedA = forTarget("conversation-a", "1757");
    const savedB = forTarget("conversation-b", "1614");
    let finishA!: (value: ReturnType<typeof envelope>) => void;
    vi.mocked(getConversations).mockResolvedValue(listEnvelope([savedA, savedB]));
    vi.mocked(createConversation).mockImplementation(async (input) => envelope(
      input.scope === "VIEW" || input.targetId === "1757" ?
        { ...savedA, messages: [savedA.messages[1]] } : { ...savedB, messages: [savedB.messages[1]] },
    ));
    vi.mocked(appendAnalysis).mockImplementation((id) => id === "conversation-a" &&
      vi.mocked(appendAnalysis).mock.calls.filter(([calledId]) => calledId === id).length === 1 ?
      new Promise((resolve) => { finishA = resolve; }) : Promise.resolve(envelope(id === "conversation-a" ? savedA : savedB)));
    vi.mocked(reopenConversation).mockResolvedValue(envelope(savedA));
    function SwitchTargets() {
      const drawer = useCommonAiDrawer();
      return <><button onClick={() => drawer.openAiDrawer(targetA)}>A 열기</button>
        <button onClick={() => drawer.openAiDrawer(targetB)}>B 열기</button></>;
    }
    render(<CommonAiDrawerHost><SwitchTargets /></CommonAiDrawerHost>);
    fireEvent.click(screen.getByRole("button", { name: "A 열기" }));
    fireEvent.click(screen.getByRole("button", { name: "분석 실행" }));
    await waitFor(() => expect(appendAnalysis).toHaveBeenCalledWith(
      "conversation-a", targetA, 1, "INSPECT_TARGET", "DETERMINISTIC",
    ));
    fireEvent.click(screen.getByRole("button", { name: "B 열기" }));
    fireEvent.click(screen.getByRole("button", { name: "분석 실행" }));
    await waitFor(() => expect(appendAnalysis).toHaveBeenCalledWith(
      "conversation-b", targetB, 1, "INSPECT_TARGET", "DETERMINISTIC",
    ));
    await act(async () => finishA(envelope(savedA)));
    expect(screen.getByText("B", { selector: "strong" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "A 열기" }));
    const recent = screen.getByRole("region", { name: "최근 대화" });
    fireEvent.click(await within(recent).findByRole("button", { name: /conversation-a/ }));
    await waitFor(() => expect(within(recent).getByRole("button", { name: /conversation-a/ })).toHaveAttribute("aria-pressed", "true"));
    expect(within(screen.getByRole("region", { name: "분석 결과" })).getByText("1757 분석 결과")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "대화 History" })).toHaveTextContent("1757 분석 결과");
    fireEvent.click(screen.getByRole("button", { name: "분석 실행" }));
    await waitFor(() => expect(vi.mocked(appendAnalysis).mock.calls.filter(([id]) => id === "conversation-a")).toHaveLength(2));
    expect(createConversation).toHaveBeenCalledTimes(2);
  });

  it("finishes A create and messages after switching to B, then restores A from saved history", async () => {
    const targetA = { ...productContext, targetId: "2111", targetLabel: "A" };
    const targetB = { ...productContext, targetId: "2048", targetLabel: "B" };
    const scoped = (id: string, targetId: string) => {
      const saved = conversation("ANSWER", id);
      const current = { ...contextView(targetId), target_label: targetId === "2111" ? "A" : "B" };
      return { ...saved, context: current, messages: saved.messages.map((message) =>
        ({ ...message, content: message.role === "ASSISTANT" ? `${targetId} result` : message.content,
          context: current })) };
    };
    const fullA = scoped("conversation-a", "2111");
    const fullB = scoped("conversation-b", "2048");
    const createdA = { ...fullA, messages: [fullA.messages[1]] };
    const createdB = { ...fullB, messages: [fullB.messages[1]] };
    let storedA: ConversationView | null = null;
    let finishCreateA!: (value: ReturnType<typeof envelope>) => void;
    let finishAppendA!: (value: ReturnType<typeof envelope>) => void;
    vi.mocked(getConversations).mockImplementation(async () => listEnvelope(
      storedA ? [storedA, fullB] : [fullB],
    ));
    vi.mocked(createConversation).mockImplementation((input) =>
      input.scope !== "VIEW" && input.targetId === "2111" ?
        new Promise((resolve) => { finishCreateA = resolve; }) : Promise.resolve(envelope(createdB)));
    vi.mocked(appendAnalysis).mockImplementation((id) => id === "conversation-a" &&
      vi.mocked(appendAnalysis).mock.calls.filter(([calledId]) => calledId === id).length === 1 ?
      new Promise((resolve) => { finishAppendA = resolve; }) : Promise.resolve(envelope(id === "conversation-a" ? fullA : fullB)));
    vi.mocked(reopenConversation).mockImplementation(async () => envelope(storedA ?? createdA));
    function SwitchTargets() {
      const drawer = useCommonAiDrawer();
      return <><button onClick={() => drawer.openAiDrawer(targetA)}>A 열기</button>
        <button onClick={() => drawer.openAiDrawer(targetB)}>B 열기</button></>;
    }
    render(<CommonAiDrawerHost><SwitchTargets /></CommonAiDrawerHost>);
    fireEvent.click(screen.getByRole("button", { name: "A 열기" }));
    fireEvent.click(screen.getByRole("button", { name: "분석 실행" }));
    await waitFor(() => expect(createConversation).toHaveBeenCalledWith(targetA));
    fireEvent.click(screen.getByRole("button", { name: "B 열기" }));
    fireEvent.click(screen.getByRole("button", { name: "분석 실행" }));
    expect(await screen.findByText("2048 result", { selector: ".common-ai-answer" })).toBeInTheDocument();
    await act(async () => finishCreateA(envelope(createdA)));
    await waitFor(() => expect(appendAnalysis).toHaveBeenCalledWith(
      "conversation-a", targetA, 1, "INSPECT_TARGET", "DETERMINISTIC",
    ));
    expect(vi.mocked(appendAnalysis).mock.calls.find(([id]) => id === "conversation-a")).toHaveLength(5);
    await act(async () => { storedA = fullA; finishAppendA(envelope(fullA)); });
    expect(screen.getByText("2048 result", { selector: ".common-ai-answer" })).toBeInTheDocument();
    expect(fullA.messages.some((message) => message.role === "USER" && message.analysis_kind === "DETERMINISTIC")).toBe(true);
    expect(fullA.messages.some((message) => message.role === "ASSISTANT" && message.request_message_id === "user-1")).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "A 열기" }));
    fireEvent.click(await screen.findByRole("button", { name: /conversation-a/ }));
    expect(await screen.findByText("2111 result", { selector: ".common-ai-answer" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "대화 History" })).toHaveTextContent("2111 result");
    fireEvent.click(screen.getByRole("button", { name: "분석 실행" }));
    await waitFor(() => expect(vi.mocked(appendAnalysis).mock.calls.filter(([id]) => id === "conversation-a")).toHaveLength(2));
    expect(createConversation).toHaveBeenCalledTimes(2);
  });

  it("shows VIEW scope with empty filters and no automatic request", () => {
    render(<CommonAiDrawer open context={{ scope: "VIEW", page: "PRODUCT_INVENTORY", filters: {} }}
      onClose={() => {}} />);
    expect(screen.getByText("PRODUCT_INVENTORY", { selector: "dd" })).toBeInTheDocument();
    expect(screen.getByText("없음")).toBeInTheDocument();
    expect(createConversation).not.toHaveBeenCalled();
  });

  it("creates, appends with revision 1, and renders structured evidence and ordered history", async () => {
    vi.mocked(createConversation).mockResolvedValue(envelope(createdConversation()));
    vi.mocked(appendAnalysis).mockResolvedValue(envelope(conversation()));
    render(<CommonAiDrawer open context={productContext} onClose={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: "분석 실행" }));
    await waitFor(() => expect(screen.getByText("정상 분석 결과")).toBeInTheDocument());
    expect(createConversation).toHaveBeenCalledWith(productContext);
    expect(appendAnalysis).toHaveBeenCalledWith(
      "conversation-a", productContext, 1, "INSPECT_TARGET", "DETERMINISTIC",
    );
    const evidence = screen.getByRole("region", { name: "근거" });
    expect(within(evidence).getByText("product-demand:SYNTHETIC_DEMO:245:2026-10-04")).toBeInTheDocument();
    expect(within(evidence).queryByText("spoofed")).not.toBeInTheDocument();
    expect(screen.getByText("주문/판매 분석 · Demo synthetic data")).toBeInTheDocument();
    const history = screen.getByRole("region", { name: "대화 History" });
    const turns = Array.from(history.querySelectorAll("ol > li"));
    expect(turns.map((item) => item.querySelector("strong")?.textContent))
      .toEqual(["요청 · HOLD", "분석 · ANSWER"]);
    expect(within(history).getAllByText("선택 대상 확인 요청")).toHaveLength(1);
    expect(turns[1]).toHaveTextContent("product-demand:SYNTHETIC_DEMO:245:2026-10-04");
    expect(screen.queryByText(/재고 부족 확정|품절 예상 확정|재고 위험 수치/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "분석 실행" }));
    await waitFor(() => expect(appendAnalysis).toHaveBeenCalledTimes(2));
    expect(createConversation).toHaveBeenCalledTimes(1);
  });

  it.each(["HYBRID", "RELATION_DOCUMENT"] as const)("keeps %s analysis requests in history", async (kind) => {
    vi.mocked(createConversation).mockResolvedValue(envelope(createdConversation()));
    const analyzed = conversation();
    analyzed.messages = analyzed.messages.map((message) => message.analysis_kind === "DETERMINISTIC" ?
      { ...message, analysis_kind: kind } : message);
    vi.mocked(appendAnalysis).mockResolvedValue(envelope(analyzed));
    render(<CommonAiDrawer open context={productContext} onClose={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: "분석 실행" }));
    await waitFor(() => expect(screen.getByText("정상 분석 결과")).toBeInTheDocument());
    const history = screen.getByRole("region", { name: "대화 History" });
    expect(history.querySelectorAll("ol > li")).toHaveLength(2);
    expect(within(history).getAllByText("선택 대상 확인 요청")).toHaveLength(1);
  });

  it.each(["HOLD", "NO_EDGE"] as const)("treats %s as a normal result", async (status) => {
    vi.mocked(createConversation).mockResolvedValue(envelope(createdConversation()));
    vi.mocked(appendAnalysis).mockResolvedValue(envelope(conversation(status)));
    render(<CommonAiDrawer open context={productContext} onClose={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: "분석 실행" }));
    expect(await screen.findByText(status === "HOLD" ?
      "판단 근거 부족 · 현재 분석 불가" : "확인된 관계 없음")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByText("주문/판매 분석 · Demo synthetic data")).not.toBeInTheDocument();
  });

  it("does not apply a late response after the drawer changes target", async () => {
    let finish!: (value: ReturnType<typeof envelope>) => void;
    vi.mocked(createConversation).mockResolvedValue(envelope(createdConversation()));
    vi.mocked(appendAnalysis).mockReturnValue(new Promise((resolve) => { finish = resolve; }));
    function TwoTargets() {
      const drawer = useCommonAiDrawer();
      return <>
        <button onClick={() => drawer.openAiDrawer(productContext)}>A 열기</button>
        <button onClick={() => drawer.openAiDrawer({ ...productContext, targetId: "246", targetLabel: "B" })}>B 열기</button>
      </>;
    }
    render(<CommonAiDrawerHost><TwoTargets /></CommonAiDrawerHost>);
    fireEvent.click(screen.getByRole("button", { name: "A 열기" }));
    fireEvent.click(screen.getByRole("button", { name: "분석 실행" }));
    await waitFor(() => expect(appendAnalysis).toHaveBeenCalled());
    fireEvent.click(screen.getByRole("button", { name: "B 열기" }));
    await act(async () => finish(envelope(conversation())));
    expect(screen.getByText("B")).toBeInTheDocument();
    expect(screen.getByText("아직 분석을 실행하지 않았습니다.")).toBeInTheDocument();
    expect(screen.queryByText("정상 분석 결과")).not.toBeInTheDocument();
  });

  it("rejects a response whose assistant is linked to another request message", async () => {
    vi.mocked(createConversation).mockResolvedValue(envelope(createdConversation()));
    vi.mocked(appendAnalysis).mockResolvedValue(envelope({ ...conversation(), messages: [
      { ...conversation().messages[0], request_message_id: "missing-user" },
      ...conversation().messages.slice(1),
    ] }));
    render(<CommonAiDrawer open context={productContext} onClose={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: "분석 실행" }));
    await waitFor(() => expect(appendAnalysis).toHaveBeenCalled());
    expect(screen.queryByText("정상 분석 결과")).not.toBeInTheDocument();
  });
});
