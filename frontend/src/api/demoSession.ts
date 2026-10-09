import { backendRequest } from "./backendHttp";

export type DemoSessionStatus = { status: "ACTIVE"; expiresAt: string };

function parseSession(value: unknown): DemoSessionStatus {
  if (typeof value !== "object" || value === null || !("status" in value) ||
    !("expires_at" in value) || value.status !== "ACTIVE" ||
    typeof value.expires_at !== "string" || !Number.isFinite(Date.parse(value.expires_at))) {
    throw new Error("Demo Session 응답을 확인할 수 없습니다.");
  }
  // The server response includes session_id; the browser shell does not retain or render it.
  return { status: "ACTIVE", expiresAt: value.expires_at };
}

export async function bootstrapDemoSession(signal?: AbortSignal): Promise<DemoSessionStatus> {
  return parseSession(await backendRequest("/api/v1/demo/session", "POST", undefined, signal));
}

export async function getDemoSessionStatus(signal?: AbortSignal): Promise<DemoSessionStatus> {
  return parseSession(await backendRequest("/api/v1/demo/session", "GET", undefined, signal));
}
