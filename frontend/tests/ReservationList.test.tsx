import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";

import {
  afterEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";

import ReservationList from "../src/features/reservations/ReservationList";
import { parseDay09ReservationsResponse } from "../src/api/day09";

const explanationRequest = vi.hoisted(() => vi.fn());
vi.mock("../src/api/explanations", () => ({ getPolicyExplanation: explanationRequest }));

import {
  reservationRiskSanitizedRealFixture,
  reservationRiskUiFixture,
} from "../src/mocks/fixtures";

afterEach(() => {
  cleanup();
  explanationRequest.mockReset();
});

describe("ReservationList", () => {
  it("SYNTHETIC_DEMO 응답의 known/unknown 두 행을 수치 변경 없이 표시한다", () => {
    explanationRequest.mockImplementation(() => new Promise(() => {}));
    const response = parseDay09ReservationsResponse({
      schema_version: "1.0",
      tenant_id: "demo_store",
      request_id: "req_demo_reservations",
      trace_id: "tr_demo_reservations",
      data: [
        {
          reservation_id: "demo_known",
          tenant_id: "demo_store",
          sku_id: "sku_known",
          required_qty: 6,
          secured_qty: 2,
          confirmed_incoming_qty: 1,
          tentative_incoming_qty: 3,
          shortage: 3,
          aging_hours: 24,
          priority: 2,
          delivery_risk: "MEDIUM",
          calculation_status: "CONFIRMED",
          quality_status: "CONFIRMED",
          source_classification: "SYNTHETIC_DEMO",
          data_mode: "SYNTHETIC_DEMO",
          as_of: "2026-09-29T00:00:00Z",
        },
        {
          reservation_id: "demo_unknown",
          tenant_id: "demo_store",
          sku_id: "sku_unknown",
          required_qty: 4,
          secured_qty: null,
          confirmed_incoming_qty: null,
          tentative_incoming_qty: 0,
          shortage: null,
          aging_hours: 0,
          priority: 0,
          delivery_risk: "UNKNOWN",
          calculation_status: "SECURED_QTY_UNKNOWN",
          quality_status: "UNKNOWN",
          source_classification: "SYNTHETIC_DEMO",
          data_mode: "SYNTHETIC_DEMO",
          as_of: "2026-09-29T00:00:00Z",
        },
      ],
      evidence_ids: [],
      warnings: [],
      as_of: "2026-09-29T00:00:00Z",
    });

    expect(response.data).toHaveLength(2);
    expect(response.data[0]).toMatchObject({
      required_qty: 6, secured_qty: 2, confirmed_incoming_qty: 1,
      tentative_incoming_qty: 3, shortage: 3, calculation_status: "CONFIRMED",
      delivery_risk: "MEDIUM", quality_status: "CONFIRMED", aging: 24,
    });
    expect(response.data[1]).toMatchObject({
      required_qty: 4, secured_qty: null, confirmed_incoming_qty: null,
      tentative_incoming_qty: 0, shortage: null,
      calculation_status: "SECURED_QTY_UNKNOWN",
      delivery_risk: "UNKNOWN", quality_status: "UNKNOWN",
    });

    render(<ReservationList items={response.data} showPolicyExplanation />);
    const rows = screen.getAllByTestId("reservation-risk-row");
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveAttribute("data-risk-state", "SHORTAGE");
    expect(rows[0]).toHaveTextContent("▲ 부족");
    expect(rows[0]).toHaveTextContent("합성 Demo 데이터");
    expect(rows[1]).toHaveAttribute("data-risk-state", "UNCERTAIN");
    expect(rows[1]).toHaveTextContent("● 확인 필요");
    expect(within(rows[1]).getAllByText("미제공")).toHaveLength(3);
    expect(within(rows[0]).getByRole("button", { name: /출고 정책 선택/ })).toBeInTheDocument();
    expect(within(rows[1]).queryByRole("button", { name: /출고 정책 선택/ })).not.toBeInTheDocument();
    expect(screen.queryByTestId("policy-explanation")).not.toBeInTheDocument();

    fireEvent.click(within(rows[0]).getByRole("button", { name: /출고 정책 선택/ }));
    expect(screen.getByTestId("policy-explanation")).toHaveAttribute("data-target-id", "demo_known");
    expect(screen.getByRole("button", { name: "정책 설명 보기" })).toBeInTheDocument();
    expect(explanationRequest).not.toHaveBeenCalled();
    expect(rows[0]).toHaveTextContent("6");
    expect(within(rows[1]).getAllByText("미제공")).toHaveLength(3);

    fireEvent.click(screen.getByRole("button", { name: "정책 설명 보기" }));
    expect(explanationRequest).toHaveBeenCalledTimes(1);
    expect(explanationRequest).toHaveBeenCalledWith("예약상품은 언제 출고해?", expect.any(AbortSignal));
  });

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
