import {
  describe,
  expect,
  it,
} from "vitest";

import type {
  ReservationRiskItem,
} from "../src/types/contracts";

import {
  formatReservationQuantity,
  getReservationRiskDisplayState,
  getReservationRiskLabel,
  getSourceClassificationLabel,
} from "../src/features/reservations/reservationViewModels";

function makeItem(
  overrides: Partial<ReservationRiskItem> = {},
): ReservationRiskItem {
  return {
    reservation_id: "reservation_test",
    product_name: "테스트 예약 상품",
    sku_id: "sku_test",

    required_qty: 8,
    secured_qty: null,
    confirmed_incoming: null,
    tentative_incoming: null,
    shortage: null,

    aging: null,
    priority: null,

    as_of: "2026-09-10T10:00:00Z",

    source_classification: "FIXTURE",

    required_state: "KNOWN",
    secured_state: "UNKNOWN",
    confirmed_incoming_state: "BLOCKED",
    tentative_incoming_state: "UNKNOWN",
    shortage_state: "BLOCKED",

    evidence_ids: [],

    ...overrides,
  };
}

describe("reservationViewModels", () => {
  it("null + BLOCKED는 0이 아니라 확인 불가로 표시한다", () => {
    expect(
      formatReservationQuantity(
        null,
        "BLOCKED",
      ),
    ).toBe("확인 불가");
  });

  it("null + UNKNOWN은 미확인으로 표시한다", () => {
    expect(
      formatReservationQuantity(
        null,
        "UNKNOWN",
      ),
    ).toBe("미확인");
  });

  it("shortage가 없거나 확정되지 않았으면 UNCERTAIN이다", () => {
    const item = makeItem();

    expect(
      getReservationRiskDisplayState(item),
    ).toBe("UNCERTAIN");

    expect(
      getReservationRiskLabel(item),
    ).toBe("● 확인 필요");
  });

  it("Backend shortage가 4이면 부족으로 표시한다", () => {
    const item = makeItem({
      shortage: 4,
      shortage_state: "KNOWN",
    });

    expect(
      getReservationRiskDisplayState(item),
    ).toBe("SHORTAGE");

    expect(
      getReservationRiskLabel(item),
    ).toBe("▲ 부족");
  });

  it("Backend가 shortage_state를 생략해도 알려진 shortage를 보존한다", () => {
    const item = makeItem({ shortage: 3, shortage_state: undefined });
    expect(getReservationRiskDisplayState(item)).toBe("SHORTAGE");
  });

  it("Backend shortage가 0이면 충분으로 표시한다", () => {
    const item = makeItem({
      shortage: 0,
      shortage_state: "KNOWN",
    });

    expect(
      getReservationRiskDisplayState(item),
    ).toBe("SUFFICIENT");

    expect(
      getReservationRiskLabel(item),
    ).toBe("✓ 충분");
  });

  it("SANITIZED_REAL은 실제 비식별 데이터로 표시한다", () => {
    expect(
      getSourceClassificationLabel(
        "SANITIZED_REAL",
      ),
    ).toBe(
      "실제 데이터 · 비식별 처리",
    );
  });

  it("FIXTURE를 실제 데이터처럼 표시하지 않는다", () => {
    expect(
      getSourceClassificationLabel(
        "FIXTURE",
      ),
    ).toBe("테스트 Fixture");
  });
});
