import { describe, expect, it } from "vitest";
import type { ApiEnvelope } from "../src/types/contracts";
import { toUrgentQueueItems } from "../src/api/day04";

function envelope(data: unknown[], requestId = "req_day04"): ApiEnvelope<unknown[]> {
  return {
    schema_version: "1.0",
    tenant_id: "demo_store",
    request_id: requestId,
    trace_id: "tr_day04",
    data,
    evidence_ids: [],
    warnings: [],
    as_of: "2026-09-03T04:40:00Z",
  };
}

describe("Day 4 insight API boundary", () => {
  it("Queue에 필요한 공통 필드만 소비하고 evidence/proposal을 만들지 않는다", () => {
    const [item] = toUrgentQueueItems(
      envelope([
        {
          insight_id: "ins_day04",
          type: "INVENTORY_RISK",
          severity: "LOW",
          confidence: 1,
          summary: "오프라인 판매가 예상 재고에 반영되었습니다.",
          evidence_ids: ["evt_day04"],
          correlation_id: "corr_day04",
          calculation: { expected_inventory: 6 },
          model_run_id: null,
          rule_version: "shadow-inventory-v1",
        },
      ]),
    );

    expect(item.data).toEqual({
      insight_id: "ins_day04",
      type: "INVENTORY_RISK",
      severity: "LOW",
      confidence: 1,
      summary: "오프라인 판매가 예상 재고에 반영되었습니다.",
    });
    expect(item.data).not.toHaveProperty("evidence");
    expect(item.data).not.toHaveProperty("proposal");
  });

  it("빈 insight 목록을 빈 Queue로 유지한다", () => {
    expect(toUrgentQueueItems(envelope([]))).toEqual([]);
  });

  it("malformed insight item은 화면 계약으로 단언하지 않고 거부한다", () => {
    expect(() =>
      toUrgentQueueItems(envelope([{ insight_id: "missing-fields" }]))
    ).toThrow("Backend insight item is malformed");
  });

  it("긴 request_id를 자르거나 바꾸지 않는다", () => {
    const requestId = `req_${"x".repeat(512)}`;
    const [item] = toUrgentQueueItems(
      envelope(
        [{
          insight_id: "ins_day04",
          type: "INVENTORY_RISK",
          severity: "LOW",
          confidence: 1,
          summary: "요약",
        }],
        requestId,
      ),
    );

    expect(item.request_id).toBe(requestId);
  });
});