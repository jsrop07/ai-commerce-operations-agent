import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

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