import { mockApiGet } from "../mocks/handlers";
import type { C04Key } from "./day04";
import type {
  ApiEnvelope,
  Freshness,
  InventoryQualityStatus,
  InventorySnapshot,
  Provider,
  RiskLevel,
} from "../types/contracts";


const useRealBackend =
  import.meta.env.VITE_USE_REAL_BACKEND === "true";

const backendBaseUrl =
  import.meta.env.VITE_BACKEND_BASE_URL ?? "";

export class RetrievalHttpError extends Error {
  constructor(public readonly status: number) {
    super(`Retrieval HTTP failed: ${status}`);
  }
}

export interface RetrievalCitation {
  rank: number;
  score: number;
  source_type: string;
  source_id: string;
  title: string;
  version: string;
  semantic_chunk_id: string;
  semantic_excerpt: string;
  semantic_excerpt_hash: string;
  as_of: string | null;
  c04_lookup?: Required<C04Key> | null;
}

export interface RetrievalSearch {
  method: "BM25";
  selection_status: "PROVISIONAL_DEV_SELECTION";
  data_mode: "SYNTHETIC_DEMO";
  actual_retrieval_executed: boolean;
  index_version: string;
  result_status: "RESULTS" | "ZERO_CITATIONS";
  citations: RetrievalCitation[];
  answer_status: string;
  human_review_required: boolean;
  human_review_reason: string[];
  warnings: string[];
  required_lookup: string[];
}

interface RetrievalMethodSummary {
  method: string;
  executed: boolean | null;
  execution_status: string;
  source_status: string | null;
  mean_recall_at_5: number | null;
  mean_mrr_at_5: number | null;
  full_evidence_numerator: number | null;
  full_evidence_denominator: number | null;
  metric_status: Record<string, string>;
}

export interface RetrievalSummary {
  selection: { method: "bm25"; status: "PROVISIONAL_DEV_SELECTION" };
  data_mode: "SYNTHETIC_DEMO";
  query_count: number;
  execution_count: number;
  error_count: number;
  actual_scale_retrieval_validation_required: boolean;
  methods: RetrievalMethodSummary[];
}

function requireRetrieval(condition: unknown): asserts condition {
  if (!condition) throw new Error("Retrieval response is malformed");
}
const textValue = (value: unknown): value is string => typeof value === "string" && value.trim().length > 0;
const stringList = (value: unknown): value is string[] => Array.isArray(value) && value.every(textValue);
const countValue = (value: unknown): value is number => typeof value === "number" && Number.isSafeInteger(value) && value >= 0;

function retrievalEnvelope(value: unknown): ApiEnvelope<unknown> {
  requireRetrieval(isRecord(value) && !Array.isArray(value));
  requireRetrieval(value.schema_version === "1.0" && textValue(value.tenant_id) &&
    textValue(value.request_id) && textValue(value.trace_id) && stringList(value.warnings) &&
    stringList(value.evidence_ids) && textValue(value.as_of) && isRecord(value.data) && !Array.isArray(value.data));
  return value as unknown as ApiEnvelope<unknown>;
}

export function parseRetrievalSearch(value: unknown): ApiEnvelope<RetrievalSearch> {
  const envelope = retrievalEnvelope(value);
  const data = envelope.data as Record<string, unknown>;
  requireRetrieval(data.method === "BM25" && data.selection_status === "PROVISIONAL_DEV_SELECTION" &&
    data.data_mode === "SYNTHETIC_DEMO" && typeof data.actual_retrieval_executed === "boolean" &&
    textValue(data.index_version) && textValue(data.answer_status) && typeof data.human_review_required === "boolean" &&
    stringList(data.human_review_reason) && stringList(data.warnings) && stringList(data.required_lookup) && Array.isArray(data.citations));
  requireRetrieval((data.result_status === "ZERO_CITATIONS" && data.citations.length === 0) ||
    (data.result_status === "RESULTS" && data.citations.length > 0));
  for (const citation of data.citations) {
    requireRetrieval(isRecord(citation) && !Array.isArray(citation) && countValue(citation.rank) && citation.rank > 0 &&
      typeof citation.score === "number" && Number.isFinite(citation.score));
    for (const field of ["source_type", "source_id", "title", "version", "semantic_chunk_id", "semantic_excerpt", "semantic_excerpt_hash"]) {
      requireRetrieval(textValue(citation[field]));
    }
    requireRetrieval(["PRODUCT", "POLICY", "INVENTORY_SNAPSHOT", "INCOMING_STOCK"].includes(String(citation.source_type)));
    requireRetrieval((citation.as_of === null && ["PRODUCT", "POLICY"].includes(String(citation.source_type))) ||
      (textValue(citation.as_of) && Number.isFinite(Date.parse(citation.as_of))));
    const key = citation.c04_lookup;
    if (key !== undefined && key !== null) {
      requireRetrieval(isRecord(key) && !Array.isArray(key) && textValue(key.source_id) && textValue(key.version) && textValue(key.chunk_id));
      requireRetrieval(/^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(key.source_id) &&
        /^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(key.version) && key.chunk_id.length <= 300);
    }
  }
  return envelope as ApiEnvelope<RetrievalSearch>;
}

export function parseRetrievalSummary(value: unknown): ApiEnvelope<RetrievalSummary> {
  const envelope = retrievalEnvelope(value);
  const data = envelope.data as Record<string, unknown>;
  requireRetrieval(isRecord(data.selection) && !Array.isArray(data.selection) && data.selection.method === "bm25" &&
    data.selection.status === "PROVISIONAL_DEV_SELECTION" && data.data_mode === "SYNTHETIC_DEMO" &&
    countValue(data.query_count) && countValue(data.execution_count) && countValue(data.error_count) &&
    typeof data.actual_scale_retrieval_validation_required === "boolean" && Array.isArray(data.methods));
  requireRetrieval(data.methods.filter((method) => isRecord(method) && method.method === "bm25").length === 1);
  for (const method of data.methods) {
    requireRetrieval(isRecord(method) && !Array.isArray(method) && textValue(method.method) &&
      (method.executed === null || typeof method.executed === "boolean") && textValue(method.execution_status) &&
      (method.source_status === null || textValue(method.source_status)) && isRecord(method.metric_status) && !Array.isArray(method.metric_status) &&
      Object.values(method.metric_status).every(textValue));
    for (const field of ["mean_recall_at_5", "mean_mrr_at_5"]) {
      const metric = method[field];
      requireRetrieval(metric === null || (typeof metric === "number" && Number.isFinite(metric) && metric >= 0 && metric <= 1));
    }
    requireRetrieval((method.full_evidence_numerator === null || countValue(method.full_evidence_numerator)) &&
      (method.full_evidence_denominator === null || countValue(method.full_evidence_denominator)));
    requireRetrieval(method.full_evidence_numerator === null ||
      (typeof method.full_evidence_denominator === "number" && method.full_evidence_numerator <= method.full_evidence_denominator));
  }
  return envelope as ApiEnvelope<RetrievalSummary>;
}

async function retrievalRequest(path: string, signal?: AbortSignal, body?: { query: string; top_k: 5; method: "BM25" }): Promise<unknown> {
  const response = await fetch(`${backendBaseUrl}${path}`, {
    method: body ? "POST" : "GET",
    headers: { Accept: "application/json", ...(body ? { "Content-Type": "application/json" } : {}) },
    ...(body ? { body: JSON.stringify(body) } : {}), signal,
  });
  if (!response.ok) throw new RetrievalHttpError(response.status);
  return response.json();
}

export async function searchRetrieval(query: string, signal?: AbortSignal) {
  if (!query.trim() || query.length > 2000) throw new RetrievalHttpError(422);
  return parseRetrievalSearch(await retrievalRequest("/api/v1/retrieval/search", signal, { query, top_k: 5, method: "BM25" }));
}

export async function getRetrievalSummary(signal?: AbortSignal) {
  return parseRetrievalSummary(await retrievalRequest("/api/v1/retrieval/summary", signal));
}

const providers: readonly Provider[] = [
  "CAFE24",
  "TOSS_POS",
  "ECOUNT",
  "DEMO",
];

const freshnessValues: readonly Freshness[] = [
  "FRESH",
  "STALE",
  "UNKNOWN",
];

const qualityStatuses: readonly InventoryQualityStatus[] = [
  "USABLE",
  "STALE",
  "UNMAPPED",
  "QUARANTINED",
  "SOURCE_QUALITY_BLOCKED",
];

const riskLevels: readonly RiskLevel[] = [
  "LOW",
  "MEDIUM",
  "HIGH",
  "PROHIBITED",
];

function isRecord(
  value: unknown,
): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

async function realApiGet(
  path: string,
  signal?: AbortSignal,
): Promise<unknown> {
  const response = await fetch(
    `${backendBaseUrl}${path}`,
    {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
      signal,
    },
  );

  if (!response.ok) {
    throw new Error(
      `Backend GET failed: ${response.status}`,
    );
  }

  return response.json() as Promise<unknown>;
}

function parseEnvelope(
  value: unknown,
): ApiEnvelope<unknown[]> {
  if (
    !isRecord(value) ||
    value.schema_version !== "1.0" ||
    typeof value.tenant_id !== "string" ||
    typeof value.request_id !== "string" ||
    typeof value.trace_id !== "string" ||
    !Array.isArray(value.data) ||
    !Array.isArray(value.evidence_ids) ||
    !Array.isArray(value.warnings) ||
    typeof value.as_of !== "string"
  ) {
    throw new Error(
      "Backend inventory envelope is malformed",
    );
  }

  return value as unknown as ApiEnvelope<unknown[]>;
}

function parseInventoryItem(
  value: unknown,
): InventorySnapshot {
  if (
    !isRecord(value) ||
    !providers.includes(value.provider as Provider) ||
    typeof value.sku_id !== "string" ||
    typeof value.on_hand !== "number" ||
    typeof value.reserved !== "number" ||
    typeof value.as_of !== "string" ||
    !freshnessValues.includes(
      value.freshness as Freshness,
    )
  ) {
    throw new Error(
      "Backend inventory item is malformed",
    );
  }

  const item: InventorySnapshot = {
    provider: value.provider as Provider,
    sku_id: value.sku_id,
    on_hand: value.on_hand,
    reserved: value.reserved,
    as_of: value.as_of,
    freshness: value.freshness as Freshness,
  };

  if (
    value.expected_inventory === null ||
    typeof value.expected_inventory === "number"
  ) {
    item.expected_inventory =
      value.expected_inventory;
  }

  if (
    value.confirmed_incoming === null ||
    typeof value.confirmed_incoming === "number"
  ) {
    item.confirmed_incoming =
      value.confirmed_incoming;
  }

  if (
    value.risk_level === null ||
    riskLevels.includes(value.risk_level as RiskLevel)
  ) {
    item.risk_level =
      value.risk_level as RiskLevel | null;
  }

  if (
    typeof value.quality_status === "string" &&
    qualityStatuses.includes(
      value.quality_status as InventoryQualityStatus,
    )
  ) {
    item.quality_status =
      value.quality_status as InventoryQualityStatus;
  }

  if (typeof value.ttl_seconds === "number") {
    item.ttl_seconds = value.ttl_seconds;
  }

  if (typeof value.age_seconds === "number") {
    item.age_seconds = value.age_seconds;
  }

  if (
    typeof value.freshness_reason === "string"
  ) {
    item.freshness_reason =
      value.freshness_reason;
  }

  if (
    typeof value.confirmed_for_total === "boolean"
  ) {
    item.confirmed_for_total =
      value.confirmed_for_total;
  }

  return item;
}

export interface Day08Insight {
  insight_id: string;
  type: string;
  severity: RiskLevel;
  confidence: number;
  summary: string;
  calculation?: Record<string, number>;
  model_run_id?: string | null;
  rule_version?: string;
}

export async function getDay08Inventory(
  signal?: AbortSignal,
): Promise<ApiEnvelope<InventorySnapshot[]>> {
  if (!useRealBackend) {
    return mockApiGet<
      ApiEnvelope<InventorySnapshot[]>
    >("/api/v1/inventory");
  }

  const rawResponse = await realApiGet(
    "/api/v1/inventory",
    signal,
  );

  const envelope = parseEnvelope(rawResponse);

  return {
    ...envelope,
    data: envelope.data.map(parseInventoryItem),
  };
}

function parseInsightItem(
  value: unknown,
): Day08Insight {
  if (
    !isRecord(value) ||
    typeof value.insight_id !== "string" ||
    typeof value.type !== "string" ||
    !riskLevels.includes(
      value.severity as RiskLevel,
    ) ||
    typeof value.confidence !== "number" ||
    typeof value.summary !== "string"
  ) {
    throw new Error(
      "Backend insight item is malformed",
    );
  }

  return {
    insight_id: value.insight_id,
    type: value.type,
    severity: value.severity as RiskLevel,
    confidence: value.confidence,
    summary: value.summary,
    calculation:
      isRecord(value.calculation)
        ? (value.calculation as Record<string, number>)
        : undefined,
    model_run_id:
      value.model_run_id === null ||
      typeof value.model_run_id === "string"
        ? value.model_run_id
        : undefined,
    rule_version:
      typeof value.rule_version === "string"
        ? value.rule_version
        : undefined,
  };
}

export async function getDay08Insights(
  signal?: AbortSignal,
): Promise<ApiEnvelope<Day08Insight[]>> {
  const rawResponse = await realApiGet(
    "/api/v1/insights",
    signal,
  );

  const envelope = parseEnvelope(rawResponse);

  return {
    ...envelope,
    data: envelope.data.map(parseInsightItem),
  };
}
