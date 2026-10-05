import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CommonAiDrawerHost } from "../src/app/CommonAiDrawerContext";
import OrdersPage from "../src/app/pages/OrdersPage";
import InquiriesPage from "../src/app/pages/InquiriesPage";
import { appendAnalysis, createConversation, getConversations } from "../src/api/conversations";

vi.mock("../src/api/conversations", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/api/conversations")>();
  return { ...actual, getConversations: vi.fn(), createConversation: vi.fn(), appendAnalysis: vi.fn() };
});

beforeEach(() => {
  vi.stubEnv("VITE_USE_REAL_BACKEND", "false");
  vi.mocked(getConversations).mockResolvedValue({ schema_version: "1.0", tenant_id: "tenant",
    request_id: "request", trace_id: "trace", evidence_ids: [], warnings: [],
    as_of: "2026-10-04T00:00:00Z", data: [] });
});
afterEach(() => { vi.clearAllMocks(); vi.unstubAllEnvs(); });

describe("Common Operations AI page launcher", () => {
  it("opens ORDERS_SALES VIEW without sending displayed order or customer rows", async () => {
    vi.mocked(createConversation).mockRejectedValue(new Error("expected test stop"));
    render(<CommonAiDrawerHost><OrdersPage /></CommonAiDrawerHost>);
    const opener = screen.getByRole("button", { name: "주문 & 매출 화면 운영 AI 열기" });
    opener.focus();
    fireEvent.click(opener);
    const drawer = screen.getByRole("dialog", { name: "운영 AI" });
    expect(within(drawer).getByText("ORDERS_SALES", { selector: "dd" })).toBeInTheDocument();
    expect(within(drawer).getByText("없음")).toBeInTheDocument();
    expect(createConversation).not.toHaveBeenCalled();
    expect(appendAnalysis).not.toHaveBeenCalled();
    await waitFor(() => expect(getConversations).toHaveBeenCalledTimes(1));
    fireEvent.click(within(drawer).getByRole("button", { name: "분석 실행" }));
    await waitFor(() => expect(createConversation).toHaveBeenCalledWith({
      scope: "VIEW", page: "ORDERS_SALES", filters: {},
    }));
    expect(JSON.stringify(vi.mocked(createConversation).mock.calls[0][0]))
      .not.toMatch(/C24-|TP-|customer|order_id|order_line_id|고객|배송|결제/);
    expect(appendAnalysis).not.toHaveBeenCalled();
    fireEvent.click(within(drawer).getByRole("button", { name: "운영 AI 패널 닫기" }));
    expect(opener).toHaveFocus();
  });

  it("does not add a launcher to inquiries", () => {
    render(<CommonAiDrawerHost><InquiriesPage /></CommonAiDrawerHost>);
    expect(screen.queryByRole("button", { name: /운영 AI.*열기/ })).not.toBeInTheDocument();
  });
});
