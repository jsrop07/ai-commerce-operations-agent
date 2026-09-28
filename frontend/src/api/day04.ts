import { mockApiGet } from "../mocks/handlers";
import type {
  ApiEnvelope,
  RiskLevel,
} from "../types/contracts";
import type { UrgentQueueInsight } from "../components/UrgentQueue";

export const useRealBackend =
  import.meta.env.VITE_USE_REAL_BACKEND === "true";

const backendBaseUrl =
  import.meta.env.VITE_BACKEND_BASE_URL ?? "";

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
    throw new BackendGetError(response.status);
  }

  return response.json() as Promise<unknown>;
}

export class BackendGetError extends Error {
  constructor(public readonly status: number) {
    super(`Backend GET failed: ${status}`);
  }
}

export type C04Key = { source_id: string; version: string; chunk_id?: string };
export type C04Document = {
  source_id: string;
  title: string;
  source_type: string;
  version: string;
  as_of: string | null;
  excerpt: string;
  excerpt_hash: string;
  stale: boolean;
  warnings: string[];
  data_mode: "SYNTHETIC_DEMO";
  visibility: "DEMO_PUBLIC";
  chunk_id: string;
  definitive_answer_allowed: false;
};

export async function getC04Lookup(key: C04Key, signal?: AbortSignal): Promise<C04Document> {
  const query = new URLSearchParams({ source_id: key.source_id, version: key.version });
  if (key.chunk_id !== undefined) query.set("chunk_id", key.chunk_id);
  const response = await realApiGet(`/api/v1/c04/lookup?${query}`, signal);
  if (!isRecord(response)) throw new Error("Malformed C04 envelope");
  // C04 PRODUCT/POLICY documents may have no timestamp; preserve that null.
  if (response.as_of !== null && typeof response.as_of !== "string") throw new Error("Malformed C04 timestamp");
  parseEnvelope({ ...response, data: [], as_of: response.as_of ?? "" });
  const data = response.data;
  if (!isRecord(data) ||
    !["source_id", "title", "version", "excerpt", "excerpt_hash", "chunk_id"].every(
      (field) => typeof data[field] === "string" && data[field].length > 0,
    ) ||
    !(typeof data.as_of === "string" && data.as_of.length > 0 ||
      data.as_of === null && ["PRODUCT", "POLICY"].includes(String(data.source_type))) ||
    !["PRODUCT", "POLICY", "INVENTORY_SNAPSHOT", "INCOMING_STOCK"].includes(String(data.source_type)) ||
    typeof data.stale !== "boolean" ||
    !Array.isArray(data.warnings) || !data.warnings.every((value) => typeof value === "string") ||
    data.data_mode !== "SYNTHETIC_DEMO" || data.visibility !== "DEMO_PUBLIC" ||
    data.definitive_answer_allowed !== false ||
    data.source_id !== key.source_id || data.version !== key.version ||
    (key.chunk_id !== undefined && data.chunk_id !== key.chunk_id)
  ) throw new Error("Malformed or mismatched C04 document");
  return { ...data, warnings: [...new Set([...data.warnings, ...response.warnings as string[]])] } as C04Document;
}

const riskLevels: readonly RiskLevel[] = [
  "LOW",
  "MEDIUM",
  "HIGH",
  "PROHIBITED",
];

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function parseEnvelope(value: unknown): ApiEnvelope<unknown[]> {
  if (
    !isRecord(value) ||
    value.schema_version !== "1.0" ||
    typeof value.tenant_id !== "string" ||
    typeof value.request_id !== "string" ||
    typeof value.trace_id !== "string" ||
    !Array.isArray(value.data) ||
    !Array.isArray(value.evidence_ids) ||
    !value.evidence_ids.every((item) => typeof item === "string") ||
    !Array.isArray(value.warnings) ||
    !value.warnings.every((item) => typeof item === "string") ||
    typeof value.as_of !== "string"
  ) {
    throw new Error("Backend insight envelope is malformed");
  }

  return value as unknown as ApiEnvelope<unknown[]>;
}

function parseUrgentInsight(value: unknown): UrgentQueueInsight {
  if (
    !isRecord(value) ||
    typeof value.insight_id !== "string" ||
    typeof value.type !== "string" ||
    !riskLevels.includes(value.severity as RiskLevel) ||
    typeof value.confidence !== "number" ||
    !Number.isFinite(value.confidence) ||
    value.confidence < 0 ||
    value.confidence > 1 ||
    typeof value.summary !== "string"
  ) {
    throw new Error("Backend insight item is malformed");
  }

  const key = value.c04_lookup;
  if (key != null && (
    !isRecord(key) ||
    typeof key.source_id !== "string" || !/^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(key.source_id) ||
    typeof key.version !== "string" || !/^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(key.version) ||
    typeof key.chunk_id !== "string" || key.chunk_id.trim().length === 0 || key.chunk_id.length > 300
  )) throw new Error("Backend C04 lookup key is malformed");

  return {
    insight_id: value.insight_id,
    type: value.type,
    severity: value.severity as RiskLevel,
    confidence: value.confidence,
    summary: value.summary,
    ...(key != null ? { c04_lookup: {
      source_id: key.source_id as string,
      version: key.version as string,
      chunk_id: key.chunk_id as string,
    } } : {}),
  };
}

export function toUrgentQueueItems(
  response: ApiEnvelope<unknown[]>,
): ApiEnvelope<UrgentQueueInsight>[] {
  return response.data.map((item) => ({
    ...response,
    data: parseUrgentInsight(item),
  }));
}

export async function getDay04Insights(
  signal?: AbortSignal,
): Promise<ApiEnvelope<unknown[]>> {
  const response = useRealBackend
    ? await realApiGet("/api/v1/insights", signal)
    : await mockApiGet<unknown>("/api/v1/insights");

  return parseEnvelope(response);
}
