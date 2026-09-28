import {
  describe,
  expect,
  it,
} from "vitest";

import {
  parseDay10ReplanProposalResponse,
  parseDay10ReplanProposalsResponse,
} from "../src/api/day10";

function makeProposal(
  overrides: Record<string, unknown> = {},
) {
  return {
    proposal_id:
      "proposal_001",

    incoming_id:
      "incoming_001",

    status:
      "PROPOSED",

    before: [
      {
        target_type:
          "LAUNCH_EVENT",
        target_id:
          "launch_001",
        scheduled_at:
          "2026-09-20T01:00:00Z",
        evidence_ids: [],
      },
    ],

    proposed_after: [
      {
        target_type:
          "LAUNCH_EVENT",
        target_id:
          "launch_001",
        scheduled_at:
          "2026-09-22T01:00:00Z",
        evidence_ids: [],
      },
    ],

    reason:
      "입고 일정 지연",

    confidence: 0.82,

    downstream_impact:
      "출시 준비 Task 재검토 필요",

    conflict: null,

    as_of:
      "2026-09-11T06:00:00Z",

    freshness: "FRESH",

    source_classification:
      "FIXTURE",

    evidence_ids: [
      "ev_replan_001",
    ],

    request_id:
      "req_replan_001",

    trace_id:
      "trace_replan_001",

    external_execution_allowed:
      false,

    ...overrides,
  };
}

function envelope(data: unknown[]) {
  return {
    schema_version: "1.0",
    tenant_id: "demo_store",
    request_id:
      "req_replans",
    trace_id:
      "trace_replans",
    data,
    evidence_ids: [],
    warnings: [],
    as_of:
      "2026-09-11T06:00:00Z",
  };
}

describe("Day 10 replan API parser", () => {
  it("before/proposed_after를 보존한다", () => {
    const result =
      parseDay10ReplanProposalsResponse(
        envelope([
          makeProposal(),
        ]),
      );

    expect(
      result.data[0].before[0]
        .scheduled_at,
    ).toBe(
      "2026-09-20T01:00:00Z",
    );

    expect(
      result.data[0]
        .proposed_after[0]
        .scheduled_at,
    ).toBe(
      "2026-09-22T01:00:00Z",
    );
  });

  it("nullable 일정은 임의값으로 만들지 않는다", () => {
    const result =
      parseDay10ReplanProposalResponse(
        makeProposal({
          before: [
            {
              target_type:
                "TASK",
              target_id:
                "task_001",
              scheduled_at: null,
              evidence_ids: [],
            },
          ],
        }),
      );

    expect(
      result.before[0]
        .scheduled_at,
    ).toBeNull();
  });

  it("confidence null을 허용한다", () => {
    const result =
      parseDay10ReplanProposalResponse(
        makeProposal({
          confidence: null,
        }),
      );

    expect(
      result.confidence,
    ).toBeNull();
  });

  it("confidence 범위를 검증한다", () => {
    expect(() =>
      parseDay10ReplanProposalResponse(
        makeProposal({
          confidence: 1.5,
        }),
      ),
    ).toThrow(
      "Schedule replan confidence is malformed",
    );
  });

  it("external_execution_allowed=true를 거부한다", () => {
    expect(() =>
      parseDay10ReplanProposalResponse(
        makeProposal({
          external_execution_allowed:
            true,
        }),
      ),
    ).toThrow(
      "Backend schedule replan proposal is malformed",
    );
  });

  it("알 수 없는 status를 거부한다", () => {
    expect(() =>
      parseDay10ReplanProposalResponse(
        makeProposal({
          status:
            "AUTO_EXECUTED",
        }),
      ),
    ).toThrow(
      "Schedule replan status is malformed",
    );
  });
});