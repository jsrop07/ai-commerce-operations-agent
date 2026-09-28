import type {
  TaskSummary,
  ReservationShortageTask,
  ReservationRiskItem,
  TaskFeedback,
} from "../types/contracts";
import { useEffect, useState } from "react";
import { getTaskFeedback, postTaskFeedback } from "../api/day10";
import { RiskLevelBadge } from "./StatusBadges";
import { taskStatusLabel } from "./statusLabels";
import SystemState from "./SystemStates";

type TodayTasksProps = {
  tasks: TaskSummary[];
  compact?: boolean;
  shortageTasks?: ReservationShortageTask[];
  reservations?: ReservationRiskItem[];
};

const shown = (value: unknown) => value === null || value === undefined || value === "" ? "확인 필요" : String(value);
const codeLabel = (value: unknown) => {
  const labels: Record<string, string> = {
    DAY11_BASELINE_UNVALIDATED: "기준선 검증 전",
    DEADLINE_UNKNOWN: "마감일 정보 없음",
    RULE: "규칙 기반",
  };
  return typeof value === "string" ? labels[value] ?? shown(value) : shown(value);
};
const feedbackValue = (value: unknown) =>
  value !== null && typeof value === "object" ? JSON.stringify(value) : shown(value);
const featureLabels = {
  deadline: "마감일",
  risk: "위험도",
  business_impact: "사업 영향",
  aging: "경과 시간",
};

function ShortageTask({ task, reservation }: { task: ReservationShortageTask; reservation?: ReservationRiskItem }) {
  const [history, setHistory] = useState<TaskFeedback[] | null>(null);
  const [decision, setDecision] = useState<"EDIT" | "REJECT">("EDIT");
  const [field, setField] = useState<"title" | "deadline">("title");
  const [after, setAfter] = useState("");
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    let active = true;
    getTaskFeedback(task.id).then((response) => { if (active) setHistory(response.data); })
      .catch((failure: unknown) => { if (active) setError(failure instanceof Error ? failure.message : "의견 기록을 읽을 수 없습니다."); });
    return () => { active = false; };
  }, [task.id]);
  async function save() {
    if (saving || history === null) return;
    setSaving(true); setError(null); setSaved(false);
    try {
      const posted = await postTaskFeedback(task.id, {
        decision, target_field: decision === "REJECT" ? null : field,
        after_value: decision === "REJECT" ? null : after,
        reason, idempotency_key: crypto.randomUUID(),
        expected_version: history.at(-1)?.feedback_version ?? 0,
      });
      const readback = await getTaskFeedback(task.id);
      setHistory(readback.data);
      if (!readback.data.some((entry) => entry.id === posted.id)) throw new Error("서버 의견 기록에서 저장 항목을 확인하지 못했습니다.");
      setSaved(true);
      setReason(""); setAfter("");
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "의견을 저장하지 못했습니다.");
    } finally { setSaving(false); }
  }
  return <article className="today-task-card shortage-task-card" data-testid={`shortage-task-${task.id}`}>
    <header className="shortage-task-heading">
      <h3>{task.title}</h3>
      <small className="muted">예약 ID: {task.reservation_id}</small>
    </header>

    <section className="shortage-task-section" aria-label="예약 수량">
      <h4>예약 수량</h4>
      {reservation ? <>
        <dl className="shortage-quantity-grid">
          <div><dt>예약 수요</dt><dd>{shown(reservation.required_qty)}</dd></div>
          <div><dt>확보·배정</dt><dd>{shown(reservation.secured_qty)}</dd></div>
          <div><dt>확정 입고</dt><dd>{shown(reservation.confirmed_incoming_qty)}</dd></div>
          <div><dt>잠정 입고</dt><dd>{shown(reservation.tentative_incoming_qty)}</dd></div>
          <div><dt>부족 수량</dt><dd>{shown(reservation.shortage)}</dd></div>
        </dl>
        <p className="muted">계산 상태: {shown(reservation.calculation_status)}</p>
      </> : <p>예약 상세 확인 필요</p>}
    </section>

    <section className="shortage-task-section" aria-label="우선순위 근거">
      <h4>규칙 기반 우선순위: {task.priority}</h4>
      <p className="muted">규칙 버전: {shown(task.priority_rule_version)} · 검증 상태: {codeLabel(task.priority_calibration_status)}</p>
      <p className="muted">출처: {codeLabel(task.priority_provenance)} · 기준 시각: {shown(task.priority_as_of)}</p>
      <p className="muted">누락 feature: {task.priority_missing_features.length ? task.priority_missing_features.join(", ") : "없음"}</p>
      <div className="shortage-feature-list">
        {(["deadline", "risk", "business_impact", "aging"] as const).map((key) => {
          const feature = task.priority_breakdown[key];
          return <div className="shortage-feature" key={key}>
            <strong>{featureLabels[key]}</strong>
            <span className="shortage-feature-main">원본값 {codeLabel(feature.raw)} · 기여도 {shown(feature.contribution)}</span>
            <small className="muted">정규화 {shown(feature.normalized)} · 가중치 {shown(feature.weight)} · 사유 {codeLabel(feature.reason)}</small>
          </div>;
        })}
      </div>
    </section>

    <section className="shortage-task-section shortage-feedback" aria-label="내부 운영 의견">
      <h4>내부 운영 의견</h4>
      <p className="muted">내부 업무 의견입니다. 외부 시스템 변경이나 Agent 재개를 의미하지 않습니다.</p>
      <div className="shortage-feedback-fields">
        <label>의견 유형 <select value={decision} onChange={(event) => setDecision(event.target.value as "EDIT" | "REJECT")}><option value="EDIT">수정 의견</option><option value="REJECT">거절 의견</option></select></label>
        {decision === "EDIT" && <><label>수정 항목 <select value={field} onChange={(event) => setField(event.target.value as "title" | "deadline")}><option value="title">title</option><option value="deadline">deadline</option></select></label><label>수정 제안값 <input value={after} onChange={(event) => setAfter(event.target.value)} /></label></>}
        <label>사유 <textarea value={reason} onChange={(event) => setReason(event.target.value)} maxLength={500} /></label>
      </div>
      <button className="internal-action" type="button" disabled={saving || history === null || !reason.trim() || (decision === "EDIT" && !after.trim())} onClick={() => void save()}>{saving ? "저장 중" : decision === "EDIT" ? "수정 의견 저장" : "거절 의견 저장"}</button>
      {error && <p role="alert">{error}</p>}
      {saved && <p role="status">서버 의견 기록을 다시 확인했습니다.</p>}
      <div className="shortage-feedback-history">
        <h5>의견 기록: {history === null ? "확인 필요" : `${history.length}건`}</h5>
        {history?.map((entry) => <article className="shortage-feedback-entry" key={entry.id}>
          <strong>{entry.decision === "EDIT" ? "수정 의견" : "거절 의견"} · 버전 {entry.feedback_version}</strong>
          <dl>
            <div><dt>대상 필드</dt><dd>{shown(entry.target_field)}</dd></div>
            <div><dt>제안값</dt><dd>{feedbackValue(entry.after_value)}</dd></div>
            <div><dt>사유</dt><dd>{entry.reason}</dd></div>
            <div><dt>작성자</dt><dd>{entry.actor}</dd></div>
          </dl>
        </article>)}
      </div>
    </section>
  </article>;
}

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
  shortageTasks = [],
  reservations = [],
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
          {tasks.length + shortageTasks.length}건
        </span>
      </div>

      {tasks.length === 0 && shortageTasks.length === 0 ? (
        <SystemState
          state="empty"
          title="오늘 예정된 확인 업무가 없습니다"
          description="새로운 내부 확인 업무가 생성되면 이곳에 표시됩니다."
        />
      ) : (
        <div className="today-task-list">
          {shortageTasks.map((task) => <ShortageTask key={task.id} task={task} reservation={reservations.find((item) => item.reservation_id === task.reservation_id)} />)}
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
