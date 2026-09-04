import {
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { describe, expect, it } from "vitest";

import DashboardPage from "../src/app/pages/DashboardPage";

describe("D03-FE-03 dashboard accessibility", () => {
  it("긴급 Queue 영역에 읽을 수 있는 제목이 있다", async () => {
    render(<DashboardPage />);

    expect(
      await screen.findByRole("heading", {
        name: "긴급 Queue",
      }),
    ).toBeInTheDocument();
  });

  it("모든 긴급 위험 카드는 접근 가능한 button이다", async () => {
    render(<DashboardPage />);

    expect(
      await screen.findByRole("button", {
        name: "예약 재고 부족 판단 근거 보기",
      }),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("button", {
        name: "일정 충돌 판단 근거 보기",
      }),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("button", {
        name: "재고 불일치 판단 근거 보기",
      }),
    ).toBeInTheDocument();
  });

  it("긴급 위험 button은 이유와 기준 시각 설명을 연결한다", async () => {
    render(<DashboardPage />);

    const button =
      await screen.findByRole("button", {
        name: "예약 재고 부족 판단 근거 보기",
      });

    const describedBy =
      button.getAttribute("aria-describedby");

    expect(describedBy).toBeTruthy();

    const ids =
      describedBy?.split(/\s+/).filter(Boolean) ?? [];

    expect(ids.length).toBeGreaterThanOrEqual(2);

    for (const id of ids) {
      expect(
        document.getElementById(id),
      ).not.toBeNull();
    }
  });

  it("위험 이유가 문장으로 읽을 수 있게 표시된다", async () => {
    render(<DashboardPage />);

    expect(
      await screen.findByText(
        /예약 수량 대비 확정 재고가 부족하여 출고 전 확인이 필요합니다/,
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        /같은 시간대에 처리해야 할 운영 일정이 겹쳐 담당자 확인이 필요합니다/,
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        /온라인·오프라인 재고 수량에 차이가 있어 실제 수량 확인이 필요합니다/,
      ),
    ).toBeInTheDocument();
  });

  it("Drawer는 접근 가능한 modal dialog로 열린다", async () => {
    render(<DashboardPage />);

    const button =
      await screen.findByRole("button", {
        name: "예약 재고 부족 판단 근거 보기",
      });

    fireEvent.click(button);

    const dialog =
      await screen.findByRole("dialog");

    expect(dialog).toHaveAttribute(
      "aria-modal",
      "true",
    );

    expect(dialog).toHaveAttribute(
      "aria-labelledby",
      "evidence-drawer-title",
    );

    expect(
      within(dialog).getByRole("heading", {
        name: "예약 재고 부족",
      }),
    ).toBeInTheDocument();
  });

  it("Drawer 닫기 button은 접근 가능한 이름을 가진다", async () => {
    render(<DashboardPage />);

    const button =
      await screen.findByRole("button", {
        name: "예약 재고 부족 판단 근거 보기",
      });

    fireEvent.click(button);

    const dialog =
      await screen.findByRole("dialog");

    expect(
      within(dialog).getByRole("button", {
        name: "판단 근거 패널 닫기",
      }),
    ).toBeInTheDocument();
  });

  it("운영자 화면에 내부 Insight enum과 request_id를 노출하지 않는다", async () => {
    render(<DashboardPage />);

    await screen.findByRole("button", {
      name: "예약 재고 부족 판단 근거 보기",
    });

    expect(
      screen.queryByText("RESERVATION_SHORTAGE"),
    ).not.toBeInTheDocument();

    expect(
      screen.queryByText("SCHEDULE_CONFLICT"),
    ).not.toBeInTheDocument();

    expect(
      screen.queryByText("INVENTORY_DISCREPANCY"),
    ).not.toBeInTheDocument();

    expect(
      screen.queryByText("req_demo_urgent_001"),
    ).not.toBeInTheDocument();

    expect(
      screen.queryByText("req_demo_urgent_002"),
    ).not.toBeInTheDocument();

    expect(
      screen.queryByText("req_demo_urgent_003"),
    ).not.toBeInTheDocument();
  });

  it("오늘 할 일도 운영자용 한글 상태로 표시한다", async () => {
    render(<DashboardPage />);

    expect(
      await screen.findByText("제안됨"),
    ).toBeInTheDocument();

    expect(
      screen.getByText("진행 중"),
    ).toBeInTheDocument();

    expect(
      screen.queryByText("PROPOSED"),
    ).not.toBeInTheDocument();

    expect(
      screen.queryByText("IN_PROGRESS"),
    ).not.toBeInTheDocument();
  });
});