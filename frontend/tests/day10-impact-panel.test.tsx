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

import ImpactPanel from "../src/features/schedule/ImpactPanel";

import type {
  DelayImpactViewModel,
} from "../src/features/schedule/impactViewModel";

function makeModel(
  overrides: Partial<DelayImpactViewModel> = {},
): DelayImpactViewModel {
  return {
    incomingId: "incoming_001",

    impactState: "KNOWN",
    impactStateLabel: "지연 영향 확인됨",

    expectedAtBefore:
      "2026-09-20T01:00:00Z",
    expectedAtBeforeLabel:
      "2026-09-20T01:00:00Z",

    expectedAtAfter:
      "2026-09-22T01:00:00Z",
    expectedAtAfterLabel:
      "2026-09-22T01:00:00Z",

    criticalPathAffected: true,
    criticalPathLabel:
      "Critical Path 영향 있음",

    tasks: [
      {
        targetType: "TASK",
        targetTypeLabel: "Task",
        targetId: "task_001",

        before:
          "2026-09-19T01:00:00Z",
        beforeLabel:
          "2026-09-19T01:00:00Z",

        after:
          "2026-09-21T01:00:00Z",
        afterLabel:
          "2026-09-21T01:00:00Z",

        lagHours: 48,
        lagLabel: "48시간",

        reason: "입고 지연 영향",
        reasonLabel: "입고 지연 영향",

        evidenceIds: [
          "ev_task_001",
        ],
      },
    ],

    reservations: [],
    launchEvents: [],

    totalImpactCount: 1,

    asOf:
      "2026-09-11T06:00:00Z",
    asOfLabel:
      "2026-09-11T06:00:00Z",

    freshness: "FRESH",

    quality: "VERIFIED",
    qualityLabel: "VERIFIED",

    sourceClassification:
      "SANITIZED_REAL",

    sourceLabel:
      "실제 기반 비식별 자료",

    sourceIsConfirmed: true,

    evidenceIds: [
      "ev_incoming_001",
    ],

    requestId: "req_impact_001",
    traceId: "trace_impact_001",

    ...overrides,
  };
}

describe("Day 10 ImpactPanel", () => {
  it("C08 합성 예시와 자료 품질 및 관계 출처를 표시한다", () => {
    const model = makeModel({
      incomingId: "incoming-demo-001", dataMode: "SYNTHETIC_DEMO",
      status: "CONTRACT_ONLY", actualDelayConfirmed: false,
      quality: "TENTATIVE", qualityLabel: "TENTATIVE",
      sourceClassification: "FIXTURE", sourceLabel: "테스트/데모 데이터", sourceIsConfirmed: false,
      tasks: [{ ...makeModel().tasks[0], targetId: "task-inspection", sourceId: "fixture:incoming-delay-3d" }],
    });
    render(<ImpactPanel model={model} />);
    expect(screen.getByText(/합성 예시/)).toBeInTheDocument();
    expect(screen.getByText(/계약 검증용/)).toBeInTheDocument();
    expect(screen.getByText("실제 지연 확정 아님")).toBeInTheDocument();
    expect(screen.getByText(/잠정 \(TENTATIVE\)/)).toBeInTheDocument();
    expect(screen.getByText(/FIXTURE/)).toBeInTheDocument();
    expect(screen.getByText(/from incoming-demo-001 → to task-inspection/)).toBeInTheDocument();
  });
  it("KNOWN 영향과 before/after를 표시한다", () => {
    render(
      <ImpactPanel model={makeModel()} />,
    );

    expect(
      screen.getByText(
        "지연 영향 확인됨",
      ),
    ).toBeInTheDocument();

    const task = screen.getByTestId(
      "impact-TASK-task_001",
    );

    expect(
      within(task).getByText(
        /변경 전: 2026-09-19/,
      ),
    ).toBeInTheDocument();

    expect(
      within(task).getByText(
        /변경 후: 2026-09-21/,
      ),
    ).toBeInTheDocument();

    expect(
      within(task).getByText(
        /지연: 48시간/,
      ),
    ).toBeInTheDocument();
  });

  it("NONE은 영향 없음으로 표시한다", () => {
    render(
      <ImpactPanel
        model={makeModel({
          impactState: "NONE",
          impactStateLabel: "영향 없음",

          tasks: [],
          reservations: [],
          launchEvents: [],

          totalImpactCount: 0,

          criticalPathAffected: false,
          criticalPathLabel:
            "Critical Path 영향 없음",
        })}
      />,
    );

    expect(
      screen.getByText(
        "확인된 지연 영향은 없습니다.",
      ),
    ).toBeInTheDocument();
  });

  it("UNKNOWN은 영향 0건으로 오해하지 않는다", () => {
    render(
      <ImpactPanel
        model={makeModel({
          impactState: "UNKNOWN",
          impactStateLabel:
            "영향 여부 미확정",

          expectedAtBefore: null,
          expectedAtBeforeLabel:
            "일정 미확정",

          expectedAtAfter: null,
          expectedAtAfterLabel:
            "일정 미확정",

          tasks: [],
          reservations: [],
          launchEvents: [],

          totalImpactCount: 0,

          criticalPathAffected: null,
          criticalPathLabel:
            "Critical Path 영향 미확정",

          sourceClassification:
            "CONTRACT_ONLY",

          sourceLabel:
            "계약 검증 전용",

          sourceIsConfirmed: false,
        })}
      />,
    );

    expect(
      screen.getByText(
        /영향 여부를 확정할 수 없습니다/,
      ),
    ).toBeInTheDocument();

    expect(
      screen.queryByText(
        "확인된 지연 영향은 없습니다.",
      ),
    ).not.toBeInTheDocument();
  });

  it("BLOCKED는 계산 불가로 표시한다", () => {
    render(
      <ImpactPanel
        model={makeModel({
          impactState: "BLOCKED",
          impactStateLabel:
            "영향 계산 불가",

          tasks: [],
          reservations: [],
          launchEvents: [],

          totalImpactCount: 0,

          criticalPathAffected: null,
          criticalPathLabel:
            "Critical Path 영향 미확정",

          sourceClassification:
            "SOURCE_QUALITY_BLOCKED",

          sourceLabel:
            "원천 품질 문제",

          sourceIsConfirmed: false,
        })}
      />,
    );

    expect(
      screen.getByText(
        /지연 영향을 계산할 수 없습니다/,
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        "원천 품질 문제",
      ),
    ).toBeInTheDocument();
  });

  it("개발 추적 ID를 운영 화면에 표시하지 않는다", () => {
    render(
      <ImpactPanel model={makeModel()} />,
    );

    expect(
      screen.queryByText(/request_id/),
    ).not.toBeInTheDocument();

    expect(
      screen.queryByText(/trace_id/),
    ).not.toBeInTheDocument();
  });
});
