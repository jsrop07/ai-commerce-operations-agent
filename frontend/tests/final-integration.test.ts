import { afterEach, describe, expect, it, vi } from "vitest";
import { BackendHttpError } from "../src/api/backendHttp";
import { aiProblem } from "../src/components/CommonAiDrawer";
import { resolveRoute, routes } from "../src/app/routes";

afterEach(() => vi.unstubAllGlobals());

describe("Local Demo final navigation and recovery", () => {
  it("removes Insights from menu and route resolution", () => {
    expect(routes.map((route) => String(route.path))).not.toContain("/insights");
    expect(resolveRoute("/insights", true).path).toBe("/");
  });

  it("explains an inaccessible owned conversation without calling it a session expiry", () => {
    const problem = aiProblem(new BackendHttpError(404, "CONVERSATION_NOT_FOUND"));
    expect(problem.sessionExpired).toBe(false);
    expect(problem.message).toContain("새 대화");
  });
});
