import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ConfidenceBadge, FreshnessBadge, RiskLevelBadge } from "../src/components/StatusBadges";

describe("StatusBadges", () => {
  it("FRESH를 최신으로 표시한다", () => {
    render(<FreshnessBadge freshness="FRESH" />);

    expect(screen.getByText(/최신/)).toBeInTheDocument();
  });

  it("STALE을 오래됨으로 표시한다", () => {
    render(<FreshnessBadge freshness="STALE" />);

    expect(screen.getByText(/오래됨/)).toBeInTheDocument();
  });

  it("UNKNOWN을 확인 불가로 표시한다", () => {
    render(<FreshnessBadge freshness="UNKNOWN" />);

    expect(screen.getByText(/확인 불가/)).toBeInTheDocument();
  });

  it("freshness 누락값을 확인 불가로 처리한다", () => {
    render(<FreshnessBadge />);

    expect(screen.getByText(/확인 불가/)).toBeInTheDocument();
  });

  it("freshness null을 확인 불가로 처리한다", () => {
    render(<FreshnessBadge freshness={null} />);

    expect(screen.getByText(/확인 불가/)).toBeInTheDocument();
  });

  it("LOW를 낮음으로 표시한다", () => {
    render(<RiskLevelBadge risk="LOW" />);

    expect(screen.getByText(/낮음/)).toBeInTheDocument();
  });

  it("MEDIUM을 보통으로 표시한다", () => {
    render(<RiskLevelBadge risk="MEDIUM" />);

    expect(screen.getByText(/보통/)).toBeInTheDocument();
  });

  it("HIGH를 높음으로 표시한다", () => {
    render(<RiskLevelBadge risk="HIGH" />);

    expect(screen.getByText(/높음/)).toBeInTheDocument();
  });

  it("PROHIBITED를 실행 금지로 표시한다", () => {
    render(<RiskLevelBadge risk="PROHIBITED" />);

    expect(screen.getByText(/실행 금지/)).toBeInTheDocument();
  });

  it("risk 누락값을 위험도 확인 불가로 처리한다", () => {
    render(<RiskLevelBadge />);

    expect(screen.getByText(/위험도 확인 불가/)).toBeInTheDocument();
  });

  it("risk null을 위험도 확인 불가로 처리한다", () => {
    render(<RiskLevelBadge risk={null} />);

    expect(screen.getByText(/위험도 확인 불가/)).toBeInTheDocument();
  });

  it("색상 없이도 상태를 구분할 수 있는 텍스트가 존재한다", () => {
    render(
      <>
        <FreshnessBadge freshness="STALE" />
        <RiskLevelBadge risk="PROHIBITED" />
      </>
    );

    expect(screen.getByText(/오래됨/)).toBeInTheDocument();
    expect(screen.getByText(/실행 금지/)).toBeInTheDocument();
  });

  it("신뢰도를 퍼센트로 표시한다", () => {
    render(<ConfidenceBadge confidence={0.97} />);

    expect(screen.getByText(/신뢰도 97%/)).toBeInTheDocument();
    });

    it("중간 신뢰도를 텍스트로 표시한다", () => {
    render(<ConfidenceBadge confidence={0.7} />);

    expect(screen.getByText(/신뢰도 70%/)).toBeInTheDocument();
    });

    it("낮은 신뢰도도 텍스트로 표시한다", () => {
    render(<ConfidenceBadge confidence={0.4} />);

    expect(screen.getByText(/신뢰도 40%/)).toBeInTheDocument();
    });

    it("신뢰도 누락값을 확인 불가로 처리한다", () => {
    render(<ConfidenceBadge />);

    expect(screen.getByText(/신뢰도 확인 불가/)).toBeInTheDocument();
    });

    it("신뢰도 null과 NaN을 확인 불가로 처리한다", () => {
    const { rerender } = render(<ConfidenceBadge confidence={null} />);

    expect(screen.getByText(/신뢰도 확인 불가/)).toBeInTheDocument();

    rerender(<ConfidenceBadge confidence={Number.NaN} />);

    expect(screen.getByText(/신뢰도 확인 불가/)).toBeInTheDocument();
    });

    it("신뢰도가 범위를 벗어나도 0~100 사이로 표시한다", () => {
    const { rerender } = render(<ConfidenceBadge confidence={1.5} />);

    expect(screen.getByText(/신뢰도 100%/)).toBeInTheDocument();

    rerender(<ConfidenceBadge confidence={-0.5} />);

    expect(screen.getByText(/신뢰도 0%/)).toBeInTheDocument();
    });
});
