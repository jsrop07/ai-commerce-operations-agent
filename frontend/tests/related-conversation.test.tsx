import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import CommonAiDrawer from "../src/components/CommonAiDrawer";
import { BackendHttpError } from "../src/api/backendHttp";
import { appendNaturalQuestion, contextIdentity, createConversation, followRelatedContext, getConversation, getConversations,
  type ConversationView, type EntityContext } from "../src/api/conversations";

vi.mock("../src/api/conversations", async (load) => {
  const actual = await load<typeof import("../src/api/conversations")>();
  return { ...actual, appendNaturalQuestion: vi.fn(), createConversation: vi.fn(),
    followRelatedContext: vi.fn(), getConversation: vi.fn(), getConversations: vi.fn() };
});

const product: EntityContext = { targetType: "PRODUCT", targetId: "9150000009",
  targetLabel: "아침 시장", source: "CAFE24_CATALOG", asOf: null };
const incoming: EntityContext = { targetType: "INCOMING", targetId: "11111111-1111-4111-8111-111111111111",
  targetLabel: "INCOMING 11111111-1111-4111-8111-111111111111",
  source: "OPERATIONS_INCOMING", asOf: null };
const task: EntityContext = { targetType: "TASK", targetId: "22222222-2222-4222-8222-222222222222",
  targetLabel: "TASK 22222222-2222-4222-8222-222222222222",
  source: "OPERATIONS_TASK", asOf: null };

function view(target: EntityContext, revision: number): ConversationView["context"] {
  return { context_revision: revision, scope: "ENTITY", page: null, filters: null,
    search: null, date_range: null, sort: null, target_type: target.targetType,
    target_id: target.targetId, target_label: target.targetLabel, source: target.source,
    source_as_of: target.asOf, data_mode: "SYNTHETIC_DEMO" };
}
function conversation(target: EntityContext, revision: number): ConversationView {
  return { conversation_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", conversation_status: "ACTIVE",
    current_context_revision: revision, context: view(target, revision), messages: [], agent_runs: [] };
}
function envelope(data: ConversationView) {
  return { schema_version: "1.0" as const, tenant_id: "tenant", request_id: "req",
    trace_id: "trace", as_of: "2026-10-10T00:00:00Z", evidence_ids: [], warnings: [], data };
}

afterEach(() => { vi.clearAllMocks(); sessionStorage.clear(); });

describe("related operations conversation", () => {
  it("starts an incoming conversation and sends a natural question to the existing endpoint", async () => {
    const created = conversation(incoming, 1);
    const question = "이 입고 상태를 확인해 줘";
    const answered: ConversationView = { ...created, messages: [
      { message_id: "request-1", message_order: 0, role: "USER", content: question,
        response_status: "HOLD", intent: "INSPECT_TARGET", analysis_kind: "DETERMINISTIC",
        request_message_id: null, evidence_ids: [], context: view(incoming, 1)! },
      { message_id: "answer-1", message_order: 1, role: "ASSISTANT",
        content: "결론: 이 대상의 자연어 분석은 아직 지원되지 않습니다.",
        response_status: "HOLD", intent: "INSPECT_TARGET", analysis_kind: "DETERMINISTIC",
        request_message_id: "request-1", evidence_ids: [], context: view(incoming, 1)! },
    ] };
    vi.mocked(getConversations).mockResolvedValue({ ...envelope(created), data: [] });
    vi.mocked(createConversation).mockResolvedValue(envelope(created));
    vi.mocked(appendNaturalQuestion).mockResolvedValue(envelope(answered));
    render(<CommonAiDrawer open context={incoming} currentPage="/" publicMode onClose={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "이 업무 대화 시작" }));
    await waitFor(() => expect(screen.getByText("업무 대화 기록 연결됨")).toBeInTheDocument());
    fireEvent.change(screen.getByRole("textbox", { name: "운영 AI 질문" }),
      { target: { value: question } });
    fireEvent.click(screen.getByRole("button", { name: "질문 전송" }));
    await waitFor(() => expect(screen.getByText(/자연어 분석은 아직 지원되지 않습니다/)).toBeInTheDocument());
    expect(createConversation).toHaveBeenCalledWith(incoming);
    expect(appendNaturalQuestion).toHaveBeenCalledWith(created.conversation_id, incoming, 1, question);
  });

  it("restores the owned conversation across a page reload before a related transition", async () => {
    const old = conversation(product, 1);
    sessionStorage.setItem("commerce-ai-active-conversation", JSON.stringify({
      contextKey: contextIdentity(product), conversationId: old.conversation_id,
    }));
    vi.mocked(getConversation).mockResolvedValue(envelope(old));
    vi.mocked(getConversations).mockResolvedValue({ ...envelope(old), data: [old] });
    render(<CommonAiDrawer open context={incoming} currentPage="/schedule" onClose={vi.fn()} />);
    await waitFor(() => expect(screen.getByText("업무 대화 기록 연결됨")).toBeInTheDocument());
    expect(getConversation).toHaveBeenCalledWith(old.conversation_id);
    expect(screen.getByRole("button", { name: "관련 업무로 이어가기" })).toBeInTheDocument();
    expect(followRelatedContext).not.toHaveBeenCalled();
  });

  it("drops only an inaccessible browser pointer and does not reuse its conversation", async () => {
    const old = conversation(product, 1);
    sessionStorage.setItem("commerce-ai-active-conversation", JSON.stringify({
      contextKey: contextIdentity(product), conversationId: old.conversation_id,
    }));
    vi.mocked(getConversation).mockRejectedValue(
      new BackendHttpError(404, "CONVERSATION_NOT_FOUND"),
    );
    vi.mocked(getConversations).mockResolvedValue({ ...envelope(old), data: [] });
    render(<CommonAiDrawer open context={incoming} currentPage="/schedule" onClose={vi.fn()} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("현재 세션에서 열 수 없습니다");
    expect(sessionStorage.getItem("commerce-ai-active-conversation")).toBeNull();
    expect(screen.getByRole("button", { name: "이 업무 대화 시작" })).toBeInTheDocument();
    expect(followRelatedContext).not.toHaveBeenCalled();
  });

  it("keeps one ID and advances revision only after the backend accepts an incoming target", async () => {
    const old = conversation(product, 1);
    old.messages = [
      { message_id: "request-1", message_order: 0, role: "USER",
        content: "상품 확인", response_status: "HOLD", intent: "INSPECT_TARGET",
        analysis_kind: "DETERMINISTIC", request_message_id: null,
        evidence_ids: [], context: view(product, 1)! },
      { message_id: "answer-1", message_order: 1, role: "ASSISTANT",
        content: "과거 상품 분석", response_status: "ANSWER", intent: "INSPECT_TARGET",
        analysis_kind: "DETERMINISTIC", request_message_id: "request-1",
        evidence_ids: ["product:synthetic:1"], context: view(product, 1)! },
    ];
    sessionStorage.setItem("commerce-ai-active-conversation", JSON.stringify({
      contextKey: contextIdentity(product), conversationId: old.conversation_id,
    }));
    vi.mocked(getConversation).mockResolvedValue(envelope(old));
    vi.mocked(getConversations).mockResolvedValue({ ...envelope(old), data: [old] });
    vi.mocked(followRelatedContext).mockResolvedValue(envelope({
      ...conversation(incoming, 2), messages: old.messages,
    }));
    const { rerender } = render(<CommonAiDrawer open context={product} currentPage="/inventory" onClose={vi.fn()} />);
    await waitFor(() => expect(screen.getByText("업무 대화 기록 연결됨")).toBeInTheDocument());
    rerender(<CommonAiDrawer open context={product} currentPage="/orders" onClose={vi.fn()} />);
    expect(screen.getByText(/현재 화면: 주문·매출/)).toBeInTheDocument();
    expect(screen.getByText("과거 상품 분석")).toBeInTheDocument();
    expect(followRelatedContext).not.toHaveBeenCalled();
    rerender(<CommonAiDrawer open context={incoming} currentPage="/schedule" onClose={vi.fn()} />);
    expect(screen.getByText(/현재 화면: 운영 일정/)).toBeInTheDocument();
    expect(screen.getByText(/새 선택 대상: 입고 예정 항목/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "관련 업무로 이어가기" }));
    await waitFor(() => expect(screen.getByText("입고 예정 항목")).toBeInTheDocument());
    expect(screen.getByText("과거 상품 분석")).toBeInTheDocument();
    expect(followRelatedContext).toHaveBeenCalledWith(old.conversation_id, incoming);
    expect(screen.getByText(/원인 분석은 현재 지원되지 않습니다/)).toBeInTheDocument();

    vi.mocked(followRelatedContext).mockRejectedValueOnce(
      new BackendHttpError(409, "UNRELATED_TARGET_NEW_CONVERSATION_REQUIRED"));
    rerender(<CommonAiDrawer open context={task} currentPage="/schedule" onClose={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "관련 업무로 이어가기" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("새 대화를 시작");
    expect(followRelatedContext).toHaveBeenLastCalledWith(old.conversation_id, task);
  });

  it("ignores an incoming transition response after the user selects another target", async () => {
    const old = conversation(product, 1);
    sessionStorage.setItem("commerce-ai-active-conversation", JSON.stringify({
      contextKey: contextIdentity(product), conversationId: old.conversation_id,
    }));
    vi.mocked(getConversation).mockResolvedValue(envelope(old));
    vi.mocked(getConversations).mockResolvedValue({ ...envelope(old), data: [old] });
    let complete!: (value: ReturnType<typeof envelope>) => void;
    vi.mocked(followRelatedContext).mockReturnValue(new Promise((resolve) => { complete = resolve; }));
    const { rerender } = render(<CommonAiDrawer open context={product} onClose={vi.fn()} />);
    await waitFor(() => expect(screen.getByText("업무 대화 기록 연결됨")).toBeInTheDocument());
    rerender(<CommonAiDrawer open context={incoming} currentPage="/schedule" onClose={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "관련 업무로 이어가기" }));
    rerender(<CommonAiDrawer open context={task} currentPage="/schedule" onClose={vi.fn()} />);
    complete(envelope(conversation(incoming, 2)));
    await waitFor(() => expect(screen.getByText(/새 선택 대상: 등록된 업무/)).toBeInTheDocument());
    expect(screen.queryByText("입고 예정 항목")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "관련 업무로 이어가기" })).toBeInTheDocument();
  });
});
