import { afterEach, describe, expect, it, vi } from "vitest";
import { BackendHttpError } from "../src/api/backendHttp";
import { bootstrapDemoSession, getDemoSessionStatus } from "../src/api/demoSession";

afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs(); });

describe("C22 Demo Session browser contract", () => {
  it("bootstraps and reads status through same-origin cookie requests without retaining ID", async () => {
    vi.stubEnv("VITE_USE_REAL_BACKEND", "true");
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({
      session_id: "server-secret-id", status: "ACTIVE", expires_at: "2026-10-07T12:00:00Z",
    }) });
    vi.stubGlobal("fetch", fetchMock);
    expect(await bootstrapDemoSession()).toEqual({ status: "ACTIVE", expiresAt: "2026-10-07T12:00:00Z" });
    expect(await getDemoSessionStatus()).toEqual({ status: "ACTIVE", expiresAt: "2026-10-07T12:00:00Z" });
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "/api/v1/demo/session", "/api/v1/demo/session",
    ]);
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: "POST" });
    expect(fetchMock.mock.calls[0][1].headers).not.toHaveProperty("X-Actor-ID");
    expect(fetchMock.mock.calls[0][1]).not.toHaveProperty("body");
  });

  it("preserves backend session-required code for renewal UX", async () => {
    vi.stubEnv("VITE_USE_REAL_BACKEND", "true");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false, status: 401, json: async () => ({ detail: "DEMO_SESSION_REQUIRED" }),
    }));
    await expect(getDemoSessionStatus()).rejects.toEqual(
      new BackendHttpError(401, "DEMO_SESSION_REQUIRED"),
    );
  });
});
