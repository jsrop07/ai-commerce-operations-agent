import {
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import {
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";

import SchedulePage from "../src/app/pages/SchedulePage";

const mockApiGet = vi.fn();

vi.mock("../src/mocks/handlers", () => ({
  mockApiGet: (...args: unknown[]) =>
    mockApiGet(...args),
}));

function envelope<T>(
  data: T[],
  requestId: string,
) {
  return {
    schema_version: "1.0",
    tenant_id: "demo_store",
    request_id: requestId,
    trace_id: `${requestId}_trace`,
    data,
    evidence_ids: [],
    warnings: [],
    as_of: "2026-09-11T06:00:00Z",
  };
}

describe("SchedulePage", () => {
  beforeEach(() => {
    mockApiGet.mockReset();
  });

  it("Mock mode에서 Fixture/Demo임을 명시하고 일정 보드를 표시한다", async () => {
    mockApiGet
  .mockResolvedValueOnce(
    envelope(
      [
        {
          id: "launch_test_001",
          product_id: "prd_001",
          launch_at:
            "2026-09-20T01:00:00Z",
          flow_template:
            "STANDARD_LAUNCH",
          status: "PLANNED",

          flow: "FLOW_A",
          template_id:
            "launch-flow-a",
          version: "1.0",
          timezone: "Asia/Seoul",

          as_of:
            "2026-09-11T06:00:00Z",
          freshness: "FRESH",

          source_classification:
            "FIXTURE",

          evidence_ids: [],
        },
      ],
      "req_launch",
    ),
  )

  .mockResolvedValueOnce(
    envelope(
      [
        {
          id: "task_test_001",
          type:
            "LAUNCH_PREPARATION",

          title:
            "출시 준비 상태 검토",

          deadline: null,

          priority: "MEDIUM",
          status: "PROPOSED",

          source_reason:
            "Fixture test",

          owner: null,
          duration_hours: null,

          flow: "FLOW_A",

          as_of: null,
          freshness: "UNKNOWN",

          source_classification:
            "FIXTURE",

          evidence_ids: [],
        },
      ],
      "req_tasks",
    ),
  )

  .mockResolvedValueOnce(
    envelope(
      [
        {
          predecessor_id:
            "task_test_001",

          successor_id:
            "task_test_002",

          lag_hours: null,
          as_of: null,

          source_classification:
            "CONTRACT_ONLY",

          evidence_ids: [],
        },
      ],
      "req_dependencies",
    ),
  )

  .mockResolvedValueOnce(
    envelope(
      [],
      "req_impacts",
    ),
  )

  .mockResolvedValueOnce(
    envelope(
      [],
      "req_replans",
    ),
  );

    render(<SchedulePage />);

    expect(
      screen.getByText(
        "Fixture / Demo",
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        "일정 데이터를 불러오는 중입니다.",
      ),
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(
        screen.getByText(
          "출시 준비 상태 검토",
        ),
      ).toBeInTheDocument();
    });

const launch = screen.getByTestId(
  "schedule-launch-launch_test_001",
);

expect(
  within(launch).getByText(
    "테스트/데모 데이터",
  ),
).toBeInTheDocument();

const task = screen.getByTestId(
  "schedule-task-task_test_001",
);

    expect(
    within(task).getByText(
        "테스트/데모 데이터",
    ),
    ).toBeInTheDocument();

    expect(
    screen.getByText(
        "계약 검증 전용",
    ),
    ).toBeInTheDocument();
  });

  it("200 empty는 오류가 아니라 빈 상태로 표시한다", async () => {
    mockApiGet
    .mockResolvedValueOnce(
        envelope(
        [],
        "req_launch_empty",
        ),
    )
    .mockResolvedValueOnce(
        envelope(
        [],
        "req_task_empty",
        ),
    )
    .mockResolvedValueOnce(
        envelope(
        [],
        "req_dependency_empty",
        ),
    )
    .mockResolvedValueOnce(
        envelope(
        [],
        "req_impact_empty",
        ),
    )
    .mockResolvedValueOnce(
        envelope(
        [],
        "req_replan_empty",
        ),
    );

    render(<SchedulePage />);

    await waitFor(() => {
      expect(
        screen.getByText(
          "표시할 일정 데이터가 없습니다.",
        ),
      ).toBeInTheDocument();
    });

    expect(
      screen.queryByText(
        "일정 데이터를 사용할 수 없습니다.",
      ),
    ).not.toBeInTheDocument();
  });

  it("API 실패는 Error 상태로 표시하고 임의 일정으로 대체하지 않는다", async () => {
    mockApiGet.mockRejectedValue(
      new Error("mock backend unavailable"),
    );

    render(<SchedulePage />);

    await waitFor(() => {
      expect(
        screen.getByRole("alert"),
      ).toBeInTheDocument();
    });

    expect(
      screen.getByText(
        "일정 데이터를 사용할 수 없습니다.",
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        /Fixture나 임의 일정으로 대체하지 않습니다/,
      ),
    ).toBeInTheDocument();

    expect(
      screen.queryByText(
        "출시 준비 상태 검토",
      ),
    ).not.toBeInTheDocument();
  });

  it("잘못된 계약 응답도 Error 상태로 처리한다", async () => {
    mockApiGet
      .mockResolvedValueOnce({
        schema_version: "2.0",
      })
      .mockResolvedValueOnce(
        envelope([], "req_task_bad"),
      )
      .mockResolvedValueOnce(
        envelope(
          [],
          "req_dependency_bad",
        ),
      );

    render(<SchedulePage />);

    await waitFor(() => {
      expect(
        screen.getByRole("alert"),
      ).toBeInTheDocument();
    });

    expect(
      screen.getByText(
        /Backend schedule envelope is malformed/,
      ),
    ).toBeInTheDocument();
  });
});