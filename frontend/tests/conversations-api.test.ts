import { afterEach, describe, expect, it, vi } from "vitest";
import {
  appendAnalysis, contextIdentity, createConversation, getConversation, getConversations,
  parseConversationList, parseConversationResponse, reopenConversation, type ConversationView,
} from "../src/api/conversations";

const context = { scope: "ENTITY" as const, targetType: "PRODUCT" as const,
  targetId: "245", targetLabel: "IMPERIAL KNIGHTS: KNIGHT QUESTORIS",
  source: "CAFE24_CATALOG", asOf: null };
const contextView = { context_revision: 1, scope: "ENTITY" as const,
  page: null, filters: null, search: null, date_range: null, sort: null,
  target_type: "PRODUCT", target_id: "245", target_label: context.targetLabel,
  source: "CAFE24_CATALOG", source_as_of: null, data_mode: "LOCAL_V2_CATALOG_MASTER" };
const message = { message_id: "user-1", message_order: 0, role: "USER" as const,
  content: "선택 대상 확인 요청", response_status: "HOLD" as const,
  intent: "INSPECT_TARGET" as const, analysis_kind: "NONE" as const,
  request_message_id: null, evidence_ids: [], context: contextView };
const data: ConversationView = { conversation_id: "conversation-a", conversation_status: "ACTIVE",
  current_context_revision: 1, context: contextView, messages: [message], agent_runs: [] };
function envelope(payload: unknown = data) {
  return { schema_version: "1.0", tenant_id: "tenant", request_id: "req",
    trace_id: "trace", evidence_ids: [], warnings: [], as_of: "2026-10-04T00:00:00Z",
    data: payload };
}
afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs(); });

describe("C09 conversation client", () => {
  it("parses messages and rejects malformed structured evidence", () => {
    expect(parseConversationResponse(envelope()).data.messages[0].evidence_ids).toEqual([]);
    expect(() => parseConversationResponse(envelope({ ...data, messages: [
      { ...message, evidence_ids: "근거: fake" },
    ] }))).toThrow(/message fields/);
  });

  it("parses distinct conversations with the same PRODUCT context", () => {
    const listed = parseConversationList(envelope([data, { ...data, conversation_id: "conversation-b" }]));
    expect(listed.data.map((item) => item.conversation_id)).toEqual(["conversation-a", "conversation-b"]);
    expect(() => parseConversationList(envelope([{ ...data, current_context_revision: "1" }]))).toThrow(/data fields/);
  });

  it("uses the catalog backend request path and sends revision and Cafe24 product_no", async () => {
    vi.stubEnv("VITE_USE_REAL_BACKEND", "true");
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => envelope() });
    vi.stubGlobal("fetch", fetchMock);
    await createConversation(context);
    await appendAnalysis("conversation-a", context, 1);
    const [createUrl, createOptions] = fetchMock.mock.calls[0];
    expect(createUrl).toContain("/api/v1/conversations");
    expect(JSON.parse(createOptions.body)).toEqual({ context });
    const [appendUrl, appendOptions] = fetchMock.mock.calls[1];
    expect(appendUrl).toContain("/api/v1/conversations/conversation-a/messages");
    expect(JSON.parse(appendOptions.body)).toEqual({ context, intent: "INSPECT_TARGET",
      analysis_kind: "DETERMINISTIC", request_revision: 1 });
    expect(JSON.parse(appendOptions.body).context.targetId).toBe("245");
  });

  it("keeps explicit view filters in context identity", () => {
    const view = { scope: "VIEW" as const, page: "PRODUCT_INVENTORY" as const,
      filters: { selling: true, sold_out: false } };
    expect(contextIdentity(view)).toBe(contextIdentity({ ...view,
      filters: { sold_out: false, selling: true } }));
    expect(contextIdentity(view)).not.toBe(contextIdentity({ ...view, filters: {} }));
  });

  it("exposes read, list and reopen through existing paths", async () => {
    vi.stubEnv("VITE_USE_REAL_BACKEND", "true");
    const fetchMock = vi.fn().mockImplementation(async (url: string) => ({
      ok: true, json: async () => envelope(url.endsWith("/api/v1/conversations") ? [data] : data),
    }));
    vi.stubGlobal("fetch", fetchMock);
    expect((await getConversation("conversation-a")).data.conversation_id).toBe("conversation-a");
    expect((await getConversations()).data).toHaveLength(1);
    expect((await reopenConversation("conversation-a")).data.conversation_status).toBe("ACTIVE");
    expect(fetchMock.mock.calls.map(([url]) => new URL(String(url)).pathname)).toEqual([
      "/api/v1/conversations/conversation-a",
      "/api/v1/conversations",
      "/api/v1/conversations/conversation-a/reopen",
    ]);
  });
});
