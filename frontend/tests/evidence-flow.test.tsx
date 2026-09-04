import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { describe, expect, it } from "vitest";

import DashboardPage from "../src/app/pages/DashboardPage";
import { mockGetEvidenceByRequestId } from "../src/mocks/evidence";
import {
  urgentQueueFixtures,
} from "../src/mocks/fixtures/urgentQueue";

describe("D03-FE-02 request_id evidence flow", () => {
  it("각 request_id가 자기 Insight만 반환한다", async () => {
    for (const fixture of urgentQueueFixtures) {
      const result =
        await mockGetEvidenceByRequestId(
          fixture.request_id,
        );

      expect(result).not.toBeNull();

      expect(result?.request_id).toBe(
        fixture.request_id,
      );

      expect(result?.data.insight_id).toBe(
        fixture.data.insight_id,
      );

      expect(result?.data.type).toBe(
        fixture.data.type,
      );
    }
  });

  it("존재하지 않는 request_id는 null을 반환한다", async () => {
    const result =
      await mockGetEvidenceByRequestId(
        "req_demo_missing",
      );

    expect(result).toBeNull();
  });

  it("위험 카드는 실제 button으로 제공된다", async () => {
    render(<DashboardPage />);

    const reservationButton =
      await screen.findByRole("button", {
        name: "예약 재고 부족 판단 근거 보기",
      });

    const scheduleButton =
      screen.getByRole("button", {
        name: "일정 충돌 판단 근거 보기",
      });

    const inventoryButton =
      screen.getByRole("button", {
        name: "재고 불일치 판단 근거 보기",
      });

    expect(reservationButton.tagName).toBe(
      "BUTTON",
    );

    expect(scheduleButton.tagName).toBe(
      "BUTTON",
    );

    expect(inventoryButton.tagName).toBe(
      "BUTTON",
    );
  });

  it("예약 재고 부족 카드를 선택하면 해당 판단 근거가 열린다", async () => {
    render(<DashboardPage />);

    const fixture =
      urgentQueueFixtures.find(
        (item) =>
          item.data.type ===
          "RESERVATION_SHORTAGE",
      )!;

    const button =
      await screen.findByRole("button", {
        name: "예약 재고 부족 판단 근거 보기",
      });

    fireEvent.click(button);

    const dialog =
      await screen.findByRole("dialog");

    expect(
      within(dialog).getByRole("heading", {
        name: "예약 재고 부족",
      }),
    ).toBeInTheDocument();

    expect(
      within(dialog).getByText(
        fixture.data.evidence[0].source_id,
      ),
    ).toBeInTheDocument();

    expect(
      within(dialog).getByText(
        fixture.data.rule_version,
      ),
    ).toBeInTheDocument();
  });

  it("일정 충돌을 선택하면 예약 부족 근거가 아니라 일정 충돌 근거가 열린다", async () => {
    render(<DashboardPage />);

    const scheduleFixture =
      urgentQueueFixtures.find(
        (item) =>
          item.data.type ===
          "SCHEDULE_CONFLICT",
      )!;

    const reservationFixture =
      urgentQueueFixtures.find(
        (item) =>
          item.data.type ===
          "RESERVATION_SHORTAGE",
      )!;

    const button =
      await screen.findByRole("button", {
        name: "일정 충돌 판단 근거 보기",
      });

    fireEvent.click(button);

    const dialog =
      await screen.findByRole("dialog");

    expect(
      within(dialog).getByRole("heading", {
        name: "일정 충돌",
      }),
    ).toBeInTheDocument();

    expect(
      within(dialog).getByText(
        scheduleFixture.data.evidence[0]
          .source_id,
      ),
    ).toBeInTheDocument();

    expect(
      within(dialog).getByText(
        scheduleFixture.data.rule_version,
      ),
    ).toBeInTheDocument();

    expect(
      within(dialog).queryByText(
        reservationFixture.data.evidence[0]
          .source_id,
      ),
    ).not.toBeInTheDocument();
  });

  it("재고 불일치도 자기 request_id의 근거를 연다", async () => {
    render(<DashboardPage />);

    const fixture =
      urgentQueueFixtures.find(
        (item) =>
          item.data.type ===
          "INVENTORY_DISCREPANCY",
      )!;

    const button =
      await screen.findByRole("button", {
        name: "재고 불일치 판단 근거 보기",
      });

    fireEvent.click(button);

    const dialog =
      await screen.findByRole("dialog");

    expect(
      within(dialog).getByRole("heading", {
        name: "재고 불일치",
      }),
    ).toBeInTheDocument();

    expect(
      within(dialog).getByText(
        fixture.data.evidence[0].source_id,
      ),
    ).toBeInTheDocument();

    expect(
      within(dialog).getByText(
        fixture.data.rule_version,
      ),
    ).toBeInTheDocument();
  });

  it("위험 카드에는 request_id를 운영자에게 직접 노출하지 않는다", async () => {
    render(<DashboardPage />);

    await screen.findByRole("button", {
      name: "예약 재고 부족 판단 근거 보기",
    });

    for (const fixture of urgentQueueFixtures) {
      expect(
        screen.queryByText(fixture.request_id),
      ).not.toBeInTheDocument();
    }
  });

  it("닫은 뒤 다른 위험을 선택하면 Drawer 내용이 교체된다", async () => {
    render(<DashboardPage />);

    const reservation =
      urgentQueueFixtures.find(
        (item) =>
          item.data.type ===
          "RESERVATION_SHORTAGE",
      )!;

    const inventory =
      urgentQueueFixtures.find(
        (item) =>
          item.data.type ===
          "INVENTORY_DISCREPANCY",
      )!;

    const reservationButton =
      await screen.findByRole("button", {
        name: "예약 재고 부족 판단 근거 보기",
      });

    fireEvent.click(reservationButton);

    const firstDialog =
      await screen.findByRole("dialog");

    expect(
      within(firstDialog).getByRole(
        "heading",
        {
          name: "예약 재고 부족",
        },
      ),
    ).toBeInTheDocument();

    expect(
      within(firstDialog).getByText(
        reservation.data.evidence[0]
          .source_id,
      ),
    ).toBeInTheDocument();

    const closeButton =
      within(firstDialog).getByRole(
        "button",
        {
          name: "판단 근거 패널 닫기",
        },
      );

    fireEvent.click(closeButton);

    await waitFor(() => {
      expect(
        screen.queryByRole("dialog"),
      ).not.toBeInTheDocument();
    });

    const inventoryButton =
      screen.getByRole("button", {
        name: "재고 불일치 판단 근거 보기",
      });

    fireEvent.click(inventoryButton);

    const secondDialog =
      await screen.findByRole("dialog");

    expect(
      within(secondDialog).getByRole(
        "heading",
        {
          name: "재고 불일치",
        },
      ),
    ).toBeInTheDocument();

    expect(
      within(secondDialog).getByText(
        inventory.data.evidence[0]
          .source_id,
      ),
    ).toBeInTheDocument();

    expect(
      within(secondDialog).queryByText(
        reservation.data.evidence[0]
          .source_id,
      ),
    ).not.toBeInTheDocument();
  });
});