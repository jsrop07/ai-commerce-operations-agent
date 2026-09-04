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
} from "../../types/contracts";
import EvidenceDrawer from "../../components/EvidenceDrawer";
import SystemState from "../../components/SystemStates";
import UrgentQueue from "../../components/UrgentQueue";
import { urgentQueueFixtures } from "../../mocks/fixtures/urgentQueue";
import TodayTasks from "../../components/TodayTasks";
import {
  getDay04Insights,
  toUrgentQueueItems,
  useRealBackend,
} from "../../api/day04";
import { providerFailureFixture } from "../../mocks/fixtures/degradedDashboard";
import type { UrgentQueueInsight } from "../../components/UrgentQueue";
export default function DashboardPage() {
  const degraded =
    new URLSearchParams(window.location.search).get("degraded") === "true";
  const [dashboard, setDashboard] =
    useState<ApiEnvelope<DashboardData> | null>(null);
  
  const [urgentItems, setUrgentItems] =
    useState<ApiEnvelope<UrgentQueueInsight>[]>(
      urgentQueueFixtures,
    );
  const [insightsUnavailable, setInsightsUnavailable] = useState(false);

  const [selectedInsight, setSelectedInsight] =
    useState<InsightSummary | null>(null);

  const [evidenceMissing, setEvidenceMissing] =
    useState(false);
  const mountedRef = useRef(true);
  const evidenceRequestRef = useRef(0);

  useEffect(() => {
    let active = true;
    mountedRef.current = true;
    const controller = new AbortController();

    mockApiGet<ApiEnvelope<DashboardData>>(
      "/api/v1/dashboard",
    ).then((response) => {
      if (active) {
        setDashboard(response);
      }
    });

    if (useRealBackend) {
      setUrgentItems([]);
      getDay04Insights(controller.signal)
        .then((response) => {
          if (active) {
            setUrgentItems(toUrgentQueueItems(response));
            setInsightsUnavailable(false);
          }
        })
        .catch((error: unknown) => {
          if (
            active &&
            !(error instanceof DOMException && error.name === "AbortError")
          ) {
            setUrgentItems([]);
            setInsightsUnavailable(true);
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

  const proposedTaskCount = data.tasks.filter(
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
      `${data.tasks.length}건`,
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
                description="선택한 위험 항목의 근거 데이터를 찾을 수 없습니다. 다른 위험 항목을 확인하거나 연결 상태를 확인하세요."
              />
            </div>
          )}

          <TodayTasks
            tasks={data.tasks}
            compact
          />
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
        open={selectedInsight !== null}
        insight={selectedInsight}
        onClose={() =>
          setSelectedInsight(null)
        }
      />
    </div>
  );
}