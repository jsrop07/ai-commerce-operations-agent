import type { DashboardQueueData, DashboardQueueItem } from "../api/dashboardQueue";

type Props = {
  data: DashboardQueueData | null;
  error: boolean;
  onRefresh: () => void;
};

const stateLabels: Record<DashboardQueueItem["state"], string> = {
  CONDITIONAL: "조건부 확보 검토",
  DATA_STALE: "데이터 최신성 부족",
  REVIEW_PENDING: "등록된 업무 검토 대기",
};

function sourceTime(value: string | null) {
  if (!value) return "기준 시각 미제공";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "기준 시각 확인 필요" :
    `자료 기준 ${date.toLocaleString("ko-KR", { timeZone: "Asia/Seoul" })}`;
}

function navigate(event: React.MouseEvent<HTMLAnchorElement>, path: string) {
  event.preventDefault();
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

export default function OperationalUrgentQueue({ data, error, onRefresh }: Props) {
  // Registered Tasks appear in Today's Tasks; they are not another calculated risk.
  const items = data?.items.filter((item) => item.kind !== "TASK_REVIEW") ?? [];
  const status = error ? "조회 실패" : data === null ? "조회 중" :
    data.status === "NO_DATA" ? "원천 데이터 없음" :
      data.status === "ANALYSIS_UNAVAILABLE" ? "일부 분석 불가" :
      data.status === "CLEAR" || items.length === 0 ? "계산된 검토 항목 없음" : `${items.length}건`;
  return <section className="urgent-queue-section" aria-labelledby="urgent-queue-title">
    <div className="urgent-section-header">
      <div><h2 id="urgent-queue-title" className="section-title">긴급 Queue</h2>
        <p className="muted section-description">DB 원천과 규칙 계산으로 페이지 조회 시 확인한 항목입니다.</p></div>
      <div className="urgent-header-meta"><span className="badge source">{status}</span>
        <button type="button" className="filter" onClick={onRefresh}>다시 조회</button></div>
    </div>
    {error && <p role="alert">운영 Queue를 조회하지 못했습니다. 위험이 없다는 뜻은 아닙니다.</p>}
    {!error && data === null && <p role="status">운영 Queue를 계산하는 중입니다.</p>}
    {!error && data?.status === "NO_DATA" && <p>조회 가능한 예약·재고·관련 Task 원천이 없습니다.</p>}
    {!error && data?.status === "CLEAR" && <p>조회한 원천에서 현재 표시할 검토 항목이 없습니다.</p>}
    {!error && data?.status === "READY" && items.length === 0 &&
      <p>계산된 검토 항목은 없습니다. 등록된 업무는 오늘 할 일에서 확인하세요.</p>}
    {!error && data?.status === "ANALYSIS_UNAVAILABLE" && <p role="status">일부 원천의 분석을 완료하지 못했습니다. 표시된 항목만 확인해 주세요.</p>}
    {!error && items.length > 0 && <div className="urgent-queue-list">
      {items.map((item) => <article className={`urgent-card urgent-card-${item.priority?.toLowerCase() ?? "unknown"}`} key={item.id}>
        <div className="urgent-card-top"><span className="badge source">{stateLabels[item.state]}</span>
          <span className="urgent-as-of">{sourceTime(item.source_as_of)}</span></div>
        <h3>{item.kind === "INVENTORY_STALE" ? "재고 수량 기준 확인 필요" : item.title}</h3>
        <p className="urgent-reason">{item.kind === "INVENTORY_STALE"
          ? "재고 자료의 최신성 또는 품질을 확인할 수 없어 현재 위험도를 판정할 수 없습니다."
          : item.reason}</p>
        <details
          className="urgent-evidence"
          style={{
            marginTop: 12,
            marginBottom: 12,
            border: "1px solid #ded8c9",
            borderRadius: 8,
            padding: "10px 12px",
            background: "#f7f5ef",
          }}
        >
          <summary
            style={{
              cursor: "pointer",
              fontWeight: 600,
              color: "#464d39",
              padding: "4px 0",
            }}
          >
            판단 근거 펼쳐보기
          </summary>

          <div style={{ paddingTop: 12 }}>
            <p>
              {item.kind === "CONDITIONAL_RESERVATION"
                ? "예약 필요 수량과 현재 확보 수량을 비교하고, 조건에 맞는 예정 입고를 반영해 계산했습니다. 예정 입고는 실제 수령·예약 배분이 확인되기 전까지 확보 수량으로 확정하지 않습니다."
                : "재고 자료의 기준 시각 또는 품질을 충분히 검증하지 못했습니다. 따라서 실제 재고 부족 여부는 아직 확정할 수 없습니다."}
            </p>
            <p className="muted">
              {sourceTime(item.source_as_of)}
            </p>
          </div>
        </details>
        <a
          href={
            item.kind === "CONDITIONAL_RESERVATION"
              ? "/schedule?focus=reservation"
              : item.target_path
          }
          onClick={(event) => {
            const destination =
              item.kind === "CONDITIONAL_RESERVATION"
                ? "/schedule?focus=reservation"
                : item.target_path;

            navigate(event, destination);
          }}
        >
          {item.kind === "CONDITIONAL_RESERVATION"
            ? "예약 수량 검토 확인"
            : item.target_path === "/schedule"
              ? "운영 일정에서 확인"
              : "상품·재고에서 확인"}
        </a>
      </article>)}
    </div>}
  </section>;
}
