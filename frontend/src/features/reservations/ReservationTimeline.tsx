import type {
  ReservationTimeline as ReservationTimelineModel,
  ReservationTimelineStage,
  ReservationTimelineStatus,
} from "../../types/contracts";

import {
  getSourceClassificationLabel,
} from "./reservationViewModels";

type ReservationTimelineProps = {
  timeline: ReservationTimelineModel;
};

function getStageLabel(
  stage: ReservationTimelineStage,
): string {
  switch (stage) {
    case "RESERVATION":
      return "예약";
    case "PURCHASE_ORDER":
      return "발주";
    case "INCOMING":
      return "입고";
    case "FULFILLMENT":
      return "출고";
  }
}

function getStatusLabel(
  status: ReservationTimelineStatus,
): string {
  switch (status) {
    case "CONFIRMED":
      return "✓ 확인 완료";
    case "PENDING":
      return "▲ 진행 확인 중";
    case "UNKNOWN":
      return "● 확인 필요";
    case "BLOCKED":
      return "● 확인 불가";
    case "CONTRACT_ONLY":
      return "▲ 계약만 확인됨";
  }
}

function formatAsOf(
  value: string | null,
): string {
  return value ?? "시각 미확인";
}

export default function ReservationTimeline({
  timeline,
}: ReservationTimelineProps) {
  return (
    <section
      className="card"
      aria-labelledby="reservation-timeline-title"
      data-testid="reservation-timeline"
    >
      <div className="card-header">
        <div>
          <strong id="reservation-timeline-title">
            예약 상태 흐름과 근거
          </strong>

          <div className="tertiary">
            {timeline.product_name}
          </div>

          <div className="mono tertiary">
            {timeline.reservation_id}
          </div>
        </div>
      </div>

      <ol
        className="stack"
        aria-label="예약 상태 흐름"
      >
        {timeline.steps.map((step) => (
          <li
            key={step.id}
            className="card card-body"
            data-testid="reservation-timeline-step"
            data-stage={step.stage}
            data-status={step.status}
          >
            <div className="badges">
              <strong>
                {getStageLabel(step.stage)}
              </strong>

              <span>
                {getStatusLabel(step.status)}
              </span>
            </div>

            <div>
              <strong>{step.title}</strong>
            </div>

            <dl>
              <div>
                <dt>기준 시각</dt>
                <dd>{formatAsOf(step.as_of)}</dd>
              </div>

              <div>
                <dt>데이터 출처</dt>
                <dd>
                  {getSourceClassificationLabel(
                    step.source_classification,
                  )}
                </dd>
              </div>

              <div>
                <dt>Source Event</dt>
                <dd className="mono">
                  {step.source_event_id ??
                    "확인된 Source Event 없음"}
                </dd>
              </div>
            </dl>

            {step.evidence &&
            step.evidence.length > 0 ? (
              <div>
                <strong>Evidence</strong>

                <ul>
                  {step.evidence.map(
                    (evidence) => (
                      <li
                        key={`${evidence.source_type}:${evidence.source_id}:${evidence.as_of}`}
                      >
                        <span className="mono">
                          {evidence.source_type}
                        </span>
                        {" / "}
                        <span className="mono">
                          {evidence.source_id}
                        </span>
                        {" / "}
                        {evidence.as_of}
                      </li>
                    ),
                  )}
                </ul>
              </div>
            ) : (
              <p className="muted">
                확인된 Evidence가 없습니다.
              </p>
            )}

            {step.note ? (
              <p className="muted">
                {step.note}
              </p>
            ) : null}
          </li>
        ))}
      </ol>
    </section>
  );
}