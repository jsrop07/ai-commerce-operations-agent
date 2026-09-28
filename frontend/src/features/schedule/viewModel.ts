import type {
  ScheduleDependency,
  ScheduleLaunchEvent,
  ScheduleSourceClassification,
  ScheduleTask,
} from "../../types/contracts";

export interface ScheduleBoardViewModel {
  timezone: string | null;
  asOf: string | null;

  launchEvents: ScheduleLaunchEventViewModel[];
  tasks: ScheduleTaskViewModel[];
  dependencies: ScheduleDependencyViewModel[];
}

export interface ScheduleLaunchEventViewModel {
  id: string;
  productId: string;

  flow: "FLOW_A" | "FLOW_B";
  flowLabel: "Flow A" | "Flow B";

  templateId: string;
  version: string;

  launchAt: string;
  launchAtLabel: string;

  timezone: string;

  status: string;

  asOf: string | null;
  asOfLabel: string;

  sourceClassification:
    ScheduleSourceClassification;
  sourceLabel: string;
  sourceIsConfirmed: boolean;

  evidenceIds: string[];
}

export interface ScheduleTaskViewModel {
  id: string;
  type: string;
  title: string;

  flow: "FLOW_A" | "FLOW_B";
  flowLabel: "Flow A" | "Flow B";

  deadline: string | null;
  deadlineLabel: string;

  owner: string | null;
  ownerLabel: string;

  durationHours: number | null;
  durationLabel: string;

  priority: ScheduleTask["priority"];
  status: ScheduleTask["status"];

  sourceReason: string;

  asOf: string | null;
  asOfLabel: string;

  sourceClassification:
    ScheduleSourceClassification;
  sourceLabel: string;
  sourceIsConfirmed: boolean;

  evidenceIds: string[];
}

export interface ScheduleDependencyViewModel {
  predecessorId: string;
  successorId: string;

  lagHours: number | null;
  lagLabel: string;

  asOf: string | null;
  asOfLabel: string;

  sourceClassification:
    ScheduleSourceClassification;
  sourceLabel: string;
  sourceIsConfirmed: boolean;

  evidenceIds: string[];
}

function formatDateTime(
  value: string | null,
  emptyLabel: string,
): string {
  if (value === null) {
    return emptyLabel;
  }

  return value;
}

function formatFlow(
  flow: "FLOW_A" | "FLOW_B",
): "Flow A" | "Flow B" {
  return flow === "FLOW_A"
    ? "Flow A"
    : "Flow B";
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

function toLaunchEventViewModel(
  item: ScheduleLaunchEvent,
): ScheduleLaunchEventViewModel {
  return {
    id: item.id,
    productId: item.product_id,

    flow: item.flow,
    flowLabel: formatFlow(item.flow),

    templateId: item.template_id,
    version: item.version,

    launchAt: item.launch_at,
    launchAtLabel: item.launch_at,

    timezone: item.timezone,

    status: item.status,

    asOf: item.as_of,
    asOfLabel: formatDateTime(
      item.as_of,
      "기준 시각 미확정",
    ),

    sourceClassification:
      item.source_classification,
    sourceLabel: formatSource(
      item.source_classification,
    ),
    sourceIsConfirmed:
      isConfirmedSource(
        item.source_classification,
      ),

    evidenceIds:
      item.evidence_ids ?? [],
  };
}

function toTaskViewModel(
  item: ScheduleTask,
): ScheduleTaskViewModel {
  return {
    id: item.id,
    type: item.type,
    title: item.title,

    flow: item.flow,
    flowLabel: formatFlow(item.flow),

    deadline: item.deadline,
    deadlineLabel: formatDateTime(
      item.deadline,
      "마감일 미확정",
    ),

    owner: item.owner,
    ownerLabel:
      item.owner ?? "담당자 미확정",

    durationHours: item.duration_hours,
    durationLabel:
      item.duration_hours === null
        ? "소요시간 미확정"
        : `${item.duration_hours}시간`,

    priority: item.priority,
    status: item.status,

    sourceReason: item.source_reason,

    asOf: item.as_of,
    asOfLabel: formatDateTime(
      item.as_of,
      "기준 시각 미확정",
    ),

    sourceClassification:
      item.source_classification,
    sourceLabel: formatSource(
      item.source_classification,
    ),
    sourceIsConfirmed:
      isConfirmedSource(
        item.source_classification,
      ),

    evidenceIds:
      item.evidence_ids ?? [],
  };
}

function toDependencyViewModel(
  item: ScheduleDependency,
): ScheduleDependencyViewModel {
  return {
    predecessorId:
      item.predecessor_id,
    successorId:
      item.successor_id,

    lagHours: item.lag_hours,
    lagLabel:
      item.lag_hours === null
        ? "간격 미확정"
        : `${item.lag_hours}시간`,

    asOf: item.as_of,
    asOfLabel: formatDateTime(
      item.as_of,
      "기준 시각 미확정",
    ),

    sourceClassification:
      item.source_classification,
    sourceLabel: formatSource(
      item.source_classification,
    ),
    sourceIsConfirmed:
      isConfirmedSource(
        item.source_classification,
      ),

    evidenceIds:
      item.evidence_ids ?? [],
  };
}

export function buildScheduleBoardViewModel(
  launchEvents: ScheduleLaunchEvent[],
  tasks: ScheduleTask[],
  dependencies: ScheduleDependency[],
): ScheduleBoardViewModel {
  const timezone =
    launchEvents[0]?.timezone ?? null;

  const asOf =
    launchEvents.find(
      (item) => item.as_of !== null,
    )?.as_of ??
    tasks.find(
      (item) => item.as_of !== null,
    )?.as_of ??
    dependencies.find(
      (item) => item.as_of !== null,
    )?.as_of ??
    null;

  return {
    timezone,
    asOf,

    launchEvents:
      launchEvents.map(
        toLaunchEventViewModel,
      ),

    tasks:
      tasks.map(
        toTaskViewModel,
      ),

    dependencies:
      dependencies.map(
        toDependencyViewModel,
      ),
  };
}