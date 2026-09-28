import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import EvidenceDrawer from "../src/components/EvidenceDrawer";
import { insights } from "../src/mocks/fixtures";

describe("EvidenceDrawer", () => {
  it("닫힌 상태에서는 렌더링하지 않는다", () => {
    render(
      <EvidenceDrawer
        open={false}
        insight={insights[0]}
        onClose={() => {}}
      />
    );

    expect(
      screen.queryByRole("dialog", { name: "예약 재고 부족" })
    ).not.toBeInTheDocument();
  });

  it("원천 근거를 표시한다", () => {
    render(
      <EvidenceDrawer
        open
        insight={insights[0]}
        onClose={() => {}}
      />
    );

    expect(screen.getByText("ord_demo_002")).toBeInTheDocument();
    expect(screen.getByText("sku_demo_001")).toBeInTheDocument();
    expect(screen.getByText("주문")).toBeInTheDocument();
    expect(screen.getByText("재고 스냅샷")).toBeInTheDocument();
  });

  it("계산 근거를 표시한다", () => {
    render(
      <EvidenceDrawer
        open
        insight={insights[0]}
        onClose={() => {}}
      />
    );

    expect(screen.getByText("reserved")).toBeInTheDocument();
    expect(screen.getByText("available")).toBeInTheDocument();
    expect(screen.getByText("confirmed_incoming")).toBeInTheDocument();
    expect(screen.getByText("shortage")).toBeInTheDocument();
  });

  it("계산식이 없으면 안내 문구를 표시한다", () => {
    render(
      <EvidenceDrawer
        open
        insight={insights[1]}
        onClose={() => {}}
      />
    );

    expect(
      screen.getByText("별도의 수치 계산식이 없는 판단입니다.")
    ).toBeInTheDocument();
  });

  it("model_run_id가 null이면 provenance를 규칙으로 단정하지 않는다", () => {
    render(
      <EvidenceDrawer
        open
        insight={insights[0]}
        onClose={() => {}}
      />
    );

    expect(screen.getByText("현재 계약으로 확인 불가")).toBeInTheDocument();
    expect(
      screen.getByText(/현재 계약만으로 판단 출처를 확정할 수 없습니다/)
    ).toBeInTheDocument();
    expect(screen.queryByText("규칙 기반 판단")).not.toBeInTheDocument();
    expect(screen.queryByText("AI 모델 기반 판단")).not.toBeInTheDocument();
  });

  it("계약에 없는 model/prompt/index 정보를 임의 생성하지 않는다", () => {
    render(
      <EvidenceDrawer
        open
        insight={insights[0]}
        onClose={() => {}}
      />
    );

    expect(screen.getByText("제공되지 않음")).toBeInTheDocument();
    expect(
      screen.getAllByText("현재 계약에서 제공되지 않음")
    ).toHaveLength(3);
    expect(screen.getByText("reservation-risk-v1")).toBeInTheDocument();
  });
  it("닫기 버튼으로 닫을 수 있다", () => {
    const onClose = vi.fn();

    render(
      <EvidenceDrawer
        open
        insight={insights[0]}
        onClose={onClose}
      />
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: "판단 근거 패널 닫기",
      })
    );

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("배경을 클릭하면 닫힌다", () => {
    const onClose = vi.fn();

    render(
      <EvidenceDrawer
        open
        insight={insights[0]}
        onClose={onClose}
      />
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: "판단 근거 닫기",
      })
    );

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("Escape 키로 닫을 수 있다", () => {
    const onClose = vi.fn();

    render(
      <EvidenceDrawer
        open
        insight={insights[0]}
        onClose={onClose}
      />
    );

    fireEvent.keyDown(window, { key: "Escape" });

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("dialog 접근성 속성을 제공한다", () => {
    render(
      <EvidenceDrawer
        open
        insight={insights[0]}
        onClose={() => {}}
      />
    );

    const dialog = screen.getByRole("dialog", {
      name: "예약 재고 부족",
    });

    expect(dialog).toHaveAttribute("aria-modal", "true");
  });

  it("열릴 때 닫기 버튼으로 focus를 이동하고 닫힐 때 원래 focus를 복원한다", () => {
    const opener = document.createElement("button");
    document.body.appendChild(opener);
    opener.focus();

    const { unmount } = render(
      <EvidenceDrawer
        open
        insight={insights[0]}
        onClose={() => {}}
      />
    );

    expect(
      screen.getByRole("button", { name: "판단 근거 패널 닫기" })
    ).toHaveFocus();

    unmount();
    expect(opener).toHaveFocus();
    opener.remove();
  });

  it("Tab focus가 dialog 밖으로 벗어나지 않는다", () => {
    render(
      <EvidenceDrawer
        open
        insight={insights[0]}
        onClose={() => {}}
      />
    );

    const closeButton = screen.getByRole("button", {
      name: "판단 근거 패널 닫기",
    });

    fireEvent.keyDown(window, { key: "Tab" });
    expect(closeButton).toHaveFocus();

    fireEvent.keyDown(window, { key: "Tab", shiftKey: true });
    expect(closeButton).toHaveFocus();
  });

  it("원천 근거가 비어 있으면 명시적인 안내를 표시한다", () => {
    render(
      <EvidenceDrawer
        open
        insight={{ ...insights[0], evidence: [] }}
        onClose={() => {}}
      />
    );

    expect(
      screen.getByText("연결된 원천 근거가 없습니다.")
    ).toBeInTheDocument();
  });

  it("긴 source_id를 생략하거나 임의 변환하지 않는다", () => {
    const longSourceId = `source_${"x".repeat(256)}`;

    render(
      <EvidenceDrawer
        open
        insight={{
          ...insights[0],
          evidence: [
            { ...insights[0].evidence[0], source_id: longSourceId },
          ],
        }}
        onClose={() => {}}
      />
    );

    expect(screen.getByText(longSourceId)).toHaveClass("mono");
  });

  it("모델 결과의 계약 미제공 버전을 임의 생성하지 않는다", () => {
    render(
      <EvidenceDrawer
        open
        insight={{ ...insights[0], model_run_id: "model_run_demo_001" }}
        onClose={() => {}}
      />
    );

    expect(screen.getByText("AI 모델 기반 판단")).toBeInTheDocument();
    expect(screen.getByText("model_run_demo_001")).toBeInTheDocument();
    expect(
      screen.getAllByText("현재 계약에서 제공되지 않음")
    ).toHaveLength(3);
  });
});

// Synthetic response fixtures only: no live retrieval or LLM execution.
describe("C04 lookup drawer", () => {
  afterEach(() => vi.unstubAllGlobals());
  const key = { source_id: "product_demo_001", version: "v1" };
  const document = {
    ...key, title: "Synthetic board game", source_type: "PRODUCT",
    as_of: "2026-09-26T00:00:00Z", excerpt: "합성 보드게임: 2–4명, 한국어판.",
    excerpt_hash: "sha256:test", data_mode: "SYNTHETIC_DEMO", visibility: "DEMO_PUBLIC",
    chunk_id: "product_demo_001:v1:c04:0", stale: false, warnings: [],
    definitive_answer_allowed: false,
  };
  function response(data = document) {
    return new Response(JSON.stringify({ schema_version: "1.0", tenant_id: "demo",
      request_id: "req_test", trace_id: "tr_test", evidence_ids: [], warnings: [],
      as_of: data.as_of, data }), { status: 200 });
  }

  it("200 원문과 모든 metadata, 합성 및 확정 불가 안내를 표시한다", async () => {
    const fetcher = vi.fn().mockResolvedValue(response());
    vi.stubGlobal("fetch", fetcher);
    render(<EvidenceDrawer open insight={null} c04Key={key} onClose={() => {}} />);
    expect(await screen.findByTestId("c04-document")).toHaveTextContent(document.title);
    for (const field of ["source_type", "version", "as_of", "stale", "warnings", "data_mode", "visibility", "chunk_id", "definitive_answer_allowed"]) {
      expect(screen.getByText(field)).toBeInTheDocument();
    }
    expect(screen.getByText(document.excerpt)).toBeInTheDocument();
    expect(screen.getByText(/합성 Demo 근거/)).toBeInTheDocument();
    expect(screen.getByText(/이 자료 하나만으로 현재 상태를 확정할 수 없습니다/)).toBeInTheDocument();
    expect(fetcher).toHaveBeenCalledWith(expect.stringContaining("/api/v1/c04/lookup?source_id=product_demo_001&version=v1"), expect.objectContaining({ method: "GET", signal: expect.any(AbortSignal) }));
  });

  it("stale 경고와 서버 warnings를 표시한다", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({ ...document, stale: true, warnings: ["C04_STALE"] } as typeof document)));
    render(<EvidenceDrawer open insight={null} c04Key={key} onClose={() => {}} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("오래된 자료");
    expect(screen.getByText("C04_STALE")).toBeInTheDocument();
  });

  it.each([
    [403, "접근/안전 정책"], [404, "근거가 없거나 version/chunk"],
    [422, "잘못된 근거 조회 요청"], [503, "근거 registry"],
  ])("HTTP %s를 성공 문서나 Mock으로 표시하지 않는다", async (status, message) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("{}", { status: Number(status) })));
    render(<EvidenceDrawer open insight={insights[0]} c04Key={key} onClose={() => {}} />);
    expect(await screen.findByRole("alert")).toHaveTextContent(String(message));
    expect(screen.queryByTestId("c04-document")).not.toBeInTheDocument();
    expect(screen.queryByText("ord_demo_002")).not.toBeInTheDocument();
  });

  it("대상 전환 시 이전 응답 역전과 닫기 후 응답을 무시한다", async () => {
    const resolves: Array<(value: Response) => void> = [];
    const fetcher = vi.fn(() => new Promise<Response>((resolve) => resolves.push(resolve)));
    vi.stubGlobal("fetch", fetcher);
    const { rerender } = render(<EvidenceDrawer open insight={null} c04Key={key} onClose={() => {}} />);
    const nextKey = { source_id: "product_demo_002", version: "v2", chunk_id: "provided-chunk" };
    rerender(<EvidenceDrawer open insight={null} c04Key={nextKey} onClose={() => {}} />);
    await act(async () => resolves[1](response({ ...document, ...nextKey, title: "Second document" })));
    expect(screen.getByText("Second document")).toBeInTheDocument();
    await act(async () => resolves[0](response()));
    expect(screen.queryByText(document.title)).not.toBeInTheDocument();
    expect(screen.getByText("Second document")).toBeInTheDocument();
    rerender(<EvidenceDrawer open insight={null} c04Key={key} onClose={() => {}} />);
    expect(screen.queryByText("Second document")).not.toBeInTheDocument();
    rerender(<EvidenceDrawer open={false} insight={null} c04Key={key} onClose={() => {}} />);
    await act(async () => resolves[2](response()));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    rerender(<EvidenceDrawer open insight={null} c04Key={key} onClose={() => {}} />);
    expect(screen.queryByTestId("c04-document")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("불러오는 중");
    expect(fetcher.mock.calls[1]).toBeDefined();
  });

  it("C04 로딩/성공에서도 focus trap, Esc와 focus 복귀를 유지한다", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response()));
    const onClose = vi.fn();
    const trigger = window.document.createElement("button");
    window.document.body.append(trigger);
    trigger.focus();
    const { rerender } = render(<EvidenceDrawer open insight={null} c04Key={key} onClose={onClose} />);
    const close = screen.getByRole("button", { name: "판단 근거 패널 닫기" });
    expect(close).toHaveFocus();
    await screen.findByTestId("c04-document");
    fireEvent.keyDown(window, { key: "Tab" });
    expect(close).toHaveFocus();
    fireEvent.keyDown(window, { key: "Tab", shiftKey: true });
    expect(close).toHaveFocus();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
    fireEvent.click(close);
    expect(onClose).toHaveBeenCalledTimes(2);
    rerender(<EvidenceDrawer open={false} insight={null} c04Key={key} onClose={onClose} />);
    await waitFor(() => expect(trigger).toHaveFocus());
    trigger.remove();
  });
});
