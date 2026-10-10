import type { ApiEnvelope } from "../types/contracts";

export type SalesAmount = { amount: string | null; order_count: number; null_order_count: number };
export type SalesSummaryData = {
  status: "AVAILABLE" | "NO_DATA";
  source_system: "SYNTHETIC_DEMO";
  timezone: "Asia/Seoul";
  from_date: string | null;
  to_date: string | null;
  currency: null;
  currency_status: "UNSPECIFIED_IN_SOURCE";
  paid_amount_semantics: "SOURCE_TOTAL_PAID_AMOUNT_NOT_SETTLED_REVENUE";
  daily_gap_policy: "OMIT_DAYS_WITHOUT_ORDERS";
  order_count: number;
  undated_order_count: number;
  order_amount: SalesAmount;
  paid_amount: SalesAmount;
  statuses: {
    paid: { T: number; F: number };
    canceled: { T: number; F: number; M: number };
    shipping_status: { T: number; F: number; M: number };
  };
  daily: Array<{ order_date: string; order_count: number; order_amount: SalesAmount; paid_amount: SalesAmount }>;
};

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function check(value: unknown, message: string): asserts value {
  if (!value) throw new Error(`매출 집계 응답 오류: ${message}`);
}
function count(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}
function isoDay(value: unknown): value is string {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return Number.isFinite(parsed.valueOf()) && parsed.toISOString().slice(0, 10) === value;
}
function amount(value: unknown): value is SalesAmount {
  return record(value) && (value.amount === null ||
    (typeof value.amount === "string" && /^-?\d+(?:\.\d+)?$/.test(value.amount))) &&
    count(value.order_count) && count(value.null_order_count);
}
function group(value: unknown, keys: string[]): boolean {
  return record(value) && keys.every((key) => count(value[key]));
}
export function parseSalesSummaryResponse(value: unknown): ApiEnvelope<SalesSummaryData> {
  check(record(value) && value.schema_version === "1.0" && typeof value.tenant_id === "string" &&
    typeof value.request_id === "string" && typeof value.trace_id === "string" &&
    typeof value.as_of === "string" && Array.isArray(value.warnings) &&
    value.warnings.every((item: unknown) => typeof item === "string") &&
    Array.isArray(value.evidence_ids) &&
    value.evidence_ids.every((item: unknown) => typeof item === "string") && record(value.data), "envelope");
  const data = value.data;
  check((data.status === "AVAILABLE" || data.status === "NO_DATA") &&
    data.source_system === "SYNTHETIC_DEMO" && data.timezone === "Asia/Seoul" &&
    (data.from_date === null || isoDay(data.from_date)) &&
    (data.to_date === null || isoDay(data.to_date)) &&
    data.currency === null && data.currency_status === "UNSPECIFIED_IN_SOURCE" &&
    data.paid_amount_semantics === "SOURCE_TOTAL_PAID_AMOUNT_NOT_SETTLED_REVENUE" &&
    data.daily_gap_policy === "OMIT_DAYS_WITHOUT_ORDERS" &&
    count(data.order_count) && count(data.undated_order_count) &&
    amount(data.order_amount) && amount(data.paid_amount) && record(data.statuses) &&
    group(data.statuses.paid, ["T", "F"]) &&
    group(data.statuses.canceled, ["T", "F", "M"]) &&
    group(data.statuses.shipping_status, ["T", "F", "M"]) &&
    Array.isArray(data.daily), "data");
  for (const item of data.daily) {
    check(record(item) && isoDay(item.order_date) && count(item.order_count) &&
      amount(item.order_amount) && amount(item.paid_amount), "daily item");
  }
  check(data.status !== "NO_DATA" ||
    (data.order_count === 0 && data.daily.length === 0 && data.order_amount.amount === null && data.paid_amount.amount === null),
  "NO_DATA");
  return value as unknown as ApiEnvelope<SalesSummaryData>;
}

export async function getSalesSummary(
  query: { from_date?: string; to_date?: string } = {}, signal?: AbortSignal,
): Promise<ApiEnvelope<SalesSummaryData>> {
  const params = new URLSearchParams();
  if (query.from_date) params.set("from_date", query.from_date);
  if (query.to_date) params.set("to_date", query.to_date);
  const baseUrl = import.meta.env.VITE_BACKEND_BASE_URL ?? "";
  const suffix = params.size ? `?${params.toString()}` : "";
  const response = await fetch(`${baseUrl}/api/v1/orders/sales-summary${suffix}`, {
    method: "GET", headers: { Accept: "application/json" },
    credentials: "include", signal,
  });
  if (!response.ok) throw new Error(`매출 집계 HTTP ${response.status} — Demo 세션 및 Backend 상태를 확인하세요.`);
  return parseSalesSummaryResponse(await response.json());
}
