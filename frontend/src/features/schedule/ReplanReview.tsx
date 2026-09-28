import type {
  ReplanReviewViewModel,
  ReplanValueViewModel,
} from "./replanViewModel";

interface ReplanReviewProps {
  model:
    ReplanReviewViewModel;
}

function ScheduleValues({
  title,
  values,
}: {
  title: string;
  values:
    ReplanValueViewModel[];
}) {
  return (
    <section>
      <h4>{title}</h4>

      {values.length === 0 ? (
        <p className="muted">
          표시할 일정이 없습니다.
        </p>
      ) : (
        <ul>
          {values.map((value) => (
            <li
              key={`${value.targetType}-${value.targetId}`}
            >
              <strong>
                {value.targetLabel}
              </strong>
              {" · "}
              {value.targetId}
              {" · "}
              {value.scheduledAtLabel}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default function ReplanReview({
  model,
}: ReplanReviewProps) {
  return (
    <section
      className="card"
      aria-labelledby={`replan-${model.proposalId}`}
    >
      <div className="card-header">
        <div>
          <h3
            id={`replan-${model.proposalId}`}
          >
            재계획 검토
          </h3>

          <p className="tertiary">
            Proposal ID:{" "}
            {model.proposalId}
          </p>
        </div>

        <span className="badge">
          {model.statusLabel}
        </span>
      </div>

      <div className="card-body stack">
        <div
          role="note"
          className="muted"
        >
          이 화면의 승인은 내부 일정
          검토 상태만 의미합니다.
          Cafe24, eCount, POS 또는 외부
          일정 시스템에 자동 반영되지
          않습니다.
        </div>

        <ScheduleValues
          title="기존 일정"
          values={model.before}
        />

        <ScheduleValues
          title="제안 일정"
          values={
            model.proposedAfter
          }
        />

        <section>
          <h4>제안 근거</h4>

          <p>
            이유: {model.reason}
          </p>

          <p>
            신뢰도:{" "}
            {model.confidenceLabel}
          </p>

          <p>
            후속 영향:{" "}
            {model.downstreamImpactLabel}
          </p>

          <p>
            충돌:{" "}
            {model.conflictLabel}
          </p>
        </section>

        <section>
          <h4>근거 정보</h4>

          <p>
            Source:{" "}
            {model.sourceLabel}
          </p>

          <p>
            기준 시각:{" "}
            {model.asOfLabel}
          </p>

          {model.evidenceIds.length >
            0 && (
            <p>
              Evidence:{" "}
              {model.evidenceIds.join(
                ", ",
              )}
            </p>
          )}

          <p className="tertiary">
            request_id:{" "}
            {model.requestId}
          </p>

          <p className="tertiary">
            trace_id:{" "}
            {model.traceId}
          </p>
        </section>
      </div>
    </section>
  );
}