import { mockApiGet } from "../mocks/handlers";
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