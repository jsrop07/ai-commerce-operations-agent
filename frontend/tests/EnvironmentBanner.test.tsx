import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "../src/app/App";
import EnvironmentBanner from "../src/components/EnvironmentBanner";

const forbiddenExternalWriteCtas = [
  "재고 수정", "재고 동기화 실행", "주문 취소", "환불", "가격 변경", "결제", "정산", "고객 답변 실제 전송",
];

describe("EnvironmentBanner", () => {
  it("renders DEMO with icon and text", () => {
    render(<EnvironmentBanner variant="DEMO" />);
    expect(screen.getByRole("banner", { name: "Demo 환경" })).toHaveTextContent("◆");
    expect(
      screen.getByText(/Demo 환경.*합성 데이터/),
    ).toBeInTheDocument();
  });
  it("renders LOCAL_EVAL with private evaluation guidance", () => {
  render(
    <EnvironmentBanner variant="LOCAL_EVAL" />,
  );

  expect(
    screen.getByRole("banner", {
      name: "Local Evaluation 환경",
    }),
  ).toHaveTextContent(
    "비공개 actual-scale 평가",
  );

  expect(
    screen.getByText(
      /PRIVATE_ACTUAL_EVAL 집계 결과/,
    ),
  ).toBeInTheDocument();
});
it("query environment=local-eval selects LOCAL_EVAL", () => {
  window.history.replaceState(
    {},
    "",
    "/insights?environment=local-eval",
  );

  render(<App />);

  expect(
    screen.getByRole("banner", {
      name: "Local Evaluation 환경",
    }),
  ).toBeInTheDocument();
  expect(
    screen.getByText(/로컬 평가 데이터 · 최근 확인/),
  ).toBeInTheDocument();

  expect(
    screen.queryByText(/합성 데이터 · 최근 확인/),
  ).not.toBeInTheDocument();
});
  it("renders PRODUCTION_READ with icon and text", () => {
    render(<EnvironmentBanner variant="PRODUCTION_READ" />);
    expect(screen.getByRole("banner", { name: "Production Read-Only 환경" })).toHaveTextContent("🔒");
    expect(
      screen.getByText(/Production Read-Only 환경.*실제 운영 데이터.*읽기 전용/),
    ).toBeInTheDocument();
  });

  it.each(routesForSafety())("contains no external write CTA on $path", (path) => {
    window.history.replaceState({}, "", path);
    render(<App environment="PRODUCTION_READ" />);
    const buttonLabels = screen.queryAllByRole("button").map((button) => button.textContent?.trim() ?? "");
    for (const forbidden of forbiddenExternalWriteCtas) {
      expect(buttonLabels.some((label) => label === forbidden)).toBe(false);
    }
  });
});

function routesForSafety() {
  return ["/", "/inventory", "/orders", "/inquiries", "/schedule", "/insights", "/settings"];
}
