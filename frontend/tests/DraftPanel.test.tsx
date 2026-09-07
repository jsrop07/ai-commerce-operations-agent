import {
  fireEvent,
  render,
  screen,
} from "@testing-library/react";

import {
  describe,
  expect,
  it,
} from "vitest";

import DraftPanel from "../src/features/inquiries/DraftPanel";

describe("DraftPanel", () => {
  it("정상 LOW 문의 Draft는 수정 가능하다", () => {
    render(
      <DraftPanel
        draft={{
          text: "합성 Draft입니다.",
          status: "DRAFT",
          provenance: "AI",
        }}
        holdRequired={false}
        evidenceCount={1}
      />,
    );

    const textarea =
      screen.getByRole("textbox", {
        name: /Draft 내용/i,
      });

    expect(textarea).toBeEnabled();

    fireEvent.change(textarea, {
      target: {
        value:
          "운영자가 수정한 Draft",
      },
    });

    expect(textarea).toHaveValue(
      "운영자가 수정한 Draft",
    );
  });

  it("승인 대기 상태로 변경할 수 있다", () => {
    render(
      <DraftPanel
        draft={{
          text: "검토할 Draft",
          status: "DRAFT",
          provenance: "AI",
        }}
        holdRequired={false}
        evidenceCount={1}
      />,
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: "승인 대기",
      }),
    );

    expect(
      screen.getByText(
        "승인 대기",
        {
          selector: ".badge",
        },
      ),
    ).toBeInTheDocument();
  });

  it("HIGH risk HOLD에서는 승인 대기를 허용하지 않는다", () => {
    render(
      <DraftPanel
        draft={{
          text: "고위험 Draft",
          status: "HOLD",
          provenance: "AI",
        }}
        holdRequired
        evidenceCount={1}
      />,
    );

    expect(
      screen.getByRole("button", {
        name: "승인 대기",
      }),
    ).toBeDisabled();

    expect(
      screen.getByText(
        "수동 검토 필요",
      ),
    ).toBeInTheDocument();
  });

  it("citation이 0건이면 근거 부족으로 처리한다", () => {
    render(
      <DraftPanel
        draft={{
          text: "",
          status:
            "INSUFFICIENT_EVIDENCE",
        }}
        holdRequired
        evidenceCount={0}
      />,
    );

    expect(
      screen.getAllByText(
        "근거 부족",
      ).length,
    ).toBeGreaterThan(0);

    expect(
      screen.getByRole("textbox", {
        name: /Draft 내용/i,
      }),
    ).toBeDisabled();

    expect(
      screen.getByRole("button", {
        name: "승인 대기",
      }),
    ).toBeDisabled();
  });

  it("REJECTED 상태와 비활성 이유를 명확히 표시한다", () => {
    render(
      <DraftPanel
        draft={{
          text: "거절된 합성 Draft",
          status: "REJECTED",
        }}
        holdRequired
        evidenceCount={1}
      />,
    );

    expect(
      screen.getByText("거절", {
        selector: ".badge",
      }),
    ).toBeInTheDocument();

    const textarea = screen.getByRole("textbox", {
      name: /Draft 내용/i,
    });
    expect(textarea).toBeDisabled();
    expect(textarea).toHaveAccessibleDescription(
      /거절된 초안이므로 수정하거나 승인 대기를 요청할 수 없습니다/,
    );
    expect(
      screen.getByRole("button", {
        name: "승인 대기",
      }),
    ).toBeDisabled();
  });

  it("실제 고객 전송 버튼이 없다", () => {
    render(
      <DraftPanel
        draft={{
          text: "Draft",
          status: "DRAFT",
        }}
        holdRequired={false}
        evidenceCount={1}
      />,
    );

    expect(
      screen.queryByRole("button", {
        name: /전송|발송|send/i,
      }),
    ).not.toBeInTheDocument();

    expect(
      screen.getByText(
        /실제 고객 전송 기능이나 Provider write 요청이 없습니다/,
      ),
    ).toBeInTheDocument();
  });
});