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
    throw new Error(
      `Backend GET failed: ${response.status}`,
    );
  }

  return response.json() as Promise<unknown>;
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

  return {
    insight_id: value.insight_id,
    type: value.type,
    severity: value.severity as RiskLevel,
    confidence: value.confidence,
    summary: value.summary,
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