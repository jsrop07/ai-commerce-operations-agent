import type {
  ScheduleDelayImpact,
  ScheduleDelayImpactItem,
  ScheduleImpactState,
  ScheduleSourceClassification,
} from "../../types/contracts";

export interface DelayImpactItemViewModel {
  targetType:
    | "TASK"
    | "RESERVATION_ORDER"
    | "LAUNCH_EVENT";

  targetTypeLabel: string;
  targetId: string;

  before: string | null;
  beforeLabel: string;

  after: string | null;
  afterLabel: string;

  lagHours: number | null;
  lagLabel: string;

  reason: string | null;
  reasonLabel: string;

  evidenceIds: string[];
}

export interface DelayImpactViewModel {
  incomingId: string;

  impactState: ScheduleImpactState;
  impactStateLabel: string;

  expectedAtBefore: string | null;
  expectedAtBeforeLabel: string;

  expectedAtAfter: string | null;
  expectedAtAfterLabel: string;

  criticalPathAffected: boolean | null;
  criticalPathLabel: string;

  tasks: DelayImpactItemViewModel[];
  reservations: DelayImpactItemViewModel[];
  launchEvents: DelayImpactItemViewModel[];

  totalImpactCount: number;

  asOf: string | null;
  asOfLabel: string;

  freshness: ScheduleDelayImpact["freshness"];

  quality: string | null;
  qualityLabel: string;

  sourceClassification:
    ScheduleSourceClassification;

  sourceLabel: string;
  sourceIsConfirmed: boolean;

  evidenceIds: string[];

  requestId: string;
  traceId: string;
}

function formatNullableDateTime(
  value: string | null,
): string {
  return value ?? "일정 미확정";
}

function formatImpactState(
  state: ScheduleImpactState,
): string {
  switch (state) {
    case "KNOWN":
      return "지연 영향 확인됨";

    case "NONE":
      return "영향 없음";

    case "UNKNOWN":
      return "영향 여부 미확정";

    case "BLOCKED":
      return "영향 계산 불가";
  }
}

function formatTargetType(
  type:
    ScheduleDelayImpactItem["target_type"],
): string {
  switch (type) {
    case "TASK":
      return "Task";

    case "RESERVATION_ORDER":
      return "예약주문";

    case "LAUNCH_EVENT":
      return "출시 일정";
  }
}

function formatCriticalPath(
  value: boolean | null,
): string {
  if (value === true) {
    return "Critical Path 영향 있음";
  }

  if (value === false) {
    return "Critical Path 영향 없음";
  }

  return "Critical Path 영향 미확정";
}

function formatSource(
  source: ScheduleSourceClassification,
): string {
  switch (source) {
    case "SANITIZED_REAL":
      return "실제 기반 비식별 자료";

    case "FIXTURE":
      return "테스트/데모 데이터";

    case "CONTRACT_ONLY":
      return "계약 검증 전용";

    case "BLOCKED":
      return "자료 없음 / 확인 불가";

    case "SOURCE_QUALITY_BLOCKED":
      return "원천 품질 문제";
  }
}

function isConfirmedSource(
  source: ScheduleSourceClassification,
): boolean {
  return source === "SANITIZED_REAL";
}

function toImpactItemViewModel(
  item: ScheduleDelayImpactItem,
): DelayImpactItemViewModel {
  return {
    targetType: item.target_type,

    targetTypeLabel:
      formatTargetType(
        item.target_type,
      ),

    targetId: item.target_id,

    before: item.before,
    beforeLabel:
      formatNullableDateTime(
        item.before,
      ),

    after: item.after,
    afterLabel:
      formatNullableDateTime(
        item.after,
      ),

    lagHours: item.lag_hours,
    lagLabel:
      item.lag_hours === null
        ? "지연 시간 미확정"
        : `${item.lag_hours}시간`,

    reason: item.reason,
    reasonLabel:
      item.reason ??
      "지연 사유 미확정",

    evidenceIds:
      item.evidence_ids ?? [],
  };
}

export function buildDelayImpactViewModel(
  impact: ScheduleDelayImpact,
): DelayImpactViewModel {
  const tasks =
    impact.affected_tasks.map(
      toImpactItemViewModel,
    );

  const reservations =
    impact.affected_reservations.map(
      toImpactItemViewModel,
    );

  const launchEvents =
    impact.affected_launch_events.map(
      toImpactItemViewModel,
    );

  return {
    incomingId:
      impact.incoming_id,

    impactState:
      impact.impact_state,

    impactStateLabel:
      formatImpactState(
        impact.impact_state,
      ),

    expectedAtBefore:
      impact.expected_at_before,

    expectedAtBeforeLabel:
      formatNullableDateTime(
        impact.expected_at_before,
      ),

    expectedAtAfter:
      impact.expected_at_after,

    expectedAtAfterLabel:
      formatNullableDateTime(
        impact.expected_at_after,
      ),

    criticalPathAffected:
      impact.critical_path_affected,

    criticalPathLabel:
      formatCriticalPath(
        impact.critical_path_affected,
      ),

    tasks,
    reservations,
    launchEvents,

    totalImpactCount:
      tasks.length +
      reservations.length +
      launchEvents.length,

    asOf:
      impact.as_of,

    asOfLabel:
      impact.as_of ??
      "기준 시각 미확정",

    freshness:
      impact.freshness,

    quality:
      impact.quality,

    qualityLabel:
      impact.quality ??
      "품질 상태 미확정",

    sourceClassification:
      impact.source_classification,

    sourceLabel:
      formatSource(
        impact.source_classification,
      ),

    sourceIsConfirmed:
      isConfirmedSource(
        impact.source_classification,
      ),

    evidenceIds:
      impact.evidence_ids ?? [],

    requestId:
      impact.request_id,

    traceId:
      impact.trace_id,
  };
}