import {
  describe,
  expect,
  it,
} from "vitest";

import {
  getTaskProposalSafetyLabel,
  getTaskProposalStatusLabel,
} from "../src/features/tasks/taskProposalViewModels";

import type {
  TaskProposal,
} from "../src/types/contracts";

const proposal: TaskProposal = {
  proposal_id: "proposal_day09_001",
  task_type: "RESERVATION_REVIEW",
  title: "예약주문 재고 확인",

  status: "PROPOSED",

  source_reason:
    "secured_qty와 confirmed_incoming을 확정할 수 없어 운영자 확인이 필요합니다.",

  priority: null,

  as_of: "2026-09-10T10:00:00Z",

  evidence_ids: [
    "evidence_reservation_day09_001",
  ],

  external_execution_allowed: false,
};

describe("taskProposalViewModels", () => {
  it("PROPOSED를 제안됨으로 표시한다", () => {
    expect(
      getTaskProposalStatusLabel(
        "PROPOSED",
      ),
    ).toBe("제안됨");
  });

  it("검토·수정·거절 상태를 구분한다", () => {
    expect(
      getTaskProposalStatusLabel(
        "UNDER_REVIEW",
      ),
    ).toBe("검토 중");

    expect(
      getTaskProposalStatusLabel(
        "EDITED",
      ),
    ).toBe("수정됨");

    expect(
      getTaskProposalStatusLabel(
        "DISMISSED",
      ),
    ).toBe("거절됨");
  });

  it("외부 Provider 실행이 없음을 명시한다", () => {
    expect(
      getTaskProposalSafetyLabel(
        proposal,
      ),
    ).toBe(
      "내부 검토 제안 · 외부 실행 없음",
    );
  });
});