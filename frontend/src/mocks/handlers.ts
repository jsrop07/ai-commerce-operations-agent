import type {
  ApiError,
} from "../types/contracts";

import {
  dashboardFixture,
  day10DelayImpactsFixture,
  day10DependenciesFixture,
  day10LaunchEventsFixture,
  day10ReplanProposalsFixture,
  day10TasksFixture,
  healthFixture,
  inquiriesFixture,
  insightsFixture,
  inventoryFixture,
  ordersFixture,
  productsFixture,
} from "./fixtures";

export interface MockHandler {
  method: "GET";
  path: string;
  resolve: () => unknown;
}

export const mockHandlers:
  readonly MockHandler[] = [
  {
    method: "GET",
    path: "/api/v1/health",
    resolve: () =>
      healthFixture,
  },
  {
    method: "GET",
    path: "/api/v1/dashboard",
    resolve: () =>
      dashboardFixture,
  },
  {
    method: "GET",
    path: "/api/v1/products",
    resolve: () =>
      productsFixture,
  },
  {
    method: "GET",
    path: "/api/v1/inventory",
    resolve: () =>
      inventoryFixture,
  },
  {
    method: "GET",
    path: "/api/v1/orders",
    resolve: () =>
      ordersFixture,
  },
  {
    method: "GET",
    path: "/api/v1/inquiries",
    resolve: () =>
      inquiriesFixture,
  },

  /*
   * Day 10 일정 화면.
   *
   * 기존 launchEventsFixture / tasksFixture가 아니라
   * Day 10 Projection 계약을 포함한 Fixture를 사용한다.
   */
  {
    method: "GET",
    path: "/api/v1/launch-events",
    resolve: () =>
      day10LaunchEventsFixture,
  },
  {
    method: "GET",
    path: "/api/v1/tasks",
    resolve: () =>
      day10TasksFixture,
  },

  {
    method: "GET",
    path: "/api/v1/insights",
    resolve: () =>
      insightsFixture,
  },

  /*
   * Day 10 Schedule Consumer Projection.
   *
   * 순서는 mocks.test.tsx의 expectedGetPaths와
   * 동일하게 유지한다.
   */
  {
    method: "GET",
    path: "/api/v1/schedule/dependencies",
    resolve: () =>
      day10DependenciesFixture,
  },
  {
    method: "GET",
    path: "/api/v1/schedule/delay-impacts",
    resolve: () =>
      day10DelayImpactsFixture,
  },
  {
    method: "GET",
    path:
      "/api/v1/schedule/replan-proposals",
    resolve: () =>
      day10ReplanProposalsFixture,
  },
];

export async function mockApiGet<T>(
  path: string,
): Promise<T> {
  const handler =
    mockHandlers.find(
      (candidate) =>
        candidate.method === "GET" &&
        candidate.path === path,
    );

  await Promise.resolve();

  if (!handler) {
    const error: ApiError = {
      error: {
        code: "MOCK_ROUTE_NOT_FOUND",
        message:
          "No mock handler exists for the requested path",
        retryable: false,
        details: {
          path,
        },
      },
      request_id:
        "req_demo_mock_not_found",
      trace_id:
        "tr_demo_mock_not_found",
    };

    throw error;
  }

  return handler.resolve() as T;
}