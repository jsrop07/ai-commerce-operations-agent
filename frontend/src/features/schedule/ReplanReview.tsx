import type { ReplanReviewViewModel, ReplanValueViewModel } from "./replanViewModel";

interface ReplanReviewProps { model: ReplanReviewViewModel }

function ScheduleValues({ title, values }: { title: string; values: ReplanValueViewModel[] }) {
  return (
    <section className="schedule-replan-column">
      <div className="schedule-impact-group-heading"><h4>{title}</h4><span className="schedule-count">{values.length}건</span></div>
      {values.length === 0 ? <p className="muted">표시할 일정이 없습니다.</p> : (
        <ul className="schedule-replan-values">
          {values.map((value) => (
            <li key={`${value.targetType}-${value.targetId}`}>
              <strong>{value.targetLabel}</strong>
              <span>{value.scheduledAtLabel}</span>
              <small className="tertiary">{value.targetId}</small>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default function ReplanReview({ model }: ReplanReviewProps) {
  return (
    <section className="card schedule-replan-panel" aria-labelledby={`replan-${model.proposalId}`}>
      <div className="card-header schedule-panel-heading">
        <div><h3 id={`replan-${model.proposalId}`}>재계획 검토</h3><p className="tertiary">변경 제안의 전후 비교</p></div>
        <span className="badge">{model.statusLabel}</span>
      </div>
      <div className="card-body schedule-replan-body">
        <p role="note" className="schedule-safety-note">
          현재는 제안 상태이며 일정에 적용되지 않았습니다. Cafe24·eCount·POS 및 외부 일정 시스템에 자동 반영되지 않습니다.
        </p>
        <div className="schedule-replan-comparison">
          <ScheduleValues title="현재 일정" values={model.before} />
          <ScheduleValues title="제안 일정" values={model.proposedAfter} />
        </div>
        <div className="schedule-replan-reason">
          <h4>제안 이유</h4>
          <p>{model.reason}</p>
        </div>
        <details className="schedule-evidence schedule-evidence-root">
          <summary>제안 평가·근거 및 제한사항</summary>
          <p className="muted">{import.meta.env.VITE_USE_REAL_BACKEND === "true"
            ? "Public Demo에서는 R10 workflow review API가 닫혀 있습니다. 제안 조회만 가능합니다."
            : "승인·실행 불가: R10 review/resume 계약 전이며 외부 실행은 허용되지 않습니다."}</p>
          <dl>
            <div><dt>Proposal ID</dt><dd>{model.proposalId}</dd></div>
            <div><dt>신뢰도</dt><dd>{model.confidenceLabel}</dd></div>
            <div><dt>후속 영향</dt><dd>{model.downstreamImpactLabel}</dd></div>
            <div><dt>충돌</dt><dd>{model.conflictLabel}</dd></div>
            <div><dt>Source</dt><dd>{model.sourceLabel}</dd></div>
            <div><dt>기준 시각</dt><dd>{model.asOfLabel}</dd></div>
            {model.evidenceIds.length > 0 && <div><dt>Evidence</dt><dd>{model.evidenceIds.join(", ")}</dd></div>}
          </dl>
        </details>
      </div>
    </section>
  );
}
