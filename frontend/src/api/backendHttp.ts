const backendBaseUrl = import.meta.env.VITE_BACKEND_BASE_URL ?? "";

export class BackendHttpError extends Error {
  constructor(public readonly status: number, public readonly code: string | null) {
    super(`Backend request failed: ${status}${code ? ` ${code}` : ""}`);
  }
}

function errorCode(value: unknown): string | null {
  if (typeof value !== "object" || value === null || !("detail" in value)) return null;
  const detail = value.detail;
  if (typeof detail === "string") return detail;
  if (typeof detail === "object" && detail !== null && "code" in detail && typeof detail.code === "string") {
    return detail.code;
  }
  return null;
}

export async function backendRequest(
  path: string,
  method: "GET" | "POST",
  body?: unknown,
  signal?: AbortSignal,
): Promise<unknown> {
  if (import.meta.env.VITE_USE_REAL_BACKEND !== "true") {
    throw new Error("Real backend mode is required");
  }
  const response = await fetch(`${backendBaseUrl}${path}`, {
    method,
    headers: body === undefined
      ? { Accept: "application/json" }
      : { Accept: "application/json", "Content-Type": "application/json" },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    signal,
  });
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null);
    throw new BackendHttpError(response.status, errorCode(payload));
  }
  return response.json() as Promise<unknown>;
}
