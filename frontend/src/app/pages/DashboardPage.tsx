import { useEffect, useRef, useState } from "react";
import { AIBadge } from "../../components/Badges";
import { FreshnessBadge } from "../../components/StatusBadges";
import {
  getProviderFailureReasonLabel,
  getProviderLabel,
} from "../../components/statusLabels";
import { mockApiGet } from "../../mocks/handlers";
import { mockGetEvidenceByRequestId } from "../../mocks/evidence";
import type {
  ApiEnvelope,
  DashboardData,
  InsightSummary,
  InventorySnapshot,
  ReservationRiskItem,
  ReservationShortageTask,
  ScheduleTask,
} from "../../types/contracts";
import EvidenceDrawer from "../../components/EvidenceDrawer";
import SystemState from "../../components/SystemStates";
import UrgentQueue from "../../components/UrgentQueue";
import { urgentQueueFixtures } from "../../mocks/fixtures/urgentQueue";
import TodayTasks from "../../components/TodayTasks";
import { getDay10Tasks } from "../../api/day10";
import { getDay09Reservations } from "../../api/day09";

import {
  getDay04Insights,
  toUrgentQueueItems,
  useRealBackend,
  type C04Key,
} from "../../api/day04";
import { providerFailureFixture } from "../../mocks/fixtures/degradedDashboard";
import type { UrgentQueueInsight } from "../../components/UrgentQueue";
import { getCatalogSummary } from "../../api/catalog";
import { getDay08Inventory } from "../../api/day08";
import {
  getRecentOrderSummary,
  type RecentOrderSummary,
} from "../../api/orders";

export default function DashboardPage() {
  const degraded =
    new URLSearchParams(window.location.search).get("degraded") === "true";
  const [dashboard, setDashboard] =
    useState<ApiEnvelope<DashboardData> | null>(null);
  const [productCount, setProductCount] = useState<number | null>(null);
  const [productCountError, setProductCountError] = useState(false);
  const [recentOrders, setRecentOrders] =
    useState<RecentOrderSummary | null>(null);

  const [recentOrdersLoaded, setRecentOrdersLoaded] =
    useState(false);

  const [recentOrdersUnavailable, setRecentOrdersUnavailable] =
    useState(false);
  const [inventoryItems, setInventoryItems] =
    useState<InventorySnapshot[]>([]);

  const [inventoryLoaded, setInventoryLoaded] = useState(false);

  const [inventoryUnavailable, setInventoryUnavailable] = useState(false);

  const [urgentItems, setUrgentItems] =
    useState<ApiEnvelope<UrgentQueueInsight>[]>(
      useRealBackend ? [] : urgentQueueFixtures,
    );
  const [insightsUnavailable, setInsightsUnavailable] = useState(false);
  const [insightsLoaded, setInsightsLoaded] = useState(false);
  const [shortageTasks, setShortageTasks] = useState<ReservationShortageTask[]>([]);
  const [allTasks, setAllTasks] =
  useState<(ScheduleTask | ReservationShortageTask)[]>([]);
  const [reservations, setReservations] = useState<ReservationRiskItem[]>([]);
  const [tasksUnavailable, setTasksUnavailable] = useState(false);
  const [tasksLoaded, setTasksLoaded] = useState(false);
  const [taskProjectionEmpty, setTaskProjectionEmpty] = useState(false);

  const [reservationsLoaded, setReservationsLoaded] = useState(false);
  const [reservationsUnavailable, setReservationsUnavailable] = useState(false);
  const [reservationRiskEmpty, setReservationRiskEmpty] = useState(false);

  const [selectedInsight, setSelectedInsight] =
    useState<InsightSummary | null>(null);
  const [selectedC04Key, setSelectedC04Key] = useState<C04Key | undefined>();

  const [evidenceMissing, setEvidenceMissing] =
    useState(false);
  const mountedRef = useRef(true);
  const evidenceRequestRef = useRef(0);
  useEffect(() => {
    let active = true;
    mountedRef.current = true;
    const controller = new AbortController();

    if (useRealBackend) {
      getCatalogSummary(controller.signal)
        .then((response) => {
          if (!active || controller.signal.aborted) return;

          setProductCount(response.data.product_count);
          setProductCountError(false);
        })
        .catch(() => {
          if (!active || controller.signal.aborted) return;

          setProductCount(null);
          setProductCountError(true);
        });
    }

    if (useRealBackend) {
      getDay08Inventory(controller.signal)
        .then((response) => {
          if (!active || controller.signal.aborted) return;

          setInventoryItems(response.data);
          setInventoryLoaded(true);
          setInventoryUnavailable(false);
        })
        .catch(() => {
          if (!active || controller.signal.aborted) return;

          setInventoryItems([]);
          setInventoryLoaded(false);
          setInventoryUnavailable(true);
        });
    }
    if (useRealBackend) {
      getRecentOrderSummary(controller.signal)
        .then((response) => {
          if (!active || controller.signal.aborted) return;

          setRecentOrders(response.data);
          setRecentOrdersLoaded(true);
          setRecentOrdersUnavailable(false);
        })
        .catch(() => {
          if (!active || controller.signal.aborted) return;

          setRecentOrders(null);
          setRecentOrdersLoaded(false);
          setRecentOrdersUnavailable(true);
        });
    }
    if (!useRealBackend) {
      mockApiGet<ApiEnvelope<DashboardData>>(
        "/api/v1/dashboard",
      ).then((response) => {
        if (active) setDashboard(response);
      });
    }

    if (useRealBackend) {
      // Task 조회: 다른 API의 성공·실패와 독립적으로 처리
      getDay10Tasks(controller.signal)
        .then((response) => {
          if (!active || controller.signal.aborted) return;

          setAllTasks(response.data);
          setTaskProjectionEmpty(
            response.data.length === 0 &&
              response.warnings.some((warning) =>
                warning.startsWith("TASKS_EMPTY")
              )
          );
          setShortageTasks(
            response.data.filter(
              (task): task is ReservationShortageTask =>
                "reservation_id" in task
            )
          );

          setTasksUnavailable(false);
          setTasksLoaded(true);
        })
        .catch(() => {
          if (!active || controller.signal.aborted) return;

          setAllTasks([]);
          setShortageTasks([]);

          setTasksUnavailable(true);
          setTasksLoaded(false);
          setTaskProjectionEmpty(false);
        });

      // Reservation 조회: Task 조회와 독립적으로 처리
      getDay09Reservations(controller.signal)
        .then((response) => {
          if (!active || controller.signal.aborted) return;

          setReservations(response.data);

          setReservationRiskEmpty(
            response.data.length === 0 &&
            response.warnings.some((warning) =>
              warning.startsWith("RESERVATION_RISK_EMPTY")
            )
          );

          setReservationsUnavailable(false);
          setReservationsLoaded(true);
        })
        .catch(() => {
          if (!active || controller.signal.aborted) return;

          setReservations([]);

          setReservationsUnavailable(true);
          setReservationsLoaded(false);

          setReservationRiskEmpty(false);
        });
      setUrgentItems([]);
      getDay04Insights(controller.signal)
        .then((response) => {
          if (!active || controller.signal.aborted) return;

          setUrgentItems(toUrgentQueueItems(response));
          setInsightsUnavailable(false);
          setInsightsLoaded(true);
        })
        .catch((error: unknown) => {
          if (
            active &&
            !(error instanceof DOMException && error.name === "AbortError")
          ) {
            setUrgentItems([]);
            setInsightsUnavailable(true);
            setInsightsLoaded(false);
          }
        });
    }

    return () => {
      active = false;
      mountedRef.current = false;
      evidenceRequestRef.current += 1;
      controller.abort();
    };
  }, []);

  async function openEvidence(requestId: string) {
    const requestNumber = ++evidenceRequestRef.current;
    setEvidenceMissing(false);

    // Actual evidence is selected by insight, never by envelope request_id.
    if (useRealBackend) {
      setSelectedInsight(null);
      setEvidenceMissing(true);
      return;
    }

    const response =
      await mockGetEvidenceByRequestId(requestId);

    if (!mountedRef.current || requestNumber !== evidenceRequestRef.current) {
      return;
    }

    if (!response) {
      setSelectedInsight(null);
      setEvidenceMissing(true);
      return;
    }

    setSelectedInsight(response.data);
  }

  function openActualEvidence(insight: UrgentQueueInsight) {
    evidenceRequestRef.current += 1;
    setSelectedInsight(null);
    setEvidenceMissing(false);
    setSelectedC04Key(insight.c04_lookup);
  }

  // 사람이 검토하거나 별도 조치해야 하는 업무만 집계
  const reviewTaskCount = allTasks.filter(
    (task) =>
      task.status === "PROPOSED" ||
      task.status === "BLOCKED"
  ).length;

  // 품질과 최신성이 확인된 재고 중 위험도가 높은 항목
  const confirmedInventoryRiskCount = inventoryItems.filter(
    (item) =>
      item.freshness === "FRESH" &&
      item.confirmed_for_total === true &&
      (item.quality_status === "USABLE" ||
        item.quality_status === "CONFIRMED") &&
      (item.risk_level === "HIGH" ||
        item.risk_level === "PROHIBITED")
  ).length;

  // 최신성·품질·위험 판정이 충분하지 않은 재고
  const unverifiedInventoryCount = inventoryItems.filter(
    (item) =>
      item.freshness !== "FRESH" ||
      item.confirmed_for_total !== true ||
      (item.quality_status !== "USABLE" &&
        item.quality_status !== "CONFIRMED") ||
      item.risk_level == null ||
      item.risk_level === "UNKNOWN"
  ).length;

  // Dashboard에서 현재 확인이 필요한 일반 업무만 표시
  const scheduleTasks = allTasks.filter(
    (task): task is ScheduleTask =>
      !("reservation_id" in task) &&
      (task.status === "PROPOSED" ||
        task.status === "BLOCKED")
  );
  
  // 부족 수량과 데이터 품질이 모두 확인된 예약만 집계
  const confirmedShortageCount = reservations.filter(
    (reservation) =>
      reservation.shortage_state === "KNOWN" &&
      reservation.quality_status === "CONFIRMED" &&
      typeof reservation.shortage === "number" &&
      Number.isFinite(reservation.shortage) &&
      reservation.shortage > 0
  ).length;

  // 부족 여부 또는 품질을 확정할 수 없는 예약
  const unverifiedReservationCount = reservations.filter(
    (reservation) =>
      reservation.shortage_state !== "KNOWN" ||
      reservation.quality_status !== "CONFIRMED" ||
      typeof reservation.shortage !== "number" ||
      !Number.isFinite(reservation.shortage)
  ).length;

  if (useRealBackend) {
    
    return <div className="page flush" data-testid="route-dashboard">
      <section
        className="dashboard-kpi-strip"
        aria-label="핵심 운영 지표"
      >
        <article className="kpi kpi-product">
          <div className="kpi-top">
            <span className="kpi-icon" aria-hidden="true">▦</span>
            <span className="kpi-status">Catalog</span>
          </div>
          <div className="kpi-value">
            {productCountError
              ? "확인 불가"
              : productCount === null
                ? "조회 중"
                : `${productCount.toLocaleString("ko-KR")}개`}
          </div>
          <div className="kpi-label">총 상품</div>
        </article>

        {[
          {
            label: "최근 주문",
            description: recentOrdersUnavailable
              ? "주문 정보 조회 실패"
              : !recentOrdersLoaded
                ? "최근 주문 조회 중"
                : recentOrders?.status === "NO_DATA"
                  ? "주문 데이터 없음"
                  : recentOrders?.status === "AVAILABLE"
                    ? `기준일 ${recentOrders.reference_date.replace(
                        /-/g,
                        ".",
                      )} · KST`
                    : "주문 정보 확인 불가",
            icon: "↗",
            type: "order",
            status: recentOrdersUnavailable
              ? "조회 실패"
              : !recentOrdersLoaded
                ? "조회 중"
                : recentOrders?.status === "NO_DATA"
                  ? "데이터 없음"
                  : "합성 데이터",
            value: recentOrdersUnavailable
              ? "확인 불가"
              : !recentOrdersLoaded
                ? "조회 중"
                : recentOrders?.status === "AVAILABLE"
                  ? `${recentOrders.order_count.toLocaleString("ko-KR")}건`
                  : "—",
          },
          {
            label: "재고 위험",
            description: inventoryUnavailable
              ? "재고 정보 조회 실패"
              : !inventoryLoaded
                ? "재고 정보 조회 중"
                : inventoryItems.length === 0
                  ? "조회된 재고 Snapshot 없음"
                  : unverifiedInventoryCount > 0
                    ? `판정 불가 ${unverifiedInventoryCount}건 별도`
                    : "확정된 고위험 재고",
            icon: "!",
            type: "risk",
            status: inventoryUnavailable
              ? "조회 실패"
              : !inventoryLoaded
                ? "조회 중"
                : inventoryItems.length === 0
                  ? "데이터 없음"
                  : unverifiedInventoryCount > 0
                    ? "일부 미확인"
                    : "조회 완료",
            value: inventoryUnavailable
              ? "확인 불가"
              : !inventoryLoaded
                ? "조회 중"
                : inventoryItems.length === 0
                  ? "—"
                  : unverifiedInventoryCount === inventoryItems.length
                    ? "—"
                    : `${confirmedInventoryRiskCount}건`,
          },
          {
            label: "예약 부족",
            description: reservationsUnavailable
              ? "예약 정보 조회 실패"
              : !reservationsLoaded
                ? "예약 정보 조회 중"
                : reservationRiskEmpty
                  ? "사용 가능한 예약 위험 데이터 없음"
                  : unverifiedReservationCount > 0
                    ? `판정 불가 ${unverifiedReservationCount}건 별도`
                    : "확정된 부족 예약",
            icon: "◷",
            type: "reservation",
            status: reservationsUnavailable
              ? "조회 실패"
              : !reservationsLoaded
                ? "조회 중"
                : reservationRiskEmpty
                  ? "데이터 없음"
                  : unverifiedReservationCount > 0
                    ? "일부 미확인"
                    : "조회 완료",
            value: reservationsUnavailable
              ? "확인 불가"
              : !reservationsLoaded
                ? "조회 중"
                : reservationRiskEmpty
                  ? "—"
                  : `${confirmedShortageCount}건`,
          },
          {
            label: "확인 업무",
            description: tasksUnavailable
              ? "업무 조회 실패"
              : !tasksLoaded
                ? "업무 데이터 조회 중"
                : taskProjectionEmpty
                  ? "사용 가능한 업무 데이터 없음"
                  : "검토 및 조치 대상",
            icon: "✓",
            type: "task",
            status: tasksUnavailable
              ? "조회 실패"
              : !tasksLoaded
                ? "조회 중"
                : taskProjectionEmpty
                  ? "데이터 없음"
                  : "조회 완료",
            value: tasksUnavailable
              ? "확인 불가"
              : !tasksLoaded
                ? "조회 중"
                : taskProjectionEmpty
                  ? "—"
                  : `${reviewTaskCount}건`,
          },
        ].map((item) => (
          <article
            className={`kpi kpi-${item.type}`}
            key={item.label}
          >
            <div className="kpi-top">
              <span className="kpi-icon" aria-hidden="true">
                {item.icon}
              </span>
              <span className="kpi-status">{item.status}</span>
            </div>

            <div className="kpi-value">
              {"value" in item ? item.value : "—"}
            </div>
            <div className="kpi-label">{item.label}</div>
            <small className="muted">{item.description}</small>
          </article>
        ))}
      </section>
      <div className="dashboard-operations-grid">
      <section className="dashboard-operations-panel" aria-label="운영 위험 모니터링">
        <UrgentQueue
          items={urgentItems}
          onSelect={openEvidence}
          onSelectActual={openActualEvidence}
          dataStatus={
            insightsUnavailable
              ? "UNAVAILABLE"
              : !insightsLoaded
                ? "LOADING"
                : urgentItems.length === 0
                  ? "NO_DATA"
                  : "READY"
          }
        />

        {insightsUnavailable && (
          <p role="alert">운영 발견 목록을 확인할 수 없습니다.</p>
        )}

        {evidenceMissing && (
          <SystemState state="empty" title="판단 근거를 찾을 수 없습니다" />
        )}
      </section>

      <section className="dashboard-operations-panel" aria-label="오늘 할 일">
        <TodayTasks
          tasks={scheduleTasks}
          shortageTasks={shortageTasks}
          reservations={reservations}
          compact
          emptyMessage={
            tasksUnavailable || reservationsUnavailable
              ? "업무 데이터를 확인할 수 없습니다"
              : !tasksLoaded || !reservationsLoaded
                ? "업무 데이터 조회 중"
                : taskProjectionEmpty && reservationRiskEmpty
                  ? "사용 가능한 업무 데이터가 없습니다"
                  : undefined
          }
          emptyDescription={
            tasksUnavailable || reservationsUnavailable
              ? "Backend 조회에 실패했습니다."
              : !tasksLoaded || !reservationsLoaded
                ? "업무 및 예약 데이터를 불러오고 있습니다."
                : taskProjectionEmpty && reservationRiskEmpty
                  ? "Backend에서 현재 사용할 수 있는 Task 및 예약 위험 Projection을 제공하지 않습니다."
                  : undefined
          }
          countUnavailable={
              tasksUnavailable ||
              reservationsUnavailable ||
              !tasksLoaded ||
              !reservationsLoaded ||
              (taskProjectionEmpty && reservationRiskEmpty)
            }
        />

        {tasksUnavailable && (
          <p role="alert">업무 데이터를 불러오지 못했습니다.</p>
        )}

        {reservationsUnavailable && (
          <p role="alert">예약 데이터를 불러오지 못했습니다.</p>
        )}
      </section>
    </div>
      <EvidenceDrawer open={selectedC04Key !== undefined} insight={null} c04Key={selectedC04Key}
        onClose={() => { setSelectedC04Key(undefined); setEvidenceMissing(false); }} />
    </div>;
  }

  if (!dashboard) {
    return (
      <div
        className="page"
        data-testid="route-dashboard"
      >
        <SystemState state="loading" />
      </div>
    );
  }

  const { data } = dashboard;

  const staleCount = data.inventory.filter(
    (item) => item.freshness === "STALE",
  ).length;

  const visibleTasks = useRealBackend ? [] : data.tasks;
  const proposedTaskCount = visibleTasks.filter(
    (task) => task.status === "PROPOSED",
  ).length;

  const identifiedModelCount = data.insights.filter(
    (item) => item.model_run_id !== null,
  ).length;

  const unknownProvenanceCount = data.insights.filter(
    (item) => item.model_run_id === null,
  ).length;

  const kpis = [
    [
      "오늘 총 주문",
      `${data.orders.length}건`,
      "온라인·오프라인 합성 주문",
      "",
    ],
    [
      "재고 채널",
      `${data.inventory.length}개`,
      "연결된 판매·재고 채널",
      "",
    ],
    [
      "지연된 재고",
      `${staleCount}건`,
      "최신 수량 확인 필요",
      "warning",
    ],
    [
      "미처리 문의",
      `${data.inquiries.length}건`,
      "담당자 검토 필요",
      "",
    ],
    [
      "오늘 확인 업무",
      `${visibleTasks.length + shortageTasks.length}건`,
      "사람이 확인할 업무",
      "warning",
    ],
    [
      "오늘 발견",
      `${data.insights.length}건`,
      "규칙·AI 운영 발견",
      "",
    ],
  ];

  return (
    <div
      className="page flush"
      data-testid="route-dashboard"
    >
      {/* KPI */}
      <section
        className="grid kpi-grid"
        aria-label="핵심 운영 지표"
      >
        {kpis.map(
          ([label, value, detail, state]) => (
            <article
              className={`kpi ${state}`}
              key={label}
            >
              <div className="kpi-label">
                {label}
              </div>

              <div className="kpi-value">
                {value}
              </div>

              <small className="muted">
                {detail}
              </small>
            </article>
          ),
        )}
      </section>

      {/* 메인 운영 영역 */}
      <div className="dashboard-console-grid">
        <main className="dashboard-console-main">
          <UrgentQueue
            items={urgentItems}
            onSelect={openEvidence}
            onSelectActual={useRealBackend ? openActualEvidence : undefined}
          />

          {insightsUnavailable && (
            <div className="notice" role="status">
              실제 운영 발견 목록을 확인할 수 없습니다. 응답 형식과 연결 상태를 확인하세요.
            </div>
          )}

          {evidenceMissing && (
            <div
              role="status"
              aria-live="polite"
            >
              <SystemState
                state="empty"
                title="판단 근거를 찾을 수 없습니다"
                description={useRealBackend
                  ? "근거 연결 없음"
                  : "선택한 위험 항목의 근거 데이터를 찾을 수 없습니다. 다른 위험 항목을 확인하거나 연결 상태를 확인하세요."}
              />
            </div>
          )}

          <TodayTasks
            tasks={visibleTasks}
            shortageTasks={shortageTasks}
            reservations={reservations}
            compact
          />
          {tasksUnavailable && <div className="notice" role="alert">실제 업무·예약 데이터를 불러오지 못했습니다.</div>}
        </main>

        <aside className="dashboard-console-side">
          {/* 연동 상태 */}
          <section className="card" aria-labelledby="provider-status-title">
            <div className="card-header" id="provider-status-title">
              연동 상태
            </div>

            <div className="card-body stack">
              {data.inventory.map((item) => (
                <div
                  className="toolbar dashboard-provider-row"
                  key={`${item.provider}-${item.sku_id}`}
                >
                  <strong>{getProviderLabel(item.provider)}</strong>
                  
                  <span className="right">
                    <FreshnessBadge
                      freshness={item.freshness}
                    />
                  </span>
                </div>
              ))}
            </div>
          </section>
          {degraded && (
              <div
                className="notice"
                role="status"
                data-testid="provider-partial-failure"
              >
                <strong>일부 연동 데이터를 불러오지 못했습니다.</strong>

                <p>
                  실패 대상: {getProviderLabel(providerFailureFixture.provider)}
                </p>

                <p>
                  사유: {getProviderFailureReasonLabel(providerFailureFixture.reason)}
                </p>

                <p>
                  마지막 정상 데이터 기준 시점:{" "}
                  <time dateTime={providerFailureFixture.last_success_as_of}>
                    {new Date(
                      providerFailureFixture.last_success_as_of,
                    ).toLocaleString("ko-KR")}
                  </time>
                </p>
              </div>
            )}
          {/* 지연 경고 */}
          {staleCount > 0 && (
            <div className="notice">
              <strong>
                ▲ eCount 데이터 확인 필요
              </strong>

              <p className="dashboard-notice-text">
                일부 재고 정보가 오래되었습니다.
                재고 위험을 판단하기 전에 최신
                수량인지 확인하세요.
              </p>
            </div>
          )}

          {/* 발견 요약 */}
          <section className="card">
            <div className="card-header">
              <AIBadge>발견 요약</AIBadge>
            </div>

            <div className="card-body stack">
              <div className="dashboard-summary-row">
                <span>출처 확인 필요</span>
                <strong>{unknownProvenanceCount}건</strong>
              </div>

              <div className="dashboard-summary-row">
                <span>모델 실행 ID 있음</span>
                <strong>{identifiedModelCount}건</strong>
              </div>

              <div className="dashboard-summary-row">
                <span>전체 운영 발견</span>
                <strong>
                  {data.insights.length}건
                </strong>
              </div>
            </div>
          </section>

          {/* 준비된 제안 */}
          <section className="card">
            <div className="card-header">
              준비된 제안
            </div>

            <div className="card-body stack">
              <div className="dashboard-summary-row">
                <span>검토 대기 업무</span>
                <strong>
                  {proposedTaskCount}건
                </strong>
              </div>

              <div className="dashboard-summary-row">
                <span>업무 생성 제안</span>
                <strong>
                  {data.insights.length}건
                </strong>
              </div>

              <div className="dashboard-safe-note">
                <strong>
                  외부 시스템 변경 없음
                </strong>

                <span>
                  조회와 내부 검토 제안만
                  제공합니다.
                </span>
              </div>
            </div>
          </section>
        </aside>
      </div>

      {/* 판단 근거 Drawer */}
      <EvidenceDrawer
        open={selectedInsight !== null || selectedC04Key !== undefined}
        insight={selectedInsight}
        c04Key={selectedC04Key}
        onClose={() => {
          evidenceRequestRef.current += 1;
          setSelectedInsight(null);
          setSelectedC04Key(undefined);
          setEvidenceMissing(false);
        }}
      />
    </div>
  );
}
