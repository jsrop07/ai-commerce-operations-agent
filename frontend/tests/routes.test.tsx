import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../src/app/App";
import { routes } from "../src/app/routes";
import InsightsPage from "../src/app/pages/InsightsPage";
import { parseActualRetrievalSummary } from "../src/api/day08";

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
  const actualSummaryData = {
    status: "COMPLETE_WITH_LIMITS",
    data_mode: "PRIVATE_ACTUAL_EVAL",
    validation_scope:
      "PRODUCT-only actual-scale mixed DEV24 retrieval baseline",
    experiment_id: "OPS-RAG-SCALE-01",
    experiment: "E08",
    task_id: "R07-PRE-AI-01",
    run_group: "OPS-RAG-SCALE-01 / E08",
    run_id: null,
    corpus_alias: "PRODUCT-SAFE-SNAPSHOT",
    question_set_alias: "R07-PRE-ACTUAL-DEV24",

    source_support: {
      PRODUCT: "SUPPORTED",
      POLICY: "MISSING",
      INVENTORY_SNAPSHOT: "BLOCKED",
      INCOMING_STOCK: "MISSING",
      C02: "BLOCKED",
    },

    counts: {
      document_count: 2167,
      chunk_count: 2167,
      question_count: 24,
      answerable_count: 24,
      hold_count: 0,
      review_completed_count: 24,
    },

    execution: {
      planned_count: 72,
      executed_count: 72,
      succeeded_count: 72,
      failed_count: 0,
      blocked_count: 0,
      not_run_count: 0,
    },

    methods: [
      {
        method: "BM25",
        execution_status: "SUCCEEDED",
        executed_count: 24,
        metric_status: "MEASURED",
        recall_at_5: 0.8333,
        mrr_at_5: 0.7917,
        full_evidence: {
          full_evidence_count: 20,
          full_evidence_denominator: 24,
        },
        latency: {
          kind: "SEARCH",
          unit: "ms",
          avg_ms: 27.84,
          warm_p95_ms: 38.96,
          http_round_trip: false,
        },
        preparation: {
          status: "NOT_APPLICABLE",
          model_load_seconds: null,
          document_embedding_seconds: null,
        },
      },
      {
        method: "DENSE",
        execution_status: "SUCCEEDED",
        executed_count: 24,
        metric_status: "MEASURED",
        recall_at_5: 0.4167,
        mrr_at_5: 0.2861,
        full_evidence: {
          full_evidence_count: 10,
          full_evidence_denominator: 24,
        },
        latency: {
          kind: "SEARCH",
          unit: "ms",
          avg_ms: 59.31,
          warm_p95_ms: 76.47,
          http_round_trip: false,
        },
        preparation: {
          status: "MEASURED",
          model_load_seconds: 3.03,
          document_embedding_seconds: 30.07,
        },
      },
      {
        method: "RRF_HYBRID",
        execution_status: "SUCCEEDED",
        executed_count: 24,
        metric_status: "MEASURED",
        recall_at_5: 0.8333,
        mrr_at_5: 0.7292,
        full_evidence: {
          full_evidence_count: 20,
          full_evidence_denominator: 24,
        },
        latency: {
          kind: "SERIAL_SEARCH_E2E",
          unit: "ms",
          avg_ms: 87.36,
          warm_p95_ms: 117.92,
          http_round_trip: false,
        },
        preparation: {
          status: "NOT_APPLICABLE",
          model_load_seconds: null,
          document_embedding_seconds: null,
        },
      },
    ],

    selection: {
      selected_method: "BM25",
      status: "PROVISIONAL_PRODUCT_ONLY",
      selection_scope:
        "PRODUCT-only mixed actual-scale DEV24",
      reasons: [
        "Hybrid Recall@5 did not improve over BM25.",
        "Hybrid MRR@5 decreased and serial search latency increased.",
        "Dense actual-scale retrieval metrics were lower than BM25.",
        "Three semantic cases failed for all three methods (task handoff).",
        "DEV24 is lexical-heavy; do not generalize to all natural-language product search.",
      ],
      final_natural_language_retriever: false,
    },
    r07: {
      status: "COMPLETE_WITH_LIMITS",
      experiment_id: "OPS-RAG-02",
      run_id: null,
      input_hashes: { product_snapshot_sha256: "safe-product-hash", dev24_sha256: "safe-dev24-hash", final12_used: false },
      validated_baseline: "BM25",
      reranker: {
        evaluation_status: "PASS_WITH_FINDING", baseline: "BM25",
        always_on_selected: false, conditional_candidate: true,
        conditional_routing_validated: false, runtime_enabled: false,
        fallback_target: "BM25",
        before: { recall_at_5: 0.8333333333333334, mrr_at_5: 0.7916666666666666, full_evidence_count: 20, full_evidence_rate: 0.8333333333333334 },
        after: { recall_at_5: 0.8333333333333334, mrr_at_5: 0.8125, full_evidence_count: 20, full_evidence_rate: 0.8333333333333334 },
        candidate_miss_count: 4, candidate_miss_category: "RETRIEVAL_CANDIDATE_MISS",
        latency: [
          { kind: "RERANK_ONLY", unit: "ms", count: 24, mean_ms: 1687.3297916664949, p95_ms: 2469.209809999938, http_round_trip: false },
          { kind: "SEARCH_PLUS_RERANK_E2E", unit: "ms", count: 24, mean_ms: 1706.9181083332599, p95_ms: 2489.187160001074, http_round_trip: false },
        ],
        observed_events: { timeout_count: 0, retry_count: 0, fallback_count: 0 },
        timeout_seconds: 120, max_retries: 1,
        model: "BAAI/bge-reranker-v2-m3", revision: "safe-revision", device: "cpu",
      },
      compression: {
        evaluation_status: "PASS_WITH_LIMITATION", scope: "SYNTHETIC_POLICY_COMPRESSION_ONLY",
        case_count: 3, before_tokens: 903, after_tokens: 445,
        reduction_ratio: 0.5071982281284606,
        evidence_preserved_count: 3, citation_preserved_count: 3, fallback_count: 0,
        latency: { kind: "SYNTHETIC_COMPRESSION", unit: "ms", count: 3, mean_ms: 0.17933333401742857, p95_ms: null, http_round_trip: false },
        actual_context_validated: false, runtime_enabled: false,
      },
    },
  };
  function setupRetrieval(
    data: unknown = searchData,
    status = 200,
    summary: unknown = summaryData,
    summaryStatus = 200,
    actualSummary: unknown = actualSummaryData,
    actualSummaryStatus = 200,
  ) {
    const fetcher = vi.fn(async (url: string) => {
      if (url.endsWith("/retrieval/actual-summary")) {
        return new Response(
          JSON.stringify(actualSummary),
          { status: actualSummaryStatus },
        );
      }

      let payload: unknown = [];
      let httpStatus = 200;

      if (url.endsWith("/retrieval/search")) {
        payload = data;
        httpStatus = status;
      }

      if (url.endsWith("/retrieval/summary")) {
        payload = summary;
        httpStatus = summaryStatus;
      }

      if (url.includes("/c04/lookup?")) {
        payload = {
          ...key,
          title: "C04 ・尖ｬｸ ・罹ｪｩ",
          source_type: "PRODUCT",
          as_of: null,
          excerpt: "원문 전체 범위 발췌",
          excerpt_hash: "sha256:full",
          data_mode: "SYNTHETIC_DEMO",
          visibility: "DEMO_PUBLIC",
          stale: true,
          warnings: ["STALE_EVIDENCE"],
          definitive_answer_allowed: false,
        };
      }

      return new Response(
        JSON.stringify({
          ...envelope,
          ...(url.includes("/c04/lookup?")
            ? { as_of: null }
            : {}),
          data: payload,
        }),
        { status: httpStatus },
      );
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
    const result = screen.getByTestId("retrieval-result");
    for (const text of ["BM25", "PROVISIONAL_DEV_SELECTION", "SYNTHETIC_DEMO", "answer_status): HOLD", "human_review_reason): STALE_EVIDENCE", "warnings): STALE_EVIDENCE", "actual_retrieval_executed): true"]) {
      expect(result).toHaveTextContent(text);
    }
    expect(document.body.outerHTML).not.toMatch(/request_id|trace_id|request_test|trace_test/);
    expect(screen.getByText(/고정 검색 조건/)).toHaveTextContent("method=BM25 · top_k=5");
    expect(screen.getByText(/서로 다른 범위일 수 있습니다/)).toBeInTheDocument();
    expect(fetcher).toHaveBeenCalledWith(expect.stringContaining("/retrieval/search"), expect.objectContaining({
      method: "POST", body: JSON.stringify({ query: "상품 근거 질문", top_k: 5, method: "BM25" }),
    }));
    fireEvent.click(within(card).getByRole("button", { name: "원문 근거 열기" }));
    expect(await screen.findByTestId("c04-document")).toHaveTextContent("원문 전체 범위 발췌");
    expect(screen.getByRole("dialog", { name: "C04 원문 근거" })).toBeInTheDocument();
    expect(document.body.outerHTML).not.toMatch(/request_id|trace_id|request_test|trace_test/);
    expect(fetcher).toHaveBeenCalledWith(expect.stringContaining(`/c04/lookup?${new URLSearchParams(key)}`), expect.objectContaining({ method: "GET" }));
    expect(fetcher.mock.calls.some(([url]) => url.includes("/c04/lookup?") && url.includes("semantic_source"))).toBe(false);
  });

  it("LOCAL_EVAL 운영 카드마다 합성 자료모드를 표시하고 문의 예시를 실제 AI 분석과 구분한다", () => {
    vi.stubEnv("VITE_USE_REAL_BACKEND", "false");
    setupRetrieval();
    render(<InsightsPage />);

    const cards = document.querySelectorAll(".insight-card");
    expect(cards).toHaveLength(3);
    for (const card of cards) {
      expect(card).toHaveTextContent("합성 예시 · SYNTHETIC_DEMO");
    }
    expect(cards[0]).toHaveTextContent("주요 케이크 재고 소진 예상");
    expect(cards[1]).toHaveTextContent("예약 주문 6건 충족 어려움");
    expect(cards[2]).toHaveTextContent("배송 지연 문의 23건 집중");
    expect(cards[2]).toHaveTextContent("합성 문의 예시이며 실제 문의 AI 분석 결과가 아닙니다.");
    expect(screen.queryByText(/실제 문의 AI 분석 결과입니다/)).not.toBeInTheDocument();
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

  it("actual-summary의 R07 중첩 aggregate를 기존 parser가 검증해 보존한다", () => {
    const parsed = parseActualRetrievalSummary(actualSummaryData);
    expect(parsed.r07?.reranker.before.mrr_at_5).toBe(0.7916666666666666);
    expect(parsed.r07?.reranker.after.mrr_at_5).toBe(0.8125);
    expect(parsed.r07?.reranker.candidate_miss_count).toBe(4);
    expect(parsed.r07?.reranker.observed_events.fallback_count).toBe(0);
    expect(parsed.r07?.compression.reduction_ratio).toBe(0.5071982281284606);
  });

  it("R07 Reranker와 Synthetic Compression 평가를 원본 수치와 제한 상태로 표시한다", async () => {
    setupRetrieval();
    render(<InsightsPage />);

    const reranker = await screen.findByTestId("r07-reranker");
    expect(reranker).toHaveTextContent("PASS_WITH_FINDING");
    expect(reranker).toHaveTextContent("Baseline: BM25");
    expect(reranker).toHaveTextContent("Recall@5 before / after: 0.833333 / 0.833333");
    expect(reranker).toHaveTextContent("MRR@5 before / after: 0.791667 / 0.812500");
    expect(reranker).toHaveTextContent("Full Evidence before / after: 20/24 / 20/24");
    expect(reranker).toHaveTextContent("Candidate miss: 4 · RETRIEVAL_CANDIDATE_MISS");
    expect(reranker).toHaveTextContent("Reranker fallback: 0");
    expect(reranker).toHaveTextContent("RERANK_ONLY");
    expect(reranker).toHaveTextContent("1687.33 ms");
    expect(reranker).toHaveTextContent("SEARCH_PLUS_RERANK_E2E");
    expect(reranker).toHaveTextContent("1706.92 ms");
    expect(reranker).toHaveTextContent("Always-on: 미선택");
    expect(reranker).toHaveTextContent("조건부 적용 후보: 예");
    expect(reranker).toHaveTextContent("조건부 routing 기준: 미검증");
    expect(reranker).toHaveTextContent("Runtime: 비활성 · Fallback 기준선: BM25");
    expect(reranker).not.toHaveTextContent("활성화됨");

    const compression = screen.getByTestId("r07-compression");
    expect(compression).toHaveTextContent("PASS_WITH_LIMITATION");
    expect(compression).toHaveTextContent("SYNTHETIC_POLICY_COMPRESSION_ONLY");
    expect(compression).toHaveTextContent("Synthetic 정책 설명: 3건");
    expect(compression).toHaveTextContent("Tokens before / after: 903 → 445");
    expect(compression).toHaveTextContent("약 50.72% (Synthetic 정책 설명 기준)");
    expect(compression).toHaveTextContent("Evidence 보존: 3/3 · Citation 보존: 3/3");
    expect(compression).toHaveTextContent("Compression fallback: 0");
    expect(compression).toHaveTextContent("0.179 ms");
    expect(compression).toHaveTextContent("Actual context: 미검증 · Runtime: 비활성");
    expect(compression).not.toHaveTextContent("운영 비용");
    expect(screen.getByTestId("actual-scale-retrieval-summary")).toHaveTextContent("C02 예약 집계: 사용 차단");
    expect(document.body.outerHTML).not.toMatch(/gold_answer|gold_evidence|private_path|FINAL12 결과|FINAL12 점수/);
  });

  it("r07 결과가 없으면 평가 결과 미수신만 표시한다", async () => {
    setupRetrieval(undefined, 200, undefined, 200, { ...actualSummaryData, r07: undefined });
    render(<InsightsPage />);
    const actual = await screen.findByTestId("actual-scale-retrieval-summary");
    await waitFor(() => expect(within(actual).getByRole("status")).toHaveTextContent("R07 평가 결과 미수신"));
    expect(screen.queryByTestId("r07-reranker")).not.toBeInTheDocument();
    expect(screen.queryByTestId("r07-compression")).not.toBeInTheDocument();
  });

  it("malformed r07은 Actual 평가 전체를 fail closed 한다", async () => {
    const malformed = { ...actualSummaryData, r07: { ...actualSummaryData.r07, reranker: { ...actualSummaryData.r07.reranker, conditional_routing_validated: true } } };
    expect(() => parseActualRetrievalSummary(malformed)).toThrow("Retrieval response is malformed");
    setupRetrieval(undefined, 200, undefined, 200, malformed);
    render(<InsightsPage />);
    const actual = await screen.findByTestId("actual-scale-retrieval-summary");
    expect(await within(actual).findByRole("alert")).toHaveTextContent("실제 규모 평가 요약을 불러오지 못했습니다");
    expect(screen.queryByTestId("r07-reranker")).not.toBeInTheDocument();
    expect(screen.queryByTestId("r07-compression")).not.toBeInTheDocument();
  });

  it("C07 actual-scale PRODUCT 한정 평가를 Synthetic과 분리해 표시한다", async () => {
    setupRetrieval();

    render(<InsightsPage />);

    const actual = await screen.findByTestId(
      "actual-scale-retrieval-summary",
    );

    await waitFor(() => {
      expect(actual).toHaveTextContent(
        "PRODUCT 한정 actual-scale retrieval 평가",
      );
    });
    expect(actual).toHaveTextContent(
      "PRIVATE_ACTUAL_EVAL",
    );
    expect(actual).not.toHaveTextContent("SYNTHETIC_DEMO");

    expect(actual).toHaveTextContent(
      "PRODUCT-only actual-scale mixed DEV24 retrieval baseline",
    );

    expect(actual).toHaveTextContent(
      "문서 2167 / 청크 2167",
    );

    expect(actual).toHaveTextContent(
      "질문 24 / 답가능 24 / HOLD 0",
    );

    expect(actual).toHaveTextContent(
      "계획 72 / 실제 실행 72 / 성공 72",
    );

    expect(actual).toHaveTextContent(
      "실패 0 / 차단 0 / 미실행 0",
    );

    expect(actual).toHaveTextContent(
      "PRODUCT: 지원",
    );

    expect(actual).toHaveTextContent(
      "POLICY: 자료 미확보",
    );

    expect(actual).toHaveTextContent(
      "INVENTORY_SNAPSHOT: 사용 차단",
    );

    expect(actual).toHaveTextContent(
      "C02 예약 집계: 사용 차단",
    );
  });
  it("C07 actual metric과 latency를 Backend 값 그대로 표시한다", async () => {
  setupRetrieval();

  render(<InsightsPage />);

  const bm25 = await screen.findByTestId(
    "actual-method-BM25",
  );

  expect(bm25).toHaveTextContent(
    "Recall@5 = 0.8333",
  );
  expect(bm25).toHaveTextContent(
    "MRR@5 = 0.7917",
  );
  expect(bm25).toHaveTextContent(
    "Full evidence = 20/24",
  );
  expect(bm25).toHaveTextContent(
    "SEARCH",
  );
  expect(bm25).toHaveTextContent(
    "27.84 ms",
  );
  expect(bm25).toHaveTextContent(
    "38.96 ms",
  );

  const dense = screen.getByTestId(
    "actual-method-DENSE",
  );

  expect(dense).toHaveTextContent(
    "Recall@5 = 0.4167",
  );
  expect(dense).toHaveTextContent(
    "MRR@5 = 0.2861",
  );
  expect(dense).toHaveTextContent(
    "Full evidence = 10/24",
  );
  expect(dense).toHaveTextContent(
    "model load 3.03초",
  );
  expect(dense).toHaveTextContent(
    "document embedding 30.07초",
  );

  const hybrid = screen.getByTestId(
    "actual-method-RRF_HYBRID",
  );

  expect(hybrid).toHaveTextContent(
    "Recall@5 = 0.8333",
  );
  expect(hybrid).toHaveTextContent(
    "MRR@5 = 0.7292",
  );
  expect(hybrid).toHaveTextContent(
    "SERIAL_SEARCH_E2E",
  );
  expect(hybrid).toHaveTextContent(
    "87.36 ms",
  );
  expect(hybrid).toHaveTextContent(
    "117.92 ms",
  );
});

it("C07 actual summary가 403이면 가짜 평가값 대신 unavailable 상태를 표시한다", async () => {
  setupRetrieval(
    searchData,
    200,
    summaryData,
    200,
    null,
    403,
  );

  render(<InsightsPage />);

const actual = await screen.findByTestId(
  "actual-scale-retrieval-summary",
);

await waitFor(() => expect(within(actual).getByRole("status")).toHaveTextContent(
  "현재 환경에서는 실제 규모 평가 요약을 사용할 수 없습니다.",
));

  expect(actual).not.toHaveTextContent(
    "문서 2167",
  );

  expect(
    screen.queryByTestId("actual-method-BM25"),
  ).not.toBeInTheDocument();
});
it("C07 actual summary schema가 다르면 fail closed 한다", async () => {
  setupRetrieval(
    searchData,
    200,
    summaryData,
    200,
    {
      ...actualSummaryData,
      data_mode: "SYNTHETIC_DEMO",
    },
    200,
  );

  render(<InsightsPage />);

const actual = await screen.findByTestId(
  "actual-scale-retrieval-summary",
);

const alert = await within(actual).findByRole(
  "alert",
);

expect(alert).toHaveTextContent(
  "실제 규모 평가 요약을 불러오지 못했습니다",
);

expect(actual).not.toHaveTextContent(
  "문서 2167",
);
});

it("C07 미측정 null 값을 0으로 표시하지 않는다", async () => {
  const actualWithUnmeasured = {
    ...actualSummaryData,
    methods: actualSummaryData.methods.map((method) =>
      method.method === "BM25"
        ? {
            ...method,
            metric_status: "UNMEASURED",
            recall_at_5: null,
            mrr_at_5: null,
            latency: {
              ...method.latency,
              avg_ms: null,
              warm_p95_ms: null,
            },
          }
        : method,
    ),
  };

  setupRetrieval(
    searchData,
    200,
    summaryData,
    200,
    actualWithUnmeasured,
    200,
  );

  render(<InsightsPage />);

  const bm25 = await screen.findByTestId(
    "actual-method-BM25",
  );

  expect(bm25).toHaveTextContent(
    "Recall@5 = 미측정",
  );

  expect(bm25).toHaveTextContent(
    "MRR@5 = 미측정",
  );

  expect(bm25).toHaveTextContent(
    "평균 미측정",
  );

  expect(bm25).toHaveTextContent(
    "warm p95 미측정",
  );
});
});
