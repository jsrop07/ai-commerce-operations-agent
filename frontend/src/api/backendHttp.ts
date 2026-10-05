const backendBaseUrl = import.meta.env.VITE_BACKEND_BASE_URL ?? "";

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
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  });
  if (!response.ok) throw new Error(`Backend ${method} failed: ${response.status}`);
  return response.json() as Promise<unknown>;
}
