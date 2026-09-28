import { AIBadge, RiskBadge, SourceBadge } from "../../components/Badges";
import InternalTaskAction from "../../components/InternalTaskAction";
import SystemState from "../../components/SystemStates";
import EvidenceDrawer from "../../components/EvidenceDrawer";
import type { C04Key } from "../../api/day04";
import type { ApiEnvelope } from "../../types/contracts";
import {
  useEffect,
  useState,
  useRef,
} from "react";

import {
  getDay08Insights,
  type Day08Insight,
  getRetrievalSummary,
  searchRetrieval,
  RetrievalHttpError,
  type RetrievalSearch,
  type RetrievalSummary,
} from "../../api/day08";

const insights = [
  { level: "critical" as const, title: "이번 주 토요일 전 주요 케이크 재고 소진 예상", problem: "현재 판매 속도라면 레드벨벳과 말차 케이크가 입고 전에 소진될 수 있습니다.", source: "최근 7일 판매량 · eCount 실재고", confidence: "94%", action: "실재고와 진열 수량을 직접 확인" },
  { level: "critical" as const, title: "9/7 예약 주문 6건 충족 어려움", problem: "예약 주문 24건 중 6건에 필요한 원자재가 부족합니다.", source: "예약 주문 · 원자재 재고", confidence: "91%", action: "긴급 원자재 확보 가능 여부 확인" },
  { level: "warning" as const, title: "배송 지연 문의 23건 집중", problem: "동일 지역의 배송 문의가 전일 대비 크게 증가했습니다.", source: "문의 유형 · 접수 시간대", confidence: "88%", action: "물류 현황과 공통 원인 확인" },
];

export default function InsightsPage() {
  const useRealBackend =
  import.meta.env.VITE_USE_REAL_BACKEND === "true";

const [realInsights, setRealInsights] =
  useState<Day08Insight[] | null>(null);

const [realError, setRealError] =
  useState(false);

useEffect(() => {
  if (!useRealBackend) {
    return;
  }

  let active = true;

  getDay08Insights()
    .then((response) => {
      if (active) {
        setRealInsights(response.data);
      }
    })
    .catch(() => {
      if (active) {
        setRealError(true);
      }
    });

  return () => {
    active = false;
  };
}, []);
if (useRealBackend) {
  if (realError) {
    return (
      <div
        className="page"
        data-testid="route-insights"
      >
        <p>
          Backend Insight를 불러오지 못했습니다.
        </p>
        <DevRetrieval />
      </div>
    );
  }

  if (!realInsights) {
    return (
      <div
        className="page"
        data-testid="route-insights"
      >
        <p>Insight를 불러오는 중입니다.</p>
        <DevRetrieval />
      </div>
    );
  }

  return (
    <div
      className="page"
      data-testid="route-insights"
    >
      <section className="stack">
        {realInsights.length === 0 ? (
          <SystemState
            state="empty"
            title="현재 표시할 AI 인사이트가 없습니다"
            description="정상적으로 조회되었으며, 현재 표시할 항목이 없습니다. 오류가 아닙니다."
          />
        ) : realInsights.map((insight) => (
          <article
            className="card"
            key={insight.insight_id}
            data-testid="real-backend-insight"
          >
            <div className="card-body stack">
              <strong>
                {insight.summary}
              </strong>

              <div>
                Severity: {insight.severity}
              </div>

              <div>
                Confidence: {insight.confidence}
              </div>

              {insight.calculation ? (
                <div
                  data-testid="insight-calculation"
                >
                  시작 재고:{" "}
                  {insight.calculation.starting_inventory ??
                    "미제공"}
                  {" / "}
                  판매:{" "}
                  {insight.calculation.sold ??
                    "미제공"}
                  {" / "}
                  예상 재고:{" "}
                  {insight.calculation.expected_inventory ??
                    "미제공"}
                </div>
              ) : null}
            </div>
          </article>
        ))}
      </section>
      <DevRetrieval />
    </div>
  );
}
  return (
    <div className="page" data-testid="route-insights">
      <div className="notice ai"><AIBadge>AI 인사이트 · 운영 패턴 감지</AIBadge><br /><span className="muted">합성 운영 데이터를 바탕으로 검토 항목을 제안하며 자동 실행하지 않습니다.</span></div>
      <div className="grid insight-kpis">{[["오늘 분석", "7건"],["검토 필요", "5건"],["평균 신뢰도", "89%"],["자동 실행", "0건"]].map(([label,value]) => <article className="kpi" key={label}><div className="kpi-label">{label}</div><div className="kpi-value">{value}</div></article>)}</div>
      <div className="toolbar"><button className="filter active">전체</button><button className="filter">위험</button><button className="filter">주의</button><span className="right tertiary">데이터 기준: 최근 확인 시각</span></div>
      <section className="stack">{insights.map((insight) => <article className={`card insight-card ${insight.level}`} key={insight.title}><div className="card-header badges"><RiskBadge level={insight.level} /><AIBadge>AI 설명</AIBadge><strong>{insight.title}</strong><span className="right badge ai">신뢰도 {insight.confidence}</span></div><div className="card-body grid insight-questions"><div><div className="kpi-label">무슨 문제인가요?</div><p>{insight.problem}</p></div><div><div className="kpi-label">어떤 데이터로 판단했나요?</div><p><SourceBadge>{insight.source}</SourceBadge></p></div><div><div className="kpi-label">지금 무엇을 확인하나요?</div><p>{insight.action}</p></div><div style={{ alignSelf: "end", justifySelf: "end" }}><InternalTaskAction compact /></div></div></article>)}</section>
      <DevRetrieval />
    </div>
  );
}

function retrievalError(error: unknown) {
  const messages: Record<number, string> = {
    403: "민감/금지 입력 또는 접근 정책으로 차단되었습니다.",
    422: "잘못된 검색 요청입니다.",
    503: "retrieval runtime/summary를 사용할 수 없습니다.",
    504: "검색 시간이 초과되었습니다. 다시 시도해 주세요.",
  };
  return error instanceof RetrievalHttpError
    ? messages[error.status] ?? "검색 서비스를 불러오지 못했습니다."
    : "응답 형식 또는 연결 상태를 확인할 수 없습니다.";
}

function DevRetrieval() {
  const [query, setQuery] = useState("");
  const [summary, setSummary] = useState<ApiEnvelope<RetrievalSummary> | null>(null);
  const [summaryError, setSummaryError] = useState<string | null>(null);
  const [result, setResult] = useState<ApiEnvelope<RetrievalSearch> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [c04Key, setC04Key] = useState<C04Key | undefined>();
  const searchController = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getRetrievalSummary(controller.signal)
      .then((value) => { if (!controller.signal.aborted) setSummary(value); })
      .catch((failure: unknown) => { if (!controller.signal.aborted) setSummaryError(retrievalError(failure)); });
    return () => { controller.abort(); searchController.current?.abort(); };
  }, []);

  async function search() {
    searchController.current?.abort();
    const controller = new AbortController();
    searchController.current = controller;
    setPending(true); setError(null); setResult(null); setC04Key(undefined);
    try {
      const response = await searchRetrieval(query, controller.signal);
      if (!controller.signal.aborted) setResult(response);
    } catch (failure) {
      if (!controller.signal.aborted) setError(retrievalError(failure));
    } finally {
      if (!controller.signal.aborted) setPending(false);
    }
  }
  const data = result?.data;
  const metric = summary?.data.methods.find((method) => method.method === "bm25");
  const metricValue = (value: number | null, status: string | undefined, decimal = false) => value === null ? (status ?? "미측정") : decimal && Number.isInteger(value) ? value.toFixed(1) : String(value);

  return <section className="card" aria-labelledby="dev-retrieval-title">
    <div className="card-body stack">
      <h2 id="dev-retrieval-title">DEV 근거 검색</h2>
      <div className="notice">
        <strong>BM25 · 임시 DEV 선택 · SYNTHETIC_DEMO</strong>
        <p>PROVISIONAL_DEV_SELECTION · 최종 운영 검색기 아님</p>
        <p>검색 근거만 조회하며 AI 답변을 생성하지 않습니다. 근거가 있어도 확정 답변이 가능한 것은 아닙니다.</p>
        <p>R09 운영 질문 패널이 아닌 Synthetic DEV 검색입니다. 실제 운영 규모 검증이 필요합니다.</p>
        <p>검색 점수는 retriever score이며 정답률·신뢰도·사실확률이 아닙니다.</p>
      </div>
      <section aria-label="Synthetic DEV 평가">
        <h3>Synthetic DEV 평가</h3>
        {summaryError ? <p role="alert">DEV 평가 조회 실패: {summaryError}</p> : !summary ? <p>DEV 평가를 불러오는 중입니다.</p> : <>
          <p>DEV 질문 {summary.data.query_count} · 실행 {summary.data.execution_count} · 오류 {summary.data.error_count}</p>
          <p>{summary.data.selection.method.toUpperCase()} · {summary.data.selection.status} · {summary.data.data_mode}</p>
          {metric && <>
            <p>Recall@5 = {metricValue(metric.mean_recall_at_5, metric.metric_status.mean_recall_at_5, true)} · MRR@5 = {metricValue(metric.mean_mrr_at_5, metric.metric_status.mean_mrr_at_5, true)} · Full evidence = {metricValue(metric.full_evidence_numerator, metric.metric_status.full_evidence_cases)}/{metricValue(metric.full_evidence_denominator, metric.metric_status.answerable_cases)}</p>
            <p>평가 실행 상태: {metric.execution_status} · {metric.source_status ?? "별도 상태 없음"}</p>
          </>}
          <p>{summary.data.actual_scale_retrieval_validation_required ? "실제 운영 규모 검증 필요" : "실제 운영 규모 검증 필요 여부: false (운영 승인 의미 아님)"} · actual_scale_retrieval_validation_required = {String(summary.data.actual_scale_retrieval_validation_required)}</p>
          {summary.warnings.map((warning, index) => <p key={index}>{warning}</p>)}
        </>}
      </section>
      <p>고정 검색 조건: method=BM25 · top_k=5</p>
      <form className="toolbar" onSubmit={(event) => { event.preventDefault(); void search(); }}>
        <label htmlFor="dev-retrieval-query">검색 질문</label>
        <input id="dev-retrieval-query" value={query} maxLength={2000} onChange={(event) => setQuery(event.target.value)} placeholder="찾고 싶은 근거를 입력하세요" />
        <button type="submit" disabled={pending || !query.trim()}>{pending ? "검색 중…" : "검색 실행"}</button>
      </form>
      {!pending && !error && !data && <p>질문을 입력하고 검색을 실행하세요.</p>}
      {pending && <p role="status">근거를 검색하는 중입니다.</p>}
      {error && <p role="alert">검색 실패: {error}</p>}
      {data && <div className="stack" data-testid="retrieval-result">
        <p>request_id: {result!.request_id} · trace_id: {result!.trace_id}</p>
        <p>{data.method} · {data.selection_status} · {data.data_mode}</p>
        <p>검색 실행 여부 (actual_retrieval_executed): {String(data.actual_retrieval_executed)}</p>
        <p>답변 상태 (answer_status): {data.answer_status}</p>
        <p>사람 검토 필요 (human_review_required): {String(data.human_review_required)}</p>
        <p>검토 이유 (human_review_reason): {data.human_review_reason.join(" / ") || "없음"}</p>
        <p>주의사항 (warnings): {[...new Set([...result!.warnings, ...data.warnings])].join(" / ") || "없음"}</p>
        <p>추가 조회: {data.required_lookup.join(" / ") || "없음"}</p>
        <p>인덱스 버전 (index_version): {data.index_version}</p>
        {data.result_status === "ZERO_CITATIONS" && <p role="status">검색 결과 0건 (ZERO_CITATIONS)</p>}
        <p>검색 발췌문(semantic_excerpt)과 C04 원문 전체 발췌문(full excerpt)은 서로 다른 범위일 수 있습니다.</p>
        {data.citations.map((citation, index) => <article className="card" key={`${citation.semantic_chunk_id}-${index}`} data-testid="retrieval-citation">
          <div className="card-body stack">
            <h3>{citation.rank}. {citation.title}</h3>
            <p>검색 점수 (retriever score): {citation.score}</p>
            <p>출처 유형: {citation.source_type} · 버전: {citation.version}</p>
            <p>검색 발췌문: {citation.semantic_excerpt}</p>
            <p>기준 시각 (as_of): {citation.as_of ?? "미제공"}</p>
            <button type="button" disabled={!citation.c04_lookup} onClick={() => setC04Key(citation.c04_lookup ?? undefined)}>원문 근거 열기</button>
            {!citation.c04_lookup && <span>원문 매핑 없음</span>}
          </div>
        </article>)}
      </div>}
    </div>
    <EvidenceDrawer open={!!c04Key} insight={null} c04Key={c04Key} onClose={() => setC04Key(undefined)} />
  </section>;
}
