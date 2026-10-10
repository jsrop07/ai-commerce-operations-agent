import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { parseDashboardQueue } from "../src/api/dashboardQueue";
import OperationalUrgentQueue from "../src/components/OperationalUrgentQueue";

const fixture = {
  data: {
    status: "READY", calculation_mode: "ON_REQUEST",
    source_counts: { reservations: 1, inventory_snapshots: 1, linked_tasks: 1 },
    items: [{ id: "reservation:one", kind: "CONDITIONAL_RESERVATION", state: "CONDITIONAL",
      priority: "MEDIUM", title: "예약 수량 확보 검토", reason: "현재 미확보 4개, 사용·배분 시 잔여 2개",
      evidence_ids: ["operations.reservations:one"], source_as_of: null,
      target_path: "/schedule", target_id: "one", task_status: null, task_due_at: null }],
  },
};

describe("request-time operations queue", () => {
  it("renders calculated evidence separately from task list", () => {
    const data = parseDashboardQueue({ data: { ...fixture.data, items: [
      ...fixture.data.items,
      { id: "task:11111111-1111-4111-8111-111111111111", kind: "TASK_REVIEW",
        state: "REVIEW_PENDING", priority: null, title: "등록된 예약 검토 Task",
        reason: "PROPOSED 상태의 기존 Task", evidence_ids: ["operations.tasks:one"],
        source_as_of: null, target_path: "/schedule", target_id: "one",
        task_status: "PROPOSED", task_due_at: null },
    ] } });
    render(<OperationalUrgentQueue data={data} error={false} onRefresh={vi.fn()} />);
    expect(screen.getByRole("heading", { name: "긴급 Queue" })).toBeInTheDocument();
    expect(screen.getByText(/현재 미확보 4개/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "운영 일정에서 확인" })).toHaveAttribute("href", "/schedule");
    expect(screen.getByText("1건")).toBeInTheDocument();
    expect(screen.queryByText(/Task|operations\.tasks/)).not.toBeInTheDocument();
  });

  it("keeps absent sources, clear results, and failure distinct", () => {
    const { rerender } = render(<OperationalUrgentQueue data={{ ...fixture.data, status: "NO_DATA", items: [] } as never}
      error={false} onRefresh={vi.fn()} />);
    expect(screen.getByText(/조회 가능한 예약·재고·관련 Task 원천이 없습니다/)).toBeInTheDocument();
    rerender(<OperationalUrgentQueue data={{ ...fixture.data, status: "CLEAR", items: [] } as never}
      error={false} onRefresh={vi.fn()} />);
    expect(screen.getByText(/현재 표시할 검토 항목이 없습니다/)).toBeInTheDocument();
    rerender(<OperationalUrgentQueue data={null} error onRefresh={vi.fn()} />);
    expect(screen.getByRole("alert")).toHaveTextContent("위험이 없다는 뜻은 아닙니다");
  });
});
