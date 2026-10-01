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

export type ActualSourceSupportStatus =
  | "SUPPORTED"
  | "MISSING"
  | "BLOCKED";

export type ActualExecutionStatus =
  | "SUCCEEDED"
  | "FAILED"
  | "BLOCKED"
  | "NOT_RUN";

export type ActualMetricStatus =
  | "MEASURED"
  | "UNMEASURED";

export type ActualPreparationStatus =
  | "MEASURED"
  | "UNMEASURED"
  | "NOT_APPLICABLE";

export interface ActualFullEvidence {
  full_evidence_count: number;
  full_evidence_denominator: number;
}

export interface ActualLatency {
  kind: "SEARCH" | "SERIAL_SEARCH_E2E";
  unit: "ms";
  avg_ms: number | null;
  warm_p95_ms: number | null;
  http_round_trip: false;
}

export interface ActualPreparation {
  status: ActualPreparationStatus;
  model_load_seconds: number | null;
  document_embedding_seconds: number | null;
}

export interface ActualRetrievalMethod {
  method: "BM25" | "DENSE" | "RRF_HYBRID";
  execution_status: ActualExecutionStatus;
  executed_count: number;
  metric_status: ActualMetricStatus;
  recall_at_5: number | null;
  mrr_at_5: number | null;
  full_evidence: ActualFullEvidence;
  latency: ActualLatency;
  preparation: ActualPreparation;
}

export interface R07Measurement {
  kind: "RERANK_ONLY" | "SEARCH_PLUS_RERANK_E2E" | "SYNTHETIC_COMPRESSION";
  unit: "ms";
  count: number;
  mean_ms: number;
  p95_ms: number | null;
  http_round_trip: false;
}

export interface R07ActualEvaluation {
  status: "COMPLETE_WITH_LIMITS";
  experiment_id: "OPS-RAG-02";
  run_id: null;
  input_hashes: {
    product_snapshot_sha256: string;
    dev24_sha256: string;
    final12_used: false;
  };
  validated_baseline: "BM25";
  reranker: {
    evaluation_status: "PASS_WITH_FINDING";
    baseline: "BM25";
    always_on_selected: false;
    conditional_candidate: true;
    conditional_routing_validated: false;
    runtime_enabled: false;
    fallback_target: "BM25";
    before: R07Metrics;
    after: R07Metrics;
    candidate_miss_count: number;
    candidate_miss_category: "RETRIEVAL_CANDIDATE_MISS";
    latency: R07Measurement[];
    observed_events: { timeout_count: number; retry_count: number; fallback_count: number };
    timeout_seconds: number;
    max_retries: number;
    model: string;
    revision: string;
    device: "cpu";
  };
  compression: {
    evaluation_status: "PASS_WITH_LIMITATION";
    scope: "SYNTHETIC_POLICY_COMPRESSION_ONLY";
    case_count: number;
    before_tokens: number;
    after_tokens: number;
    reduction_ratio: number;
    evidence_preserved_count: number;
    citation_preserved_count: number;
    fallback_count: number;
    latency: R07Measurement;
    actual_context_validated: false;
    runtime_enabled: false;
  };
}

export interface R07Metrics {
  recall_at_5: number;
  mrr_at_5: number;
  full_evidence_count: number;
  full_evidence_rate: number;
}

export interface ActualRetrievalSummary {
  status: "COMPLETE_WITH_LIMITS";
  data_mode: "PRIVATE_ACTUAL_EVAL";
  validation_scope:
    "PRODUCT-only actual-scale mixed DEV24 retrieval baseline";

  experiment_id: "OPS-RAG-SCALE-01";
  experiment: "E08";
  task_id: "R07-PRE-AI-01";
  run_group: "OPS-RAG-SCALE-01 / E08";
  run_id: string | null;

  corpus_alias: "PRODUCT-SAFE-SNAPSHOT";
  question_set_alias: "R07-PRE-ACTUAL-DEV24";

  source_support: {
    PRODUCT: ActualSourceSupportStatus;
    POLICY: ActualSourceSupportStatus;
    INVENTORY_SNAPSHOT: ActualSourceSupportStatus;
    INCOMING_STOCK: ActualSourceSupportStatus;
    C02: ActualSourceSupportStatus;
  };

  counts: {
    document_count: number;
    chunk_count: number;
    question_count: number;
    answerable_count: number;
    hold_count: number;
    review_completed_count: number;
  };

  execution: {
    planned_count: number;
    executed_count: number;
    succeeded_count: number;
    failed_count: number;
    blocked_count: number;
    not_run_count: number;
  };

  methods: ActualRetrievalMethod[];

  selection: {
    selected_method: "BM25";
    status: "PROVISIONAL_PRODUCT_ONLY";
    selection_scope: "PRODUCT-only mixed actual-scale DEV24";
    reasons: string[];
    final_natural_language_retriever: false;
  };
  r07?: R07ActualEvaluation | null;
}

function requireRetrieval(condition: unknown): asserts condition {
  if (!condition) throw new Error("Retrieval response is malformed");
}
const textValue = (value: unknown): value is string => typeof value === "string" && value.trim().length > 0;
const stringList = (value: unknown): value is string[] => Array.isArray(value) && value.every(textValue);
const countValue = (value: unknown): value is number => typeof value === "number" && Number.isSafeInteger(value) && value >= 0;

const finiteNonNegativeNumber = (
  value: unknown,
): value is number =>
  typeof value === "number" &&
  Number.isFinite(value) &&
  value >= 0;

const nullableFiniteNonNegativeNumber = (
  value: unknown,
): value is number | null =>
  value === null || finiteNonNegativeNumber(value);

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

function r07Ratio(value: unknown): value is number {
  return finiteNonNegativeNumber(value) && value <= 1;
}

function requireR07Measurement(value: unknown, kind: R07Measurement["kind"]): void {
  requireRetrieval(isRecord(value) && !Array.isArray(value));
  requireRetrieval(
    value.kind === kind && value.unit === "ms" && countValue(value.count) &&
    finiteNonNegativeNumber(value.mean_ms) && nullableFiniteNonNegativeNumber(value.p95_ms) &&
    value.http_round_trip === false,
  );
}

function requireR07Metrics(value: unknown): void {
  requireRetrieval(isRecord(value) && !Array.isArray(value));
  requireRetrieval(
    r07Ratio(value.recall_at_5) && r07Ratio(value.mrr_at_5) &&
    countValue(value.full_evidence_count) && r07Ratio(value.full_evidence_rate),
  );
}

function requireR07Evaluation(value: unknown): void {
  requireRetrieval(isRecord(value) && !Array.isArray(value));
  requireRetrieval(
    value.status === "COMPLETE_WITH_LIMITS" && value.experiment_id === "OPS-RAG-02" &&
    value.run_id === null && value.validated_baseline === "BM25" &&
    isRecord(value.input_hashes) && !Array.isArray(value.input_hashes) &&
    textValue(value.input_hashes.product_snapshot_sha256) &&
    textValue(value.input_hashes.dev24_sha256) && value.input_hashes.final12_used === false,
  );

  const reranker = value.reranker;
  requireRetrieval(isRecord(reranker) && !Array.isArray(reranker));
  requireRetrieval(
    reranker.evaluation_status === "PASS_WITH_FINDING" && reranker.baseline === "BM25" &&
    reranker.always_on_selected === false && reranker.conditional_candidate === true &&
    reranker.conditional_routing_validated === false && reranker.runtime_enabled === false &&
    reranker.fallback_target === "BM25" && countValue(reranker.candidate_miss_count) &&
    reranker.candidate_miss_category === "RETRIEVAL_CANDIDATE_MISS" &&
    finiteNonNegativeNumber(reranker.timeout_seconds) && reranker.timeout_seconds > 0 &&
    countValue(reranker.max_retries) && textValue(reranker.model) &&
    textValue(reranker.revision) && reranker.device === "cpu",
  );
  requireR07Metrics(reranker.before);
  requireR07Metrics(reranker.after);
  requireRetrieval(Array.isArray(reranker.latency) && reranker.latency.length === 2);
  requireR07Measurement(reranker.latency[0], "RERANK_ONLY");
  requireR07Measurement(reranker.latency[1], "SEARCH_PLUS_RERANK_E2E");
  requireRetrieval(isRecord(reranker.observed_events) && !Array.isArray(reranker.observed_events));
  requireRetrieval(
    countValue(reranker.observed_events.timeout_count) &&
    countValue(reranker.observed_events.retry_count) &&
    countValue(reranker.observed_events.fallback_count),
  );

  const compression = value.compression;
  requireRetrieval(isRecord(compression) && !Array.isArray(compression));
  requireRetrieval(
    compression.evaluation_status === "PASS_WITH_LIMITATION" &&
    compression.scope === "SYNTHETIC_POLICY_COMPRESSION_ONLY" &&
    countValue(compression.case_count) && countValue(compression.before_tokens) &&
    countValue(compression.after_tokens) && r07Ratio(compression.reduction_ratio) &&
    countValue(compression.evidence_preserved_count) &&
    countValue(compression.citation_preserved_count) && countValue(compression.fallback_count) &&
    compression.actual_context_validated === false && compression.runtime_enabled === false,
  );
  requireR07Measurement(compression.latency, "SYNTHETIC_COMPRESSION");
}

export function parseActualRetrievalSummary(
  value: unknown,
): ActualRetrievalSummary {
  requireRetrieval(
    isRecord(value) &&
      !Array.isArray(value),
  );

  requireRetrieval(
    value.status === "COMPLETE_WITH_LIMITS" &&
      value.data_mode === "PRIVATE_ACTUAL_EVAL" &&
      value.validation_scope ===
        "PRODUCT-only actual-scale mixed DEV24 retrieval baseline" &&
      value.experiment_id === "OPS-RAG-SCALE-01" &&
      value.experiment === "E08" &&
      value.task_id === "R07-PRE-AI-01" &&
      value.run_group === "OPS-RAG-SCALE-01 / E08" &&
      (value.run_id === null || textValue(value.run_id)) &&
      value.corpus_alias === "PRODUCT-SAFE-SNAPSHOT" &&
      value.question_set_alias === "R07-PRE-ACTUAL-DEV24",
  );

  requireRetrieval(
    isRecord(value.source_support) &&
      !Array.isArray(value.source_support),
  );

  const sourceSupport = value.source_support;
  const sourceStatuses = [
    "SUPPORTED",
    "MISSING",
    "BLOCKED",
  ];

  requireRetrieval(
    sourceStatuses.includes(String(sourceSupport.PRODUCT)) &&
      sourceStatuses.includes(String(sourceSupport.POLICY)) &&
      sourceStatuses.includes(
        String(sourceSupport.INVENTORY_SNAPSHOT),
      ) &&
      sourceStatuses.includes(
        String(sourceSupport.INCOMING_STOCK),
      ) &&
      sourceStatuses.includes(String(sourceSupport.C02)),
  );

  // 이번 R07-PRE actual 평가의 확정 지원범위를 보존한다.
  requireRetrieval(
    sourceSupport.PRODUCT === "SUPPORTED" &&
      sourceSupport.POLICY === "MISSING" &&
      sourceSupport.INVENTORY_SNAPSHOT === "BLOCKED" &&
      sourceSupport.INCOMING_STOCK === "MISSING" &&
      sourceSupport.C02 === "BLOCKED",
  );

  requireRetrieval(
    isRecord(value.counts) &&
      !Array.isArray(value.counts),
  );

  const counts = value.counts;

  for (const field of [
    "document_count",
    "chunk_count",
    "question_count",
    "answerable_count",
    "hold_count",
    "review_completed_count",
  ]) {
    requireRetrieval(countValue(counts[field]));
  }

  requireRetrieval(
    isRecord(value.execution) &&
      !Array.isArray(value.execution),
  );

  const execution = value.execution;

  for (const field of [
    "planned_count",
    "executed_count",
    "succeeded_count",
    "failed_count",
    "blocked_count",
    "not_run_count",
  ]) {
    requireRetrieval(countValue(execution[field]));
  }

  // planned와 executed는 별도 의미다.
  // 단, 실제 수행 수는 성공/실패의 합과 일치해야 한다.
  requireRetrieval(
    execution.executed_count ===
      Number(execution.succeeded_count) +
        Number(execution.failed_count),
  );

  requireRetrieval(Array.isArray(value.methods));
  requireRetrieval(value.methods.length === 3);

  const methodNames = new Set<string>();

  for (const method of value.methods) {
    requireRetrieval(
      isRecord(method) &&
        !Array.isArray(method),
    );

    requireRetrieval(
      ["BM25", "DENSE", "RRF_HYBRID"].includes(
        String(method.method),
      ),
    );

    methodNames.add(String(method.method));

    requireRetrieval(
      [
        "SUCCEEDED",
        "FAILED",
        "BLOCKED",
        "NOT_RUN",
      ].includes(String(method.execution_status)),
    );

    requireRetrieval(countValue(method.executed_count));

    requireRetrieval(
      ["MEASURED", "UNMEASURED"].includes(
        String(method.metric_status),
      ),
    );

    for (const metric of [
      method.recall_at_5,
      method.mrr_at_5,
    ]) {
      requireRetrieval(
        metric === null ||
          (typeof metric === "number" &&
            Number.isFinite(metric) &&
            metric >= 0 &&
            metric <= 1),
      );
    }

    requireRetrieval(
      isRecord(method.full_evidence) &&
        !Array.isArray(method.full_evidence) &&
        countValue(
          method.full_evidence.full_evidence_count,
        ) &&
        countValue(
          method.full_evidence
            .full_evidence_denominator,
        ) &&
        method.full_evidence.full_evidence_count <=
          method.full_evidence
            .full_evidence_denominator,
    );

    requireRetrieval(
      isRecord(method.latency) &&
        !Array.isArray(method.latency) &&
        ["SEARCH", "SERIAL_SEARCH_E2E"].includes(
          String(method.latency.kind),
        ) &&
        method.latency.unit === "ms" &&
        nullableFiniteNonNegativeNumber(
          method.latency.avg_ms,
        ) &&
        nullableFiniteNonNegativeNumber(
          method.latency.warm_p95_ms,
        ) &&
        method.latency.http_round_trip === false,
    );

    if (method.method === "RRF_HYBRID") {
      requireRetrieval(
        method.latency.kind === "SERIAL_SEARCH_E2E",
      );
    } else {
      requireRetrieval(
        method.latency.kind === "SEARCH",
      );
    }

    requireRetrieval(
      isRecord(method.preparation) &&
        !Array.isArray(method.preparation) &&
        [
          "MEASURED",
          "UNMEASURED",
          "NOT_APPLICABLE",
        ].includes(String(method.preparation.status)) &&
        nullableFiniteNonNegativeNumber(
          method.preparation.model_load_seconds,
        ) &&
        nullableFiniteNonNegativeNumber(
          method.preparation.document_embedding_seconds,
        ),
    );
  }

  requireRetrieval(
    methodNames.size === 3 &&
      methodNames.has("BM25") &&
      methodNames.has("DENSE") &&
      methodNames.has("RRF_HYBRID"),
  );

  requireRetrieval(
    isRecord(value.selection) &&
      !Array.isArray(value.selection) &&
      value.selection.selected_method === "BM25" &&
      value.selection.status ===
        "PROVISIONAL_PRODUCT_ONLY" &&
      value.selection.selection_scope ===
        "PRODUCT-only mixed actual-scale DEV24" &&
      stringList(value.selection.reasons) &&
      value.selection.final_natural_language_retriever ===
        false,
  );

  if (value.r07 !== undefined && value.r07 !== null) {
    requireR07Evaluation(value.r07);
  }

  return value as unknown as ActualRetrievalSummary;
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

export async function getActualRetrievalSummary(
  signal?: AbortSignal,
) {
  return parseActualRetrievalSummary(
    await retrievalRequest(
      "/api/v1/retrieval/actual-summary",
      signal,
    ),
  );
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
