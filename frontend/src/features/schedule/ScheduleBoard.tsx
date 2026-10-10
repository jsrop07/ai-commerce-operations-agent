import type { ScheduleBoardViewModel } from "./viewModel";

interface ScheduleBoardProps {
  model: ScheduleBoardViewModel;
}

function SourceBadge({ label, confirmed }: { label: string; confirmed: boolean }) {
  return <span className={confirmed ? "badge success" : "badge warning"}>{label}</span>;
}

export default function ScheduleBoard({ model }: ScheduleBoardProps) {
  const empty =
    model.launchEvents.length === 0 &&
    model.tasks.length === 0 &&
    model.dependencies.length === 0;

  return (
    <section className="card schedule-overview" aria-labelledby="schedule-board-title">
      <div className="card-header schedule-overview-header">
        <div>
          <h3 id="schedule-board-title">출시 일정</h3>
          <p className="tertiary">출시 일정과 관련 업무를 확인합니다.</p>
        </div>
        <span className="schedule-overview-count">{empty ? "0건" : `출시 ${model.launchEvents.length} · Task ${model.tasks.length} · 관계 ${model.dependencies.length}`}</span>
      </div>

      {empty ? (
        <div className="schedule-overview-empty" data-testid="schedule-board-empty">
          <strong>등록된 출시 일정이 없습니다.</strong>
          <p>출시 일정, 관련 Task 및 의존관계가 모두 비어 있습니다.</p>
          
        </div>
      ) : (
        <div className="schedule-overview-content">
          <div className="schedule-overview-meta">
            <span>시간대: {model.timezone ?? "미확정"}</span>
            <span>기준 시각: {model.asOf ?? "미확정"}</span>
          </div>

          <section className="schedule-overview-group" aria-labelledby="schedule-launch-title">
            <div className="schedule-overview-group-heading">
              <h4 id="schedule-launch-title">출시 일정</h4>
              <span>{model.launchEvents.length}건</span>
            </div>
            {model.launchEvents.length === 0 ? (
              <p className="schedule-overview-group-empty">표시할 출시 일정이 없습니다.</p>
            ) : (
              <div className="schedule-overview-items">
                {model.launchEvents.map((event) => (
                  <article className="schedule-overview-item" key={event.id} data-testid={`schedule-launch-${event.id}`}>
                    <div className="schedule-overview-item-main">
                      <strong>{event.flowLabel}</strong>
                      <span>출시 시각: {event.launchAtLabel}</span>
                      <small>Template: {event.templateId} · Version: {event.version}</small>
                    </div>
                    <div className="schedule-overview-badges">
                      <span className="badge">{event.status}</span>
                      <SourceBadge label={event.sourceLabel} confirmed={event.sourceIsConfirmed} />
                    </div>
                    <div className="schedule-overview-asof">기준 시각: {event.asOfLabel}</div>
                  </article>
                ))}
              </div>
            )}
          </section>

          <section className="schedule-overview-group" aria-labelledby="schedule-task-title">
            <div className="schedule-overview-group-heading">
              <h4 id="schedule-task-title">관련 Task</h4>
              <span>{model.tasks.length}건</span>
            </div>
            {model.tasks.length === 0 ? (
              <p className="schedule-overview-group-empty">표시할 Task가 없습니다.</p>
            ) : (
              <div className="schedule-overview-items">
                {model.tasks.map((task) => (
                  <article className="schedule-overview-item" key={task.id} data-testid={`schedule-task-${task.id}`}>
                    <div className="schedule-overview-item-main">
                      <strong>{task.title}</strong>
                      <span>{task.flowLabel} · 마감: {task.deadlineLabel}</span>
                      <span>담당: {task.ownerLabel} · 소요: {task.durationLabel}</span>
                      <small>이유: {task.sourceReason}</small>
                    </div>
                    <div className="schedule-overview-badges">
                      <span className="badge">{task.status}</span>
                      <span className="badge">{task.priority}</span>
                      <SourceBadge label={task.sourceLabel} confirmed={task.sourceIsConfirmed} />
                    </div>
                    <div className="schedule-overview-asof">기준 시각: {task.asOfLabel}</div>
                  </article>
                ))}
              </div>
            )}
          </section>

          <section className="schedule-overview-group" aria-labelledby="schedule-dependency-title">
            <div className="schedule-overview-group-heading">
              <h4 id="schedule-dependency-title">업무 선후관계</h4>
              <span>{model.dependencies.length}건</span>
            </div>
            {model.dependencies.length === 0 ? (
              <p className="schedule-overview-group-empty">표시할 의존관계가 없습니다.</p>
            ) : (
              <div className="schedule-overview-items">
                {model.dependencies.map((dependency) => (
                  <article className="schedule-overview-dependency" key={`${dependency.predecessorId}-${dependency.successorId}`}>
                    <div className="schedule-overview-dependency-main">
                      <strong>{dependency.predecessorId}</strong>
                      <span aria-label="선행 작업에서 후속 작업으로">→</span>
                      <strong>{dependency.successorId}</strong>
                    </div>
                    <div className="schedule-overview-dependency-detail">
                      <span>시차: {dependency.lagLabel}</span>
                      <SourceBadge label={dependency.sourceLabel} confirmed={dependency.sourceIsConfirmed} />
                    </div>
                    <small>관계 유형: 미확인 · Source: {dependency.sourceLabel} · 기준 시각: {dependency.asOf ?? "미확정"}</small>
                  </article>
                ))}
              </div>
            )}
          </section>
        </div>
      )}
    </section>
  );
}
