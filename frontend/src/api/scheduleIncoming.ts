import type { ApiEnvelope } from "../types/contracts";

export type IncomingRelatedTask = {
  id: string;
  task_type: "RESERVATION_SHORTAGE";
  title: string;
  status: string;
  due_at: string | null;
  priority: string | null;
  dependency_type: string;
};

export type IncomingSchedule = {
  id: string;
  external_reference: string | null;
  expected_arrival_at: string | null;
  incoming_status: string;
  confidence_status: string;
  source_system: "SYNTHETIC_DEMO";
  source_as_of: null;
  product_id: string;
  product_variant_id: string | null;
  related_tasks: IncomingRelatedTask[];
};

export type IncomingSchedulesData = {
  items: IncomingSchedule[];
  total: number;
};

const object = (x: unknown): x is Record<string, unknown> =>
  typeof x === "object" && x !== null && !Array.isArray(x);
const nullableString = (x: unknown): x is string | null => x === null || typeof x === "string";
const nonnegativeInteger = (x: unknown): x is number =>
  typeof x === "number" && Number.isSafeInteger(x) && x >= 0;

function parseTask(x: unknown): IncomingRelatedTask {
  if (!object(x) || typeof x.id !== "string" || x.task_type !== "RESERVATION_SHORTAGE" ||
      typeof x.title !== "string" || typeof x.status !== "string" ||
      !nullableString(x.due_at) || !nullableString(x.priority) ||
      typeof x.dependency_type !== "string") {
    throw new Error("입고 관련 Task 응답 형식이 올바르지 않습니다.");
  }
  return {
    id: x.id, task_type: "RESERVATION_SHORTAGE", title: x.title,
    status: x.status, due_at: x.due_at, priority: x.priority,
    dependency_type: x.dependency_type,
  };
}

function parseIncoming(x: unknown): IncomingSchedule {
  if (!object(x) || typeof x.id !== "string" || !nullableString(x.external_reference) ||
      !nullableString(x.expected_arrival_at) || typeof x.incoming_status !== "string" ||
      typeof x.confidence_status !== "string" || x.source_system !== "SYNTHETIC_DEMO" ||
      x.source_as_of !== null || typeof x.product_id !== "string" ||
      !nullableString(x.product_variant_id) || !Array.isArray(x.related_tasks)) {
    throw new Error("입고 일정 응답 형식이 올바르지 않습니다.");
  }
  return {
    id: x.id, external_reference: x.external_reference,
    expected_arrival_at: x.expected_arrival_at, incoming_status: x.incoming_status,
    confidence_status: x.confidence_status, source_system: "SYNTHETIC_DEMO",
    source_as_of: null, product_id: x.product_id,
    product_variant_id: x.product_variant_id,
    related_tasks: x.related_tasks.map(parseTask),
  };
}

export function parseIncomingSchedules(x: unknown): ApiEnvelope<IncomingSchedulesData> {
  if (!object(x) || x.schema_version !== "1.0" ||
      typeof x.tenant_id !== "string" || typeof x.request_id !== "string" ||
      typeof x.trace_id !== "string" || typeof x.as_of !== "string" ||
      !Array.isArray(x.warnings) || !x.warnings.every((w) => typeof w === "string") ||
      !Array.isArray(x.evidence_ids) || !x.evidence_ids.every((id) => typeof id === "string") ||
      !object(x.data) || !Array.isArray(x.data.items) || !nonnegativeInteger(x.data.total)) {
    throw new Error("입고 일정 API Envelope 형식이 올바르지 않습니다.");
  }
  const items = x.data.items.map(parseIncoming);
  if (items.length > x.data.total) throw new Error("입고 일정 건수가 올바르지 않습니다.");
  return { ...x, data: { items, total: x.data.total } } as ApiEnvelope<IncomingSchedulesData>;
}

export async function getIncomingSchedules(signal?: AbortSignal): Promise<ApiEnvelope<IncomingSchedulesData>> {
  if (import.meta.env.VITE_USE_REAL_BACKEND !== "true") {
    throw new Error("Synthetic DB 입고 일정 조회는 Backend 모드에서만 지원합니다.");
  }
  const base = import.meta.env.VITE_BACKEND_BASE_URL ?? "";
  const res = await fetch(`${base}/api/v1/schedule/incoming-shipments`, {
    method: "GET", headers: { Accept: "application/json" },
    credentials: "include", signal,
  });
  if (!res.ok) {
    const errorBody: unknown = await res.json().catch(() => null);
    const detail = object(errorBody) && object(errorBody.detail) ? errorBody.detail : null;
    const code = detail && typeof detail.code === "string" ? detail.code : null;
    throw new Error(`입고 일정 조회 실패 (HTTP ${res.status}${code ? ` · ${code}` : ""})`);
  }
  return parseIncomingSchedules(await res.json());
}
