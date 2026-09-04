import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import SystemState from "../src/components/SystemStates";
import { systemStateFixtures } from "../src/mocks/fixtures/systemStates";

describe("SystemStates", () => {
  it("loading 상태를 표시한다", () => {
    render(<SystemState state="loading" />);

    expect(
      screen.getByText(systemStateFixtures.loading.title)
    ).toBeInTheDocument();

    expect(
      screen.getByText(systemStateFixtures.loading.description)
    ).toBeInTheDocument();
  });

  it("empty 상태를 표시한다", () => {
    render(<SystemState state="empty" />);

    expect(
      screen.getByText(systemStateFixtures.empty.title)
    ).toBeInTheDocument();

    expect(
      screen.getByText(systemStateFixtures.empty.description)
    ).toBeInTheDocument();
  });

  it("stale 상태를 표시한다", () => {
    render(<SystemState state="stale" />);

    expect(
      screen.getByText(systemStateFixtures.stale.title)
    ).toBeInTheDocument();

    expect(
      screen.getByText(systemStateFixtures.stale.description)
    ).toBeInTheDocument();
  });

  it("denied 상태를 표시한다", () => {
    render(<SystemState state="denied" />);

    expect(
      screen.getByText(systemStateFixtures.denied.title)
    ).toBeInTheDocument();

    expect(
      screen.getByText(systemStateFixtures.denied.description)
    ).toBeInTheDocument();
  });

  it("denied 상태는 일반 오류가 아니라 안전 정책 사유를 표시한다", () => {
    render(<SystemState state="denied" />);

    expect(
      screen.getByText(/안전 정책으로 실행할 수 없습니다/)
    ).toBeInTheDocument();

    expect(
      screen.getByText(/외부 시스템 변경이 차단/)
    ).toBeInTheDocument();

    expect(
      screen.queryByText("오류가 발생했습니다")
    ).not.toBeInTheDocument();
  });

  it("stale 상태는 직접 검토 필요성을 표시한다", () => {
    render(<SystemState state="stale" />);

    expect(
      screen.getByText(/직접 검토하세요/)
    ).toBeInTheDocument();
  });

  it("stale 상태의 다시 확인 행동을 실행한다", () => {
    const onAction = vi.fn();

    render(
      <SystemState
        state="stale"
        onAction={onAction}
      />
    );

    fireEvent.click(
      screen.getByRole("button", { name: "다시 확인" })
    );

    expect(onAction).toHaveBeenCalledTimes(1);
  });

  it("stale에 action handler가 없으면 동작 버튼을 노출하지 않는다", () => {
    render(<SystemState state="stale" />);

    expect(
      screen.queryByRole("button", { name: "다시 확인" })
    ).not.toBeInTheDocument();
  });

  it("사용자 지정 제목과 설명을 표시할 수 있다", () => {
    render(
      <SystemState
        state="empty"
        title="검색 결과가 없습니다"
        description="다른 조건으로 다시 확인해주세요."
      />
    );

    expect(
      screen.getByText("검색 결과가 없습니다")
    ).toBeInTheDocument();

    expect(
      screen.getByText("다른 조건으로 다시 확인해주세요.")
    ).toBeInTheDocument();
  });

  it("loading 상태는 status role을 제공한다", () => {
    render(<SystemState state="loading" />);

    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("상태 region을 제목으로 식별할 수 있다", () => {
    render(<SystemState state="denied" />);

    expect(
      screen.getByRole("region", {
        name: systemStateFixtures.denied.title,
      })
    ).toBeInTheDocument();
  });

  it("네 가지 상태가 색상 없이도 텍스트로 구분된다", () => {
    const { rerender } = render(
      <SystemState state="loading" />
    );

    expect(
      screen.getByText(/데이터를 불러오는 중/)
    ).toBeInTheDocument();

    rerender(<SystemState state="empty" />);
    expect(
      screen.getByText(/표시할 데이터가 없습니다/)
    ).toBeInTheDocument();

    rerender(<SystemState state="stale" />);
    expect(
      screen.getByText(/정보가 오래되었습니다/)
    ).toBeInTheDocument();

    rerender(<SystemState state="denied" />);
    expect(
      screen.getByText(/안전 정책으로 실행할 수 없습니다/)
    ).toBeInTheDocument();
  });
});
