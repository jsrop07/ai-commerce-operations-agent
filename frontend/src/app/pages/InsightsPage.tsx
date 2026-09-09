import { AIBadge, RiskBadge, SourceBadge } from "../../components/Badges";
import InternalTaskAction from "../../components/InternalTaskAction";
import {
  useEffect,
  useState,
} from "react";

import {
  getDay08Insights,
  type Day08Insight,
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
      </div>
    );
  }

  return (
    <div
      className="page"
      data-testid="route-insights"
    >
      <section className="stack">
        {realInsights.map((insight) => (
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
    </div>
  );
}
  return (
    <div className="page" data-testid="route-insights">
      <div className="notice ai"><AIBadge>AI 인사이트 · 운영 패턴 감지</AIBadge><br /><span className="muted">합성 운영 데이터를 바탕으로 검토 항목을 제안하며 자동 실행하지 않습니다.</span></div>
      <div className="grid insight-kpis">{[["오늘 분석", "7건"],["검토 필요", "5건"],["평균 신뢰도", "89%"],["자동 실행", "0건"]].map(([label,value]) => <article className="kpi" key={label}><div className="kpi-label">{label}</div><div className="kpi-value">{value}</div></article>)}</div>
      <div className="toolbar"><button className="filter active">전체</button><button className="filter">위험</button><button className="filter">주의</button><span className="right tertiary">데이터 기준: 최근 확인 시각</span></div>
      <section className="stack">{insights.map((insight) => <article className={`card insight-card ${insight.level}`} key={insight.title}><div className="card-header badges"><RiskBadge level={insight.level} /><AIBadge>AI 설명</AIBadge><strong>{insight.title}</strong><span className="right badge ai">신뢰도 {insight.confidence}</span></div><div className="card-body grid insight-questions"><div><div className="kpi-label">무슨 문제인가요?</div><p>{insight.problem}</p></div><div><div className="kpi-label">어떤 데이터로 판단했나요?</div><p><SourceBadge>{insight.source}</SourceBadge></p></div><div><div className="kpi-label">지금 무엇을 확인하나요?</div><p>{insight.action}</p></div><div style={{ alignSelf: "end", justifySelf: "end" }}><InternalTaskAction compact /></div></div></article>)}</section>
    </div>
  );
}
