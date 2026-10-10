import { backendRequest } from "./backendHttp";

export type DashboardQueueItem = {
  id: string;
  kind: "CONDITIONAL_RESERVATION" | "INVENTORY_STALE" | "TASK_REVIEW";
  state: "CONDITIONAL" | "DATA_STALE" | "REVIEW_PENDING";
  priority: "HIGH" | "MEDIUM" | "LOW" | null;
  title: string;
  reason: string;
  evidence_ids: string[];
  source_as_of: string | null;
  target_path: "/inventory" | "/schedule";
  target_id: string | null;
  task_status: string | null;
  task_due_at: string | null;
};

export type DashboardQueueData = {
  status: "READY" | "NO_DATA" | "CLEAR" | "ANALYSIS_UNAVAILABLE";
  calculation_mode: "ON_REQUEST";
  items: DashboardQueueItem[];
  source_counts: { reservations: number; inventory_snapshots: number; linked_tasks: number };
};

const record = (x: unknown): x is Record<string, unknown> =>
  typeof x === "object" && x !== null && !Array.isArray(x);
const nullableString = (x: unknown): x is string | null => x === null || typeof x === "string";

export function parseDashboardQueue(value: unknown): DashboardQueueData {
  if (!record(value) || !record(value.data) ||
      !["READY", "NO_DATA", "CLEAR", "ANALYSIS_UNAVAILABLE"].includes(String(value.data.status)) ||
      value.data.calculation_mode !== "ON_REQUEST" || !Array.isArray(value.data.items) ||
      !record(value.data.source_counts)) {
    throw new Error("긴급 Queue 응답 형식이 올바르지 않습니다.");
  }
  const counts = value.data.source_counts;
  if (![counts.reservations, counts.inventory_snapshots, counts.linked_tasks].every(
    (x) => typeof x === "number" && Number.isSafeInteger(x) && x >= 0,
  )) throw new Error("긴급 Queue 원천 건수가 올바르지 않습니다.");
  for (const item of value.data.items) {
    if (!record(item) || typeof item.id !== "string" ||
        !["CONDITIONAL_RESERVATION", "INVENTORY_STALE", "TASK_REVIEW"].includes(String(item.kind)) ||
        !["CONDITIONAL", "DATA_STALE", "REVIEW_PENDING"].includes(String(item.state)) ||
        (item.priority !== null && !["HIGH", "MEDIUM", "LOW"].includes(String(item.priority))) ||
        typeof item.title !== "string" || typeof item.reason !== "string" ||
        !Array.isArray(item.evidence_ids) || !item.evidence_ids.every((id) => typeof id === "string") ||
        !nullableString(item.source_as_of) ||
        (item.target_path !== "/inventory" && item.target_path !== "/schedule") ||
        !nullableString(item.target_id) || !nullableString(item.task_status) ||
        !nullableString(item.task_due_at)) {
      throw new Error("긴급 Queue 항목 형식이 올바르지 않습니다.");
    }
  }
  return value.data as DashboardQueueData;
}

export async function getDashboardQueue(signal?: AbortSignal): Promise<DashboardQueueData> {
  return parseDashboardQueue(await backendRequest("/api/v1/dashboard/urgent-queue", "GET", undefined, signal));
}
