import { useEffect, useState, type MouseEvent } from "react";
import { FreshnessBadge } from "../../components/StatusBadges";
import {
  getProviderFailureReasonLabel,
  getProviderLabel,
} from "../../components/statusLabels";
import { mockApiGet } from "../../mocks/handlers";
import type {
  ApiEnvelope,
  DashboardData,
  InventorySnapshot,
  ReservationRiskItem,
  ReservationShortageTask,
  ScheduleTask,
} from "../../types/contracts";
import SystemState from "../../components/SystemStates";
import TodayTasks from "../../components/TodayTasks";
import OperationalUrgentQueue from "../../components/OperationalUrgentQueue";
import { getDashboardQueue, type DashboardQueueData } from "../../api/dashboardQueue";
import { getDay10Tasks } from "../../api/day10";
import { getDay09Reservations } from "../../api/day09";

import { useRealBackend } from "../../api/day04";
import { useOptionalCommonAiDrawer } from "../CommonAiDrawerContext";
import { providerFailureFixture } from "../../mocks/fixtures/degradedDashboard";
import { getCatalogSummary } from "../../api/catalog";
import { getDay08Inventory } from "../../api/day08";
import {
  getRecentOrderSummary,
  type RecentOrderSummary,
} from "../../api/orders";

function navigateDashboard(event: MouseEvent<HTMLAnchorElement>, path: string) {
  event.preventDefault();
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

export default function DashboardPage() {
  const sessionState = useOptionalCommonAiDrawer()?.sessionState ?? "ready";
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
  const [queue, setQueue] = useState<DashboardQueueData | null>(null);
  const [queueError, setQueueError] = useState(false);
  const [queueRequest, setQueueRequest] = useState(0);

  useEffect(() => {
    if (!useRealBackend || sessionState !== "ready") return;
    const controller = new AbortController();
    setQueue(null);
    setQueueError(false);
    void getDashboardQueue(controller.signal).then((data) => {
      if (!controller.signal.aborted) setQueue(data);
    }).catch(() => {
      if (!controller.signal.aborted) setQueueError(true);
    });
    return () => controller.abort();
  }, [queueRequest, sessionState]);

  useEffect(() => {
    let active = true;
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
    }

    return () => {
      active = false;
      controller.abort();
    };
  }, []);

  // 사람이 검토하거나 별도 조치해야 하는 업무만 집계
  const reviewTaskCount = allTasks.filter(
    (task) =>
      task.status === "PROPOSED" ||
      task.status === "BLOCKED"
  ).length + (queue?.items.filter((item) => item.kind === "TASK_REVIEW").length ?? 0);
  const storedReviewTasks = queue?.items.filter((item) => item.kind === "TASK_REVIEW") ?? [];
  const conditionalReservationCount = queue?.items.filter(
    (item) => item.kind === "CONDITIONAL_RESERVATION",
  ).length ?? 0;

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
        <a className="kpi kpi-product dashboard-kpi-link" href="/inventory"
          onClick={(event) => navigateDashboard(event, "/inventory")}>
          <div className="kpi-top">
            <span className="kpi-icon" aria-hidden="true">▦</span>
            <span className="kpi-status">합성 상품</span>
          </div>
          <div className="kpi-value">
            {productCountError
              ? "확인 불가"
              : productCount === null
                ? "조회 중"
                : `${productCount.toLocaleString("ko-KR")}개`}
          </div>
          <div className="kpi-label">총 상품</div>
        </a>

        {[
          {
            label: "최근 주문",
            href: "/orders",
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
            href: "/inventory?tab=snapshot",
            description: inventoryUnavailable
              ? "재고 정보 조회 실패"
              : !inventoryLoaded
                ? "재고 정보 조회 중"
                : inventoryItems.length === 0
                  ? "조회된 재고 자료 없음"
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
            href: "/schedule?focus=reservation",
            description: reservationsUnavailable
              ? "예약 정보 조회 실패"
              : !reservationsLoaded
                ? "예약 정보 조회 중"
                : reservationRiskEmpty && conditionalReservationCount > 0
                  ? "예약·입고 자료 기반 조건부 확보 검토"
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
                : reservationRiskEmpty && conditionalReservationCount > 0
                  ? "조건부 검토"
                  : reservationRiskEmpty
                    ? "데이터 없음"
                  : unverifiedReservationCount > 0
                    ? "일부 미확인"
                    : "조회 완료",
            value: reservationsUnavailable
              ? "확인 불가"
              : !reservationsLoaded
                ? "조회 중"
                : reservationRiskEmpty && conditionalReservationCount > 0
                  ? `검토 ${conditionalReservationCount}건`
                  : reservationRiskEmpty
                    ? "—"
                  : `${confirmedShortageCount}건`,
          },
          {
            label: "확인 업무",
            href: "/schedule?focus=tasks",
            description: tasksUnavailable
              ? "업무 조회 실패"
              : !tasksLoaded
                ? "업무 데이터 조회 중"
                : taskProjectionEmpty && storedReviewTasks.length === 0
                  ? "사용 가능한 업무 데이터 없음"
                  : "검토 및 조치 대상",
            icon: "✓",
            type: "task",
            status: tasksUnavailable
              ? "조회 실패"
              : !tasksLoaded
                ? "조회 중"
                : taskProjectionEmpty && storedReviewTasks.length === 0
                  ? "데이터 없음"
                  : "조회 완료",
            value: tasksUnavailable
              ? "확인 불가"
              : !tasksLoaded
                ? "조회 중"
                : taskProjectionEmpty && storedReviewTasks.length === 0
                  ? "—"
                  : `${reviewTaskCount}건`,
          },
        ].map((item) => (
          <a
            className={`kpi kpi-${item.type} dashboard-kpi-link`}
            href={item.href}
            onClick={(event) => navigateDashboard(event, item.href)}
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
          </a>
        ))}
      </section>
      <div className="dashboard-operations-grid">
      <section className="dashboard-operations-panel" aria-label="운영 위험 모니터링">
        <OperationalUrgentQueue data={queue} error={queueError}
          onRefresh={() => setQueueRequest((value) => value + 1)} />
      </section>
      <section className="dashboard-operations-panel" aria-label="오늘 할 일">
        <TodayTasks
          tasks={scheduleTasks}
          shortageTasks={shortageTasks}
          storedTasks={storedReviewTasks}
          reservations={reservations}
          compact
          emptyMessage={
            tasksUnavailable || reservationsUnavailable
              ? "업무 데이터를 확인할 수 없습니다"
              : !tasksLoaded || !reservationsLoaded
                ? "업무 데이터 조회 중"
                : taskProjectionEmpty && reservationRiskEmpty && storedReviewTasks.length === 0
                  ? "사용 가능한 업무 데이터가 없습니다"
                  : undefined
          }
          emptyDescription={
            tasksUnavailable || reservationsUnavailable
              ? "Backend 조회에 실패했습니다."
              : !tasksLoaded || !reservationsLoaded
                ? "업무 및 예약 데이터를 불러오고 있습니다."
                : taskProjectionEmpty && reservationRiskEmpty && storedReviewTasks.length === 0
                  ? "현재 사용할 수 있는 확인 업무와 예약 위험 자료가 없습니다."
                  : undefined
          }
          countUnavailable={
              tasksUnavailable ||
              reservationsUnavailable ||
              !tasksLoaded ||
              !reservationsLoaded ||
              (taskProjectionEmpty && reservationRiskEmpty && storedReviewTasks.length === 0)
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

    </div>
  );
}
