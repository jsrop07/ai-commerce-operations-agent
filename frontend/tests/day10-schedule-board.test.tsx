import {
  render,
  screen,
  within,
} from "@testing-library/react";
import {
  describe,
  expect,
  it,
} from "vitest";

import ScheduleBoard from "../src/features/schedule/ScheduleBoard";
import type {
  ScheduleBoardViewModel,
} from "../src/features/schedule/viewModel";

function makeModel(
  overrides: Partial<ScheduleBoardViewModel> = {},
): ScheduleBoardViewModel {
  return {
    timezone: "Asia/Seoul",
    asOf: "2026-09-11T06:00:00Z",

    launchEvents: [
      {
        id: "launch_001",
        productId: "prd_001",
        flow: "FLOW_A",
        flowLabel: "Flow A",
        templateId: "template_a",
        version: "1.0",
        launchAt: "2026-09-20T01:00:00Z",
        launchAtLabel: "2026-09-20T01:00:00Z",
        timezone: "Asia/Seoul",
        status: "PLANNED",
        asOf: "2026-09-11T06:00:00Z",
        asOfLabel: "2026-09-11T06:00:00Z",
        sourceClassification: "SANITIZED_REAL",
        sourceLabel: "실제 기반 비식별 자료",
        sourceIsConfirmed: true,
        evidenceIds: ["ev_launch_001"],
      },
    ],

    tasks: [
      {
        id: "task_001",
        type: "INCOMING_CONFIRMATION",
        title: "입고일 확인",
        flow: "FLOW_A",
        flowLabel: "Flow A",
        deadline: null,
        deadlineLabel: "마감일 미확정",
        owner: null,
        ownerLabel: "담당자 미확정",
        durationHours: null,
        durationLabel: "소요시간 미확정",
        priority: "HIGH",
        status: "BLOCKED",
        sourceReason: "confirmation missing",
        asOf: null,
        asOfLabel: "기준 시각 미확정",
        sourceClassification: "BLOCKED",
        sourceLabel: "자료 없음 / 확인 불가",
        sourceIsConfirmed: false,
        evidenceIds: [],
      },
    ],

    dependencies: [
      {
        predecessorId: "task_001",
        successorId: "task_002",
        lagHours: null,
        lagLabel: "간격 미확정",
        asOf: null,
        asOfLabel: "기준 시각 미확정",
        sourceClassification: "CONTRACT_ONLY",
        sourceLabel: "계약 검증 전용",
        sourceIsConfirmed: false,
        evidenceIds: [],
      },
    ],

    ...overrides,
  };
}

describe("Day 10 ScheduleBoard", () => {
    it("Flow A/B와 timezone/as_of를 표시한다", () => {
    render(
        <ScheduleBoard
        model={makeModel()}
        />,
    );

    // 보드 전체 헤더
    expect(
        screen.getByText(
        /시간대: Asia\/Seoul/,
        ),
    ).toBeInTheDocument();

    // Launch Event 한 건 안에서만 검사
    const launch = screen.getByTestId(
        "schedule-launch-launch_001",
    );

    expect(
        within(launch).getByText("Flow A"),
    ).toBeInTheDocument();

    expect(
        within(launch).getByText(
        /기준 시각: 2026-09-11T06:00:00Z/,
        ),
    ).toBeInTheDocument();

    // Task 한 건 안에서만 검사
    const task = screen.getByTestId(
        "schedule-task-task_001",
    );

    expect(
        within(task).getByText("Flow A"),
    ).toBeInTheDocument();
    });

  it("nullable task 값을 임의값으로 표시하지 않는다", () => {
    render(
      <ScheduleBoard
        model={makeModel()}
      />,
    );

    expect(
      screen.getByText(
        /마감: 마감일 미확정/,
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        /담당: 담당자 미확정/,
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        /소요: 소요시간 미확정/,
      ),
    ).toBeInTheDocument();
  });

  it("dependency null lag를 0으로 표시하지 않는다", () => {
    render(
      <ScheduleBoard
        model={makeModel()}
      />,
    );

    expect(
      screen.getByText(
        /간격 미확정/,
      ),
    ).toBeInTheDocument();

    expect(
      screen.queryByText("0시간"),
    ).not.toBeInTheDocument();
  });

  it("BLOCKED와 CONTRACT_ONLY를 실제 확정처럼 표시하지 않는다", () => {
    render(
      <ScheduleBoard
        model={makeModel()}
      />,
    );

    expect(
      screen.getByText(
        "자료 없음 / 확인 불가",
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        "계약 검증 전용",
      ),
    ).toBeInTheDocument();
  });

  it("200 empty용 빈 상태를 표시한다", () => {
    render(
      <ScheduleBoard
        model={makeModel({
          timezone: null,
          asOf: null,
          launchEvents: [],
          tasks: [],
          dependencies: [],
        })}
      />,
    );

    expect(
      screen.getByText(
        "표시할 일정 데이터가 없습니다.",
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        /임의 일정을 생성하지 않습니다/,
      ),
    ).toBeInTheDocument();
  });
});