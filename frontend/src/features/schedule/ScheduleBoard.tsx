import type {
  ScheduleBoardViewModel,
} from "./viewModel";

interface ScheduleBoardProps {
  model: ScheduleBoardViewModel;
}

function SourceBadge({
  label,
  confirmed,
}: {
  label: string;
  confirmed: boolean;
}) {
  return (
    <span
      className={
        confirmed
          ? "badge success"
          : "badge warning"
      }
    >
      {label}
    </span>
  );
}

export default function ScheduleBoard({
  model,
}: ScheduleBoardProps) {
  if (
    model.launchEvents.length === 0 &&
    model.tasks.length === 0 &&
    model.dependencies.length === 0
  ) {
    return (
      <section
        className="card"
        aria-labelledby="schedule-board-title"
      >
        <div className="card-header">
          <h3 id="schedule-board-title">
            출시·입고 일정
          </h3>
        </div>

        <div className="card-body">
          <p>
            표시할 일정 데이터가 없습니다.
          </p>

          <p className="muted">
            Backend 응답이 200 empty인 경우
            임의 일정을 생성하지 않습니다.
          </p>
        </div>
      </section>
    );
  }

  return (
    <section
      className="card"
      aria-labelledby="schedule-board-title"
    >
      <div className="card-header">
        <div>
          <h3 id="schedule-board-title">
            출시·입고 일정
          </h3>

          <p className="tertiary">
            시간대:{" "}
            {model.timezone ??
              "시간대 미확정"}
            {" · "}
            기준 시각:{" "}
            {model.asOf ??
              "기준 시각 미확정"}
          </p>
        </div>
      </div>

      <div className="card-body stack">
        <section
          aria-labelledby="schedule-launch-title"
        >
          <h4 id="schedule-launch-title">
            출시 일정
          </h4>

          {model.launchEvents.length === 0 ? (
            <p className="muted">
              출시 일정이 없습니다.
            </p>
          ) : (
            <div className="stack">
              {model.launchEvents.map(
                (event) => (
                  <article
                    className="timeline-item"
                    key={event.id}
                    data-testid={`schedule-launch-${event.id}`}
                  >
                    <div>
                      <strong>
                        {event.flowLabel}
                      </strong>

                      <div>
                        출시 시각:{" "}
                        {event.launchAtLabel}
                      </div>

                      <div className="tertiary">
                        Template:{" "}
                        {event.templateId}
                        {" · "}
                        Version:{" "}
                        {event.version}
                      </div>
                    </div>

                    <div>
                      <span className="badge">
                        {event.status}
                      </span>

                      <SourceBadge
                        label={
                          event.sourceLabel
                        }
                        confirmed={
                          event.sourceIsConfirmed
                        }
                      />
                    </div>

                    <div className="tertiary">
                      기준 시각:{" "}
                      {event.asOfLabel}
                    </div>
                  </article>
                ),
              )}
            </div>
          )}
        </section>

        <section
          aria-labelledby="schedule-task-title"
        >
          <h4 id="schedule-task-title">
            Task
          </h4>

          {model.tasks.length === 0 ? (
            <p className="muted">
              표시할 Task가 없습니다.
            </p>
          ) : (
            <div className="stack">
              {model.tasks.map(
                (task) => (
                  <article
                    className="timeline-item"
                    key={task.id}
                    data-testid={`schedule-task-${task.id}`}
                  >
                    <div>
                      <strong>
                        {task.title}
                      </strong>

                      <div>
                        {task.flowLabel}
                      </div>

                      <div>
                        마감:{" "}
                        {task.deadlineLabel}
                      </div>

                      <div>
                        담당:{" "}
                        {task.ownerLabel}
                      </div>

                      <div>
                        소요:{" "}
                        {task.durationLabel}
                      </div>

                      <div className="tertiary">
                        이유:{" "}
                        {task.sourceReason}
                      </div>
                    </div>

                    <div>
                      <span className="badge">
                        {task.status}
                      </span>

                      <span className="badge">
                        {task.priority}
                      </span>

                      <SourceBadge
                        label={
                          task.sourceLabel
                        }
                        confirmed={
                          task.sourceIsConfirmed
                        }
                      />
                    </div>

                    <div className="tertiary">
                      기준 시각:{" "}
                      {task.asOfLabel}
                    </div>
                  </article>
                ),
              )}
            </div>
          )}
        </section>

        <section
          aria-labelledby="schedule-dependency-title"
        >
          <h4 id="schedule-dependency-title">
            Task Dependency
          </h4>

          {model.dependencies.length === 0 ? (
            <p className="muted">
              Dependency 정보가 없습니다.
            </p>
          ) : (
            <ul>
              {model.dependencies.map(
                (dependency) => (
                  <li
                    key={
                      `${dependency.predecessorId}` +
                      `-${dependency.successorId}`
                    }
                  >
                    <strong>
                      {
                        dependency.predecessorId
                      }
                    </strong>
                    {" → "}
                    <strong>
                      {
                        dependency.successorId
                      }
                    </strong>

                    {" · "}

                    {dependency.lagLabel}

                    {" · "}

                    <SourceBadge
                      label={
                        dependency.sourceLabel
                      }
                      confirmed={
                        dependency.sourceIsConfirmed
                      }
                    />
                  </li>
                ),
              )}
            </ul>
          )}
        </section>
      </div>
    </section>
  );
}