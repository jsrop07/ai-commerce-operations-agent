import type {
  TaskSummary,
} from "../types/contracts";
import { RiskLevelBadge } from "./StatusBadges";
import { taskStatusLabel } from "./statusLabels";
import SystemState from "./SystemStates";

type TodayTasksProps = {
  tasks: TaskSummary[];
  compact?: boolean;
};

function formatDateTime(
  value: string,
): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "시간 확인 불가";
  }

  return date.toLocaleString("ko-KR");
}

function getTaskReasonLabel(
  reason: string,
): string {
  const labels: Record<string, string> = {
    "inventory discrepancy":
      "재고 수량 차이가 발견되어 확인이 필요합니다.",

    "draft ready":
      "AI 문의 초안이 준비되어 담당자 검토가 필요합니다.",

    "human approval required":
      "담당자 승인이 필요한 업무입니다.",
  };

  return (
    labels[reason] ??
    "운영 확인이 필요한 내부 업무입니다."
  );
}

export default function TodayTasks({
  tasks,
  compact = false,
}: TodayTasksProps) {
  return (
    <section
      className={`today-task-section ${
        compact ? "compact" : ""
      }`}
      aria-labelledby="today-task-title"
    >
      <div className="today-task-header">
        <div>
          <h2
            id="today-task-title"
            className="section-title"
          >
            오늘 할 일
          </h2>

          <p className="muted section-description">
            오늘 사람이 직접 확인해야 하는
            내부 업무입니다.
          </p>
        </div>

        <span className="badge source">
          {tasks.length}건
        </span>
      </div>

      {tasks.length === 0 ? (
        <SystemState
          state="empty"
          title="오늘 예정된 확인 업무가 없습니다"
          description="새로운 내부 확인 업무가 생성되면 이곳에 표시됩니다."
        />
      ) : (
        <div className="today-task-list">
          {tasks.map((task) => (
            <article
              className="today-task-card"
              key={task.id}
            >
              <div className="today-task-card-top">
                <div className="badges">
                  <RiskLevelBadge
                    risk={task.priority}
                  />

                  <span className="badge source">
                    {
                      taskStatusLabel[
                        task.status
                      ]
                    }
                  </span>
                </div>

                <span className="today-task-deadline">
                  {formatDateTime(
                    task.deadline,
                  )}
                </span>
              </div>

              <div className="today-task-content">
                <h3>{task.title}</h3>

                <p className="muted">
                  {getTaskReasonLabel(
                    task.source_reason,
                  )}
                </p>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}