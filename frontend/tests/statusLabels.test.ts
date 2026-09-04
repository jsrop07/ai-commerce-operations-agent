import { describe, expect, it } from "vitest";
import {
  getProviderFailureReasonLabel,
  getProviderLabel,
} from "../src/components/statusLabels";

describe("Day 4 degraded labels", () => {
  it("TIMEOUT enum을 운영자 문구로 변환한다", () => {
    expect(getProviderFailureReasonLabel("TIMEOUT")).toBe("응답 시간 초과");
  });

  it("unknown provider와 failure reason을 내부 값 그대로 노출하지 않는다", () => {
    expect(getProviderLabel("FUTURE_PROVIDER")).toBe("알 수 없는 연동사");
    expect(getProviderFailureReasonLabel("FUTURE_REASON")).toBe(
      "확인되지 않은 연동 오류",
    );
  });
});