import { describe, expect, it } from "vitest";

import {
  parseDay10DependenciesResponse,
  parseDay10LaunchEventsResponse,
  parseDay10TasksResponse,
} from "../src/api/day10";

function envelope(data: unknown[]) {
  return {
    schema_version: "1.0",
    tenant_id: "demo_store",
    request_id: "req_day10_test",
    trace_id: "tr_day10_test",
    data,
    evidence_ids: [],
    warnings: [],
    as_of: "2026-09-11T06:00:00Z",
  };
}

describe("Day 10 schedule adapter", () => {
  it("launch event의 Flow, timezone, source 정보를 보존한다", () => {
    const result = parseDay10LaunchEventsResponse(
      envelope([
        {
          id: "launch_demo_001",
          product_id: "prd_demo_001",
          launch_at: "2026-09-20T01:00:00Z",
          flow_template: "STANDARD_LAUNCH",
          status: "PLANNED",

          flow: "FLOW_A",
          template_id: "launch-flow-a",
          version: "1.0",
          timezone: "Asia/Seoul",

          as_of: "2026-09-11T06:00:00Z",
          freshness: "FRESH",
          source_classification: "FIXTURE",
          evidence_ids: ["ev_launch_001"],
        },
      ]),
    );

    expect(result.data[0]).toMatchObject({
      flow: "FLOW_A",
      timezone: "Asia/Seoul",
      source_classification: "FIXTURE",
    });
  });

  it("Task deadline null을 임의 날짜로 변환하지 않는다", () => {
    const result = parseDay10TasksResponse(
      envelope([
        {
          id: "task_demo_001",
          type: "INCOMING_REVIEW",
          title: "입고 일정 확인",
          deadline: null,
          priority: "HIGH",
          status: "BLOCKED",
          source_reason: "입고일 미확정",

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
    expect(result.data[0].owner).toBeNull();
    expect(result.data[0].duration_hours).toBeNull();
    expect(result.data[0].as_of).toBeNull();
  });

  it("dependency lag_hours null을 0으로 변환하지 않는다", () => {
    const result =
      parseDay10DependenciesResponse(
        envelope([
          {
            predecessor_id: "task_demo_001",
            successor_id: "task_demo_002",
            lag_hours: null,
            as_of: null,
            source_classification: "CONTRACT_ONLY",
            evidence_ids: [],
          },
        ]),
      );

    expect(result.data[0].lag_hours).toBeNull();
    expect(
      result.data[0].source_classification,
    ).toBe("CONTRACT_ONLY");
  });

  it("SOURCE_QUALITY_BLOCKED를 정상적인 source 상태로 보존한다", () => {
    const result =
      parseDay10DependenciesResponse(
        envelope([
          {
            predecessor_id: "task_demo_001",
            successor_id: "task_demo_002",
            lag_hours: null,
            as_of: null,
            source_classification:
              "SOURCE_QUALITY_BLOCKED",
            evidence_ids: ["ev_source_quality"],
          },
        ]),
      );

    expect(
      result.data[0].source_classification,
    ).toBe("SOURCE_QUALITY_BLOCKED");
  });

  it("알 수 없는 source classification은 거부한다", () => {
    expect(() =>
      parseDay10DependenciesResponse(
        envelope([
          {
            predecessor_id: "task_demo_001",
            successor_id: "task_demo_002",
            lag_hours: 24,
            as_of: "2026-09-11T06:00:00Z",
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
            id: "launch_demo_001",
            product_id: "prd_demo_001",
            launch_at: "2026-09-20T01:00:00Z",
            flow_template: "STANDARD_LAUNCH",
            status: "PLANNED",

            flow: "FLOW_C",
            template_id: "invalid-flow",
            version: "1.0",
            timezone: "Asia/Seoul",

            as_of: "2026-09-11T06:00:00Z",
            freshness: "FRESH",
            source_classification: "FIXTURE",
            evidence_ids: [],
          },
        ]),
      ),
    ).toThrow(
      "Schedule flow is malformed",
    );
  });
});