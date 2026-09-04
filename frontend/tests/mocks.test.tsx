import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "../src/app/App";
import { mockApiGet, mockHandlers } from "../src/mocks/handlers";
import type { ApiEnvelope, DashboardData } from "../src/types/contracts";

const expectedGetPaths = [
  "/api/v1/health",
  "/api/v1/dashboard",
  "/api/v1/products",
  "/api/v1/inventory",
  "/api/v1/orders",
  "/api/v1/inquiries",
  "/api/v1/launch-events",
  "/api/v1/tasks",
  "/api/v1/insights",
];

describe("contract mock handlers", () => {
  it("provides only the required GET endpoints", () => {
    expect(mockHandlers.map((handler) => handler.path)).toEqual(expectedGetPaths);
    expect(mockHandlers.every((handler) => handler.method === "GET")).toBe(true);
  });

  it("returns and consumes the Dashboard mock response", async () => {
    const response = await mockApiGet<ApiEnvelope<DashboardData>>("/api/v1/dashboard");
    expect(response.data.insights[0].insight_id).toBe("ins_demo_001");
    expect(response.data.inventory.some((item) => item.freshness === "STALE")).toBe(true);
  });

  it("renders the home screen from mock data", async () => {
    window.history.replaceState({}, "", "/");
    render(<App />);
    expect(
      (await screen.findAllByText("예약 재고 부족")).length
    ).toBeGreaterThanOrEqual(1);

    expect(
      screen.queryByText("RESERVATION_SHORTAGE")
    ).not.toBeInTheDocument();

    expect(
      screen.getByText("긴급 Queue")
    ).toBeInTheDocument();

    expect(
      screen.getAllByText("재고 불일치").length
    ).toBeGreaterThanOrEqual(1);

    expect(
      screen.queryByText("INVENTORY_DISCREPANCY")
    ).not.toBeInTheDocument();
  });
});
