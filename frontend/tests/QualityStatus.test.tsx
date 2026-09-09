import {
  cleanup,
  render,
  screen,
} from "@testing-library/react";
import {
  afterEach,
  describe,
  expect,
  it,
} from "vitest";

import QualityStatus from "../src/features/integrations/QualityStatus";

afterEach(() => {
  cleanup();
});

describe("QualityStatus", () => {
  it("STALE 상태라도 confirmed_for_total=false이면 확정 합계에서 제외한다", () => {
    const { container } = render(
      <QualityStatus
        status="STALE"
        provider="CAFE24"
        confirmedForTotal={false}
      />,
    );

    expect(
      screen.getByText("확정 재고 합계에서 제외"),
    ).toBeInTheDocument();

    expect(
      container.querySelector(
        ".quality-status-usage",
      ),
    ).toHaveAttribute(
      "data-usable-for-confirmed-inventory",
      "false",
    );
  });

  it("STALE 상태라도 Backend가 confirmed_for_total=true를 주면 그대로 표시한다", () => {
    const { container } = render(
      <QualityStatus
        status="STALE"
        provider="CAFE24"
        confirmedForTotal={true}
      />,
    );

    expect(
      screen.getByText("확정 재고 합계에 포함"),
    ).toBeInTheDocument();

    expect(
      container.querySelector(
        ".quality-status-usage",
      ),
    ).toHaveAttribute(
      "data-usable-for-confirmed-inventory",
      "true",
    );
  });

  it("confirmed_for_total이 없으면 false로 추정하지 않는다", () => {
    const { container } = render(
      <QualityStatus
        status="UNMAPPED"
        provider="TOSS_POS"
      />,
    );

    expect(
      screen.getByText(
        "확정 재고 합계 포함 여부 미제공",
      ),
    ).toBeInTheDocument();

    expect(
      container.querySelector(
        ".quality-status-usage",
      ),
    ).toHaveAttribute(
      "data-usable-for-confirmed-inventory",
      "unknown",
    );
  });

  it("SOURCE_QUALITY_BLOCKED와 confirmed_for_total=false를 표시한다", () => {
    render(
      <QualityStatus
        status="SOURCE_QUALITY_BLOCKED"
        provider="ECOUNT"
        confirmedForTotal={false}
      />,
    );

    expect(
      screen.getByText("ECOUNT"),
    ).toBeInTheDocument();

    expect(
      screen.getByText("확정 재고 합계에서 제외"),
    ).toBeInTheDocument();
  });
});