import {
  render,
  screen,
} from "@testing-library/react";

import {
  describe,
  expect,
  it,
} from "vitest";

import ReplanReview from "../src/features/schedule/ReplanReview";

import {
  buildReplanReviewViewModel,
} from "../src/features/schedule/replanViewModel";

import type {
  ScheduleReplanProposal,
} from "../src/types/contracts";

function proposal(): ScheduleReplanProposal {
  return {
    proposal_id:
      "proposal_001",

    incoming_id:
      "incoming_001",

    status: "PROPOSED",

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
  };
}

describe("Day 10 ReplanReview", () => {
  it("기존 일정과 제안 일정을 함께 표시한다", () => {
    render(
      <ReplanReview
        model={
          buildReplanReviewViewModel(
            proposal(),
          )
        }
      />,
    );

    expect(
      screen.getByText(
        "기존 일정",
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        "제안 일정",
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        /2026-09-20/,
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        /2026-09-22/,
      ),
    ).toBeInTheDocument();
  });

  it("외부 자동 실행이 아님을 표시한다", () => {
    render(
      <ReplanReview
        model={
          buildReplanReviewViewModel(
            proposal(),
          )
        }
      />,
    );

    expect(
      screen.getByText(
        /Cafe24, eCount, POS/,
      ),
    ).toBeInTheDocument();

    expect(
      screen.queryByRole(
        "button",
        {
          name:
            /Cafe24|eCount|실행|적용/,
        },
      ),
    ).not.toBeInTheDocument();
  });

  it("신뢰도와 downstream impact를 표시한다", () => {
    render(
      <ReplanReview
        model={
          buildReplanReviewViewModel(
            proposal(),
          )
        }
      />,
    );

    expect(
      screen.getByText(
        /신뢰도: 82%/,
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        /출시 준비 Task 재검토 필요/,
      ),
    ).toBeInTheDocument();
  });

  it("request_id와 trace_id를 표시한다", () => {
    render(
      <ReplanReview
        model={
          buildReplanReviewViewModel(
            proposal(),
          )
        }
      />,
    );

    expect(
      screen.getByText(
        /req_replan_001/,
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        /trace_replan_001/,
      ),
    ).toBeInTheDocument();
  });
});