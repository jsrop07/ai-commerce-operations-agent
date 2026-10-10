// frontend/tests/OrdersPage_UI_병렬검증.test.tsx
// 실제 Backend가 없어도 주문 목록과 매출 분석의 프론트엔드 동작을 확인합니다.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { OrderListBrowser, SalesAnalysisPanel, type OrderDisplayItem } from "../src/app/pages/OrdersPage";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const sampleOrders: OrderDisplayItem[] = [
  {
    orderId: "DEMO-ORD-001",
    orderedAt: "2026-10-05T01:30:00Z",
    products: [{ name: "테스트 보드게임 A", quantity: 2 }],
    orderAmount: "42000",
    paidAmount: "42000",
    paid: "T",
    canceled: "F",
    shippingStatus: "T",
  },
  {
    orderId: "DEMO-ORD-002",
    orderedAt: "2026-10-06T03:30:00Z",
    products: [
      { name: "테스트 보드게임 B", option: "기본", quantity: 1 },
      { name: "테스트 확장팩", quantity: 2 },
    ],
    orderAmount: "25000",
    paidAmount: null,
    paid: "F",
    canceled: "M",
    shippingStatus: "F",
  },
];

describe("주문 목록 UI — Backend 독립 테스트", () => {
  it("미연결 상태를 실제 0건으로 오인하지 않고 안내한다", () => {
    render(<OrderListBrowser />);
    expect(screen.getByText("주문 목록 API 연결 대기")).toBeTruthy();
    expect(screen.getByText("페이지 정보 미연결")).toBeTruthy();
  });

  it("연결된 자료에 대해 주문번호로 검색하고 초기화할 수 있다", () => {
    render(<OrderListBrowser records={sampleOrders} />);
    fireEvent.change(screen.getByRole("textbox", { name: "주문번호 또는 상품명 검색" }), {
      target: { value: "DEMO-ORD-002" },
    });
    fireEvent.click(screen.getByRole("button", { name: "검색" }));
    expect(screen.getByText("DEMO-ORD-002")).toBeTruthy();
    expect(screen.queryByText("DEMO-ORD-001")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /상세 필터/ }));
    fireEvent.click(screen.getByRole("button", { name: "초기화" }));
    expect(screen.getByText("DEMO-ORD-001")).toBeTruthy();
  });

  it("다중 상품 주문의 상세를 펼치고 다시 접을 수 있다", () => {
    render(<OrderListBrowser records={[sampleOrders[1]]} />);
    fireEvent.click(screen.getByRole("button", { name: "펼치기" }));
    expect(screen.getByText(/테스트 확장팩 · 수량 2/)).toBeTruthy();
    expect(screen.getByText("결제 표시 금액: 미제공")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "접기" }));
    expect(screen.queryByText(/테스트 확장팩 · 수량 2/)).toBeNull();
  });

  it("시작일이 종료일보다 늦으면 필터 적용을 막는다", () => {
    render(<OrderListBrowser records={sampleOrders} />);
    fireEvent.click(screen.getByRole("button", { name: /상세 필터/ }));
    fireEvent.change(screen.getByLabelText("시작일"), { target: { value: "2026-10-09" } });
    fireEvent.change(screen.getByLabelText("종료일"), { target: { value: "2026-10-01" } });
    fireEvent.click(screen.getByRole("button", { name: "적용" }));
    expect(screen.getByRole("alert").textContent).toContain("시작일이 종료일보다 늦을 수 없습니다.");
    expect(screen.getByText("DEMO-ORD-001")).toBeTruthy();
  });

  it("데이터가 연결되어도 미제공 상태를 0으로 표현하지 않는다", () => {
    render(<OrderListBrowser records={[sampleOrders[1]]} />);
    const row = screen.getByText("DEMO-ORD-002").closest("tr");
    expect(row).not.toBeNull();
    expect(within(row!).getByText("확인 필요")).toBeTruthy();
  });
});

describe("매출 분석 UI — Backend 독립 테스트", () => {
  it("집계가 없으면 임의 수치와 가짜 차트를 표시하지 않는다", () => {
    render(<SalesAnalysisPanel />);
    expect(screen.getByText("일별 집계 API 연결 대기")).toBeTruthy();
    expect(screen.getByText("상태별 집계 API 연결 대기")).toBeTruthy();
    expect(screen.getAllByText("—").length).toBe(4);
  });

  it("제공된 합성 집계값은 그대로 표시하고 정산 매출로 주장하지 않는다", () => {
    render(<SalesAnalysisPanel data={{
      periodLabel: "2026-10-01 ~ 2026-10-05",
      totalOrderAmount: "100000",
      paidMarkedAmount: "80000",
      orderCount: 3,
      uncertainOrCanceledCount: 1,
      daily: [{ date: "2026-10-05", orderAmount: 100000 }],
      states: [{ label: "취소 T", count: 1 }],
    }} />);
    expect(screen.getByText("3건")).toBeTruthy();
    expect(screen.getByText("취소 T")).toBeTruthy();
    expect(screen.getByText(/실제 결제 정산이나 환불 반영 순매출이 아닙니다/)).toBeTruthy();
  });
});
