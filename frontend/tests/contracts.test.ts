import { describe, expect, expectTypeOf, it } from "vitest";
import type { ApiEnvelope, ApiError, DashboardData, InsightSummary } from "../src/types/contracts";
import {
  ambiguousSkuMappingFixture,
  agentWaitingApprovalFixture,
  dashboardFixture,
  freshnessFixtures,
  healthFixture,
  insightsFixture,
  lowConfidenceFixture,
  partialProviderFailureFixture,
  policyDeniedFixture,
} from "../src/mocks/fixtures";

describe("official frontend contracts", () => {
  it("consumes the common API envelope", () => {
    expectTypeOf(dashboardFixture).toMatchTypeOf<ApiEnvelope<DashboardData>>();
    expect(dashboardFixture).toMatchObject({
      schema_version: "1.0",
      tenant_id: "demo_store",
      evidence_ids: expect.any(Array),
      warnings: expect.any(Array),
      as_of: expect.any(String),
    });
  });

  it("consumes the Insight contract without attributing rule calculations to AI", () => {
    expectTypeOf(insightsFixture.data).toMatchTypeOf<InsightSummary[]>();
    expect(insightsFixture.data[0]).toMatchObject({
      insight_id: "ins_demo_001",
      type: "RESERVATION_SHORTAGE",
      severity: "HIGH",
      model_run_id: null,
      rule_version: "reservation-risk-v1",
    });
  });

  it("consumes official error envelopes", () => {
    expectTypeOf(partialProviderFailureFixture).toMatchTypeOf<ApiError>();
    expect(partialProviderFailureFixture.error).toEqual(expect.objectContaining({ code: "PARTIAL_PAGE", retryable: true }));
  });

  it("matches the current health response contract", () => {
    expect(healthFixture).toEqual({
      status: "ok",
      environment: "DEMO",
      contract_version: "1.0",
      write_mode: "disabled",
      global_write_kill: true,
    });
  });

  it("keeps stale freshness explicit", () => {
    expect(freshnessFixtures.STALE.data[0].freshness).toBe("STALE");
    expect(freshnessFixtures.STALE.warnings).not.toHaveLength(0);
  });

  it("uses the documented ambiguous mapping error", () => {
    expect(ambiguousSkuMappingFixture.error.code).toBe("AMBIGUOUS_SKU_MAPPING");
    expect(ambiguousSkuMappingFixture.error.retryable).toBe(false);
  });

  it("represents low confidence, policy denial, and approval waiting with official fields", () => {
    expect(lowConfidenceFixture.data[0].confidence).toBeLessThan(0.75);
    expect(policyDeniedFixture.error.code).toBe("PROVIDER_WRITE_BLOCKED");
    expect(agentWaitingApprovalFixture.data[0].status).toBe("PROPOSED");
  });
});
