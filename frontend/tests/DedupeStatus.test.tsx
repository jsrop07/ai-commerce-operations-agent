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

import DedupeStatus from "../src/features/integrations/DedupeStatus";

afterEach(() => {
  cleanup();
});

describe("DedupeStatus", () => {
  it("동일 이벤트 2회 수신 시 Effect 1회를 정상으로 표시한다", () => {
    render(
      <DedupeStatus
        eventId="evt_fe_day04_001"
        receivedCount={2}
        duplicateCount={1}
        appliedEffectCount={1}
      />,
    );

    expect(
      screen.getByText(
        "중복 이벤트가 재고에 추가 반영되지 않았습니다.",
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByTestId("dedupe-result"),
    ).toHaveClass("notice");
  });

  it("중복 이벤트가 Effect를 두 번 만들면 경고한다", () => {
    render(
      <DedupeStatus
        eventId="evt_fe_day04_001"
        receivedCount={2}
        duplicateCount={1}
        appliedEffectCount={2}
      />,
    );

    expect(
      screen.getByText(
        "중복 이벤트 처리 결과를 확인해야 합니다.",
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByTestId("dedupe-result"),
    ).toHaveClass("warning");
  });

  it("운영자가 처리 횟수를 확인할 수 있다", () => {
    render(
      <DedupeStatus
        eventId="evt_fe_day04_001"
        receivedCount={10}
        duplicateCount={9}
        appliedEffectCount={1}
      />,
    );

    expect(
      screen.getByText("evt_fe_day04_001"),
    ).toBeInTheDocument();

    expect(
      screen.getByText("10"),
    ).toBeInTheDocument();

    expect(
      screen.getByText("9"),
    ).toBeInTheDocument();
  });
});