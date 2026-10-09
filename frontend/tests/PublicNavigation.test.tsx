import { render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import App from "../src/app/App";
import { resolveRoute } from "../src/app/routes";

vi.mock("../src/api/demoSession", () => ({
  bootstrapDemoSession: vi.fn().mockResolvedValue({
    status: "ACTIVE", expiresAt: "2099-01-01T00:00:00Z",
  }),
}));

afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); });

it("hides Inquiry AI and provides global launcher in Public Demo", () => {
  vi.stubEnv("VITE_USE_REAL_BACKEND", "true");
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline test")));
  window.history.replaceState({}, "", "/inquiries");
  render(<App environment="DEMO" />);
  expect(resolveRoute("/inquiries", true).path).toBe("/");
  expect(screen.queryByRole("link", { name: /고객 문의/ })).not.toBeInTheDocument();
  expect(screen.queryByTestId("route-inquiries")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "운영 AI 열기" })).toBeInTheDocument();
  expect(screen.queryByText("전체 주문 247건")).not.toBeInTheDocument();
});

it("keeps the public Demo boundary when a visitor adds an environment query", () => {
  vi.stubEnv("VITE_USE_REAL_BACKEND", "true");
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline test")));
  window.history.replaceState({}, "", "/inquiries?environment=local-eval");
  render(<App />);
  expect(screen.getByRole("banner", { name: "Demo 환경" })).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: /고객 문의/ })).not.toBeInTheDocument();
  expect(screen.queryByTestId("route-inquiries")).not.toBeInTheDocument();
});
