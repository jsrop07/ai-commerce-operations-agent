import type { ApiEnvelope } from "../types/contracts";
import { backendRequest } from "./backendHttp";

export type AnalysisKind = "NONE" | "DETERMINISTIC" | "HYBRID" | "RELATION_DOCUMENT";
export type Intent = "INSPECT_TARGET" | "FOLLOW_RELATED_TARGET";
export type ResponseStatus = "ANSWER" | "NO_EDGE" | "HOLD";

export type EntityContext = {
  scope?: "ENTITY";
  targetType: "PRODUCT" | "INCOMING" | "TASK";
  targetId: string;
  targetLabel: string;
  source: string;
  asOf: string | null;
};
export type ViewContext = {
  scope: "VIEW";
  page: "PRODUCT_INVENTORY" | "ORDERS_SALES";
  filters: { selling?: boolean; sold_out?: boolean; major_category?: string };
  search?: string | null;
  date_range?: { from_date: string; to_date: string } | null;
  sort?: { by: "cafe24_product_no" | "sale_price" | "as_of"; direction: "asc" | "desc" } | null;
};
export type ConversationContext = EntityContext | ViewContext;

export type ContextView = {
  context_revision: number;
  scope: "ENTITY" | "VIEW";
  page: string | null;
  filters: ViewContext["filters"] | null;
  search: string | null;
  date_range: ViewContext["date_range"];
  sort: ViewContext["sort"];
  target_type: string | null;
  target_id: string | null;
  target_label: string | null;
  source: string | null;
  source_as_of: string | null;
  data_mode: string | null;
};
export type MessageView = {
  message_id: string;
  message_order: number;
  role: "USER" | "ASSISTANT";
  content: string;
  response_status: ResponseStatus;
  intent: Intent | null;
  analysis_kind: AnalysisKind | null;
  request_message_id: string | null;
  evidence_ids: string[];
  context: ContextView;
};
export type ConversationView = {
  conversation_id: string;
  conversation_status: string;
  current_context_revision: number;
  context: ContextView | null;
  messages: MessageView[];
  agent_runs: Array<{ workflow_id: string; thread_id: string; run_status: string }>;
};

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function requireValue(condition: unknown, field: string): asserts condition {
  if (!condition) throw new Error(`Conversation ${field} is malformed`);
}
function nullableString(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}
function positiveInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value > 0;
}
function nonnegativeInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}
function stringList(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}
function parseContext(value: unknown): ContextView {
  requireValue(record(value), "context");
  requireValue(positiveInteger(value.context_revision), "context revision");
  requireValue(value.scope === "ENTITY" || value.scope === "VIEW", "context scope");
  requireValue(nullableString(value.page) && nullableString(value.target_type) &&
    nullableString(value.target_id) && nullableString(value.target_label) &&
    nullableString(value.source) && nullableString(value.source_as_of) &&
    nullableString(value.data_mode) && nullableString(value.search), "context fields");
  requireValue(value.filters === null || record(value.filters), "context filters");
  requireValue(value.date_range === null || record(value.date_range), "context date range");
  requireValue(value.sort === null || record(value.sort), "context sort");
  if (record(value.date_range)) requireValue(
    typeof value.date_range.from_date === "string" &&
    typeof value.date_range.to_date === "string" &&
    Object.keys(value.date_range).every((key) => ["from_date", "to_date"].includes(key)),
    "context date range",
  );
  if (record(value.sort)) requireValue(
    ["cafe24_product_no", "sale_price", "as_of"].includes(String(value.sort.by)) &&
    (value.sort.direction === "asc" || value.sort.direction === "desc") &&
    Object.keys(value.sort).every((key) => ["by", "direction"].includes(key)),
    "context sort",
  );
  if (value.scope === "ENTITY") {
    requireValue(value.target_type !== null && value.target_id !== null, "entity identity");
  } else {
    requireValue(value.page === "PRODUCT_INVENTORY" || value.page === "ORDERS_SALES", "view page");
    requireValue(record(value.filters), "view filters");
    for (const [key, field] of Object.entries(value.filters)) {
      requireValue(["selling", "sold_out", "major_category"].includes(key), "view filter key");
      requireValue(key === "major_category" ? typeof field === "string" : typeof field === "boolean", "view filter value");
    }
  }
  return value as ContextView;
}
function parseMessage(value: unknown): MessageView {
  requireValue(record(value), "message");
  requireValue(typeof value.message_id === "string" && value.message_id.length > 0 &&
    nonnegativeInteger(value.message_order) &&
    (value.role === "USER" || value.role === "ASSISTANT") &&
    typeof value.content === "string" &&
    (value.response_status === "ANSWER" || value.response_status === "NO_EDGE" || value.response_status === "HOLD") &&
    (value.intent === null || value.intent === "INSPECT_TARGET" || value.intent === "FOLLOW_RELATED_TARGET") &&
    (value.analysis_kind === null || value.analysis_kind === "NONE" ||
      value.analysis_kind === "DETERMINISTIC" || value.analysis_kind === "HYBRID" ||
      value.analysis_kind === "RELATION_DOCUMENT") &&
    nullableString(value.request_message_id) && stringList(value.evidence_ids), "message fields");
  return { ...value, context: parseContext(value.context) } as MessageView;
}
function parseConversation(value: unknown): ConversationView {
  requireValue(record(value), "data");
  requireValue(typeof value.conversation_id === "string" && value.conversation_id.length > 0 &&
    typeof value.conversation_status === "string" &&
    nonnegativeInteger(value.current_context_revision) &&
    Array.isArray(value.messages) && Array.isArray(value.agent_runs), "data fields");
  const messages = value.messages.map(parseMessage);
  const runs = value.agent_runs.map((run: unknown) => {
    requireValue(record(run) && typeof run.workflow_id === "string" &&
      typeof run.thread_id === "string" && typeof run.run_status === "string", "agent run");
    return run as ConversationView["agent_runs"][number];
  });
  return { ...value, context: value.context === null ? null : parseContext(value.context),
    messages, agent_runs: runs } as ConversationView;
}
function parseEnvelope(value: unknown): ApiEnvelope<unknown> {
  requireValue(record(value) && value.schema_version === "1.0" &&
    typeof value.tenant_id === "string" && typeof value.request_id === "string" &&
    typeof value.trace_id === "string" && typeof value.as_of === "string" &&
    stringList(value.evidence_ids) && stringList(value.warnings), "envelope");
  return value as unknown as ApiEnvelope<unknown>;
}
export function parseConversationResponse(value: unknown): ApiEnvelope<ConversationView> {
  const envelope = parseEnvelope(value);
  return { ...envelope, data: parseConversation(envelope.data) };
}
export function parseConversationList(value: unknown): ApiEnvelope<ConversationView[]> {
  const envelope = parseEnvelope(value);
  requireValue(Array.isArray(envelope.data), "list");
  return { ...envelope, data: envelope.data.map(parseConversation) };
}
export async function createConversation(context: ConversationContext, signal?: AbortSignal) {
  return parseConversationResponse(await backendRequest("/api/v1/conversations", "POST", { context }, signal));
}
export async function appendAnalysis(
  conversationId: string, context: ConversationContext, requestRevision: number,
  intent: Intent = "INSPECT_TARGET", analysisKind: AnalysisKind = "DETERMINISTIC",
  signal?: AbortSignal,
) {
  return parseConversationResponse(await backendRequest(
    `/api/v1/conversations/${encodeURIComponent(conversationId)}/messages`, "POST",
    { context, intent, analysis_kind: analysisKind, request_revision: requestRevision }, signal,
  ));
}

export async function appendNaturalQuestion(
  conversationId: string,
  context: EntityContext,
  requestRevision: number,
  question: string,
  signal?: AbortSignal,
) {
  return parseConversationResponse(
    await backendRequest(
      `/api/v1/conversations/${encodeURIComponent(conversationId)}/questions`,
      "POST",
      {
        context,
        question,
        request_revision: requestRevision,
      },
      signal,
    ),
  );
}

export async function getConversation(conversationId: string, signal?: AbortSignal) {
  return parseConversationResponse(await backendRequest(
    `/api/v1/conversations/${encodeURIComponent(conversationId)}`, "GET", undefined, signal,
  ));
}
export async function getConversations(signal?: AbortSignal) {
  return parseConversationList(await backendRequest("/api/v1/conversations", "GET", undefined, signal));
}
export async function reopenConversation(conversationId: string, signal?: AbortSignal) {
  return parseConversationResponse(await backendRequest(
    `/api/v1/conversations/${encodeURIComponent(conversationId)}/reopen`, "POST", {}, signal,
  ));
}

export async function createProductSearchConversation(query: string, signal?: AbortSignal) {
  return parseConversationResponse(await backendRequest(
    "/api/v1/conversations/product-search", "POST", { query }, signal,
  ));
}

export async function appendProductSearch(
  conversationId: string, query: string, requestRevision: number,
  signal?: AbortSignal,
) {
  return parseConversationResponse(await backendRequest(
    `/api/v1/conversations/${encodeURIComponent(conversationId)}/product-search/messages`,
    "POST", { query, intent: "INSPECT_TARGET", request_revision: requestRevision }, signal,
  ));
}

function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (record(value)) return `{${Object.keys(value).sort().map((key) => `${key}:${canonical(value[key])}`).join(",")}}`;
  return JSON.stringify(value);
}
function timeIdentity(value: string | null): string | null {
  return value === null ? null : new Date(value).toISOString();
}
export function contextIdentity(context: ConversationContext | ContextView): string {
  if ("targetType" in context) return canonical({ scope: "ENTITY", type: context.targetType,
    id: context.targetId, source: context.source, asOf: timeIdentity(context.asOf) });
  if ("scope" in context && context.scope === "ENTITY") return canonical({ scope: "ENTITY",
    type: context.target_type, id: context.target_id, source: context.source,
    asOf: timeIdentity(context.source_as_of) });
  return canonical({ scope: "VIEW", page: context.page, filters: context.filters ?? {},
    search: context.search ?? null, date_range: context.date_range ?? null, sort: context.sort ?? null });
}
