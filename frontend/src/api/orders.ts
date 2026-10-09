import type { ApiEnvelope } from "../types/contracts";

export type RecentOrderSummary =
  | {
      status: "AVAILABLE";
      order_count: number;
      reference_date: string;
      timezone: "Asia/Seoul";
      source_system: "SYNTHETIC_DEMO";
      aggregation: "LATEST_ORDER_DATE";
      includes_all_order_statuses: true;
    }
  | {
      status: "NO_DATA";
      order_count: null;
      reference_date: null;
      timezone: "Asia/Seoul";
      source_system: "SYNTHETIC_DEMO";
      aggregation: "LATEST_ORDER_DATE";
      includes_all_order_statuses: true;
    };

function isRecord(
  value: unknown,
): value is Record<string, unknown> {
  return (
    typeof value === "object" &&
    value !== null &&
    !Array.isArray(value)
  );
}

export async function getRecentOrderSummary(
  signal?: AbortSignal,
): Promise<ApiEnvelope<RecentOrderSummary>> {
  const baseUrl =
    import.meta.env.VITE_BACKEND_BASE_URL ?? "";

  const response = await fetch(
    `${baseUrl}/api/v1/orders/recent-summary`,
    {
      method: "GET",
      headers: { Accept: "application/json" },
      signal,
    },
  );

  if (!response.ok) {
    throw new Error(
      `Recent orders GET failed: ${response.status}`,
    );
  }

  const raw: unknown = await response.json();

  if (
    !isRecord(raw) ||
    raw.schema_version !== "1.0" ||
    typeof raw.tenant_id !== "string" ||
    typeof raw.request_id !== "string" ||
    typeof raw.trace_id !== "string" ||
    typeof raw.as_of !== "string" ||
    !Array.isArray(raw.warnings) ||
    !raw.warnings.every(
      (item) => typeof item === "string",
    ) ||
    !Array.isArray(raw.evidence_ids) ||
    !raw.evidence_ids.every(
      (item) => typeof item === "string",
    ) ||
    !isRecord(raw.data)
  ) {
    throw new Error("Recent orders envelope is malformed");
  }

  const data = raw.data;

  const validSharedFields =
    data.timezone === "Asia/Seoul" &&
    data.source_system === "SYNTHETIC_DEMO" &&
    data.aggregation === "LATEST_ORDER_DATE" &&
    data.includes_all_order_statuses === true;

  const validAvailable =
    data.status === "AVAILABLE" &&
    typeof data.order_count === "number" &&
    Number.isSafeInteger(data.order_count) &&
    data.order_count >= 1 &&
    typeof data.reference_date === "string" &&
    /^\d{4}-\d{2}-\d{2}$/.test(data.reference_date) &&
    Number.isFinite(
      Date.parse(`${data.reference_date}T00:00:00Z`),
    );

  const validNoData =
    data.status === "NO_DATA" &&
    data.order_count === null &&
    data.reference_date === null;

  if (!validSharedFields || (!validAvailable && !validNoData)) {
    throw new Error("Recent orders data is malformed");
  }

  return raw as unknown as ApiEnvelope<RecentOrderSummary>;
}