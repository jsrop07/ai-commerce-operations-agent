import {
  describe,
  expect,
  it,
} from "vitest";

import type {
  ScheduleDependency,
  ScheduleLaunchEvent,
  ScheduleTask,
} from "../src/types/contracts";

import {
  buildScheduleBoardViewModel,
} from "../src/features/schedule/viewModel";

describe("Day 10 schedule view model", () => {
  it("nullable 일정값을 임의 값으로 만들지 않는다", () => {
    const launchEvents: ScheduleLaunchEvent[] = [
      {
        id: "launch_001",
        product_id: "prd_001",
        launch_at: "2026-09-20T01:00:00Z",
        flow_template: "STANDARD_LAUNCH",
        status: "PLANNED",
        flow: "FLOW_A",
        template_id: "template_a",
        version: "1.0",
        timezone: "Asia/Seoul",
        as_of: null,
        freshness: "UNKNOWN",
        source_classification: "CONTRACT_ONLY",
        evidence_ids: [],
      },
    ];

    const tasks: ScheduleTask[] = [
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
    ];

    const dependencies: ScheduleDependency[] = [
      {
        predecessor_id: "task_001",
        successor_id: "task_002",
        lag_hours: null,
        as_of: null,
        source_classification: "CONTRACT_ONLY",
        evidence_ids: [],
      },
    ];

    const result = buildScheduleBoardViewModel(
      launchEvents,
      tasks,
      dependencies,
    );

    expect(
      result.tasks[0].deadlineLabel,
    ).toBe("마감일 미확정");

    expect(
      result.tasks[0].ownerLabel,
    ).toBe("담당자 미확정");

    expect(
      result.tasks[0].durationLabel,
    ).toBe("소요시간 미확정");

    expect(
      result.dependencies[0].lagLabel,
    ).toBe("간격 미확정");

    expect(
      result.tasks[0].deadline,
    ).toBeNull();

    expect(
      result.dependencies[0].lagHours,
    ).toBeNull();
  });

  it("Flow A/B를 운영자 표시값으로 변환한다", () => {
    const launchEvents: ScheduleLaunchEvent[] = [
      {
        id: "launch_a",
        product_id: "prd_a",
        launch_at: "2026-09-20T01:00:00Z",
        flow_template: "A",
        status: "PLANNED",
        flow: "FLOW_A",
        template_id: "template_a",
        version: "1",
        timezone: "Asia/Seoul",
        as_of: "2026-09-11T06:00:00Z",
        freshness: "FRESH",
        source_classification: "SANITIZED_REAL",
        evidence_ids: [],
      },
      {
        id: "launch_b",
        product_id: "prd_b",
        launch_at: "2026-09-21T01:00:00Z",
        flow_template: "B",
        status: "PLANNED",
        flow: "FLOW_B",
        template_id: "template_b",
        version: "1",
        timezone: "Asia/Seoul",
        as_of: "2026-09-11T06:00:00Z",
        freshness: "FRESH",
        source_classification: "FIXTURE",
        evidence_ids: [],
      },
    ];

    const result = buildScheduleBoardViewModel(
      launchEvents,
      [],
      [],
    );

    expect(
      result.launchEvents[0].flowLabel,
    ).toBe("Flow A");

    expect(
      result.launchEvents[1].flowLabel,
    ).toBe("Flow B");
  });

  it("source classification을 실제 확정 여부와 혼동하지 않는다", () => {
    const makeTask = (
      id: string,
      source_classification:
        | "SANITIZED_REAL"
        | "FIXTURE"
        | "CONTRACT_ONLY"
        | "BLOCKED"
        | "SOURCE_QUALITY_BLOCKED",
    ): ScheduleTask => ({
      id,
      type: "TEST",
      title: id,
      deadline: null,
      priority: "LOW",
      status: "PROPOSED",
      source_reason: "test",
      owner: null,
      duration_hours: null,
      flow: "FLOW_A",
      as_of: null,
      freshness: "UNKNOWN",
      source_classification,
      evidence_ids: [],
    });

    const result = buildScheduleBoardViewModel(
      [],
      [
        makeTask(
          "real",
          "SANITIZED_REAL",
        ),
        makeTask(
          "fixture",
          "FIXTURE",
        ),
        makeTask(
          "contract",
          "CONTRACT_ONLY",
        ),
        makeTask(
          "blocked",
          "BLOCKED",
        ),
        makeTask(
          "quality",
          "SOURCE_QUALITY_BLOCKED",
        ),
      ],
      [],
    );

    expect(
      result.tasks[0].sourceIsConfirmed,
    ).toBe(true);

    expect(
      result.tasks[1].sourceIsConfirmed,
    ).toBe(false);

    expect(
      result.tasks[2].sourceIsConfirmed,
    ).toBe(false);

    expect(
      result.tasks[3].sourceIsConfirmed,
    ).toBe(false);

    expect(
      result.tasks[4].sourceIsConfirmed,
    ).toBe(false);
  });

  it("source classification을 운영자용 문구로 구분한다", () => {
    const tasks: ScheduleTask[] = [
      {
        id: "fixture_task",
        type: "TEST",
        title: "Fixture task",
        deadline: null,
        priority: "LOW",
        status: "PROPOSED",
        source_reason: "test",
        owner: null,
        duration_hours: null,
        flow: "FLOW_A",
        as_of: null,
        freshness: "UNKNOWN",
        source_classification: "FIXTURE",
        evidence_ids: [],
      },
      {
        id: "blocked_task",
        type: "TEST",
        title: "Blocked task",
        deadline: null,
        priority: "LOW",
        status: "BLOCKED",
        source_reason: "test",
        owner: null,
        duration_hours: null,
        flow: "FLOW_A",
        as_of: null,
        freshness: "UNKNOWN",
        source_classification:
          "SOURCE_QUALITY_BLOCKED",
        evidence_ids: [],
      },
    ];

    const result = buildScheduleBoardViewModel(
      [],
      tasks,
      [],
    );

    expect(
      result.tasks[0].sourceLabel,
    ).toBe("테스트/데모 데이터");

    expect(
      result.tasks[1].sourceLabel,
    ).toBe("원천 품질 문제");
  });

  it("timezone과 as_of를 Backend 값에서만 가져온다", () => {
    const launchEvents: ScheduleLaunchEvent[] = [
      {
        id: "launch_001",
        product_id: "prd_001",
        launch_at: "2026-09-20T01:00:00Z",
        flow_template: "STANDARD_LAUNCH",
        status: "PLANNED",
        flow: "FLOW_A",
        template_id: "template_a",
        version: "1.0",
        timezone: "Asia/Seoul",
        as_of: "2026-09-11T06:00:00Z",
        freshness: "FRESH",
        source_classification: "SANITIZED_REAL",
        evidence_ids: [],
      },
    ];

    const result = buildScheduleBoardViewModel(
      launchEvents,
      [],
      [],
    );

    expect(result.timezone).toBe(
      "Asia/Seoul",
    );

    expect(result.asOf).toBe(
      "2026-09-11T06:00:00Z",
    );
  });

  it("모든 as_of가 null이면 임의 시각을 만들지 않는다", () => {
    const result =
      buildScheduleBoardViewModel(
        [],
        [],
        [],
      );

    expect(result.asOf).toBeNull();
    expect(result.timezone).toBeNull();
  });
});