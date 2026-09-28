import {
  cleanup,
  render,
  screen,
  within,
} from "@testing-library/react";

import {
  afterEach,
  describe,
  expect,
  it,
} from "vitest";

import ReservationTimeline from "../src/features/reservations/ReservationTimeline";

import {
  reservationTimelineFixture,
} from "../src/mocks/fixtures";

afterEach(() => {
  cleanup();
});

describe("ReservationTimeline", () => {
  it("예약→발주→입고→출고 순서를 표시한다", () => {
    render(
      <ReservationTimeline
        timeline={reservationTimelineFixture}
      />,
    );

    const steps =
      screen.getAllByTestId(
        "reservation-timeline-step",
      );

    expect(steps).toHaveLength(4);

    expect(steps[0]).toHaveAttribute(
      "data-stage",
      "RESERVATION",
    );

    expect(steps[1]).toHaveAttribute(
      "data-stage",
      "PURCHASE_ORDER",
    );

    expect(steps[2]).toHaveAttribute(
      "data-stage",
      "INCOMING",
    );

    expect(steps[3]).toHaveAttribute(
      "data-stage",
      "FULFILLMENT",
    );
  });

  it("CONTRACT_ONLY 발주를 완료라고 표시하지 않는다", () => {
    render(
      <ReservationTimeline
        timeline={reservationTimelineFixture}
      />,
    );

    const purchaseOrderStep =
      screen
        .getAllByTestId(
          "reservation-timeline-step",
        )
        .find(
          (step) =>
            step.getAttribute("data-stage") ===
            "PURCHASE_ORDER",
        );

    expect(purchaseOrderStep).toBeDefined();

    if (!purchaseOrderStep) {
      return;
    }

    expect(
      within(purchaseOrderStep).getByText(
        "▲ 계약만 확인됨",
      ),
    ).toBeInTheDocument();

    expect(
      purchaseOrderStep,
    ).not.toHaveTextContent(
      "발주 완료",
    );
  });

  it("BLOCKED 입고를 완료라고 표시하지 않는다", () => {
    render(
      <ReservationTimeline
        timeline={reservationTimelineFixture}
      />,
    );

    const incomingStep =
      screen
        .getAllByTestId(
          "reservation-timeline-step",
        )
        .find(
          (step) =>
            step.getAttribute("data-stage") ===
            "INCOMING",
        );

    expect(incomingStep).toBeDefined();

    if (!incomingStep) {
      return;
    }

    expect(
      within(incomingStep).getByText(
        "● 확인 불가",
      ),
    ).toBeInTheDocument();

    expect(
      incomingStep,
    ).not.toHaveTextContent(
      "입고 완료",
    );
  });

  it("as_of가 없으면 임의 날짜 대신 시각 미확인으로 표시한다", () => {
    render(
      <ReservationTimeline
        timeline={reservationTimelineFixture}
      />,
    );

    expect(
      screen.getAllByText(
        "시각 미확인",
      ).length,
    ).toBeGreaterThanOrEqual(1);
  });

  it("확인된 Source Event와 Evidence를 표시한다", () => {
    render(
      <ReservationTimeline
        timeline={reservationTimelineFixture}
      />,
    );

    expect(
      screen.getByText(
        "evt_reservation_created_001",
      ),
    ).toBeInTheDocument();

    expect(
    screen.getAllByText(
        /reservation_fixture_timeline_001/,
    ).length,
    ).toBeGreaterThanOrEqual(2);
  });
});