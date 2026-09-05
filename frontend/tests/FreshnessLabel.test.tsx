import {
  render,
  screen,
} from "@testing-library/react";
import { describe, expect, it } from "vitest";

import FreshnessLabel from "../src/components/FreshnessLabel";

describe("FreshnessLabel", () => {
  it("FRESH 상태와 source/as_of를 표시한다", () => {
    render(
      <FreshnessLabel
        freshness="FRESH"
        source="CAFE24"
        asOf="2026-09-02T06:30:00Z"
      />,
    );

    expect(
        screen.getByText(/최신/, {
            selector: ".badge",
        }),
    ).toBeInTheDocument();

    expect(
        screen.getByText(/CAFE24/), 
    ).toBeInTheDocument();

    expect(
      document.querySelector('time[datetime="2026-09-02T06:30:00Z"]'),
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        /현재 최신성 기준을 만족하는 데이터입니다/,
      ),
    ).toBeInTheDocument();
  });

  it("STALE은 확정 판단에 사용하지 않는다고 설명한다", () => {
    render(
      <FreshnessLabel
        freshness="STALE"
        source="ECOUNT"
        asOf="2026-09-02T05:43:00Z"
      />,
    );

    expect(
      screen.getByText(
        /최신성 기준을 초과한 데이터입니다/,
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        /확정 판단에 사용하지 않습니다/,
      ),
    ).toBeInTheDocument();
  });

  it("UNKNOWN은 FRESH나 재고 0으로 취급하지 않는다", () => {
    render(
      <FreshnessLabel
        freshness="UNKNOWN"
        source="TOSS_POS"
        asOf="2026-09-02T06:30:00Z"
      />,
    );

    expect(
      screen.getByText(
        /최신성 판단 정보가 없습니다/,
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        /재고 0으로 간주하지 않습니다/,
      ),
    ).toBeInTheDocument();
  });

  it("최신성 설명을 키보드로 접근 가능한 도움말로 제공한다", () => {
    render(
      <FreshnessLabel
        freshness="STALE"
        source="ECOUNT"
        asOf="2026-09-02T05:43:00Z"
      />,
    );

    const help = screen.getByLabelText(
      "최신성 도움말",
    );

    expect(help).toHaveAttribute(
      "tabindex",
      "0",
    );

    expect(help).toHaveAttribute(
      "title",
      expect.stringContaining(
        "최신성 기준을 초과",
      ),
    );

    expect(help).toHaveAccessibleDescription(
      /최신성 기준을 초과/,
    );
  });
});
