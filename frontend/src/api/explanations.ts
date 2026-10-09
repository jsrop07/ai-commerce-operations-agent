import type { ApiEnvelope } from "../types/contracts";
import type { C04Key } from "./day04";
import { BackendHttpError } from "./backendHttp";

export type Explanation = {
  status: "ANSWER" | "HOLD";
  conclusion: string;
  used_facts: string[];
  used_numeric_facts: { field: string; value: number; unit: string }[];
  citations: { source_id: string; version: string }[];
  next_check: string | null;
  model_used: boolean;
  data_mode: "SYNTHETIC_DEMO";
  request_id: string;
  warnings: string[];
  c04_lookup: Required<C04Key>[];
};

const record = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);
const nonempty = (value: unknown): value is string =>
  typeof value === "string" && value.trim().length > 0;
const strings = (value: unknown): value is string[] =>
  Array.isArray(value) && value.every(nonempty);

export function parseExplanation(value: unknown): ApiEnvelope<Explanation> {
  if (!record(value) || value.schema_version !== "1.0" ||
    !nonempty(value.tenant_id) || !nonempty(value.request_id) ||
    !nonempty(value.trace_id) || !strings(value.evidence_ids) ||
    !strings(value.warnings) || !nonempty(value.as_of) || !record(value.data)) {
    throw new Error("Malformed explanation envelope");
  }
  const data = value.data;
  if ((data.status !== "ANSWER" && data.status !== "HOLD") ||
    !nonempty(data.conclusion) || !strings(data.used_facts) ||
    !Array.isArray(data.used_numeric_facts) || !Array.isArray(data.citations) ||
    !(data.next_check === null || nonempty(data.next_check)) ||
    typeof data.model_used !== "boolean" || data.data_mode !== "SYNTHETIC_DEMO" ||
    data.request_id !== value.request_id || !strings(data.warnings) ||
    !Array.isArray(data.c04_lookup)) {
    throw new Error("Malformed explanation response");
  }
  if (!data.used_numeric_facts.every((fact: unknown) => record(fact) &&
    nonempty(fact.field) && typeof fact.value === "number" &&
    Number.isSafeInteger(fact.value) && nonempty(fact.unit)) ||
    !data.citations.every((citation: unknown) => record(citation) &&
      nonempty(citation.source_id) && nonempty(citation.version)) ||
    !data.c04_lookup.every((key: unknown) => record(key) &&
      nonempty(key.source_id) && nonempty(key.version) && nonempty(key.chunk_id))) {
    throw new Error("Malformed explanation evidence");
  }
  if (data.status === "ANSWER" && (!data.model_used || data.citations.length === 0 ||
    data.warnings.length > 0) || data.status === "HOLD" &&
    (data.used_facts.length > 0 || data.used_numeric_facts.length > 0)) {
    throw new Error("Inconsistent explanation status");
  }
  return value as unknown as ApiEnvelope<Explanation>;
}

export async function getPolicyExplanation(question: string, signal?: AbortSignal): Promise<ApiEnvelope<Explanation>> {
  const deadline = AbortSignal.timeout(70_000);
  const requestSignal = signal ? AbortSignal.any([signal, deadline]) : deadline;
  const response = await fetch(`${import.meta.env.VITE_BACKEND_BASE_URL ?? ""}/api/v1/retrieval/explanations`, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({ question, condition: "CITATION", scope: "POLICY_ONLY" }),
    signal: requestSignal,
  });
  if (!response.ok) {
    const value: unknown = await response.json().catch(() => null);
    const detail = record(value) ? value.detail : null;
    const code = typeof detail === "string" ? detail :
      record(detail) && typeof detail.code === "string" ? detail.code : null;
    throw new BackendHttpError(response.status, code);
  }
  return parseExplanation(await response.json());
}
