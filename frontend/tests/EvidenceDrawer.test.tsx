import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import EvidenceDrawer from "../src/components/EvidenceDrawer";
import { insights } from "../src/mocks/fixtures";

describe("EvidenceDrawer", () => {
  it("닫힌 상태에서는 렌더링하지 않는다", () => {
    render(
      <EvidenceDrawer
        open={false}
        insight={insights[0]}
        onClose={() => {}}
      />
    );

    expect(
      screen.queryByRole("dialog", { name: "예약 재고 부족" })
    ).not.toBeInTheDocument();
  });

  it("원천 근거를 표시한다", () => {
    render(
      <EvidenceDrawer
        open
        insight={insights[0]}
        onClose={() => {}}
      />
    );

    expect(screen.getByText("ord_demo_002")).toBeInTheDocument();
    expect(screen.getByText("sku_demo_001")).toBeInTheDocument();
    expect(screen.getByText("주문")).toBeInTheDocument();
    expect(screen.getByText("재고 스냅샷")).toBeInTheDocument();
  });

  it("계산 근거를 표시한다", () => {
    render(
      <EvidenceDrawer
        open
        insight={insights[0]}
        onClose={() => {}}
      />
    );

    expect(screen.getByText("reserved")).toBeInTheDocument();
    expect(screen.getByText("available")).toBeInTheDocument();
    expect(screen.getByText("confirmed_incoming")).toBeInTheDocument();
    expect(screen.getByText("shortage")).toBeInTheDocument();
  });

  it("계산식이 없으면 안내 문구를 표시한다", () => {
    render(
      <EvidenceDrawer
        open
        insight={insights[1]}
        onClose={() => {}}
      />
    );

    expect(
      screen.getByText("별도의 수치 계산식이 없는 판단입니다.")
    ).toBeInTheDocument();
  });

  it("model_run_id가 null이면 provenance를 규칙으로 단정하지 않는다", () => {
    render(
      <EvidenceDrawer
        open
        insight={insights[0]}
        onClose={() => {}}
      />
    );

    expect(screen.getByText("현재 계약으로 확인 불가")).toBeInTheDocument();
    expect(
      screen.getByText(/현재 계약만으로 판단 출처를 확정할 수 없습니다/)
    ).toBeInTheDocument();
    expect(screen.queryByText("규칙 기반 판단")).not.toBeInTheDocument();
    expect(screen.queryByText("AI 모델 기반 판단")).not.toBeInTheDocument();
  });

  it("계약에 없는 model/prompt/index 정보를 임의 생성하지 않는다", () => {
    render(
      <EvidenceDrawer
        open
        insight={insights[0]}
        onClose={() => {}}
      />
    );

    expect(screen.getByText("제공되지 않음")).toBeInTheDocument();
    expect(
      screen.getAllByText("현재 계약에서 제공되지 않음")
    ).toHaveLength(3);
    expect(screen.getByText("reservation-risk-v1")).toBeInTheDocument();
  });
  it("닫기 버튼으로 닫을 수 있다", () => {
    const onClose = vi.fn();

    render(
      <EvidenceDrawer
        open
        insight={insights[0]}
        onClose={onClose}
      />
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: "판단 근거 패널 닫기",
      })
    );

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("배경을 클릭하면 닫힌다", () => {
    const onClose = vi.fn();

    render(
      <EvidenceDrawer
        open
        insight={insights[0]}
        onClose={onClose}
      />
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: "판단 근거 닫기",
      })
    );

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("Escape 키로 닫을 수 있다", () => {
    const onClose = vi.fn();

    render(
      <EvidenceDrawer
        open
        insight={insights[0]}
        onClose={onClose}
      />
    );

    fireEvent.keyDown(window, { key: "Escape" });

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("dialog 접근성 속성을 제공한다", () => {
    render(
      <EvidenceDrawer
        open
        insight={insights[0]}
        onClose={() => {}}
      />
    );

    const dialog = screen.getByRole("dialog", {
      name: "예약 재고 부족",
    });

    expect(dialog).toHaveAttribute("aria-modal", "true");
  });

  it("열릴 때 닫기 버튼으로 focus를 이동하고 닫힐 때 원래 focus를 복원한다", () => {
    const opener = document.createElement("button");
    document.body.appendChild(opener);
    opener.focus();

    const { unmount } = render(
      <EvidenceDrawer
        open
        insight={insights[0]}
        onClose={() => {}}
      />
    );

    expect(
      screen.getByRole("button", { name: "판단 근거 패널 닫기" })
    ).toHaveFocus();

    unmount();
    expect(opener).toHaveFocus();
    opener.remove();
  });

  it("Tab focus가 dialog 밖으로 벗어나지 않는다", () => {
    render(
      <EvidenceDrawer
        open
        insight={insights[0]}
        onClose={() => {}}
      />
    );

    const closeButton = screen.getByRole("button", {
      name: "판단 근거 패널 닫기",
    });

    fireEvent.keyDown(window, { key: "Tab" });
    expect(closeButton).toHaveFocus();

    fireEvent.keyDown(window, { key: "Tab", shiftKey: true });
    expect(closeButton).toHaveFocus();
  });

  it("원천 근거가 비어 있으면 명시적인 안내를 표시한다", () => {
    render(
      <EvidenceDrawer
        open
        insight={{ ...insights[0], evidence: [] }}
        onClose={() => {}}
      />
    );

    expect(
      screen.getByText("연결된 원천 근거가 없습니다.")
    ).toBeInTheDocument();
  });

  it("긴 source_id를 생략하거나 임의 변환하지 않는다", () => {
    const longSourceId = `source_${"x".repeat(256)}`;

    render(
      <EvidenceDrawer
        open
        insight={{
          ...insights[0],
          evidence: [
            { ...insights[0].evidence[0], source_id: longSourceId },
          ],
        }}
        onClose={() => {}}
      />
    );

    expect(screen.getByText(longSourceId)).toHaveClass("mono");
  });

  it("모델 결과의 계약 미제공 버전을 임의 생성하지 않는다", () => {
    render(
      <EvidenceDrawer
        open
        insight={{ ...insights[0], model_run_id: "model_run_demo_001" }}
        onClose={() => {}}
      />
    );

    expect(screen.getByText("AI 모델 기반 판단")).toBeInTheDocument();
    expect(screen.getByText("model_run_demo_001")).toBeInTheDocument();
    expect(
      screen.getAllByText("현재 계약에서 제공되지 않음")
    ).toHaveLength(3);
  });
});
