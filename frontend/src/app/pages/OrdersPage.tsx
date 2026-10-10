import { Fragment, useEffect, useMemo, useState, type FormEvent } from "react";
import { getDay09Reservations } from "../../api/day09";
import { getRecentOrderSummary, getOrdersPage, type RecentOrderSummary, type OrdersQuery } from "../../api/orders";
import ReservationList from "../../features/reservations/ReservationList";
import type { ReservationRiskItem } from "../../types/contracts";
import {
  getSalesSummary,
  type SalesSummaryData,
} from "../../api/salesSummary";

// 화면별 UI를 먼저 정리한다. 미확인 주문·매출 수치는 생성하지 않는다.
type OrdersTab = "orders" | "sales";
const usingBackend = import.meta.env.VITE_USE_REAL_BACKEND === "true";

// 이 모델은 화면 표시용으로만 사용합니다. Backend 응답 검증·매핑은 계약 확정 후 API adapter에서 담당합니다.
export type OrderDisplayItem = {
  orderId: string;
  orderedAt: string | null;
  products: { name: string; option?: string | null; quantity: number | null }[];
  orderAmount: string | null;
  paidAmount: string | null;
  paid: "T" | "F" | "M" | null;
  canceled: "T" | "F" | "M" | null;
  shippingStatus: "T" | "F" | "M" | null;
};

const orderPageSize = 20;
const statusOptions = [
  { value: "", label: "전체" },
  { value: "T", label: "예" },
  { value: "F", label: "아니요" },
  { value: "M", label: "확인 필요" },
];

function formatStatus(value: OrderDisplayItem["paid"]) {
  return value === null ? "미제공" : value === "T" ? "예" : value === "F" ? "아니요" : "확인 필요";
}

// 합성 주문금액은 소수점 아래가 0인 경우에만 원 단위로 표시합니다.
// 금액의 정식 currency 계약은 Backend에서 별도 확정해야 합니다.
function formatOrderAmount(value: string | null): string {
  if (value === null) return "미제공";
  if (!/^-?\d+(?:\.\d+)?$/.test(value)) return "미제공";
  const [whole, fraction = ""] = value.split(".");
  const grouped = BigInt(whole).toLocaleString("ko-KR");
  if (fraction && /[1-9]/.test(fraction)) {
    return `${grouped}.${fraction.replace(/0+$/, "")} (단위 미확정)`;
  }
  return `${grouped}원`;
}

function formatDate(value: string | null) {
  if (!value) return "미제공";
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? "미제공" : date.toLocaleString("ko-KR", { timeZone: "Asia/Seoul" });
}

// records가 전달되지 않은 동안은 목록 API 미연결을 명시합니다.
export function OrderListBrowser({ records = null, serverMode = false, onTotalChange }: {
  records?: OrderDisplayItem[] | null;
  serverMode?: boolean;
  onTotalChange?: (count: number | null) => void;
}) {
  const [draftQuery, setDraftQuery] = useState("");
  const [draftSearchType, setDraftSearchType] = useState<"order_number" | "product_name">("order_number");
  const [draftFrom, setDraftFrom] = useState("");
  const [draftTo, setDraftTo] = useState("");
  const [draftPaid, setDraftPaid] = useState("");
  const [draftCanceled, setDraftCanceled] = useState("");
  const [draftShipping, setDraftShipping] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [applied, setApplied] = useState({ query: "", searchType: "order_number" as "order_number" | "product_name", from: "", to: "", paid: "", canceled: "", shipping: "" });
  const [page, setPage] = useState(0);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [validationError, setValidationError] = useState("");
  // 서버 모드에서는 필터·페이지네이션을 Backend가 수행합니다.
  const [serverRecords, setServerRecords] = useState<OrderDisplayItem[] | null>(null);
  const [serverTotal, setServerTotal] = useState<number | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);
  const [serverLoading, setServerLoading] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!serverMode) return;
    const controller = new AbortController();
    const query: OrdersQuery = {
      limit: orderPageSize,
      offset: page * orderPageSize,
      sort_by: "order_date",
      sort_order: "desc",
    };
    const q = applied.query.trim();
    // 두 검색 파라미터를 동시에 사용하면 AND 조건이 될 수 있어 선택한 하나만 전달합니다.
    if (q) query[applied.searchType] = q;
    if (applied.from) query.from_date = applied.from;
    if (applied.to) query.to_date = applied.to;
    if (applied.paid === "T" || applied.paid === "F") query.paid = applied.paid;
    if (applied.canceled === "T" || applied.canceled === "F" || applied.canceled === "M") query.canceled = applied.canceled;
    if (applied.shipping === "T" || applied.shipping === "F" || applied.shipping === "M") query.shipping_status = applied.shipping;
    setServerLoading(true);
    setServerError(null);
    void getOrdersPage(query, controller.signal)
      .then((response) => {
        if (controller.signal.aborted) return;
        setServerRecords(response.data.items.map((item) => ({
          orderId: item.order_number,
          orderedAt: item.order_date,
          products: item.items.map((product) => ({name: product.product_name, option: product.option_name, quantity: product.quantity})),
          orderAmount: item.total_order_amount,
          paidAmount: item.total_paid_amount,
          paid: item.paid,
          canceled: item.canceled,
          shippingStatus: item.shipping_status,
        })));
        setServerTotal(response.data.total);
        onTotalChange?.(response.data.total);
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setServerError(error instanceof Error ? error.message : "주문 데이터를 불러오지 못했습니다.");
        setServerRecords(null);
        setServerTotal(null);
        onTotalChange?.(null);
      })
      .finally(() => { if (!controller.signal.aborted) setServerLoading(false); });
    return () => controller.abort();
  }, [serverMode, applied, page, reloadKey, onTotalChange]);
  const connected = serverMode ? serverRecords !== null : records !== null;
  const filtered = useMemo(() => {
    if (!records || serverMode) return [];
    const normalized = applied.query.trim().toLocaleLowerCase("ko-KR");
    return records.filter((item) => {
      if (normalized && !item.orderId.toLocaleLowerCase("ko-KR").includes(normalized) &&
          !item.products.some((product) => product.name.toLocaleLowerCase("ko-KR").includes(normalized))) return false;
      if (applied.paid && item.paid !== applied.paid) return false;
      if (applied.canceled && item.canceled !== applied.canceled) return false;
      if (applied.shipping && item.shippingStatus !== applied.shipping) return false;
      if (applied.from || applied.to) {
        if (!item.orderedAt) return false;
        const date = new Date(item.orderedAt);
        if (Number.isNaN(date.valueOf())) return false;
        const kstDate = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Seoul", year: "numeric", month: "2-digit", day: "2-digit" }).format(date);
        if (applied.from && kstDate < applied.from) return false;
        if (applied.to && kstDate > applied.to) return false;
      }
      return true;
    });
  }, [records, applied, serverMode]);
  const pageCount = serverMode ? Math.ceil((serverTotal ?? 0) / orderPageSize) : Math.ceil(filtered.length / orderPageSize);
  const visible = serverMode ? (serverRecords ?? []) : filtered.slice(page * orderPageSize, (page + 1) * orderPageSize);

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (draftFrom && draftTo && draftFrom > draftTo) {
      setValidationError("시작일이 종료일보다 늦을 수 없습니다.");
      return;
    }
    setValidationError("");
    setApplied({ query: draftQuery, searchType: draftSearchType, from: draftFrom, to: draftTo, paid: draftPaid, canceled: draftCanceled, shipping: draftShipping });
    setPage(0);
    setExpanded(null);
  }
  function clearFilters() {
    setDraftQuery(""); setDraftSearchType("order_number"); setDraftFrom(""); setDraftTo(""); setDraftPaid(""); setDraftCanceled(""); setDraftShipping("");
    setApplied({ query: "", searchType: "order_number", from: "", to: "", paid: "", canceled: "", shipping: "" });
    setValidationError(""); setPage(0); setExpanded(null);
  }

  return (
    <section className="card orders-browser" aria-labelledby="order-list-title" data-testid="orders-list-state">
      <header className="orders-section-heading">
        <h2 id="order-list-title">주문 목록</h2>
        <span className="orders-muted">{connected ? `조회 결과 ${(serverMode ? serverTotal ?? 0 : filtered.length).toLocaleString("ko-KR")}건 · ${serverMode ? "서버 조회 기준" : "표시 자료 기준"}` : serverLoading ? "주문 목록 조회 중" : serverError ? "조회 실패" : "API 연결 대기 · 조회 전용"}</span>
      </header>
      <form className="orders-search-form" onSubmit={applyFilters}>
        <div className="orders-search-line">
          {serverMode && <select aria-label="검색 기준" value={draftSearchType} onChange={(event) => setDraftSearchType(event.target.value as "order_number" | "product_name")}>
            <option value="order_number">주문번호</option>
            <option value="product_name">상품명</option>
          </select>}
          <label className="orders-search-field">
            <span className="orders-visually-hidden">주문번호 또는 상품명</span>
            <input value={draftQuery} onChange={(event) => setDraftQuery(event.target.value)} placeholder={serverMode ? (draftSearchType === "order_number" ? "주문번호 검색" : "상품명 검색") : "주문번호 또는 상품명 검색"} aria-label={serverMode ? (draftSearchType === "order_number" ? "주문번호 검색" : "상품명 검색") : "주문번호 또는 상품명 검색"} />
          </label>
          <button type="submit" className="orders-action-button">검색</button>
          <button
            type="button"
            className="orders-filter-toggle"
            aria-expanded={filtersOpen}
            aria-controls="orders-advanced-filters"
            onClick={() => setFiltersOpen((value) => !value)}
          >
            상세 필터
          </button>
        </div>
        <div id="orders-advanced-filters" className="orders-advanced-filters" hidden={!filtersOpen}>
          <label>시작일<input type="date" value={draftFrom} onChange={(event) => setDraftFrom(event.target.value)} /></label>
          <label>종료일<input type="date" value={draftTo} onChange={(event) => setDraftTo(event.target.value)} /></label>
          <label>결제 상태<select value={draftPaid} onChange={(event) => setDraftPaid(event.target.value)}>{statusOptions.filter((o) => !serverMode || o.value !== "M").map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select></label>
          <label>취소 상태<select value={draftCanceled} onChange={(event) => setDraftCanceled(event.target.value)}>{statusOptions.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select></label>
          <label>배송 상태<select value={draftShipping} onChange={(event) => setDraftShipping(event.target.value)}>{statusOptions.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select></label>
          <div className="orders-filter-actions"><button type="button" onClick={clearFilters}>초기화</button><button type="submit" className="orders-action-button">적용</button></div>
        </div>
        {validationError && <p className="orders-validation-error" role="alert">{validationError}</p>}
      </form>
      <div className="orders-table-scroll">
        <table className="dense-table orders-data-table">
          <colgroup><col className="orders-col-id" /><col className="orders-col-date" /><col className="orders-col-product" /><col className="orders-col-qty" /><col className="orders-col-money" /><col className="orders-col-status" /><col className="orders-col-status" /><col className="orders-col-status" /><col className="orders-col-detail" /></colgroup>
          <thead><tr><th>주문번호</th><th>주문일</th><th>상품</th><th className="orders-align-end">수량</th><th className="orders-align-end">주문금액</th><th className="orders-align-center">결제</th><th className="orders-align-center">배송</th><th className="orders-align-center">취소</th><th className="orders-align-center">상세</th></tr></thead>
          <tbody>
            {serverMode && serverLoading ? <tr><td colSpan={9}><div className="orders-table-state" role="status"><strong>주문을 조회하는 중입니다</strong></div></td></tr>
              : serverMode && serverError ? <tr><td colSpan={9}><div className="orders-table-state" role="alert"><strong>주문 목록 조회 실패</strong><p>{serverError}</p><button type="button" className="orders-action-button" onClick={() => setReloadKey((key) => key + 1)}>다시 시도</button></div></td></tr>
              : !connected ? <tr><td colSpan={9}><div className="orders-table-state" role="status"><strong>주문 목록 API 연결 대기</strong><p>화면의 검색·필터·테이블 구조는 준비되었습니다. 현재는 조회 가능한 주문별 API가 없어 실제 행을 표시하지 않습니다.</p></div></td></tr>
              : visible.length === 0 ? <tr><td colSpan={9}><div className="orders-table-state"><strong>표시할 주문이 없습니다</strong><p>조회 자료나 검색 조건을 확인해 주세요.</p></div></td></tr>
              : visible.map((item) => <Fragment key={item.orderId}><tr>
                  <td className="mono">{item.orderId}</td><td>{formatDate(item.orderedAt)}</td>
                  <td>{item.products[0]?.name ?? "미제공"}{item.products.length > 1 && ` 외 ${item.products.length - 1}종`}</td>
                  <td className="number">{item.products.every((p) => p.quantity !== null) ? item.products.reduce((sum, p) => sum + (p.quantity ?? 0), 0) : "미제공"}</td>
                  <td className="number">{formatOrderAmount(item.orderAmount)}</td><td className="orders-align-center">{formatStatus(item.paid)}</td><td className="orders-align-center">{formatStatus(item.shippingStatus)}</td><td className="orders-align-center">{formatStatus(item.canceled)}</td>
                  <td className="orders-align-center"><button type="button" className="orders-detail-toggle" aria-expanded={expanded === item.orderId} onClick={() => setExpanded((current) => current === item.orderId ? null : item.orderId)}>{expanded === item.orderId ? "접기" : "펼치기"}</button></td>
                </tr>{expanded === item.orderId && <tr><td colSpan={9}><div className="orders-item-details"><strong>주문 상품</strong><ul>{item.products.map((product, index) => <li key={`${item.orderId}-${index}`}>{product.name}{product.option ? ` / ${product.option}` : ""} · 수량 {product.quantity ?? "미제공"}</li>)}</ul><span>결제 표시 금액: {formatOrderAmount(item.paidAmount)}</span></div></td></tr>}</Fragment>)}
          </tbody>
        </table>
      </div>
      <footer className="orders-pagination catalog-pagination">
        <span>{connected ? `총 ${(serverMode ? serverTotal ?? 0 : filtered.length).toLocaleString("ko-KR")}건 · ${pageCount === 0 ? 0 : page + 1} / ${pageCount} 페이지` : "페이지 정보 미연결"}</span>
        <nav className="catalog-page-buttons" aria-label="주문 목록 페이지">
          <button type="button" disabled={!connected || serverLoading || page === 0} onClick={() => { setPage(0); setExpanded(null); }}>처음</button>
          <button type="button" disabled={!connected || serverLoading || page === 0} onClick={() => { setPage((p) => Math.max(0, p - 1)); setExpanded(null); }}>이전</button>
          {Array.from({ length: Math.min(5, pageCount) }, (_, index) => {
            const start = Math.max(0, Math.min(page - 2, pageCount - 5));
            return start + index;
          }).map((pageIndex) => (
            <button key={pageIndex} type="button" className={pageIndex === page ? "active" : ""} aria-label={`${pageIndex + 1}페이지`} aria-current={pageIndex === page ? "page" : undefined} disabled={!connected || serverLoading} onClick={() => { setPage(pageIndex); setExpanded(null); }}>{pageIndex + 1}</button>
          ))}
          <button type="button" disabled={!connected || serverLoading || page + 1 >= pageCount} onClick={() => { setPage((p) => p + 1); setExpanded(null); }}>다음</button>
          <button type="button" disabled={!connected || serverLoading || page + 1 >= pageCount} onClick={() => { setPage(Math.max(0, pageCount - 1)); setExpanded(null); }}>마지막</button>
        </nav>
      </footer>
    </section>
  );
}

// 매출 집계 응답의 실제 API 계약이 확정되기 전에는 화면 전용 타입으로만 사용합니다.
// API adapter는 별도 계약 검증 후 연결합니다.
export type SalesDisplayData = {
  periodLabel: string;
  totalOrderAmount: string | null;
  paidMarkedAmount: string | null;
  orderCount: number | null;
  uncertainOrCanceledCount: number | null;
  daily: { date: string; orderAmount: number | null }[] | null;
  states: { label: string; count: number }[] | null;
};









export function SalesAnalysisPanel({ data = null, loading = false, error = null, onPeriodApply }: {
  data?: SalesDisplayData | null;
  loading?: boolean;
  error?: string | null;
  onPeriodApply?: (fromDate: string | null, toDate: string | null) => void;
}) {
  // 조회 조건과 실제 적용된 집계 기간을 분리합니다.
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [periodError, setPeriodError] = useState<string | null>(null);
  const [hoveredDay, setHoveredDay] = useState<{
    date: string;
    amount: number;
  } | null>(null);
  const periodEnabled = typeof onPeriodApply === "function" && !loading;
  const hasData = data !== null && !loading && !error;

  function applyPeriod(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (fromDate && toDate && fromDate > toDate) {
      setPeriodError("시작일은 종료일보다 늦을 수 없습니다.");
      return;
    }
    setPeriodError(null);
    onPeriodApply?.(fromDate || null, toDate || null);
  }

  const kpis = [
    { title: "총 주문금액", value: data?.totalOrderAmount ?? "—", note: "Synthetic 주문금액 · 정산 매출 아님" },
    { title: "결제 표시 금액", value: data?.paidMarkedAmount ?? "—", note: "결제 표시 기준 · 환불 미반영" },
    { title: "주문 건수", value: data?.orderCount == null ? "—" : `${data.orderCount.toLocaleString("ko-KR")}건`, note: "주문 단위 집계" },
    { title: "취소·불확실 주문", value: data?.uncertainOrCanceledCount == null ? "—" : `${data.uncertainOrCanceledCount.toLocaleString("ko-KR")}건`, note: "집계 계약의 상태 분류 기준" },
  ];
  const daily = hasData && data ? data.daily : null;
  const validDaily = daily?.filter((item) => item.orderAmount !== null && Number.isFinite(item.orderAmount) && item.orderAmount >= 0) ?? [];
  const maxDaily = Math.max(0, ...validDaily.map((item) => item.orderAmount ?? 0));
  // 실제 데이터 최대값에 맞춰 Y축 눈금을 자동으로 계산합니다.
  // 기본 상한 600만원. 실제 일별 최대값이 넘으면 200만원 단위로 확장합니다.
  const yAxisMax = Math.max(
    6_000_000,
    Math.ceil(maxDaily / 2_000_000) * 2_000_000,
  );

  // 작은 주문금액도 비교하기 쉽도록 100만원 눈금을 추가합니다.
  const yTicks = [
    0,
    1_000_000,
    ...Array.from(
      { length: yAxisMax / 2_000_000 },
      (_, index) => (index + 1) * 2_000_000,
    ),
  ];
  const states = hasData && data ? data.states : null;
  const validStates = states?.filter((item) => Number.isSafeInteger(item.count) && item.count >= 0) ?? [];
  const maxState = Math.max(0, ...validStates.map((item) => item.count));

  return (
    <div className="orders-sales-analysis">
      <div className="orders-sales-intro">
        <div><h2>매출 분석</h2><p>Synthetic 주문 데이터 기반 지표 · 실제 정산 및 환불 반영 순매출 아님</p></div>
        <span className="orders-data-label">{hasData && data ? data.periodLabel : "집계 API 연결 대기"}</span>
      </div>

      <form className="orders-sales-period" onSubmit={applyPeriod} aria-label="매출 분석 조회 기간">
        <div className="orders-sales-period-fields">
          <label>시작일 <input type="date" value={fromDate} max={toDate || undefined} onChange={(event) => { setFromDate(event.target.value); setPeriodError(null); }} /></label>
          <label>종료일 <input type="date" value={toDate} min={fromDate || undefined} onChange={(event) => { setToDate(event.target.value); setPeriodError(null); }} /></label>
          <button type="submit" className="orders-sales-apply" disabled={!periodEnabled}>기간 조회</button>
          <button type="button" className="orders-sales-reset" disabled={!periodEnabled} onClick={() => { setFromDate(""); setToDate(""); setPeriodError(null); onPeriodApply?.(null, null); }}>전체 기간</button>
        </div>
        {periodError ? <p role="alert" className="orders-sales-period-error">{periodError}</p> : null}
        {!onPeriodApply ? <p className="orders-sales-period-note">기간 입력 UI 준비 완료 · 집계 API 연결 후 조회 버튼이 활성화됩니다. 입력한 날짜는 아직 KPI에 반영되지 않습니다.</p> : null}
      </form>

      {error ? <section className="card card-body" role="alert"><strong>매출 집계 조회 실패</strong><p>{error}</p></section> : null}
      {loading ? <p role="status" className="orders-sales-loading">매출 집계를 불러오는 중입니다.</p> : null}
      <div className="orders-summary-grid orders-summary-grid--sales" aria-busy={loading}>
        {kpis.map((kpi) => <section className="card orders-summary-card" key={kpi.title}>
          <span className="orders-card-label">{kpi.title}</span>
          <strong className="orders-card-value">{hasData ? kpi.value : "—"}</strong>
          <span className="orders-card-caption">{hasData ? kpi.note : "집계 API 연결 대기"}</span>
        </section>)}
      </div>

      <div className="orders-sales-panels">
        <section className="card orders-analysis-card" aria-labelledby="orders-trend-title">
          <header className="orders-section-heading"><div><h3 id="orders-trend-title">일별 주문금액 추이</h3><p>KST 주문일 기준 · 주문금액 (원)</p></div></header>
          {daily === null ? <div className="orders-analysis-empty" role="status"><strong>일별 집계 데이터 연결 대기</strong><p>Backend 계약이 연결되면 날짜별 금액이 표시됩니다.</p></div>
            : daily.length === 0 ? <div className="orders-analysis-empty"><strong>선택 기간에 데이터가 없습니다</strong></div>
           : (
            <div className="orders-trend-layout">
  <div className="orders-trend-readout" aria-live="off">
    {hoveredDay ? (
      <>
        <strong>{hoveredDay.date}</strong>
        <span>
          주문금액 {hoveredDay.amount.toLocaleString("ko-KR")}원
        </span>
      </>
    ) : (
      <span>막대에 마우스를 올리면 정확한 주문금액을 확인할 수 있습니다.</span>
    )}
  </div>

  <div className="orders-trend-plot">
    <div className="orders-trend-y-axis" aria-hidden="true">
      {yTicks.map((tick) => (
        <span
          key={tick}
          className="orders-trend-y-tick"
          style={{ bottom: `${(tick / yAxisMax) * 100}%` }}
        >
          {tick === 0
            ? "0원"
            : `${(tick / 10_000).toLocaleString("ko-KR")}만원`}
        </span>
      ))}
    </div>

    <div className="orders-trend-scroll">
      <div className="orders-trend-chart">
        {daily.map((point) => {
          const valid =
            point.orderAmount !== null &&
            Number.isFinite(point.orderAmount) &&
            point.orderAmount >= 0;

          const amount = valid ? point.orderAmount! : null;

          return (
            <div className="orders-trend-item" key={point.date}>
              <div className="orders-trend-bar-track">
                {amount !== null ? (
                  <div
                    className="orders-trend-bar"
                    tabIndex={0}
                    role="img"
                    aria-label={`${point.date} 주문금액 ${amount.toLocaleString("ko-KR")}원`}
                    onMouseEnter={() =>
                      setHoveredDay({ date: point.date, amount })
                    }
                    onMouseLeave={() => setHoveredDay(null)}
                    onFocus={() =>
                      setHoveredDay({ date: point.date, amount })
                    }
                    onBlur={() => setHoveredDay(null)}
                    style={{
                      height: `${(amount / yAxisMax) * 100}%`,
                    }}
                  />
                ) : (
                  <span className="orders-chart-unknown">
                    미제공
                  </span>
                )}
              </div>

              <time
                className="orders-trend-date"
                dateTime={point.date}
              >
                {point.date.slice(5)}
              </time>
            </div>
          );
        })}
      </div>
    </div>
  </div>
</div>
          )}
        </section>
        <section className="card orders-analysis-card" aria-labelledby="orders-state-title">
          <header className="orders-section-heading"><div><h3 id="orders-state-title">주문 상태별 건수</h3><p>주문 단위 · 상태 그룹 간 중복 가능</p></div></header>
          {states === null ? <div className="orders-analysis-empty" role="status"><strong>상태별 집계 데이터 연결 대기</strong><p>결제·취소 상태별 집계는 Backend 계약에 맞춰 표시합니다.</p></div>
            : states.length === 0 ? <div className="orders-analysis-empty"><strong>선택 기간에 데이터가 없습니다</strong></div>
            : <div className="orders-state-bars">{validStates.map((state) => <div key={state.label} className="orders-state-row">
                <div className="orders-state-row-header"><span>{state.label}</span><strong>{state.count.toLocaleString("ko-KR")}건</strong></div>
                <div className="orders-state-track" role="meter" aria-label={state.label} aria-valuemin={0} aria-valuemax={Math.max(1,maxState)} aria-valuenow={state.count}>
                  <div className="orders-state-fill" style={{ width: `${maxState === 0 ? 0 : (state.count / maxState) * 100}%` }} />
                </div>
              </div>)}</div>}
        </section>
      </div>
      <details className="orders-analysis-notice"><summary>지표 해석 및 데이터 제한 안내</summary>
        <p>총 주문금액과 결제 표시 금액은 Synthetic 주문 필드 기반이며 실제 입금·정산 완료액이 아닙니다.</p>
        <p>환불 금액·결제일·판매 채널 구분이 없어 순매출·결제일 매출·Cafe24/Toss 비교는 제공하지 않습니다.</p>
        <p>금액 미제공은 0이 아니며, 결제·취소 상태 그룹은 서로 배타적이지 않을 수 있습니다.</p>
      </details>
    </div>
  );
}

// SalesAnalysisPanel 아래, export default function OrdersPage() 바로 위에 삽입합니다.
// import: import { getSalesSummary, type SalesSummaryData } from "../../api/salesSummary";

// 사용자 확인: 현재 Synthetic Demo 주문금액은 모두 원화입니다.
// Backend 원천의 currency=null 계약은 변경하지 않습니다.
function formatSyntheticAmount(value: string | null): string {
  if (value === null) return "미제공";
  if (!/^-?\d+(?:\.\d+)?$/.test(value)) return "미제공";

  const [whole, fractional = ""] = value.split(".");
  const grouped = BigInt(whole).toLocaleString("ko-KR");
  const usefulFraction = fractional.replace(/0+$/, "");

  return `${grouped}${usefulFraction ? `.${usefulFraction}` : ""}원`;
}

function toSafeChartNumber(value: string | null): number | null {
  if (value === null || !/^(?:0|[1-9]\d*)(?:\.\d+)?$/.test(value)) return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) && numeric >= 0 && numeric <= Number.MAX_SAFE_INTEGER ? numeric : null;
}

function mapSalesData(data: SalesSummaryData): SalesDisplayData {
  const canceled = data.statuses.canceled;
  const uncertainOrCanceledCount = canceled.T + canceled.M;
  return {
    periodLabel: data.from_date || data.to_date
      ? `${data.from_date ?? "전체 시작"} ~ ${data.to_date ?? "전체 종료"} · KST 주문일 기준`
      : "전체 기간 · KST 주문일 기준",
    totalOrderAmount: formatSyntheticAmount(data.order_amount.amount),
    paidMarkedAmount: formatSyntheticAmount(data.paid_amount.amount),
    orderCount: data.order_count,
    uncertainOrCanceledCount,
    daily: data.daily.map((item) => ({
      date: item.order_date,
      orderAmount: toSafeChartNumber(item.order_amount.amount),
    })),
    states: [
      { label: "결제 예", count: data.statuses.paid.T },
      { label: "결제 아니요", count: data.statuses.paid.F },
      { label: "취소 예", count: canceled.T },
      { label: "취소 아니요", count: canceled.F },
      { label: "취소 확인 필요", count: canceled.M },
    ],
  };
}

export function SalesSummaryContainer() {
  const [period, setPeriod] = useState<{ from_date?: string; to_date?: string }>({});
  const [data, setData] = useState<SalesDisplayData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(usingBackend);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!usingBackend) return;
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    void getSalesSummary(period, controller.signal)
      .then((response) => {
        if (!controller.signal.aborted) setData(mapSalesData(response.data));
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) {
          setData(null);
          setError(reason instanceof Error ? reason.message : "매출 집계를 불러오지 못했습니다.");
        }
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [period, reloadKey]);

  return (
    <div>
      <SalesAnalysisPanel
        data={data}
        loading={loading}
        error={error}
        onPeriodApply={usingBackend ? (fromDate, toDate) => {
          setPeriod({ from_date: fromDate ?? undefined, to_date: toDate ?? undefined });
        } : undefined}
      />
      {error && usingBackend && (
        <button type="button" className="orders-action-button" onClick={() => setReloadKey((key) => key + 1)}>
          매출 집계 다시 시도
        </button>
      )}
    </div>
  );
}


export default function OrdersPage() {
  const [activeTab, setActiveTab] = useState<OrdersTab>("orders");
  const [reservationItems, setReservationItems] = useState<ReservationRiskItem[] | null>(null);
  const [reservationWarnings, setReservationWarnings] = useState<string[]>([]);
  const [reservationError, setReservationError] = useState<string | null>(null);
  const [recentSummary, setRecentSummary] = useState<RecentOrderSummary | null>(null);
  const [recentSummaryError, setRecentSummaryError] = useState(false);
  const [recentSummaryLoading, setRecentSummaryLoading] = useState(usingBackend);
  const [allOrdersCount, setAllOrdersCount] = useState<number | null>(null);

  useEffect(() => {
    if (!usingBackend) return;
    const controller = new AbortController();

    void getDay09Reservations(controller.signal)
      .then((response) => {
        if (controller.signal.aborted) return;
        setReservationItems(response.data);
        setReservationWarnings(response.warnings);
        setReservationError(null);
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setReservationError("예약 위험 Backend Projection을 불러오지 못했습니다.");
        }
      });

    void getRecentOrderSummary(controller.signal)
      .then((response) => {
        if (controller.signal.aborted) return;
        setRecentSummary(response.data);
        setRecentSummaryError(false);
      })
      .catch(() => {
        if (!controller.signal.aborted) setRecentSummaryError(true);
      })
      .finally(() => {
        if (!controller.signal.aborted) setRecentSummaryLoading(false);
      });

    return () => controller.abort();
  }, []);

  const recentAvailable = recentSummary?.status === "AVAILABLE";

  return (
    <div className="page inventory-page orders-page" data-testid="route-orders">
      <header className="inventory-page-heading orders-page-heading">
        <h1>주문 · 매출</h1>
        <span className="orders-data-label">합성 데이터 · 조회 전용</span>
      </header>

      <div className="inventory-page-tabs" role="tablist" aria-label="주문·매출 보기">
        <button
          type="button" id="orders-list-tab" role="tab"
          aria-selected={activeTab === "orders"}
          aria-controls="orders-list-panel"
          tabIndex={activeTab === "orders" ? 0 : -1}
          onClick={() => setActiveTab("orders")}
        >
          주문 목록
        </button>
        <button
          type="button" id="orders-sales-tab" role="tab"
          aria-selected={activeTab === "sales"}
          aria-controls="orders-sales-panel"
          tabIndex={activeTab === "sales" ? 0 : -1}
          onClick={() => setActiveTab("sales")}
        >
          매출 분석
        </button>
      </div>

      <section
        id="orders-list-panel" role="tabpanel" aria-labelledby="orders-list-tab"
        className="inventory-tab-panel orders-tab-content" hidden={activeTab !== "orders"}
      >
        <div className="orders-summary-grid">
          <section className="card orders-summary-card">
            <span className="orders-card-label">최근 주문일의 주문 건수</span>
            <strong className="orders-card-value">
              {recentSummaryLoading ? "조회 중" : recentAvailable ? recentSummary.order_count.toLocaleString("ko-KR") + "건" : "—"}
            </strong>
            <span className="orders-card-caption">
              {recentAvailable ? `${recentSummary.reference_date} · 전체 상태 포함` :
                recentSummaryError ? "요약 조회 실패" : "확인 가능한 집계 없음"}
            </span>
          </section>
          <section className="card orders-summary-card">
            <span className="orders-card-label">조회 조건 일치 주문 건수</span>
            <strong className="orders-card-value">{allOrdersCount === null ? "—" : `${allOrdersCount.toLocaleString("ko-KR")}건`}</strong>
            <span className="orders-card-caption">{allOrdersCount === null ? "주문 목록 조회 전 또는 실패" : "현재 필터에 일치하는 주문 건수"}</span>
          </section>
          <section className="card orders-summary-card">
            <span className="orders-card-label">주문 조회 출처</span>
            <strong className="orders-card-value orders-card-value--text">Synthetic Demo</strong>
            <span className="orders-card-caption">운영 데이터가 아닙니다</span>
          </section>
        </div>
        <details className="orders-reservation-disclosure">
          <summary>
            <span>예약주문 위험 현황</span>
            <span className="orders-reservation-hint">
              상세 보기
            </span>
          </summary>

        <section className="orders-reservation-section" aria-label="예약 위험 현황">
          {!usingBackend ? (
            <section className="card card-body" data-testid="reservation-fixture-placeholder">
              <strong>예약 위험 테스트 화면</strong>
              <p className="muted">Mock 모드에서는 Day 9 Fixture를 실제 Backend 데이터로 표시하지 않습니다.</p>
            </section>
          ) : reservationError ? (
            <section className="card card-body" data-testid="reservation-error">
              <strong>예약 위험 정보를 불러오지 못했습니다</strong>
              <p className="muted">{reservationError}</p>
            </section>
          ) : reservationItems === null ? (
            <section className="card card-body" data-testid="reservation-loading">
              <strong>예약 위험 정보를 불러오는 중입니다</strong>
            </section>
          ) : (
            <div className="orders-reservation-results">
              {reservationWarnings.length > 0 && (
                <details className="inventory-safety-notice" data-testid="reservation-warning">
                  <summary>예약 위험 데이터 확인 안내 · 상세 보기</summary>
                  <div className="inventory-safety-notice-detail">
                    <ul>{reservationWarnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
                  </div>
                </details>
              )}
              <ReservationList items={reservationItems} showPolicyExplanation />
            </div>
          )}
        </section>
        </details>
        <OrderListBrowser serverMode={usingBackend} onTotalChange={setAllOrdersCount} />
      </section>

      <section
        id="orders-sales-panel" role="tabpanel" aria-labelledby="orders-sales-tab"
        className="inventory-tab-panel orders-tab-content" hidden={activeTab !== "sales"}
        data-testid="sales-analysis-panel"
      >
        <SalesSummaryContainer />
      </section>
    </div>
  );
}
