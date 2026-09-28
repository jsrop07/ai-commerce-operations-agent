import {
  describe,
  expect,
  it,
} from "vitest";

import {
  parseDay10DependenciesResponse,
  parseDay10LaunchEventsResponse,
  parseDay10TasksResponse,
} from "../src/api/day10";

function envelope<T>(data: T[]) {
  return {
    schema_version: "1.0",
    tenant_id: "demo_store",
    request_id: "req_day10_test",
    trace_id: "tr_day10_test",
    data,
    evidence_ids: ["evidence_day10"],
    warnings: [],
    as_of: "2026-09-11T06:00:00Z",
  };
}

describe("Day 10 schedule API parser", () => {
  it("C03 숫자 priority와 missing feature null을 보존하고 주문 ID를 소비하지 않는다", () => {
    const feature = { raw: null, normalized: null, weight: 0.25, contribution: null, reason: "missing" };
    const task = parseDay10TasksResponse(envelope([{
      id: "task-shortage", task_id: "task-shortage", tenant_id: "demo_store",
      reservation_id: "reservation-a", sku_id: "sku-a", task_type: "RESERVATION_SHORTAGE",
      title: "예약 부족", deadline: null, risk_level: "HIGH", affected_count: 1,
      aging_hours: 12, priority: 42, priority_reason: "rule", status: "PROPOSED",
      source_reason: "CONFIRMED", source_classification: "FIXTURE", evidence_ids: [],
      as_of: "2026-09-11T06:00:00Z", replay_count: 0, priority_rule_score: 42,
      priority_breakdown: { deadline: feature, risk: feature, business_impact: feature, aging: feature },
      priority_rule_version: "task-priority.v0.1", priority_provenance: "RULE",
      priority_calibration_status: "DAY11_BASELINE_UNVALIDATED",
      priority_missing_features: ["deadline"], priority_coverage_weight: 0.75,
      priority_as_of: "2026-09-11T06:00:00Z", affected_order_ids: ["private-order"],
    }])).data[0];
    expect(task.priority).toBe(42);
    if (!("reservation_id" in task)) throw new Error("C03 task expected");
    expect(task.priority_breakdown.deadline.normalized).toBeNull();
    expect(task.priority_breakdown.deadline.contribution).toBeNull();
    expect(task.priority_calibration_status).toBe("DAY11_BASELINE_UNVALIDATED");
    expect(task).not.toHaveProperty("affected_order_ids");
  });
  it("launch event의 timezone, source, nullable as_of를 보존한다", () => {
    const result = parseDay10LaunchEventsResponse(
      envelope([
        {
          id: "launch_001",
          product_id: "prd_001",
          launch_at: "2026-09-20T01:00:00Z",
          flow_template: "STANDARD_LAUNCH",
          status: "PLANNED",

          flow: "FLOW_A",
          template_id: "launch-flow-a",
          version: "1.0",
          timezone: "Asia/Seoul",

          as_of: null,
          freshness: "UNKNOWN",
          source_classification: "CONTRACT_ONLY",
          evidence_ids: ["ev_launch_001"],
        },
      ]),
    );

    expect(result.data[0].timezone).toBe(
      "Asia/Seoul",
    );

    expect(result.data[0].as_of).toBeNull();

    expect(
      result.data[0].source_classification,
    ).toBe("CONTRACT_ONLY");
  });

  it("task의 nullable deadline과 duration을 0이나 날짜로 대체하지 않는다", () => {
    const result = parseDay10TasksResponse(
      envelope([
        {
          id: "task_001",
          type: "INCOMING_CONFIRMATION",
          title: "입고일 확인",
          deadline: null,
          priority: "HIGH",
          status: "BLOCKED",
          source_reason: "confirmation missing",

          owner: null,
          duration_hours: null,
          flow: "FLOW_A",

          as_of: null,
          freshness: "UNKNOWN",
          source_classification: "BLOCKED",
          evidence_ids: [],
        },
      ]),
    );

    expect(result.data[0].deadline).toBeNull();
    expect(
      result.data[0].duration_hours,
    ).toBeNull();
    expect(result.data[0].owner).toBeNull();
    expect(result.data[0].as_of).toBeNull();
  });

  it("dependency의 nullable lag_hours를 그대로 보존한다", () => {
    const result =
      parseDay10DependenciesResponse(
        envelope([
          {
            predecessor_id: "task_001",
            successor_id: "task_002",
            lag_hours: null,
            as_of: null,
            source_classification:
              "CONTRACT_ONLY",
            evidence_ids: ["ev_dep_001"],
          },
        ]),
      );

    expect(
      result.data[0].lag_hours,
    ).toBeNull();
  });

  it("SOURCE_QUALITY_BLOCKED를 정상 source classification으로 허용한다", () => {
    const result = parseDay10TasksResponse(
      envelope([
        {
          id: "task_002",
          type: "INVENTORY_DEPENDENCY",
          title: "재고 Source 확인",
          deadline: null,
          priority: "MEDIUM",
          status: "BLOCKED",
          source_reason:
            "inventory source quality blocked",

          owner: null,
          duration_hours: null,
          flow: "FLOW_B",

          as_of: null,
          freshness: "UNKNOWN",
          source_classification:
            "SOURCE_QUALITY_BLOCKED",
          evidence_ids: [],
        },
      ]),
    );

    expect(
      result.data[0].source_classification,
    ).toBe("SOURCE_QUALITY_BLOCKED");
  });

  it("알 수 없는 source classification은 거부한다", () => {
    expect(() =>
      parseDay10TasksResponse(
        envelope([
          {
            id: "task_bad_source",
            type: "TEST",
            title: "잘못된 Source",
            deadline: null,
            priority: "LOW",
            status: "PROPOSED",
            source_reason: "test",

            owner: null,
            duration_hours: null,
            flow: "FLOW_A",

            as_of: null,
            freshness: "UNKNOWN",
            source_classification: "LIVE",
            evidence_ids: [],
          },
        ]),
      ),
    ).toThrow(
      "Schedule source classification is malformed",
    );
  });

  it("알 수 없는 Flow는 거부한다", () => {
    expect(() =>
      parseDay10LaunchEventsResponse(
        envelope([
          {
            id: "launch_bad_flow",
            product_id: "prd_001",
            launch_at: "2026-09-20T01:00:00Z",
            flow_template: "STANDARD_LAUNCH",
            status: "PLANNED",

            flow: "FLOW_C",
            template_id: "bad-flow",
            version: "1.0",
            timezone: "Asia/Seoul",

            as_of: null,
            freshness: "UNKNOWN",
            source_classification: "FIXTURE",
            evidence_ids: [],
          },
        ]),
      ),
    ).toThrow(
      "Schedule flow is malformed",
    );
  });

  it("잘못된 envelope schema_version은 거부한다", () => {
    expect(() =>
      parseDay10LaunchEventsResponse({
        ...envelope([]),
        schema_version: "2.0",
      }),
    ).toThrow(
      "Backend schedule envelope is malformed",
    );
  });
});
