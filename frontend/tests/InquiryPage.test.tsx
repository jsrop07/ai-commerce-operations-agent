import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import InquiriesPage from "../src/app/pages/InquiriesPage";

describe("InquiriesPage", () => {
  it("현재 범위를 안내하고 과거 AI Workbench와 Draft를 노출하지 않는다", () => {
    render(<InquiriesPage />);

    expect(screen.getByTestId("route-inquiries")).toBeInTheDocument();
    expect(
      screen.getByText("고객문의 AI 기능은 현재 사용하지 않습니다"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/문의 목록, 새 문의, 내부 읽음 연결은 후속 R11 범위입니다/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/외부 고객답변 전송 기능은 없습니다/),
    ).toBeInTheDocument();

    expect(screen.queryByText("AI Workbench")).not.toBeInTheDocument();
    expect(screen.queryByText("Retrieval Evidence")).not.toBeInTheDocument();
    expect(screen.queryByText("Intent:")).not.toBeInTheDocument();
    expect(screen.queryByText("Entities")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("textbox", { name: /Draft 내용/i }),
    ).not.toBeInTheDocument();
  });
});
