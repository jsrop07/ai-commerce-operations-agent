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

import ReservationList from "../src/features/reservations/ReservationList";

import {
  reservationRiskSanitizedRealFixture,
  reservationRiskUiFixture,
} from "../src/mocks/fixtures";

afterEach(() => {
  cleanup();
});

describe("ReservationList", () => {
  it("SANITIZED_REAL의 blocked 값을 0으로 표시하지 않는다", () => {
    render(
      <ReservationList
        items={
          reservationRiskSanitizedRealFixture.data
        }
      />,
    );

    const row = screen.getByTestId(
      "reservation-risk-row",
    );

    expect(row).toHaveTextContent(
      "실제 데이터 · 비식별 처리",
    );

    expect(row).toHaveTextContent(
      "● 확인 필요",
    );

    expect(row).toHaveTextContent(
      "확인 불가",
    );
  });

  it("Backend shortage 값이 있는 Fixture는 부족 상태를 표시한다", () => {
    render(
      <ReservationList
        items={reservationRiskUiFixture.data}
      />,
    );

    const shortageRow = screen
      .getAllByTestId("reservation-risk-row")
      .find((row) =>
        row.textContent?.includes(
          "reservation_fixture_shortage",
        ),
      );

    expect(shortageRow).toBeDefined();

    if (!shortageRow) {
      return;
    }

    expect(
      within(shortageRow).getByText("▲ 부족"),
    ).toBeInTheDocument();

    expect(shortageRow).toHaveAttribute(
      "data-risk-state",
      "SHORTAGE",
    );

    expect(shortageRow).toHaveTextContent(
      "테스트 Fixture",
    );
  });

  it("shortage 0은 충분으로 표시한다", () => {
    render(
      <ReservationList
        items={reservationRiskUiFixture.data}
      />,
    );

    const sufficientRow = screen
      .getAllByTestId("reservation-risk-row")
      .find((row) =>
        row.textContent?.includes(
          "reservation_fixture_sufficient",
        ),
      );

    expect(sufficientRow).toBeDefined();

    if (!sufficientRow) {
      return;
    }

    expect(
      within(sufficientRow).getByText("✓ 충분"),
    ).toBeInTheDocument();
  });

  it("shortage가 BLOCKED이면 0 대신 확인 필요 상태를 표시한다", () => {
    render(
      <ReservationList
        items={reservationRiskUiFixture.data}
      />,
    );

    const unknownRow = screen
      .getAllByTestId("reservation-risk-row")
      .find((row) =>
        row.textContent?.includes(
          "reservation_fixture_unknown",
        ),
      );

    expect(unknownRow).toBeDefined();

    if (!unknownRow) {
      return;
    }

    expect(
      within(unknownRow).getByText(
        "● 확인 필요",
      ),
    ).toBeInTheDocument();

    expect(unknownRow).toHaveAttribute(
      "data-risk-state",
      "UNCERTAIN",
    );
  });

  it("빈 배열이면 actual 값을 만들어내지 않고 Empty 상태를 표시한다", () => {
    render(
      <ReservationList items={[]} />,
    );

    expect(
      screen.getByTestId(
        "reservation-list-empty",
      ),
    ).toHaveTextContent(
      "현재 확정 가능한 예약 위험 Projection이 없습니다.",
    );
  });
});