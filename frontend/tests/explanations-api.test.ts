import { afterEach, describe, expect, it, vi } from "vitest";
import { getPolicyExplanation, parseExplanation } from "../src/api/explanations";

export const answer = {
  schema_version: "1.0", tenant_id: "demo", request_id: "req_internal_test",
  trace_id: "tr_test", evidence_ids: [], warnings: [], as_of: "2026-09-28T00:00:00Z",
  data: {
    status: "ANSWER", conclusion: "검수 후 출고합니다.", used_facts: ["입고와 검수 후 출고"],
    used_numeric_facts: [{ field: "required_qty", value: 0, unit: "count" }],
    citations: [{ source_id: "policy_shipping_demo", version: "v2" }],
    next_check: "입고 확인", model_used: true, data_mode: "SYNTHETIC_DEMO",
    request_id: "req_internal_test", warnings: [],
    c04_lookup: [{ source_id: "policy_shipping_demo", version: "v2", chunk_id: "exact-backend-key" }],
  },
};

describe("C06 explanation API contract (mock HTTP)", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("exact policy request, backend envelope and internal request_id", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify(answer), { status: 200 }));
    vi.stubGlobal("fetch", fetcher);
    const result = await getPolicyExplanation("예약상품은 언제 출고해?");
    expect(result.data.request_id).toBe("req_internal_test");
    expect(result.data.used_numeric_facts[0].value).toBe(0);
    expect(fetcher).toHaveBeenCalledWith(expect.stringContaining("/api/v1/retrieval/explanations"),
      expect.objectContaining({ method: "POST", body: JSON.stringify({ question: "예약상품은 언제 출고해?", condition: "CITATION", scope: "POLICY_ONLY" }) }));
  });

  it.each([
    { data: { ...answer.data, model_used: false } },
    { data: { ...answer.data, used_numeric_facts: [{ field: "required_qty", value: null, unit: "count" }] } },
    { data: { ...answer.data, c04_lookup: [{ source_id: "x", version: "v1" }] } },
    { data: { ...answer.data, request_id: "different" } },
    { data: { ...answer.data, citations: [] } },
  ])("malformed or contradictory ANSWER is rejected", (change) => {
    expect(() => parseExplanation({ ...answer, ...change })).toThrow();
  });

  it("HOLD with model_used=false preserves its reason and never creates facts", () => {
    const hold = { ...answer, data: { ...answer.data, status: "HOLD", model_used: false,
      used_facts: [], used_numeric_facts: [], citations: [], c04_lookup: [],
      warnings: ["NOT_SUPPORTED_C02_RUNTIME_SOURCE_MISSING"] } };
    expect(parseExplanation(hold).data.warnings).toEqual(["NOT_SUPPORTED_C02_RUNTIME_SOURCE_MISSING"]);
  });
});
