import type {
  DelayImpactItemViewModel,
  DelayImpactViewModel,
} from "./impactViewModel";

interface ImpactPanelProps {
  model: DelayImpactViewModel;
}

function ImpactList({
  title,
  items,
}: {
  title: string;
  items: DelayImpactItemViewModel[];
}) {
  return (
    <section>
      <h4>{title}</h4>

      {items.length === 0 ? (
        <p className="muted">
          표시할 영향 항목이 없습니다.
        </p>
      ) : (
        <div className="stack">
          {items.map((item) => (
            <article
              key={`${item.targetType}-${item.targetId}`}
              className="timeline-item"
              data-testid={`impact-${item.targetType}-${item.targetId}`}
            >
              <div>
                <strong>
                  {item.targetTypeLabel}
                </strong>

                <div>
                  ID: {item.targetId}
                </div>
              </div>

              <div>
                <div>
                  변경 전: {item.beforeLabel}
                </div>

                <div>
                  변경 후: {item.afterLabel}
                </div>

                <div>
                  지연: {item.lagLabel}
                </div>
              </div>

              <div className="tertiary">
                사유: {item.reasonLabel}
              </div>

              {item.evidenceIds.length > 0 && (
                <div className="tertiary">
                  Evidence:{" "}
                  {item.evidenceIds.join(", ")}
                </div>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function ImpactStateMessage({
  model,
}: {
  model: DelayImpactViewModel;
}) {
  switch (model.impactState) {
    case "NONE":
      return (
        <p>
          확인된 지연 영향은 없습니다.
        </p>
      );

    case "UNKNOWN":
      return (
        <p>
          현재 자료만으로는 지연 영향 여부를
          확정할 수 없습니다.
        </p>
      );

    case "BLOCKED":
      return (
        <p>
          Source 또는 자료 품질 문제로
          지연 영향을 계산할 수 없습니다.
        </p>
      );

    case "KNOWN":
      return (
        <p>
          총 {model.totalImpactCount}개의
          영향 항목이 확인되었습니다.
        </p>
      );
  }
}

export default function ImpactPanel({
  model,
}: ImpactPanelProps) {
  return (
    <section
      className="card"
      aria-labelledby="delay-impact-title"
    >
      <div className="card-header">
        <div>
          <h3 id="delay-impact-title">
            입고 지연 영향
          </h3>

          <p className="tertiary">
            Incoming ID: {model.incomingId}
          </p>
        </div>

        <div>
          <span className="badge">
            {model.impactStateLabel}
          </span>

          <span
            className={
              model.sourceIsConfirmed
                ? "badge success"
                : "badge warning"
            }
          >
            {model.sourceLabel}
          </span>
        </div>
      </div>

      <div className="card-body stack">
        <section>
          <h4>입고 예정 변경</h4>

          <div>
            변경 전:{" "}
            {model.expectedAtBeforeLabel}
          </div>

          <div>
            변경 후:{" "}
            {model.expectedAtAfterLabel}
          </div>
        </section>

        <section>
          <h4>영향 상태</h4>

          <ImpactStateMessage
            model={model}
          />

          <p>
            {model.criticalPathLabel}
          </p>
        </section>

        <ImpactList
          title="영향받는 Task"
          items={model.tasks}
        />

        <ImpactList
          title="영향받는 예약주문"
          items={model.reservations}
        />

        <ImpactList
          title="영향받는 출시 일정"
          items={model.launchEvents}
        />

        <section>
          <h4>근거 및 Source</h4>

          <div>
            기준 시각: {model.asOfLabel}
          </div>

          <div>
            Freshness: {model.freshness}
          </div>

          <div>
            Quality: {model.qualityLabel}
          </div>

          <div>
            Source: {model.sourceLabel}
          </div>

          {model.evidenceIds.length > 0 && (
            <div>
              Evidence:{" "}
              {model.evidenceIds.join(", ")}
            </div>
          )}

          <div className="tertiary">
            request_id: {model.requestId}
          </div>

          <div className="tertiary">
            trace_id: {model.traceId}
          </div>
        </section>
      </div>
    </section>
  );
}