import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import PolicyExplanation from "../src/features/reservations/PolicyExplanation";
import { explanationWarning } from "../src/features/reservations/PolicyExplanation";

const request = vi.hoisted(() => vi.fn());
vi.mock("../src/api/explanations", () => ({ getPolicyExplanation: request }));

const answer = {
  status: "ANSWER", conclusion: "검수 후 출고합니다.", used_facts: ["입고와 검수 완료"],
  used_numeric_facts: [{ field: "required_qty", value: 0, unit: "count" }],
  citations: [{ source_id: "policy_shipping_demo", version: "v2" }], next_check: "입고 상태 확인",
  model_used: true, data_mode: "SYNTHETIC_DEMO", request_id: "req_secret_internal", warnings: [],
  c04_lookup: [{ source_id: "policy_shipping_demo", version: "v2", chunk_id: "backend-exact-key" }],
} as const;
const envelope = (data: unknown) => ({ data });
const view = (id = "A", name = "상품 A") => <PolicyExplanation key={id} targetId={id} productName={name} />;

describe("reservation policy explanation (component mock)", () => {
  beforeEach(() => request.mockReset());
  afterEach(() => vi.unstubAllGlobals());

  it("keeps C24 quota and disabled-model warnings distinct from general HOLD", async () => {
    expect(explanationWarning("C24_QUOTA_EXCEEDED")).toContain("사용 한도");
    expect(explanationWarning("C24_QUOTA_UNCONFIGURED")).toContain("모델 호출이 현재 중지");
    request.mockResolvedValue(envelope({ ...answer, status: "HOLD", model_used: false,
      used_facts: [], used_numeric_facts: [], citations: [], c04_lookup: [],
      warnings: ["C24_QUOTA_EXCEEDED"] }));
    render(view());
    fireEvent.click(screen.getByRole("button", { name: "정책 설명 보기" }));
    expect(await screen.findByText(/AI 모델 호출 상태를 확인/)).toBeInTheDocument();
    expect(screen.queryByText("현재 근거만으로 설명할 수 없습니다.")).not.toBeInTheDocument();
  });

  it("ANSWER presents facts, numeric fact, citation, next check and demo marker without request_id", async () => {
    request.mockResolvedValue(envelope(answer));
    render(view());
    fireEvent.click(screen.getByRole("button", { name: "정책 설명 보기" }));
    expect(await screen.findByText(answer.conclusion)).toBeInTheDocument();
    expect(screen.getByText(answer.used_facts[0])).toBeInTheDocument();
    expect(screen.getByText("required_qty: 0 count")).toBeInTheDocument();
    expect(screen.getByText(/policy_shipping_demo · v2/)).toBeInTheDocument();
    expect(screen.getByText(/다음 확인: 입고 상태 확인/)).toBeInTheDocument();
    expect(screen.getByText(/예시 데이터/)).toBeInTheDocument();
    expect(screen.queryByText(/req_secret_internal/)).not.toBeInTheDocument();
  });

  it("pre-HOLD shows reason without AI answer and retains surrounding data", async () => {
    request.mockResolvedValue(envelope({ ...answer, status: "HOLD", model_used: false,
      used_facts: [], used_numeric_facts: [], citations: [], c04_lookup: [],
      warnings: ["UNSUPPORTED_CLAIM"] }));
    render(<><p>기존 예약 수량: 미확인</p>{view()}</>);
    fireEvent.click(screen.getByRole("button", { name: "정책 설명 보기" }));
    expect(await screen.findByText("현재 지원하지 않는 분석입니다.")).toBeInTheDocument();
    expect(screen.getByText("기존 예약 수량: 미확인")).toBeInTheDocument();
    expect(screen.queryByText(answer.conclusion)).not.toBeInTheDocument();
    expect(screen.queryByText(/AI 분석 결과|AI가 답변/)).not.toBeInTheDocument();
  });

  it("failure leaves existing quantity and only explicit retry makes another request", async () => {
    request.mockRejectedValueOnce(new Error("timeout")).mockResolvedValueOnce(envelope(answer));
    render(<><p>기존 확보 수량: 미확인</p>{view()}</>);
    fireEvent.click(screen.getByRole("button", { name: "정책 설명 보기" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("설명을 불러오지 못했습니다");
    expect(request).toHaveBeenCalledTimes(1);
    expect(screen.getByText("기존 확보 수량: 미확인")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "정책 설명 다시 확인" }));
    expect(await screen.findByText(answer.conclusion)).toBeInTheDocument();
    expect(request).toHaveBeenCalledTimes(2);
  });

  it("pending click is deduplicated and button exposes disabled loading state", async () => {
    let resolveRequest!: (value: unknown) => void;
    request.mockReturnValue(new Promise((resolve) => { resolveRequest = resolve; }));
    render(view());
    const button = screen.getByRole("button", { name: "정책 설명 보기" });
    fireEvent.click(button);
    const loading = screen.getByRole("button", { name: "설명 생성 중" });
    expect(loading).toBeDisabled();
    fireEvent.click(loading);
    expect(request).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("status")).toHaveTextContent("설명 생성 중입니다");
    await act(async () => { resolveRequest(envelope(answer)); });
  });

  it("target change clears A explanation before B is requested", async () => {
    request.mockResolvedValueOnce(envelope(answer)).mockResolvedValueOnce(envelope({ ...answer, conclusion: "B 정책" }));
    const { rerender } = render(view("A", "상품 A"));
    fireEvent.click(screen.getByRole("button", { name: "정책 설명 보기" }));
    expect(await screen.findByText(answer.conclusion)).toBeInTheDocument();
    rerender(view("B", "상품 B"));
    expect(screen.queryByText(answer.conclusion)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "정책 설명 보기" }));
    expect(await screen.findByText("B 정책")).toBeInTheDocument();
    expect(request).toHaveBeenCalledTimes(2);
  });

  it("late A response cannot overwrite B after target change", async () => {
    request.mockImplementationOnce(() => new Promise((resolve) => {
      setTimeout(() => resolve(envelope(answer)), 30);
    })).mockResolvedValueOnce(envelope({ ...answer, conclusion: "B 정책" }));
    const { rerender } = render(view("A", "상품 A"));
    fireEvent.click(screen.getByRole("button", { name: "정책 설명 보기" }));
    rerender(view("B", "상품 B"));
    fireEvent.click(screen.getByRole("button", { name: "정책 설명 보기" }));
    expect(await screen.findByText("B 정책")).toBeInTheDocument();
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(screen.getByText("B 정책")).toBeInTheDocument();
    expect(screen.queryByText(answer.conclusion)).not.toBeInTheDocument();
  });

  it("uses exact backend lookup and drawer restores trigger focus", async () => {
    request.mockResolvedValue(envelope(answer));
    const fetcher = vi.fn().mockResolvedValue(new Response("{}", { status: 404 }));
    vi.stubGlobal("fetch", fetcher);
    render(view());
    fireEvent.click(screen.getByRole("button", { name: "정책 설명 보기" }));
    const trigger = await screen.findByRole("button", { name: "원문 근거 열기" });
    trigger.focus();
    fireEvent.click(trigger);
    await waitFor(() => expect(fetcher).toHaveBeenCalledWith(
      expect.stringContaining("chunk_id=backend-exact-key"), expect.anything()));
    expect(await screen.findByRole("alert")).toHaveTextContent("version/chunk");
    fireEvent.click(screen.getByRole("button", { name: "판단 근거 패널 닫기" }));
    await waitFor(() => expect(trigger).toHaveFocus());
  });

  it("missing lookup disables source opening without synthesized key", async () => {
    request.mockResolvedValue(envelope({ ...answer, c04_lookup: [] }));
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    render(view());
    fireEvent.click(screen.getByRole("button", { name: "정책 설명 보기" }));
    expect(await screen.findByText("원문 연결 없음")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "원문 근거 열기" })).toBeDisabled();
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("keeps distinct backend reasons including C02 source missing", () => {
    expect(explanationWarning("CLAIM_SUPPORT_INSUFFICIENT:POLICY")).toContain("근거");
    expect(explanationWarning("NOT_SUPPORTED_C02_RUNTIME_SOURCE_MISSING")).toContain("예약 집계 자료");
    expect(explanationWarning("STALE_EVIDENCE")).toContain("오래되어");
  });
});
