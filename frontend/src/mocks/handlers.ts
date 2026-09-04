import type { ApiError } from "../types/contracts";
import {
  dashboardFixture, healthFixture, inquiriesFixture, insightsFixture, inventoryFixture,
  launchEventsFixture, ordersFixture, productsFixture, tasksFixture,
} from "./fixtures";

export interface MockHandler {
  method: "GET";
  path: string;
  resolve: () => unknown;
}

export const mockHandlers: readonly MockHandler[] = [
  { method: "GET", path: "/api/v1/health", resolve: () => healthFixture },
  { method: "GET", path: "/api/v1/dashboard", resolve: () => dashboardFixture },
  { method: "GET", path: "/api/v1/products", resolve: () => productsFixture },
  { method: "GET", path: "/api/v1/inventory", resolve: () => inventoryFixture },
  { method: "GET", path: "/api/v1/orders", resolve: () => ordersFixture },
  { method: "GET", path: "/api/v1/inquiries", resolve: () => inquiriesFixture },
  { method: "GET", path: "/api/v1/launch-events", resolve: () => launchEventsFixture },
  { method: "GET", path: "/api/v1/tasks", resolve: () => tasksFixture },
  { method: "GET", path: "/api/v1/insights", resolve: () => insightsFixture },
];

export async function mockApiGet<T>(path: string): Promise<T> {
  const handler = mockHandlers.find((candidate) => candidate.method === "GET" && candidate.path === path);
  await Promise.resolve();
  if (!handler) {
    const error: ApiError = {
      error: { code: "MOCK_ROUTE_NOT_FOUND", message: "No mock handler exists for the requested path", retryable: false, details: { path } },
      request_id: "req_demo_mock_not_found",
      trace_id: "tr_demo_mock_not_found",
    };
    throw error;
  }
  return handler.resolve() as T;
}
