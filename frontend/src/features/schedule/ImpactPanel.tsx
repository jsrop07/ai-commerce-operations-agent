import type { DelayImpactItemViewModel, DelayImpactViewModel } from "./impactViewModel";

interface ImpactPanelProps { model: DelayImpactViewModel }

function ImpactItems({ title, items, incomingId, asOf }: {
  title: string;
  items: DelayImpactItemViewModel[];
  incomingId: string;
  asOf: string | null;
}) {
  return (
    <section className="schedule-impact-group">
      <div className="schedule-impact-group-heading">
        <h4>{title}</h4>
        <span className="schedule-count">{items.length}건</span>
      </div>
      {items.length === 0 ? <p className="muted">표시할 영향 항목이 없습니다.</p> : (
        <div className="schedule-impact-items">
          {items.map((item) => (
            <article className="schedule-impact-item" key={`${item.targetType}-${item.targetId}`}
              data-testid={`impact-${item.targetType}-${item.targetId}`}>
              <div className="schedule-impact-item-main">
                <strong>{item.targetTypeLabel}</strong>
                <span className="schedule-impact-item-shift">{item.beforeLabel} → {item.afterLabel}</span>
                <span className="schedule-impact-lag">지연 {item.lagLabel}</span>
              </div>
              <p className="muted">{item.reasonLabel}</p>
              <details className="schedule-evidence">
                <summary>대상·관계 및 근거 보기</summary>
                <dl>
                  <div><dt>대상 ID</dt><dd>{item.targetId}</dd></div>
                  <div><dt>관계</dt><dd>{incomingId} → {item.targetId} · {item.targetType}</dd></div>
                  <div><dt>관계 확정</dt><dd>확인 필요</dd></div>
                  <div><dt>출처</dt><dd>{item.sourceId ?? "확인 필요"}</dd></div>
                  <div><dt>기준 시각</dt><dd>{asOf ?? "확인 필요"}</dd></div>
                  {item.evidenceIds.length > 0 && <div><dt>Evidence</dt><dd>{item.evidenceIds.join(", ")}</dd></div>}
                </dl>
              </details>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function stateDescription(model: DelayImpactViewModel): string {
  switch (model.impactState) {
    case "NONE": return "확인된 지연 영향은 없습니다.";
    case "UNKNOWN": return "현재 자료만으로는 지연 영향 여부를 확정할 수 없습니다.";
    case "BLOCKED": return "출처 또는 자료 품질 문제로 지연 영향을 계산할 수 없습니다.";
    case "KNOWN": return `총 ${model.totalImpactCount}개의 영향 항목이 확인되었습니다.`;
  }
}

export default function ImpactPanel({ model }: ImpactPanelProps) {
  return (
    <section className="card schedule-impact-panel" aria-labelledby="delay-impact-title">
      <div className="card-header schedule-panel-heading">
        <div>
          <h3 id="delay-impact-title">입고 지연 영향</h3>
          <p className="tertiary">선택한 입고의 일정 변경과 후속 영향</p>
        </div>
        <div className="schedule-panel-badges">
          <span className="badge">{model.impactStateLabel}</span>
          <span className={model.sourceIsConfirmed ? "badge success" : "badge warning"}>{model.sourceLabel}</span>
        </div>
      </div>
      <div className="card-body schedule-impact-body">
        {model.dataMode === "SYNTHETIC_DEMO" && <p className="schedule-safety-note" role="note">합성 예시(SYNTHETIC_DEMO) · 실제 사업 입고 자료가 아닙니다.</p>}
        {model.status === "CONTRACT_ONLY" && <p className="schedule-safety-note">계약 검증용(CONTRACT_ONLY) 자료입니다.</p>}
        {model.actualDelayConfirmed === false && <p className="schedule-safety-note">실제 지연이 확정된 상태가 아닙니다.</p>}
        <div className="schedule-impact-summary" role="status">
          <strong>{stateDescription(model)}</strong>
          <span className="muted">{model.criticalPathLabel}</span>
        </div>
        <section className="schedule-impact-change" aria-label="입고 예정 변경">
          <h4>입고 예정 변경</h4>
          <div className="schedule-change-pair">
            <div><span>변경 전</span><strong>{model.expectedAtBeforeLabel}</strong></div>
            <span aria-hidden="true">→</span>
            <div><span>변경 후</span><strong>{model.expectedAtAfterLabel}</strong></div>
          </div>
        </section>
        <ImpactItems title="영향받는 Task" items={model.tasks} incomingId={model.incomingId} asOf={model.asOf} />
        <ImpactItems title="영향받는 예약주문" items={model.reservations} incomingId={model.incomingId} asOf={model.asOf} />
        <ImpactItems title="영향받는 출시 일정" items={model.launchEvents} incomingId={model.incomingId} asOf={model.asOf} />
        <details className="schedule-evidence schedule-evidence-root">
          <summary>입고 원천·품질 및 분석 근거</summary>
          <dl>
            <div><dt>Incoming ID</dt><dd>{model.incomingId}</dd></div>
            <div><dt>기준 시각</dt><dd>{model.asOfLabel}</dd></div>
            <div><dt>Freshness</dt><dd>{model.freshness}</dd></div>
            <div><dt>Quality</dt><dd>{model.quality === "TENTATIVE" ? "잠정 (TENTATIVE)" : model.qualityLabel}</dd></div>
            <div><dt>Source</dt><dd>{model.sourceClassification === "FIXTURE" ? `${model.sourceLabel} (FIXTURE)` : model.sourceLabel}</dd></div>
            {model.evidenceIds.length > 0 && <div><dt>Evidence</dt><dd>{model.evidenceIds.join(", ")}</dd></div>}
          </dl>
        </details>
      </div>
    </section>
  );
}
