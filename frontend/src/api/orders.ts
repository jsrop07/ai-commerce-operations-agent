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

// Synthetic Demo 주문 목록 계약 — 금액은 통화 단위를 가정하지 않는 원문 문자열입니다.
export type OrderFlag = "T" | "F" | "M";
export interface OrdersQuery {
  order_number?: string;
  product_name?: string;
  from_date?: string;
  to_date?: string;
  paid?: "T" | "F";
  canceled?: OrderFlag;
  shipping_status?: OrderFlag;
  sort_by?: "order_date" | "order_number";
  sort_order?: "asc" | "desc";
  limit?: number;
  offset?: number;
}
export interface OrderRow {
  order_number: string;
  order_date: string | null;
  total_order_amount: string | null;
  total_paid_amount: string | null;
  paid: "T" | "F";
  canceled: OrderFlag;
  shipping_status: OrderFlag;
  source_system: "SYNTHETIC_DEMO";
  items: { product_name: string; option_name: string | null; quantity: number }[];
}
export interface OrdersPageData {
  items: OrderRow[];
  total: number;
  limit: number;
  offset: number;
}
function requireOrders(value: unknown, message: string): asserts value {
  if (!value) throw new Error(`주문 목록 응답 오류: ${message}`);
}
function optionalDecimal(value: unknown): value is string | null {
  return value === null || (typeof value === "string" && /^-?\d+(?:\.\d+)?$/.test(value));
}
function nonnegativeInt(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}
function orderFlag(value: unknown): value is OrderFlag {
  return value === "T" || value === "F" || value === "M";
}
function parseOrdersPage(value: unknown): ApiEnvelope<OrdersPageData> {
  requireOrders(isRecord(value) && value.schema_version === "1.0" &&
    typeof value.tenant_id === "string" && typeof value.request_id === "string" &&
    typeof value.trace_id === "string" && typeof value.as_of === "string" &&
    Array.isArray(value.warnings) && value.warnings.every((w: unknown) => typeof w === "string") &&
    Array.isArray(value.evidence_ids) && value.evidence_ids.every((id: unknown) => typeof id === "string") &&
    isRecord(value.data), "envelope");
  const data = value.data;
  requireOrders(nonnegativeInt(data.total) && nonnegativeInt(data.offset) &&
    nonnegativeInt(data.limit) && data.limit >= 1 && data.limit <= 100 &&
    Array.isArray(data.items), "페이지 메타데이터");
  for (const item of data.items) {
    requireOrders(isRecord(item) && typeof item.order_number === "string" &&
      (item.order_date === null || (typeof item.order_date === "string" && Number.isFinite(Date.parse(item.order_date)))) &&
      optionalDecimal(item.total_order_amount) && optionalDecimal(item.total_paid_amount) &&
      (item.paid === "T" || item.paid === "F") && orderFlag(item.canceled) &&
      orderFlag(item.shipping_status) && item.source_system === "SYNTHETIC_DEMO" &&
      Array.isArray(item.items), "주문 필드");
    for (const product of item.items) {
      requireOrders(isRecord(product) && typeof product.product_name === "string" &&
        (product.option_name === null || typeof product.option_name === "string") &&
        nonnegativeInt(product.quantity), "주문 상품 필드");
    }
  }
  return value as unknown as ApiEnvelope<OrdersPageData>;
}
export async function getOrdersPage(query: OrdersQuery, signal?: AbortSignal): Promise<ApiEnvelope<OrdersPageData>> {
  const baseUrl = import.meta.env.VITE_BACKEND_BASE_URL ?? "";
  const params = new URLSearchParams();
  Object.entries(query).forEach(([key, val]) => { if (val !== undefined && val !== "") params.set(key, String(val)); });
  const response = await fetch(`${baseUrl}/api/v1/orders?${params.toString()}`, {
    method: "GET", headers: { Accept: "application/json" }, credentials: "include", signal,
  });
  if (!response.ok) throw new Error(`주문 목록 HTTP ${response.status} — Demo 세션 및 Backend 상태를 확인하세요.`);
  return parseOrdersPage(await response.json());
}
