import type {
  ApiEnvelope,
  InsightSummary,
  RiskLevel,
} from "../types/contracts";
import { getInsightTypeLabel } from "./statusLabels";
import {
  ConfidenceBadge,
  RiskLevelBadge,
} from "./StatusBadges";
import SystemState from "./SystemStates";

type UrgentQueueProps = {
  items: ApiEnvelope<UrgentQueueInsight>[];
  onSelect?: (requestId: string) => void;
};

export type UrgentQueueInsight = Pick<
  InsightSummary,
  "insight_id" | "type" | "severity" | "confidence" | "summary"
>;

const severityPriority: Record<
  RiskLevel,
  number
> = {
  PROHIBITED: 4,
  HIGH: 3,
  MEDIUM: 2,
  LOW: 1,
};

export function sortUrgentQueue(
  items: ApiEnvelope<UrgentQueueInsight>[],
): ApiEnvelope<UrgentQueueInsight>[] {
  return [...items].sort((a, b) => {
    const severityDifference =
      severityPriority[b.data.severity] -
      severityPriority[a.data.severity];

    if (severityDifference !== 0) {
      return severityDifference;
    }

    const timeDifference =
      new Date(b.as_of).getTime() -
      new Date(a.as_of).getTime();

    if (timeDifference !== 0) {
      return timeDifference;
    }

    return a.data.insight_id.localeCompare(
      b.data.insight_id,
    );
  });
}

function formatDateTime(
  asOf: string,
): string {
  const date = new Date(asOf);

  if (Number.isNaN(date.getTime())) {
    return "기준시각 확인 불가";
  }

  return date.toLocaleString("ko-KR");
}

export default function UrgentQueue({
  items,
  onSelect,
}: UrgentQueueProps) {
  const sortedItems =
    sortUrgentQueue(items);

  return (
    <section
      className="urgent-queue-section"
      aria-labelledby="urgent-queue-title"
    >
      <div className="urgent-section-header">
        <div>
          <h2
            id="urgent-queue-title"
            className="section-title"
          >
            긴급 Queue
          </h2>

          <p className="muted section-description">
            지금 먼저 확인해야 하는 운영
            문제입니다.
          </p>
        </div>

        <div className="urgent-header-meta">
          <span className="badge source">
            {sortedItems.length}건
          </span>

          <span className="tertiary">
            위험도 높은 순 · 같은 위험도는
            최신순
          </span>
        </div>
      </div>

      {sortedItems.length === 0 ? (
        <SystemState
          state="empty"
          title="현재 긴급 위험이 없습니다"
          description="새로운 운영 위험이 감지되면 위험도와 이유를 기준으로 이곳에 표시됩니다. 현재는 일반 운영 업무를 확인하세요."
        />
      ) : (
        <div className="urgent-queue-list">
          {sortedItems.map((item) => {
            const insight = item.data;

            return (
              <article
                className={`urgent-card urgent-card-${insight.severity.toLowerCase()}`}
                key={`${item.request_id}-${insight.insight_id}`}
                >
                <button
                    type="button"
                    className="urgent-card-button"
                    onClick={() => onSelect?.(item.request_id)}
                    aria-label={`${getInsightTypeLabel(
                    insight.type,
                    )} 판단 근거 보기`}
                    aria-describedby={`${insight.insight_id}-reason ${insight.insight_id}-time`}
                >
                <div className="urgent-card-top">
                  <div className="badges">
                    <RiskLevelBadge
                      risk={insight.severity}
                    />

                    <ConfidenceBadge
                      confidence={
                        insight.confidence
                      }
                    />
                  </div>

                  <span
                    className="urgent-as-of"
                    id={`${insight.insight_id}-time`}
                    >
                    기준 {formatDateTime(item.as_of)}
                </span>
                </div>

                <h3>
                  {getInsightTypeLabel(
                    insight.type,
                  )}
                </h3>

                <p
                    className="urgent-reason"
                    id={`${insight.insight_id}-reason`}
                >
                    {insight.summary}
                </p>
                </button>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}