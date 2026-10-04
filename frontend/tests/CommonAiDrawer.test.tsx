import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import CommonAiDrawer, { type AiPanelContext } from "../src/components/CommonAiDrawer";
import {
  CommonAiDrawerHost,
  useCommonAiDrawer,
} from "../src/app/CommonAiDrawerContext";

const context: AiPanelContext = {
  targetType: "PRODUCT",
  targetId: "product-101",
  targetLabel: "Sample product",
  source: "commerce_ops_v2",
  asOf: null,
};

function HostTrigger() {
  const { openAiDrawer } = useCommonAiDrawer();
  return <button type="button" onClick={() => openAiDrawer(context)}>대상 열기</button>;
}

describe("Common AI Drawer shell", () => {
  it("does not render in CLOSED state", () => {
    render(<CommonAiDrawer open={false} context={null} onClose={() => {}} />);
    expect(screen.queryByRole("dialog", { name: "운영 AI" })).not.toBeInTheDocument();
  });

  it("shows only context and idle shell, preserving unknown time", () => {
    const extended = { ...context, request_id: "internal-request", trace_id: "internal-trace" };
    render(<CommonAiDrawer open context={extended} onClose={() => {}} />);
    const dialog = screen.getByRole("dialog", { name: "운영 AI" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    for (const value of ["Sample product", "PRODUCT", "product-101", "commerce_ops_v2", "기준 시각 미확인",
      "아직 분석을 실행하지 않았습니다.", "연결된 근거 없음", "현재 context 기준 후속 확인 없음", "C09 대화 연결 전입니다."]) {
      expect(within(dialog).getByText(value)).toBeInTheDocument();
    }
    expect(within(dialog).getByRole("textbox", { name: "후속 질문 입력" })).toBeDisabled();
    expect(within(dialog).getByRole("button", { name: "전송" })).toBeDisabled();
    expect(dialog).not.toHaveTextContent("internal-request");
    expect(dialog).not.toHaveTextContent("internal-trace");
    expect(dialog).not.toHaveTextContent("request_id");
    expect(dialog).not.toHaveTextContent("trace_id");
  });

  it("shows a provided data timestamp without replacing it", () => {
    render(<CommonAiDrawer open context={{ ...context, asOf: "2026-09-11T06:00:00Z" }} onClose={() => {}} />);
    expect(screen.getByText("2026-09-11T06:00:00Z")).toHaveAttribute("datetime", "2026-09-11T06:00:00Z");
  });

  it("uses one App-level host, traps focus, and restores the opener after Escape", () => {
    render(<CommonAiDrawerHost><HostTrigger /></CommonAiDrawerHost>);
    const opener = screen.getByRole("button", { name: "대상 열기" });
    opener.focus();
    fireEvent.click(opener);
    const dialog = screen.getByRole("dialog", { name: "운영 AI" });
    expect(screen.getAllByRole("dialog")).toHaveLength(1);
    const close = within(dialog).getByRole("button", { name: "운영 AI 패널 닫기" });
    expect(close).toHaveFocus();
    fireEvent.keyDown(window, { key: "Tab" });
    expect(close).toHaveFocus();
    fireEvent.keyDown(window, { key: "Tab", shiftKey: true });
    expect(close).toHaveFocus();
    opener.focus();
    fireEvent.keyDown(window, { key: "Tab" });
    expect(close).toHaveFocus();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("dialog", { name: "운영 AI" })).not.toBeInTheDocument();
    expect(opener).toHaveFocus();
  });

  it("closes through backdrop and returns focus", () => {
    render(<CommonAiDrawerHost><HostTrigger /></CommonAiDrawerHost>);
    const opener = screen.getByRole("button", { name: "대상 열기" });
    opener.focus();
    fireEvent.click(opener);
    fireEvent.click(screen.getByRole("button", { name: "운영 AI 패널 배경 닫기" }));
    expect(screen.queryByRole("dialog", { name: "운영 AI" })).not.toBeInTheDocument();
    expect(opener).toHaveFocus();
    fireEvent.click(opener);
    fireEvent.click(screen.getByRole("button", { name: "운영 AI 패널 닫기" }));
    expect(screen.queryByRole("dialog", { name: "운영 AI" })).not.toBeInTheDocument();
    expect(opener).toHaveFocus();
  });
});
