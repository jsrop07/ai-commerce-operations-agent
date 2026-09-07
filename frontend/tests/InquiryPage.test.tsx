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

import InquiriesPage from "../src/app/pages/InquiriesPage";

describe("InquiriesPage", () => {
  it("LOW 문의를 기본 선택하고 Draft 준비 상태를 보여준다", () => {
    render(<InquiriesPage />);

    expect(
      screen.getByText(
        "이 확장팩을 본판 없이 사용할 수 있는지 궁금합니다.",
      ),
    ).toBeInTheDocument();

    expect(
    screen.getByText("초안", {
        selector: ".badge",
    }),
    ).toBeInTheDocument();

    expect(
    screen.getByRole("textbox", {
        name: /Draft 내용/i,
    }),
    ).toBeEnabled();

    expect(
      screen.getByText(/Retrieval answer status:/),
    ).toHaveTextContent("DRAFT");

    expect(
    screen.getByText(
        /실제 고객 전송 기능이나 Provider write 요청이 없습니다/,
    ),
    ).toBeInTheDocument();
  });

  it("HIGH 문의 선택 시 Conversation과 Workbench가 함께 갱신된다", () => {
    render(<InquiriesPage />);

    const highInquiry =
      screen.getByRole("button", {
        name: /REFUND_REQUEST/i,
      });

    fireEvent.click(highInquiry);

    expect(
      screen.getByText(
        "주문 취소와 환불 처리를 요청합니다.",
      ),
    ).toBeInTheDocument();

    expect(
    screen.getByText(
        "수동 검토 필요",
    ),
    ).toBeInTheDocument();

    expect(
    screen.getByText("보류", {
        selector: ".badge",
    }),
    ).toBeInTheDocument();

    expect(
    screen.getByRole("button", {
        name: "승인 대기",
    }),
    ).toBeDisabled();

    expect(
      screen.getByText(/Retrieval answer status:/),
    ).toHaveTextContent("HOLD");

    expect(
      screen.getByText(
        /고위험 문의입니다/,
      ),
    ).toBeInTheDocument();
  });

  it("LOW confidence 문의는 risk가 LOW여도 HOLD 처리한다", () => {
    render(<InquiriesPage />);

    const productButtons =
      screen.getAllByRole("button", {
        name: /PRODUCT_INFO/i,
      });

    fireEvent.click(
      productButtons[
        productButtons.length - 1
      ],
    );

    expect(
      screen.getByText(
        /신뢰도가 낮아 추가 근거 확인이 필요합니다/,
      ),
    ).toBeInTheDocument();

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

  it("실제 고객 전송 CTA가 존재하지 않는다", () => {
    render(<InquiriesPage />);

    expect(
      screen.queryByRole("button", {
        name: /전송|발송|send/i,
      }),
    ).not.toBeInTheDocument();
  });

  it("문의 선택에 따라 Draft 상태도 함께 변경된다", () => {
    render(<InquiriesPage />);

    expect(
        screen.getByRole("textbox", {
        name: /Draft 내용/i,
        }),
    ).toBeEnabled();

    fireEvent.click(
        screen.getByRole("button", {
        name: /REFUND_REQUEST/i,
        }),
    );

    expect(
        screen.getByText(
        "수동 검토 필요",
        ),
    ).toBeInTheDocument();

    expect(
        screen.getByRole("button", {
        name: "승인 대기",
        }),
    ).toBeDisabled();
    });
});