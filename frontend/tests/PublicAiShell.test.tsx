import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CommonAiDrawerHost, useCommonAiDrawer } from "../src/app/CommonAiDrawerContext";
import { aiProblem } from "../src/components/CommonAiDrawer";
import { BackendHttpError } from "../src/api/backendHttp";
import { bootstrapDemoSession } from "../src/api/demoSession";
import { appendAnalysis, createConversation, createProductSearchConversation,
  getConversations, type ConversationView } from "../src/api/conversations";

vi.mock("../src/api/demoSession", () => ({ bootstrapDemoSession: vi.fn() }));
vi.mock("../src/api/conversations", async (original) => ({
  ...await original<typeof import("../src/api/conversations")>(),
  appendAnalysis: vi.fn(), createConversation: vi.fn(),
  createProductSearchConversation: vi.fn(), appendProductSearch: vi.fn(),
  getConversations: vi.fn(), reopenConversation: vi.fn(),
}));

const context = { context_revision: 1, scope: "ENTITY" as const, page: null, filters: null,
  search: null, date_range: null, sort: null, target_type: "PRODUCT", target_id: "245",
  target_label: "투명 주사위", source: "CAFE24_CATALOG", source_as_of: null,
  data_mode: "SYNTHETIC_DEMO" };
const saved: ConversationView = {
  conversation_id: "internal-conversation-id", conversation_status: "ACTIVE",
  current_context_revision: 1, context, agent_runs: [], messages: [
    { message_id: "request", message_order: 0, role: "USER", content: "상품 검색 요청",
      response_status: "HOLD", intent: "INSPECT_TARGET", analysis_kind: "HYBRID",
      request_message_id: null, evidence_ids: [], context },
    { message_id: "answer", message_order: 1, role: "ASSISTANT", content: "저장된 Product 근거에서 확인했습니다.\n근거: internal-source-id",
      response_status: "ANSWER", intent: "INSPECT_TARGET", analysis_kind: "HYBRID",
      request_message_id: "request", evidence_ids: ["internal-source-id"], context },
  ],
};
function envelope<T extends ConversationView | ConversationView[]>(data: T) {
  return { schema_version: "1.0" as const, tenant_id: "tenant", request_id: "internal-request-id",
    trace_id: "internal-trace-id", evidence_ids: [], warnings: [], as_of: "2026-10-07T00:00:00Z", data };
}
function OpenGlobal() {
  const { openAiDrawer } = useCommonAiDrawer();
  return <button type="button" onClick={() => openAiDrawer(null)}>운영 AI 열기</button>;
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(bootstrapDemoSession).mockResolvedValue({
    status: "ACTIVE", expiresAt: new Date(Date.now() + 60_000).toISOString(),
  });
  vi.mocked(getConversations).mockResolvedValue(envelope([]));
});

describe("Public Demo Operations AI shell", () => {
  it("bootstraps session and opens without analysis, then uses real Product search contract", async () => {
    vi.mocked(createProductSearchConversation).mockResolvedValue(envelope(saved));
    render(<CommonAiDrawerHost sessionRequired><OpenGlobal /></CommonAiDrawerHost>);
    await waitFor(() => expect(bootstrapDemoSession).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByRole("button", { name: "운영 AI 열기" }));
    expect(await screen.findByRole("dialog", { name: "운영 AI" })).toBeInTheDocument();
    expect(createConversation).not.toHaveBeenCalled();
    expect(appendAnalysis).not.toHaveBeenCalled();
    expect(createProductSearchConversation).not.toHaveBeenCalled();
    fireEvent.change(screen.getByRole("textbox", { name: "Product 검색 질문" }),
      { target: { value: "투명 주사위 찾아줘" } });
    fireEvent.click(screen.getByRole("button", { name: "전송" }));
    expect(await screen.findByText("저장된 Product 근거에서 확인했습니다.",
      { selector: ".common-ai-answer" })).toBeInTheDocument();
    expect(createProductSearchConversation).toHaveBeenCalledWith("투명 주사위 찾아줘");
    expect(screen.getByRole("region", { name: "근거" })).toHaveTextContent("검색·문서 근거 · 1건");
    expect(screen.getByRole("dialog")).not.toHaveTextContent("internal-source-id");
    expect(screen.getByRole("dialog")).not.toHaveTextContent("internal-conversation-id");
  });

  it("keeps search context unchanged on ambiguous response", async () => {
    vi.mocked(createProductSearchConversation).mockRejectedValue(
      new BackendHttpError(409, "PRODUCT_SEARCH_AMBIGUOUS"));
    render(<CommonAiDrawerHost sessionRequired><OpenGlobal /></CommonAiDrawerHost>);
    fireEvent.click(screen.getByRole("button", { name: "운영 AI 열기" }));
    await screen.findByRole("textbox", { name: "Product 검색 질문" });
    fireEvent.change(screen.getByRole("textbox", { name: "Product 검색 질문" }),
      { target: { value: "폭풍 항구 확장" } });
    fireEvent.click(screen.getByRole("button", { name: "전송" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("일치하는 상품이 여러 개");
    expect(screen.getByRole("region", { name: "현재 분석 범위" })).toHaveTextContent("상품을 자연어로 찾거나");
    expect(createConversation).not.toHaveBeenCalled();
  });

  it("clears the old visitor's history when a session expires and a new one starts", async () => {
    vi.mocked(getConversations)
      .mockResolvedValueOnce(envelope([saved]))
      .mockRejectedValueOnce(new BackendHttpError(403, "C09_TRUSTED_ACTOR_REQUIRED"))
      .mockResolvedValue(envelope([]));
    render(<CommonAiDrawerHost sessionRequired><OpenGlobal /></CommonAiDrawerHost>);
    fireEvent.click(screen.getByRole("button", { name: "운영 AI 열기" }));
    expect(await screen.findByRole("button", { name: /투명 주사위 · ACTIVE/ })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "운영 AI 패널 닫기" }));
    fireEvent.click(screen.getByRole("button", { name: "운영 AI 열기" }));
    expect(await screen.findByText("Demo Session이 만료되었습니다.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /투명 주사위 · ACTIVE/ })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "새 Demo Session 시작" }));
    await waitFor(() => expect(bootstrapDemoSession).toHaveBeenCalledTimes(2));
    fireEvent.click(screen.getByRole("button", { name: "운영 AI 열기" }));
    expect(await screen.findByText("이 범위의 최근 대화가 없습니다.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /투명 주사위 · ACTIVE/ })).not.toBeInTheDocument();
  });

  it("distinguishes quota, rate, disabled model and provider failure codes", () => {
    expect(aiProblem(new BackendHttpError(429, null)).message).toContain("요청이 잠시 제한");
    expect(aiProblem(new BackendHttpError(422, "C24_QUOTA_EXCEEDED")).message).toContain("사용 한도");
    expect(aiProblem(new BackendHttpError(503, "C24_QUOTA_UNCONFIGURED")).message).toContain("모델 호출이 현재 중지");
    expect(aiProblem(new BackendHttpError(503, "PROVIDER_FAILED")).message).toContain("일시적으로");
    expect(aiProblem(new BackendHttpError(403, "C09_TRUSTED_ACTOR_REQUIRED")).sessionExpired).toBe(true);
  });
});
