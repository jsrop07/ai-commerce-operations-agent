import { backendRequest } from "./backendHttp";

export type ShortageAnalysis = {
  status: "CONDITIONAL" | "HOLD";
  source_system: "SYNTHETIC_DEMO";
  required_quantity: number;
  secured_quantity: number | null;
  promised_date: string | null;
  reservation_quality: string;
  baseline_unsecured_quantity: number | null;
  conditional_shortage_quantity: number | null;
  conditional_incoming_quantity: number;
  inventory_data_as_of: string | null;
  incoming_source_as_of: null;
  allocation_verified: false;
  receipt_verified: false;
  warnings: string[];
};

export async function getShortageAnalysis(signal?: AbortSignal): Promise<ShortageAnalysis> {
  const response = await backendRequest(
    "/api/v1/reservations/shortage-analysis", "GET", undefined, signal,
  );
  if (typeof response !== "object" || response === null || !("data" in response)) {
    throw new Error("예약 검토 응답 형식이 올바르지 않습니다.");
  }
  const data = response.data;
  if (typeof data !== "object" || data === null || !("status" in data) ||
      (data.status !== "CONDITIONAL" && data.status !== "HOLD") ||
      !("source_system" in data) || data.source_system !== "SYNTHETIC_DEMO" ||
      !("required_quantity" in data) || typeof data.required_quantity !== "number" ||
      !("warnings" in data) || !Array.isArray(data.warnings)) {
    throw new Error("예약 검토 응답 데이터가 올바르지 않습니다.");
  }
  return data as ShortageAnalysis;
}
