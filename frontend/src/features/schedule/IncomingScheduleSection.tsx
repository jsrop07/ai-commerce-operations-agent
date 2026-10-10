import { useEffect, useState } from "react";
import { useOptionalCommonAiDrawer } from "../../app/CommonAiDrawerContext";
import { getCatalogProducts } from "../../api/catalog";
import { getShortageAnalysis, type ShortageAnalysis } from "../../api/reservationShortage";
import {
  getIncomingSchedules,
  type IncomingSchedulesData,
} from "../../api/scheduleIncoming";

type LoadState = "loading" | "ready" | "error";

const incomingLabels: Record<string, string> = {
  EXPECTED: "입고 예정",
  CONFIRMED: "입고 예정 확인",
  RECEIVED: "입고 완료",
  CANCELED: "취소",
};
const taskTitleLabels: Record<string, string> = {
  RESERVATION_SHORTAGE: "예약 수량 확보 검토",
};
const taskLabels: Record<string, string> = {
  PROPOSED: "검토 예정",
  APPROVED: "승인됨",
  IN_PROGRESS: "진행 중",
  DONE: "완료",
  BLOCKED: "보류",
  DISMISSED: "제외",
};
const confidenceLabels: Record<string, string> = {
  CONFIRMED: "확인됨",
  TENTATIVE: "잠정",
  UNKNOWN: "확인 필요",
};

function formatDate(value: string | null): string {
  if (!value) return "일정 미정";
  const ms = Date.parse(value);
  return Number.isFinite(ms)
    ? new Intl.DateTimeFormat("ko-KR", {
        dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Seoul",
      }).format(ms)
    : "날짜 확인 필요";
}

function focusScheduleTarget() {
  const focus = new URLSearchParams(window.location.search).get("focus");

  if (focus !== "reservation" && focus !== "tasks") return;

  window.requestAnimationFrame(() => {
    const target =
        focus === "reservation"
            ? document.getElementById("schedule-reservation-review")
            : document.querySelector(".schedule-incoming-tasks");

    target?.scrollIntoView({
      behavior: "smooth",
      block: "center",
    });
  });
}

export default function IncomingScheduleSection() {
  const ai = useOptionalCommonAiDrawer();
  const backendMode = import.meta.env.VITE_USE_REAL_BACKEND === "true";
  const [state, setState] = useState<LoadState>("loading");
  const [data, setData] = useState<IncomingSchedulesData | null>(null);
  const [productNames, setProductNames] = useState<Record<string, string>>({});
  const [productLookupUnavailable, setProductLookupUnavailable] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [shortage, setShortage] = useState<ShortageAnalysis | null>(null);
  const [shortageError, setShortageError] = useState(false);

  useEffect(() => {
    if (!backendMode) return;
    const controller = new AbortController();
    setState("loading");
    setError(null);
    setData(null);
    setProductNames({});
    setProductLookupUnavailable(false);
    setShortage(null);
    setShortageError(false);
    void getShortageAnalysis(controller.signal).then((result) => {
      if (!controller.signal.aborted) setShortage(result);
    }).catch(() => {
      if (!controller.signal.aborted) setShortageError(true);
    });

    // 입고 조회는 상품명 조회와 독립적으로 성공/실패해야 합니다.
    void getIncomingSchedules(controller.signal).then((response) => {
      if (controller.signal.aborted) return;
      setData(response.data);
      setState("ready");
      if (response.data.items.length === 0) return;

      // 기존 상품 목록 API를 재사용해 product_id와 product_name을 연결합니다.
      // Synthetic 상품 150건을 한 번에 조회할 수 있는 기존 limit(최대 200) 계약입니다.
      void getCatalogProducts(200, 0, controller.signal).then((catalog) => {
        if (controller.signal.aborted) return;
        const names: Record<string, string> = {};
        for (const product of catalog.data.items) {
          if (product.product_name.trim()) names[product.id] = product.product_name;
        }
        setProductNames(names);
        setProductLookupUnavailable(catalog.data.total > catalog.data.items.length);
      }).catch(() => {
        if (!controller.signal.aborted) setProductLookupUnavailable(true);
      });
    }).catch((cause: unknown) => {
      if (controller.signal.aborted) return;
      setError(cause instanceof Error ? cause.message : "입고 일정 조회 중 오류가 발생했습니다.");
      setState("error");
    });
    return () => controller.abort();
  }, [attempt, backendMode]);

  useEffect(() => {
    if (state !== "ready") return;

    focusScheduleTarget();
    }, [state, shortage]);

  if (!backendMode) return null;
  return (
    <section className="card schedule-incoming-section" aria-labelledby="schedule-incoming-heading">
      <div className="card-header schedule-incoming-heading">
        <h3 id="schedule-incoming-heading">입고 예정 일정</h3>
        {state === "ready" && data && <span className="schedule-incoming-count">{data.total}건</span>}
      </div>
      {state === "loading" && <div className="card-body" role="status">입고 일정을 불러오는 중입니다.</div>}
      {state === "error" && <div className="card-body" role="alert">
        <strong>입고 일정을 불러오지 못했습니다.</strong>
        <p className="muted">{error}</p>
        <button type="button" className="filter" onClick={() => setAttempt((n) => n + 1)}>다시 시도</button>
      </div>}
      {state === "ready" && data?.items.length === 0 &&
        <div className="card-body">등록된 입고 예정 일정이 없습니다.</div>}
      {state === "ready" && data && data.items.length > 0 && (
        <div className="schedule-incoming-list">
          {data.items.map((incoming) => {
            const name = productNames[incoming.product_id];
            return (
              <article className="schedule-incoming-item" key={incoming.id}>
                <div className="schedule-incoming-title">
                  <strong>{name ?? "상품명 확인 필요"}</strong>
                  <span className="badge">{incomingLabels[incoming.incoming_status] ?? incoming.incoming_status}</span>
                  {ai && <button type="button" className="filter" onClick={() => ai.openAiDrawer({
                    targetType: "INCOMING", targetId: incoming.id,
                    targetLabel: `INCOMING ${incoming.id}`, source: "OPERATIONS_INCOMING", asOf: null,
                  })}>이 입고로 업무 이어보기</button>}
                </div>
                <div className="schedule-incoming-meta">
                  <span>입고 예정일 <strong>{formatDate(incoming.expected_arrival_at)}</strong></span>
                  <span>확인 상태 <strong>{confidenceLabels[incoming.confidence_status] ?? "확인 필요"}</strong></span>
                </div>
                {productLookupUnavailable && !name && (
                  <p className="schedule-incoming-subtle">상품 정보를 조회할 수 없습니다.</p>
                )}
                {incoming.related_tasks.length > 0 && (
                  <details
                    id={incoming.related_tasks.length > 0
                        ? `schedule-related-tasks-${incoming.id}`
                        : undefined}
                    className="schedule-incoming-tasks"
                    open={
                        new URLSearchParams(window.location.search).get("focus") === "tasks"
                    }
                    >
                    <summary>관련 업무 {incoming.related_tasks.length}건</summary>
                    <div className="schedule-incoming-task-list">
                      {incoming.related_tasks.map((task) => (
                        <div key={task.id} className="schedule-incoming-task">
                          <strong>{taskTitleLabels[task.task_type] ?? task.title}</strong>
                          <span>{taskLabels[task.status] ?? task.status} · 마감 {formatDate(task.due_at)}</span>
                          {ai && <button type="button" className="filter" onClick={() => ai.openAiDrawer({
                            targetType: "TASK", targetId: task.id,
                            targetLabel: `TASK ${task.id}`, source: "OPERATIONS_TASK", asOf: null,
                          })}>이 Task로 업무 이어보기</button>}
                        </div>
                      ))}
                    </div>
                  </details>
                )}
                <details className="schedule-incoming-technical">
                  <summary>상세 정보</summary>
                  <dl>
                    <div><dt>입고번호</dt><dd>{incoming.external_reference ?? "미제공"}</dd></div>
                    <div><dt>상품 ID</dt><dd>{incoming.product_id}</dd></div>
                    <div><dt>입고 ID</dt><dd>{incoming.id}</dd></div>
                    <div><dt>원천 기준 시각</dt><dd>미제공</dd></div>
                  </dl>
                </details>
              </article>
            );
          })}
        </div>
      )}
      {shortage && (
        <div
            id="schedule-reservation-review"
            className="card-body"
            role="status"
        >
          <strong>예약 수량 확보 검토 · SYNTHETIC_DEMO</strong>
          <p>필요 {shortage.required_quantity}개 · 확보 {shortage.secured_quantity ?? "미확인"}개 · 약속일 {shortage.promised_date ?? "미확인"}</p>
          <p>현재 미확보 수량 {shortage.baseline_unsecured_quantity ?? "판정 불가"}개. 이는 입고 예정 수량을 아직 확보로 세지 않은 값입니다.</p>
          {shortage.status === "CONDITIONAL" && shortage.conditional_shortage_quantity !== null ? (
            <p>예정 입고 {shortage.conditional_incoming_quantity}개가 약속일 전에 실제 사용 가능하고 이 예약에 배분된다면 남는 수량은 {shortage.conditional_shortage_quantity}개입니다. 수령·배분은 확인되지 않았습니다.</p>
          ) : <p>예정 입고를 반영한 부족 수량은 현재 판정할 수 없습니다.</p>}
          <p className="muted">입고 원천 기준 시각 미제공 · 재고 Snapshot 기준 {shortage.inventory_data_as_of ?? "미확인"} · 기존 Task 관계는 시나리오 참조입니다.</p>
        </div>
      )}
      {shortageError && <div className="card-body" role="alert">예약 수량 검토를 확인할 수 없습니다. 입고 일정과 별개의 조회입니다.</div>}
    </section>
  );
}
