import {
  describe,
  expect,
  it,
} from "vitest";

import type {
  ScheduleDelayImpact,
} from "../src/types/contracts";

import {
  buildDelayImpactViewModel,
} from "../src/features/schedule/impactViewModel";

function makeImpact(
  overrides: Partial<ScheduleDelayImpact> = {},
): ScheduleDelayImpact {
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
          "예약 일정 미확정",
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
          "출시 일정 영향",
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

describe(
  "Day 10 delay impact view model",
  () => {
    it("KNOWN 영향의 전체 영향 건수를 계산한다", () => {
      const result =
        buildDelayImpactViewModel(
          makeImpact(),
        );

      expect(
        result.impactStateLabel,
      ).toBe("지연 영향 확인됨");

      expect(
        result.totalImpactCount,
      ).toBe(3);

      expect(
        result.tasks,
      ).toHaveLength(1);

      expect(
        result.reservations,
      ).toHaveLength(1);

      expect(
        result.launchEvents,
      ).toHaveLength(1);
    });

    it("NONE은 영향 없음으로 표시한다", () => {
      const result =
        buildDelayImpactViewModel(
          makeImpact({
            impact_state: "NONE",
            affected_tasks: [],
            affected_reservations: [],
            affected_launch_events: [],
            critical_path_affected:
              false,
          }),
        );

      expect(
        result.impactStateLabel,
      ).toBe("영향 없음");

      expect(
        result.totalImpactCount,
      ).toBe(0);

      expect(
        result.criticalPathLabel,
      ).toBe(
        "Critical Path 영향 없음",
      );
    });

    it("UNKNOWN을 영향 없음으로 바꾸지 않는다", () => {
      const result =
        buildDelayImpactViewModel(
          makeImpact({
            impact_state: "UNKNOWN",

            expected_at_before: null,
            expected_at_after: null,

            affected_tasks: [],
            affected_reservations: [],
            affected_launch_events: [],

            critical_path_affected:
              null,

            as_of: null,
            freshness: "UNKNOWN",

            source_classification:
              "CONTRACT_ONLY",
          }),
        );

      expect(
        result.impactStateLabel,
      ).toBe("영향 여부 미확정");

      expect(
        result.expectedAtBeforeLabel,
      ).toBe("일정 미확정");

      expect(
        result.expectedAtAfterLabel,
      ).toBe("일정 미확정");

      expect(
        result.criticalPathLabel,
      ).toBe(
        "Critical Path 영향 미확정",
      );

      expect(
        result.asOfLabel,
      ).toBe("기준 시각 미확정");

      expect(
        result.sourceIsConfirmed,
      ).toBe(false);
    });

    it("BLOCKED를 영향 계산 불가로 표시한다", () => {
      const result =
        buildDelayImpactViewModel(
          makeImpact({
            impact_state: "BLOCKED",

            affected_tasks: [],
            affected_reservations: [],
            affected_launch_events: [],

            critical_path_affected:
              null,

            quality:
              "SOURCE_QUALITY_BLOCKED",

            source_classification:
              "SOURCE_QUALITY_BLOCKED",
          }),
        );

      expect(
        result.impactStateLabel,
      ).toBe("영향 계산 불가");

      expect(
        result.sourceLabel,
      ).toBe("원천 품질 문제");

      expect(
        result.sourceIsConfirmed,
      ).toBe(false);
    });

    it("nullable before/after/lag를 임의값으로 만들지 않는다", () => {
      const result =
        buildDelayImpactViewModel(
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

            affected_reservations: [],
            affected_launch_events: [],
          }),
        );

      const task =
        result.tasks[0];

      expect(
        task.before,
      ).toBeNull();

      expect(
        task.beforeLabel,
      ).toBe("일정 미확정");

      expect(
        task.after,
      ).toBeNull();

      expect(
        task.afterLabel,
      ).toBe("일정 미확정");

      expect(
        task.lagHours,
      ).toBeNull();

      expect(
        task.lagLabel,
      ).toBe("지연 시간 미확정");

      expect(
        task.reasonLabel,
      ).toBe("지연 사유 미확정");
    });

    it("request_id와 trace_id를 보존한다", () => {
      const result =
        buildDelayImpactViewModel(
          makeImpact(),
        );

      expect(
        result.requestId,
      ).toBe("req_impact_001");

      expect(
        result.traceId,
      ).toBe("trace_impact_001");
    });
  },
);