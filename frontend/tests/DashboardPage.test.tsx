import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ReservationShortageTask, ReservationRiskItem } from "../src/types/contracts";

const getFeedback = vi.fn();
const postFeedback = vi.fn();
vi.mock("../src/api/day10", () => ({
  getTaskFeedback: (...args: unknown[]) => getFeedback(...args),
  postTaskFeedback: (...args: unknown[]) => postFeedback(...args),
}));

import UrgentQueue, {
  sortUrgentQueue,
} from "../src/components/UrgentQueue";
import TodayTasks from "../src/components/TodayTasks";
import {
  emptyUrgentQueueFixture,
  urgentQueueFixtures,
} from "../src/mocks/fixtures/urgentQueue";
import { tasks } from "../src/mocks/fixtures";

describe("Dashboard Day 3 urgent queue", () => {
  it("예약 부족, 일정 충돌, 재고 불일치 세 위험을 표시한다", () => {
    render(
      <UrgentQueue items={urgentQueueFixtures} />
    );

    expect(
      screen.getByText("예약 재고 부족")
    ).toBeInTheDocument();

    expect(
      screen.getByText("일정 충돌")
    ).toBeInTheDocument();

    expect(
      screen.getByText("재고 불일치")
    ).toBeInTheDocument();
  });

  it("내부 Insight enum을 운영자 화면에 직접 노출하지 않는다", () => {
    render(
      <UrgentQueue items={urgentQueueFixtures} />
    );

    expect(
      screen.queryByText("RESERVATION_SHORTAGE")
    ).not.toBeInTheDocument();

    expect(
      screen.queryByText("SCHEDULE_CONFLICT")
    ).not.toBeInTheDocument();

    expect(
      screen.queryByText("INVENTORY_DISCREPANCY")
    ).not.toBeInTheDocument();
  });

  it("위험 이유를 문장으로 표시한다", () => {
    render(
      <UrgentQueue items={urgentQueueFixtures} />
    );

    expect(
      screen.getByText(
        /예약 수량 대비 확정 재고가 부족/
      )
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        /같은 시간대에 처리해야 할 운영 일정/
      )
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        /온라인·오프라인 재고 수량에 차이/
      )
    ).toBeInTheDocument();
  });

  it("정렬 기준을 화면에서 설명한다", () => {
    render(
      <UrgentQueue items={urgentQueueFixtures} />
    );

    expect(
      screen.getByText(
        /위험도 높은 순/
      )
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        /같은 위험도는 최신순/
      )
    ).toBeInTheDocument();
  });

  it("HIGH가 MEDIUM보다 먼저 정렬된다", () => {
    const sorted =
      sortUrgentQueue(urgentQueueFixtures);

    expect(sorted[0].data.severity).toBe("HIGH");
    expect(sorted[1].data.severity).toBe("HIGH");
    expect(sorted[2].data.severity).toBe("MEDIUM");
  });

  it("같은 severity라면 최신 기준시각이 먼저 온다", () => {
    const sorted =
      sortUrgentQueue(urgentQueueFixtures);

    expect(sorted[0].data.type).toBe(
      "RESERVATION_SHORTAGE"
    );

    expect(sorted[1].data.type).toBe(
      "SCHEDULE_CONFLICT"
    );

    expect(
      new Date(sorted[0].as_of).getTime()
    ).toBeGreaterThan(
      new Date(sorted[1].as_of).getTime()
    );
  });

  it("severity와 기준시각이 같아도 insight_id로 안정적으로 정렬한다", () => {
    const base = urgentQueueFixtures[0];

    const laterId = {
      ...base,
      request_id: "req_demo_sort_b",
      data: {
        ...base.data,
        insight_id: "ins_demo_sort_b",
      },
    };

    const earlierId = {
      ...base,
      request_id: "req_demo_sort_a",
      data: {
        ...base.data,
        insight_id: "ins_demo_sort_a",
      },
    };

    const sorted = sortUrgentQueue([
      laterId,
      earlierId,
    ]);

    expect(sorted[0].data.insight_id).toBe(
      "ins_demo_sort_a"
    );

    expect(sorted[1].data.insight_id).toBe(
      "ins_demo_sort_b"
    );
  });

  it("기준시각을 카드에 표시한다", () => {
    render(
      <UrgentQueue items={urgentQueueFixtures} />
    );

    expect(
      screen.getAllByText(/기준/).length
    ).toBeGreaterThanOrEqual(3);
  });

  it("빈 Queue에서는 이유와 다음 행동을 표시한다", () => {
    render(
      <UrgentQueue
        items={emptyUrgentQueueFixture}
      />
    );

    expect(
      screen.getByText("현재 긴급 위험이 없습니다")
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        /현재는 일반 운영 업무를 확인하세요/
      )
    ).toBeInTheDocument();
  });
});

describe("Dashboard Day 3 today tasks", () => {
  it("오늘 할 일을 표시한다", () => {
    render(<TodayTasks tasks={tasks} compact />);

    expect(
      screen.getByText("합성 SKU 재고 차이 확인")
    ).toBeInTheDocument();

    expect(
      screen.getByText("합성 문의 초안 검토")
    ).toBeInTheDocument();
  });

  it("Task 상태 enum을 한글 label로 표시한다", () => {
    render(<TodayTasks tasks={tasks} compact />);

    expect(
      screen.getByText("제안됨")
    ).toBeInTheDocument();

    expect(
      screen.getByText("진행 중")
    ).toBeInTheDocument();

    expect(
      screen.queryByText("PROPOSED")
    ).not.toBeInTheDocument();

    expect(
      screen.queryByText("IN_PROGRESS")
    ).not.toBeInTheDocument();
  });

  it("Task의 내부 reason을 운영자용 문장으로 표시한다", () => {
    render(<TodayTasks tasks={tasks} compact />);

    expect(
      screen.getByText(
        /재고 수량 차이가 발견되어 확인이 필요/
      )
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        /AI 문의 초안이 준비되어 담당자 검토가 필요/
      )
    ).toBeInTheDocument();

    expect(
      screen.queryByText("inventory discrepancy")
    ).not.toBeInTheDocument();

    expect(
      screen.queryByText("draft ready")
    ).not.toBeInTheDocument();
  });
});

const feature = { raw: null, normalized: null, weight: 0.25, contribution: null, reason: "missing" };
const shortageTask: ReservationShortageTask = {
  id: "task-a", tenant_id: "demo_store", reservation_id: "reservation-a", sku_id: "same-sku",
  task_type: "RESERVATION_SHORTAGE", title: "예약 부족", deadline: null, risk_level: "HIGH",
  affected_count: 1, aging_hours: 12, priority: 21.25, priority_reason: "rule", status: "PROPOSED",
  source_reason: "CONFIRMED", source_classification: "FIXTURE", evidence_ids: [], as_of: null,
  replay_count: 0, priority_rule_score: 21.25,
  priority_breakdown: { deadline: { ...feature, raw: "DEADLINE_UNKNOWN" }, risk: feature, business_impact: feature, aging: feature },
  priority_rule_version: "task-priority.v0.1", priority_provenance: "RULE",
  priority_calibration_status: "DAY11_BASELINE_UNVALIDATED", priority_missing_features: ["deadline"],
  priority_coverage_weight: 0.75, priority_as_of: null,
};
const reservation = (id: string, shortage: number | null): ReservationRiskItem => ({
  reservation_id: id, product_name: "demo", sku_id: "same-sku", required_qty: 5,
  secured_qty: 1, confirmed_incoming: 2, tentative_incoming: 0,
  confirmed_incoming_qty: 2, tentative_incoming_qty: 0, shortage,
  calculation_status: "CONFIRMED", as_of: "2026-09-11T06:00:00Z", source_classification: "FIXTURE",
});

describe("C03 dashboard task", () => {
  it("reservation_id로만 결합하고 5/1/2/0/2 및 미검증 priority를 표시한다", async () => {
    getFeedback.mockResolvedValue({ data: [] });
    render(<TodayTasks tasks={[]} shortageTasks={[shortageTask]} reservations={[reservation("other", 99), reservation("reservation-a", 2)]} />);
    const card = screen.getByTestId("shortage-task-task-a");
    const quantities = within(card).getByRole("region", { name: "예약 수량" });
    for (const [label, value] of [["예약 수요", "5"], ["확보·배정", "1"], ["확정 입고", "2"], ["잠정 입고", "0"], ["부족 수량", "2"]]) {
      const term = within(quantities).getByText(label);
      expect(term.parentElement).toHaveTextContent(value);
    }
    expect(within(card).queryByText(/99/)).not.toBeInTheDocument();
    expect(within(card).getByText(/규칙 기반 우선순위: 21.25/)).toBeInTheDocument();
    expect(within(card).getByText(/기준선 검증 전/)).toBeInTheDocument();
    expect(within(card).getByText(/출처: 규칙 기반/)).toBeInTheDocument();
    expect(within(card).getByText(/원본값 마감일 정보 없음 · 기여도 확인 필요/)).toBeInTheDocument();
    expect(within(card).getAllByText(/정규화 확인 필요/)).toHaveLength(4);
    expect(within(card).queryByText(/private-order/)).not.toBeInTheDocument();
    await waitFor(() => expect(within(card).getByText("의견 기록: 0건")).toBeInTheDocument());
  });

  it("null 부족은 0으로 표시하지 않는다", () => {
    getFeedback.mockResolvedValue({ data: [] });
    render(<TodayTasks tasks={[]} shortageTasks={[shortageTask]} reservations={[reservation("reservation-a", null)]} />);
    expect(screen.getByText("부족 수량").parentElement).toHaveTextContent("확인 필요");
  });

  it("EDIT와 REJECT는 POST 뒤 GET readback을 거치며 실패는 성공으로 표시하지 않는다", async () => {
    getFeedback.mockReset().mockResolvedValueOnce({ data: [] }).mockResolvedValueOnce({ data: [{ id: "f1", feedback_version: 1, decision: "EDIT", target_field: "title", after_value: "새 제목", reason: "수정", actor: "DEMO_OPERATOR" }] });
    postFeedback.mockReset().mockResolvedValue({ id: "f1" });
    render(<TodayTasks tasks={[]} shortageTasks={[shortageTask]} reservations={[]} />);
    await waitFor(() => expect(screen.getByText("의견 기록: 0건")).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText("수정 제안값"), { target: { value: "새 제목" } });
    fireEvent.change(screen.getByLabelText("사유"), { target: { value: "수정" } });
    fireEvent.click(screen.getByRole("button", { name: "수정 의견 저장" }));
    await waitFor(() => expect(screen.getByText("의견 기록: 1건")).toBeInTheDocument());
    expect(screen.getByText("수정 의견 · 버전 1")).toBeInTheDocument();
    expect(screen.getByText("새 제목")).toBeInTheDocument();
    expect(screen.getByText("DEMO_OPERATOR")).toBeInTheDocument();
    expect(screen.getByText("내부 업무 의견입니다. 외부 시스템 변경이나 Agent 재개를 의미하지 않습니다.")).toBeInTheDocument();
    expect(postFeedback.mock.calls[0][1]).toMatchObject({ decision: "EDIT", target_field: "title", expected_version: 0 });
    getFeedback.mockResolvedValueOnce({ data: [{ id: "f1", feedback_version: 1, decision: "EDIT", reason: "수정", actor: "DEMO_OPERATOR" }] });
    postFeedback.mockRejectedValueOnce(new Error("409 FEEDBACK_VERSION_CONFLICT"));
    fireEvent.change(screen.getByLabelText("의견 유형"), { target: { value: "REJECT" } });
    fireEvent.change(screen.getByLabelText("사유"), { target: { value: "거절" } });
    fireEvent.click(screen.getByRole("button", { name: "거절 의견 저장" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("FEEDBACK_VERSION_CONFLICT"));
    expect(postFeedback.mock.calls[1][1]).toMatchObject({ decision: "REJECT", target_field: null, after_value: null, expected_version: 1 });
    expect(screen.getByLabelText("사유")).toHaveValue("거절");
    expect(screen.queryByText("서버 의견 기록을 다시 확인했습니다.")).not.toBeInTheDocument();
    postFeedback.mockRejectedValueOnce(new Error("500 storage failure"));
    fireEvent.click(screen.getByRole("button", { name: "거절 의견 저장" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("500 storage failure"));
    expect(screen.getByLabelText("사유")).toHaveValue("거절");
    expect(screen.queryByText("서버 의견 기록을 다시 확인했습니다.")).not.toBeInTheDocument();
  });

  it("새로고침과 같은 재마운트 후 서버 의견 이력을 다시 표시한다", async () => {
    const entry = { id: "f1", feedback_version: 1, decision: "EDIT", target_field: "title", after_value: "새 제목", reason: "수정", actor: "DEMO_OPERATOR" };
    getFeedback.mockReset().mockResolvedValue({ data: [entry] });
    const first = render(<TodayTasks tasks={[]} shortageTasks={[shortageTask]} />);
    await waitFor(() => expect(screen.getByText("의견 기록: 1건")).toBeInTheDocument());
    first.unmount();
    render(<TodayTasks tasks={[]} shortageTasks={[shortageTask]} />);
    await waitFor(() => expect(screen.getByText("새 제목")).toBeInTheDocument());
    expect(getFeedback).toHaveBeenCalledTimes(2);
  });
});
