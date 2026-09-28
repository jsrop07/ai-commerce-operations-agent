import {
  describe,
  expect,
  it,
} from "vitest";

import {
  parseDay10DelayImpactResponse,
  parseDay10DelayImpactsResponse,
} from "../src/api/day10";

function envelope<T>(data: T[]) {
  return {
    schema_version: "1.0",
    tenant_id: "demo_store",
    request_id: "req_delay_001",
    trace_id: "trace_delay_001",
    data,
    evidence_ids: [],
    warnings: [],
    as_of: "2026-09-11T06:00:00Z",
  };
}

function makeImpact(
  overrides: Record<string, unknown> = {},
) {
  return {
    incoming_id: "incoming_001",

    expected_at_before:
      "2026-09-20T01:00:00Z",
    expected_at_after:
      "2026-09-22T01:00:00Z",

    impact_state: "KNOWN",

    affected_tasks: [
      {
        target_type: "TASK",
        target_id: "task_001",
        before:
          "2026-09-19T01:00:00Z",
        after:
          "2026-09-21T01:00:00Z",
        lag_hours: 48,
        reason: "입고 지연 영향",
        evidence_ids: [
          "ev_task_001",
        ],
      },
    ],

    affected_reservations: [
      {
        target_type:
          "RESERVATION_ORDER",
        target_id:
          "reservation_001",
        before: null,
        after: null,
        lag_hours: null,
        reason:
          "예약주문 일정 미확정",
        evidence_ids: [],
      },
    ],

    affected_launch_events: [
      {
        target_type:
          "LAUNCH_EVENT",
        target_id:
          "launch_001",
        before:
          "2026-09-21T01:00:00Z",
        after:
          "2026-09-23T01:00:00Z",
        lag_hours: 48,
        reason:
          "출시 준비 일정 영향",
        evidence_ids: [],
      },
    ],

    critical_path_affected: true,

    as_of:
      "2026-09-11T06:00:00Z",
    freshness: "FRESH",
    quality: "VERIFIED",

    source_classification:
      "SANITIZED_REAL",

    evidence_ids: [
      "ev_incoming_001",
    ],

    request_id:
      "req_impact_001",
    trace_id:
      "trace_impact_001",

    ...overrides,
  };
}

describe("Day 10 delay impact API parser", () => {
  it("KNOWN impact의 Task/예약/출시 영향을 파싱한다", () => {
    const result =
      parseDay10DelayImpactsResponse(
        envelope([
          makeImpact(),
        ]),
      );

    expect(
      result.data[0].impact_state,
    ).toBe("KNOWN");

    expect(
      result.data[0]
        .affected_tasks[0]
        .target_type,
    ).toBe("TASK");

    expect(
      result.data[0]
        .affected_reservations[0]
        .target_type,
    ).toBe(
      "RESERVATION_ORDER",
    );

    expect(
      result.data[0]
        .affected_launch_events[0]
        .target_type,
    ).toBe("LAUNCH_EVENT");
  });

  it("NONE은 영향 0건으로 보존한다", () => {
    const result =
      parseDay10DelayImpactResponse(
        makeImpact({
          impact_state: "NONE",
          affected_tasks: [],
          affected_reservations: [],
          affected_launch_events: [],
          critical_path_affected: false,
        }),
      );

    expect(
      result.impact_state,
    ).toBe("NONE");

    expect(
      result.affected_tasks,
    ).toHaveLength(0);

    expect(
      result.affected_reservations,
    ).toHaveLength(0);

    expect(
      result.affected_launch_events,
    ).toHaveLength(0);

    expect(
      result.critical_path_affected,
    ).toBe(false);
  });

  it("UNKNOWN을 영향 0건으로 변환하지 않는다", () => {
    const result =
      parseDay10DelayImpactResponse(
        makeImpact({
          impact_state: "UNKNOWN",

          expected_at_before: null,
          expected_at_after: null,

          affected_tasks: [],
          affected_reservations: [],
          affected_launch_events: [],

          critical_path_affected: null,

          as_of: null,
          freshness: "UNKNOWN",

          source_classification:
            "CONTRACT_ONLY",
        }),
      );

    expect(
      result.impact_state,
    ).toBe("UNKNOWN");

    expect(
      result.expected_at_before,
    ).toBeNull();

    expect(
      result.expected_at_after,
    ).toBeNull();

    expect(
      result.critical_path_affected,
    ).toBeNull();

    expect(
      result.as_of,
    ).toBeNull();
  });

  it("BLOCKED와 SOURCE_QUALITY_BLOCKED를 보존한다", () => {
    const result =
      parseDay10DelayImpactResponse(
        makeImpact({
          impact_state: "BLOCKED",

          expected_at_before: null,
          expected_at_after: null,

          affected_tasks: [],
          affected_reservations: [],
          affected_launch_events: [],

          critical_path_affected: null,

          freshness: "UNKNOWN",
          quality:
            "SOURCE_QUALITY_BLOCKED",

          source_classification:
            "SOURCE_QUALITY_BLOCKED",
        }),
      );

    expect(
      result.impact_state,
    ).toBe("BLOCKED");

    expect(
      result.source_classification,
    ).toBe(
      "SOURCE_QUALITY_BLOCKED",
    );

    expect(
      result.critical_path_affected,
    ).toBeNull();
  });

  it("영향 항목의 nullable before/after/lag를 임의값으로 만들지 않는다", () => {
    const result =
      parseDay10DelayImpactResponse(
        makeImpact({
          affected_tasks: [
            {
              target_type: "TASK",
              target_id: "task_null",
              before: null,
              after: null,
              lag_hours: null,
              reason: null,
              evidence_ids: [],
            },
          ],
        }),
      );

    const item =
      result.affected_tasks[0];

    expect(
      item.before,
    ).toBeNull();

    expect(
      item.after,
    ).toBeNull();

    expect(
      item.lag_hours,
    ).toBeNull();

    expect(
      item.reason,
    ).toBeNull();
  });

  it("잘못된 impact_state는 거부한다", () => {
    expect(() =>
      parseDay10DelayImpactResponse(
        makeImpact({
          impact_state: "NO_IMPACT",
        }),
      ),
    ).toThrow(
      "Schedule impact state is malformed",
    );
  });

  it("잘못된 target_type은 거부한다", () => {
    expect(() =>
      parseDay10DelayImpactResponse(
        makeImpact({
          affected_tasks: [
            {
              target_type: "ORDER",
              target_id: "bad_001",
              before: null,
              after: null,
              lag_hours: null,
              reason: null,
              evidence_ids: [],
            },
          ],
        }),
      ),
    ).toThrow(
      "Backend schedule delay impact item is malformed",
    );
  });
});