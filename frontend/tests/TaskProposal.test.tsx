import {
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";

import {
  afterEach,
  describe,
  expect,
  it,
} from "vitest";

import TaskProposal from "../src/features/tasks/TaskProposal";

import type {
  TaskProposal as TaskProposalModel,
} from "../src/types/contracts";

const proposal: TaskProposalModel = {
  proposal_id:
    "proposal_day09_001",

  task_type:
    "RESERVATION_REVIEW",

  title:
    "예약주문 재고 확인",

  status:
    "PROPOSED",

  source_reason:
    "secured_qty와 confirmed_incoming을 확정할 수 없어 운영자 확인이 필요합니다.",

  priority: null,

  as_of:
    "2026-09-10T10:00:00Z",

  evidence_ids: [
    "evidence_reservation_day09_001",
  ],

  external_execution_allowed:
    false,
};

afterEach(() => {
  cleanup();
});

describe("TaskProposal", () => {
  it("제안 상태와 외부 실행 없음 안내를 표시한다", () => {
    render(
      <TaskProposal
        proposal={proposal}
      />,
    );

    expect(
      screen.getByText(
        "제안됨",
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByTestId(
        "task-proposal-safety",
      ),
    ).toHaveTextContent(
      "내부 검토 제안 · 외부 실행 없음",
    );
  });

  it("검토는 내부 상태만 UNDER_REVIEW로 변경한다", () => {
    render(
      <TaskProposal
        proposal={proposal}
      />,
    );

    fireEvent.click(
      screen.getByRole(
        "button",
        {
          name: "검토",
        },
      ),
    );

    expect(
      screen.getByTestId(
        "task-proposal",
      ),
    ).toHaveAttribute(
      "data-status",
      "UNDER_REVIEW",
    );

    expect(
      screen.getByText(
        "검토 중",
      ),
    ).toBeInTheDocument();
  });

  it("수정 후 EDITED 상태가 된다", () => {
    render(
      <TaskProposal
        proposal={proposal}
      />,
    );

    fireEvent.click(
      screen.getByRole(
        "button",
        {
          name: "수정",
        },
      ),
    );

    const input =
      screen.getByRole(
        "textbox",
        {
          name: "제안 제목",
        },
      );

    fireEvent.change(
      input,
      {
        target: {
          value:
            "예약주문 입고 근거 확인",
        },
      },
    );

    fireEvent.click(
      screen.getByRole(
        "button",
        {
          name: "수정 저장",
        },
      ),
    );

    expect(
      screen.getByText(
        "수정됨",
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        "예약주문 입고 근거 확인",
      ),
    ).toBeInTheDocument();
  });

  it("거절하면 DISMISSED 상태가 되고 추가 검토를 막는다", () => {
    render(
      <TaskProposal
        proposal={proposal}
      />,
    );

    fireEvent.click(
      screen.getByRole(
        "button",
        {
          name: "거절",
        },
      ),
    );

    expect(
      screen.getByText(
        "거절됨",
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByRole(
        "button",
        {
          name: "검토",
        },
      ),
    ).toBeDisabled();

    expect(
      screen.getByRole(
        "button",
        {
          name: "수정",
        },
      ),
    ).toBeDisabled();
  });

  it("외부 실행 CTA를 제공하지 않는다", () => {
    render(
      <TaskProposal
        proposal={proposal}
      />,
    );

    expect(
      screen.queryByRole(
        "button",
        {
          name:
            /발주 실행|주문 생성|재고 반영|Provider 전송/,
        },
      ),
    ).not.toBeInTheDocument();
  });
});