import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../src/app/App";
import { routes } from "../src/app/routes";
import InsightsPage from "../src/app/pages/InsightsPage";

describe("routes", () => {
  it.each(routes)("renders $path", ({ path, label }) => {
    window.history.replaceState({}, "", path);
    render(<App />);
    expect(screen.getByRole("heading", { level: 1, name: label })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: new RegExp(label.split(" / ")[0]) })).toHaveAttribute("aria-current", "page");
  });

  it("moves between routes with Navigation", () => {
    render(<App />);
    fireEvent.click(screen.getByRole("link", { name: "주문 & 매출" }));
    expect(window.location.pathname).toBe("/orders");
    expect(screen.getByRole("heading", { level: 1, name: "주문 & 매출" })).toBeInTheDocument();
  });
});

describe("InsightsPage actual backend", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_USE_REAL_BACKEND", "true");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  const envelope = {
    schema_version: "1.0",
    tenant_id: "tenant_test",
    request_id: "request_test",
    trace_id: "trace_test",
    evidence_ids: [],
    warnings: [],
    as_of: "2026-09-26T00:00:00Z",
  };

  const key = { source_id: "source_exact", version: "v3", chunk_id: "c04:full:0" };
  const citation = {
    rank: 1, score: 12.80915432, source_type: "PRODUCT", source_id: "semantic_source",
    title: "DEV 상품 근거", version: "semantic-v9", semantic_chunk_id: "semantic:3",
    semantic_excerpt: "검색 범위 발췌", semantic_excerpt_hash: "sha256:semantic", as_of: null, c04_lookup: key,
  };
  const searchData = {
    method: "BM25", selection_status: "PROVISIONAL_DEV_SELECTION", data_mode: "SYNTHETIC_DEMO",
    actual_retrieval_executed: true, index_version: "runtime-v3", result_status: "RESULTS",
    citations: [citation], answer_status: "HOLD", human_review_required: true,
    human_review_reason: ["STALE_EVIDENCE"], warnings: ["STALE_EVIDENCE"], required_lookup: [],
  };
  const summaryData = {
    selection: { method: "bm25", status: "PROVISIONAL_DEV_SELECTION" }, data_mode: "SYNTHETIC_DEMO",
    query_count: 24, execution_count: 72, error_count: 0, actual_scale_retrieval_validation_required: true,
    methods: [{ method: "bm25", executed: true, execution_status: "EXECUTED", source_status: null,
      mean_recall_at_5: 1, mean_mrr_at_5: 0.9375, full_evidence_numerator: 16, full_evidence_denominator: 16,
      mean_latency_ms: 999, p95_latency_ms: 1234, metric_status: {} }],
  };
  function setupRetrieval(data: unknown = searchData, status = 200, summary: unknown = summaryData, summaryStatus = 200) {
    const fetcher = vi.fn(async (url: string) => {
      let payload: unknown = [];
      let httpStatus = 200;
      if (url.endsWith("/retrieval/search")) { payload = data; httpStatus = status; }
      if (url.endsWith("/retrieval/summary")) { payload = summary; httpStatus = summaryStatus; }
      if (url.includes("/c04/lookup?")) payload = {
        ...key, title: "C04 원문 제목", source_type: "PRODUCT", as_of: null, excerpt: "원문 전체 범위 발췌",
        excerpt_hash: "sha256:full", data_mode: "SYNTHETIC_DEMO", visibility: "DEMO_PUBLIC",
        stale: true, warnings: ["STALE_EVIDENCE"], definitive_answer_allowed: false,
      };
      return new Response(JSON.stringify({ ...envelope, ...(url.includes("/c04/lookup?") ? { as_of: null } : {}), data: payload }), { status: httpStatus });
    });
    vi.stubGlobal("fetch", fetcher);
    return fetcher;
  }
  async function runSearch() {
    render(<InsightsPage />);
    await screen.findByTestId("system-state-empty");
    fireEvent.change(screen.getByRole("textbox", { name: "검색 질문" }), { target: { value: "상품 근거 질문" } });
    fireEvent.click(screen.getByRole("button", { name: "검색 실행" }));
  }

  it("BM25 citation과 원점수를 표시하고 정확한 C04 key로 기존 Drawer를 연다", async () => {
    const fetcher = setupRetrieval();
    await runSearch();
    const card = await screen.findByTestId("retrieval-citation");
    expect(card).toHaveTextContent("1. DEV 상품 근거");
    expect(card).toHaveTextContent("검색 점수 (retriever score): 12.80915432");
    expect(card).not.toHaveTextContent("%");
    expect(card).toHaveTextContent("PRODUCT");
    expect(card).toHaveTextContent("검색 범위 발췌");
    expect(card).toHaveTextContent("버전: semantic-v9");
    expect(card).toHaveTextContent("기준 시각 (as_of): 미제공");
    expect(screen.getByTestId("retrieval-result")).toHaveTextContent("request_id: request_test · trace_id: trace_test");
    expect(screen.getByText(/고정 검색 조건/)).toHaveTextContent("method=BM25 · top_k=5");
    expect(screen.getByText(/서로 다른 범위일 수 있습니다/)).toBeInTheDocument();
    expect(fetcher).toHaveBeenCalledWith(expect.stringContaining("/retrieval/search"), expect.objectContaining({
      method: "POST", body: JSON.stringify({ query: "상품 근거 질문", top_k: 5, method: "BM25" }),
    }));
    fireEvent.click(within(card).getByRole("button", { name: "원문 근거 열기" }));
    expect(await screen.findByTestId("c04-document")).toHaveTextContent("원문 전체 범위 발췌");
    expect(screen.getByRole("dialog", { name: "C04 원문 근거" })).toBeInTheDocument();
    expect(fetcher).toHaveBeenCalledWith(expect.stringContaining(`/c04/lookup?${new URLSearchParams(key)}`), expect.objectContaining({ method: "GET" }));
    expect(fetcher.mock.calls.some(([url]) => url.includes("/c04/lookup?") && url.includes("semantic_source"))).toBe(false);
  });

  it.each([null, undefined])("c04_lookup %s이면 원문 버튼을 비활성화한다", async (lookup) => {
    setupRetrieval({ ...searchData, citations: [{ ...citation, c04_lookup: lookup }] });
    await runSearch();
    await screen.findByTestId("retrieval-citation");
    expect(screen.getByRole("button", { name: "원문 근거 열기" })).toBeDisabled();
  });

  it("ZERO_CITATIONS는 NO_SOURCE로 바꾸지 않고 검색 결과 0건을 표시한다", async () => {
    setupRetrieval({ ...searchData, citations: [], result_status: "ZERO_CITATIONS", answer_status: "INSUFFICIENT_EVIDENCE" });
    await runSearch();
    expect(await screen.findByText("검색 결과 0건 (ZERO_CITATIONS)")).toBeInTheDocument();
    expect(screen.queryByText(/NO_SOURCE/)).not.toBeInTheDocument();
    expect(screen.queryByTestId("retrieval-citation")).not.toBeInTheDocument();
  });

  it.each([[403, "민감/금지"], [422, "잘못된 검색"], [503, "사용할 수 없습니다"], [504, "시간이 초과"]])("HTTP %s는 성공 결과를 표시하지 않는다", async (status, message) => {
    setupRetrieval(searchData, Number(status));
    await runSearch();
    expect(await screen.findByRole("alert")).toHaveTextContent(String(message));
    expect(screen.queryByTestId("retrieval-result")).not.toBeInTheDocument();
  });

  it("citation이 있어도 HOLD / STALE_EVIDENCE와 실행 메타를 유지한다", async () => {
    setupRetrieval({ ...searchData, actual_retrieval_executed: false });
    await runSearch();
    const result = await screen.findByTestId("retrieval-result");
    for (const text of ["answer_status): HOLD", "human_review_required): true", "human_review_reason): STALE_EVIDENCE", "warnings): STALE_EVIDENCE", "index_version): runtime-v3", "actual_retrieval_executed): false"]) expect(result).toHaveTextContent(text);
  });

  it("summary는 Synthetic DEV 평가와 실제 운영 규모 검증 필요를 표시하고 과거 latency를 노출하지 않는다", async () => {
    setupRetrieval();
    render(<InsightsPage />);
    expect(await screen.findByText(/실제 운영 규모 검증 필요 ·/)).toBeInTheDocument();
    const summary = screen.getByRole("region", { name: "Synthetic DEV 평가" });
    for (const text of ["DEV 질문 24", "실행 72", "오류 0", "Recall@5 = 1.0", "MRR@5 = 0.9375", "Full evidence = 16/16", "actual_scale_retrieval_validation_required = true"]) expect(summary).toHaveTextContent(text);
    expect(summary).not.toHaveTextContent("999");
    expect(summary).not.toHaveTextContent("1234");
  });

  it.each([
    { ...searchData, citations: [{ ...citation, c04_lookup: { source_id: "invented" } }] },
    { ...searchData, citations: [{ ...citation, c04_lookup: { ...key, chunk_id: "" } }] },
    { ...searchData, citations: [{ ...citation, c04_lookup: { ...key, version: "../other" } }] },
    { ...searchData, citations: [{ ...citation, score: "0.99" }] },
    { ...searchData, actual_retrieval_executed: "true" },
    { ...searchData, result_status: "ZERO_CITATIONS" },
  ])("malformed 검색 응답은 fail closed", async (data) => {
    setupRetrieval(data);
    await runSearch();
    expect(await screen.findByRole("alert")).toHaveTextContent("응답 형식");
    expect(screen.queryByTestId("retrieval-result")).not.toBeInTheDocument();
  });

  it.each([503, 200])("summary 실패/malformed (%s)는 DEV 수치를 표시하지 않는다", async (status) => {
    setupRetrieval(searchData, 200, null, status);
    render(<InsightsPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("DEV 평가 조회 실패");
    expect(screen.queryByText(/DEV 질문 24/)).not.toBeInTheDocument();
  });

  it("summary 미측정 값은 0으로 바꾸지 않는다", async () => {
    setupRetrieval(searchData, 200, { ...summaryData, methods: [{ ...summaryData.methods[0],
      executed: false, execution_status: "NOT_EXECUTED", source_status: "NOT_EXECUTED",
      mean_recall_at_5: null, mean_mrr_at_5: null, full_evidence_numerator: null, full_evidence_denominator: null,
      metric_status: { mean_recall_at_5: "NOT_EXECUTED", mean_mrr_at_5: "UNMEASURED", full_evidence_cases: "HOLD", answerable_cases: "NOT_APPLICABLE" },
    }] });
    render(<InsightsPage />);
    expect(await screen.findByText(/Recall@5 = NOT_EXECUTED/)).toHaveTextContent("MRR@5 = UNMEASURED · Full evidence = HOLD/NOT_APPLICABLE");
  });

  it("summary metric_status 배열은 malformed로 처리한다", async () => {
    setupRetrieval(searchData, 200, { ...summaryData, methods: [{ ...summaryData.methods[0], metric_status: [] }] });
    render(<InsightsPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("DEV 평가 조회 실패");
    expect(screen.queryByText(/DEV 질문 24/)).not.toBeInTheDocument();
  });

  it("검색 전 안내와 검색 중 상태를 구분하고 응답 전 citation을 표시하지 않는다", async () => {
    const fetcher = setupRetrieval();
    render(<InsightsPage />);
    await screen.findByTestId("system-state-empty");
    await screen.findByText(/DEV 질문 24/);
    expect(screen.getByText("질문을 입력하고 검색을 실행하세요.")).toBeInTheDocument();
    let complete!: (response: Response) => void;
    fetcher.mockImplementationOnce(() => new Promise<Response>((resolve) => { complete = resolve; }));
    fireEvent.change(screen.getByRole("textbox", { name: "검색 질문" }), { target: { value: "합성 상품 근거" } });
    fireEvent.click(screen.getByRole("button", { name: "검색 실행" }));
    expect(screen.getByText("근거를 검색하는 중입니다.")).toHaveAttribute("role", "status");
    expect(screen.getByRole("button", { name: "검색 중…" })).toBeDisabled();
    expect(screen.queryByTestId("retrieval-citation")).not.toBeInTheDocument();
    complete(new Response(JSON.stringify({ ...envelope, data: searchData }), { status: 200 }));
    await screen.findByTestId("retrieval-citation");
    expect(screen.queryByText("근거를 검색하는 중입니다.")).not.toBeInTheDocument();
  });

  it("재검색 실패 시 이전 citation을 성공 결과로 남기지 않는다", async () => {
    const fetcher = setupRetrieval();
    await runSearch();
    await screen.findByTestId("retrieval-citation");
    fetcher.mockResolvedValueOnce(new Response("{}", { status: 503 }));
    fireEvent.click(screen.getByRole("button", { name: "검색 실행" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("검색 실패");
    expect(screen.queryByTestId("retrieval-result")).not.toBeInTheDocument();
  });

  it("HTTP 200 data=[] 응답은 loading 이후 정상 Empty를 표시한다", async () => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation(async () => new Response(
      JSON.stringify({ ...envelope, data: [] }), { status: 200 },
    )));

    render(<InsightsPage />);
    expect(screen.getByText("Insight를 불러오는 중입니다.")).toBeInTheDocument();
    expect(screen.queryByTestId("system-state-empty")).not.toBeInTheDocument();

    expect(await screen.findByTestId("system-state-empty")).toHaveTextContent(
      "현재 표시할 AI 인사이트가 없습니다",
    );
    expect(screen.getByTestId("system-state-empty")).toHaveTextContent("오류가 아닙니다.");
    expect(screen.queryByText("Insight를 불러오는 중입니다.")).not.toBeInTheDocument();
    expect(screen.queryByText("Backend Insight를 불러오지 못했습니다.")).not.toBeInTheDocument();
    expect(screen.queryByTestId("real-backend-insight")).not.toBeInTheDocument();
  });

  it("non-empty 응답은 기존 insight card와 계산을 표시한다", async () => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation(async () => new Response(
      JSON.stringify({ ...envelope, data: [{
        insight_id: "insight_test",
        type: "OFFLINE_SALE",
        severity: "LOW",
        confidence: 1,
        summary: "오프라인 판매가 예상 재고에 반영되었습니다.",
        calculation: { starting_inventory: 8, sold: 2, expected_inventory: 6 },
      }] }), { status: 200 },
    )));

    render(<InsightsPage />);
    const card = await screen.findByTestId("real-backend-insight");
    expect(card).toHaveTextContent("오프라인 판매가 예상 재고에 반영되었습니다.");
    expect(card).toHaveTextContent("Severity: LOW");
    expect(card).toHaveTextContent("Confidence: 1");
    expect(screen.getByTestId("insight-calculation")).toHaveTextContent(
      "시작 재고: 8 / 판매: 2 / 예상 재고: 6",
    );
    expect(screen.queryByTestId("system-state-empty")).not.toBeInTheDocument();
  });

  it.each(["fetch", "parser"])("%s 실패는 Empty 대신 error를 유지한다", async (failure) => {
    vi.stubGlobal("fetch", failure === "fetch"
      ? vi.fn().mockRejectedValue(new Error("Network failure"))
      : vi.fn().mockImplementation(async () => new Response(
        JSON.stringify({ ...envelope, data: null }), { status: 200 },
      )));

    render(<InsightsPage />);
    expect(await screen.findByText("Backend Insight를 불러오지 못했습니다.")).toBeInTheDocument();
    expect(screen.queryByTestId("system-state-empty")).not.toBeInTheDocument();
    expect(screen.queryByText("Insight를 불러오는 중입니다.")).not.toBeInTheDocument();
  });
});
