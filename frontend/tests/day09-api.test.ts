import {
  describe,
  expect,
  it,
} from "vitest";

import {
  parseDay09ReservationsResponse,
} from "../src/api/day09";

describe("Day 9 reservation API boundary", () => {
  it("C03 수량과 numeric priority를 서버 값 그대로 보존한다", () => {
    const result = parseDay09ReservationsResponse({
      schema_version: "1.0", tenant_id: "demo_store", request_id: "req_c03",
      trace_id: "tr_c03", evidence_ids: [], warnings: [], as_of: "2026-09-11T06:00:00Z",
      data: [{ reservation_id: "reservation-a", sku_id: "sku-a", required_qty: 5,
        secured_qty: 1, confirmed_incoming_qty: 2, tentative_incoming_qty: 0,
        shortage: 2, aging_hours: 12, priority: 42, priority_reason: "rule",
        calculation_status: "CONFIRMED", delivery_risk: "HIGH", evidence: [],
        source_classification: "FIXTURE", quality_status: "CONFIRMED", as_of: "2026-09-11T06:00:00Z" }],
    });
    expect(result.data[0]).toMatchObject({ reservation_id: "reservation-a", required_qty: 5,
      secured_qty: 1, confirmed_incoming_qty: 2, tentative_incoming_qty: 0,
      shortage: 2, priority: 42, calculation_status: "CONFIRMED" });
  });
  it("실제 fail-closed empty 응답과 warning을 그대로 보존한다", () => {
    const result =
      parseDay09ReservationsResponse({
        schema_version: "1.0",
        tenant_id: "demo_store",
        request_id: "req_day09_empty",
        trace_id: "tr_day09_empty",
        data: [],
        evidence_ids: [],
        warnings: [
          "RESERVATION_RISK_EMPTY: no usable reservation risk projection available",
        ],
        as_of: "2026-09-10T10:00:00Z",
      });

    expect(result.data).toEqual([]);

    expect(result.warnings).toContain(
      "RESERVATION_RISK_EMPTY: no usable reservation risk projection available",
    );

    expect(result.schema_version).toBe(
      "1.0",
    );
  });

  it("BLOCKED와 UNKNOWN 수량을 null 그대로 보존한다", () => {
    const result =
      parseDay09ReservationsResponse({
        schema_version: "1.0",
        tenant_id: "demo_store",
        request_id: "req_day09_blocked",
        trace_id: "tr_day09_blocked",

        data: [
          {
            reservation_id:
              "reservation_actual_001",

            product_name:
              "Warhammer Pre-Order Product",

            sku_id:
              "sku_reservation_actual_001",

            required_qty: 8,
            secured_qty: null,
            confirmed_incoming: null,
            tentative_incoming: null,
            shortage: null,

            aging: null,
            priority: null,

            as_of:
              "2026-09-10T10:00:00Z",

            source_classification:
              "SANITIZED_REAL",

            required_state: "KNOWN",
            secured_state: "BLOCKED",
            confirmed_incoming_state:
              "BLOCKED",
            tentative_incoming_state:
              "UNKNOWN",
            shortage_state: "BLOCKED",

            evidence_ids: [
              "evidence_reservation_actual_001",
            ],
          },
        ],

        evidence_ids: [
          "evidence_reservation_actual_001",
        ],

        warnings: [],

        as_of:
          "2026-09-10T10:00:00Z",
      });

    const [item] = result.data;

    expect(item.required_qty).toBe(8);

    expect(item.secured_qty).toBeNull();
    expect(
      item.confirmed_incoming,
    ).toBeNull();
    expect(
      item.tentative_incoming,
    ).toBeNull();
    expect(item.shortage).toBeNull();

    expect(item.secured_state).toBe(
      "BLOCKED",
    );

    expect(item.shortage_state).toBe(
      "BLOCKED",
    );

    expect(
      item.source_classification,
    ).toBe("SANITIZED_REAL");
  });

  it("Frontend가 null shortage를 0으로 변환하지 않는다", () => {
    const result =
      parseDay09ReservationsResponse({
        schema_version: "1.0",
        tenant_id: "demo_store",
        request_id: "req_day09_null",
        trace_id: "tr_day09_null",

        data: [
          {
            reservation_id:
              "reservation_null",

            product_name:
              "예약 상품",

            required_qty: 8,
            secured_qty: null,
            confirmed_incoming: null,
            tentative_incoming: null,
            shortage: null,

            as_of:
              "2026-09-10T10:00:00Z",

            source_classification:
              "SANITIZED_REAL",

            shortage_state:
              "BLOCKED",
          },
        ],

        evidence_ids: [],
        warnings: [],

        as_of:
          "2026-09-10T10:00:00Z",
      });

    expect(
      result.data[0].shortage,
    ).toBeNull();

    expect(
      result.data[0].shortage,
    ).not.toBe(0);
  });

  it("잘못된 source_classification은 거부한다", () => {
    expect(() =>
      parseDay09ReservationsResponse({
        schema_version: "1.0",
        tenant_id: "demo_store",
        request_id: "req_invalid",
        trace_id: "tr_invalid",

        data: [
          {
            reservation_id:
              "reservation_invalid",

            product_name:
              "예약 상품",

            required_qty: 8,
            secured_qty: null,
            confirmed_incoming: null,
            tentative_incoming: null,
            shortage: null,

            as_of:
              "2026-09-10T10:00:00Z",

            source_classification:
              "MADE_UP_ACTUAL",
          },
        ],

        evidence_ids: [],
        warnings: [],

        as_of:
          "2026-09-10T10:00:00Z",
      }),
    ).toThrow(
      "Backend reservation risk item is malformed",
    );
  });

  it("필수 수량 필드가 숫자/null이 아니면 거부한다", () => {
    expect(() =>
      parseDay09ReservationsResponse({
        schema_version: "1.0",
        tenant_id: "demo_store",
        request_id: "req_invalid_qty",
        trace_id: "tr_invalid_qty",

        data: [
          {
            reservation_id:
              "reservation_invalid_qty",

            product_name:
              "예약 상품",

            required_qty: "8",
            secured_qty: null,
            confirmed_incoming: null,
            tentative_incoming: null,
            shortage: null,

            as_of:
              "2026-09-10T10:00:00Z",

            source_classification:
              "SANITIZED_REAL",
          },
        ],

        evidence_ids: [],
        warnings: [],

        as_of:
          "2026-09-10T10:00:00Z",
      }),
    ).toThrow(
      "Reservation field required_qty is malformed",
    );
  });
});
