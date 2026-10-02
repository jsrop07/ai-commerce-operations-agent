import type {
  ApiEnvelope,
  ScheduleDependency,
  ScheduleLaunchEvent,
  ScheduleSourceClassification,
  ScheduleDelayImpact,
  ScheduleDelayImpactItem,
  ScheduleTask,
  ScheduleFlow,
  Freshness,
  RiskLevel,
  TaskStatus,
  ScheduleReplanProposal,
  ScheduleReplanValue,
  ReservationShortageTask,
  TaskFeedback,
} from "../types/contracts";

const useRealBackend =
  import.meta.env.VITE_USE_REAL_BACKEND === "true";

const backendBaseUrl =
  import.meta.env.VITE_BACKEND_BASE_URL ?? "";

const sourceClassifications: ScheduleSourceClassification[] = [
  "LIVE_READ",
  "FILE_IMPORT",
  "UNKNOWN",
  "SANITIZED_REAL",
  "FIXTURE",
  "CONTRACT_ONLY",
  "BLOCKED",
  "SOURCE_QUALITY_BLOCKED",
];

const scheduleFlows: ScheduleFlow[] = [
  "FLOW_A",
  "FLOW_B",
];

const freshnessValues: Freshness[] = [
  "FRESH",
  "STALE",
  "UNKNOWN",
];

const riskLevels: RiskLevel[] = [
  "LOW",
  "MEDIUM",
  "HIGH",
];

const taskStatuses: TaskStatus[] = [
  "PROPOSED",
  "APPROVED",
  "IN_PROGRESS",
  "DONE",
  "BLOCKED",
  "DISMISSED",
];

function isRecord(
  value: unknown,
): value is Record<string, unknown> {
  return (
    typeof value === "object" &&
    value !== null &&
    !Array.isArray(value)
  );
}

async function realApiGet(
  path: string,
  signal?: AbortSignal,
): Promise<unknown> {
  const response = await fetch(
    `${backendBaseUrl}${path}`,
    {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
      signal,
    },
  );

  if (!response.ok) {
    throw await backendError(response);
  }

  return response.json();
}

function parseNullableString(
  value: unknown,
  fieldName: string,
): string | null {
  if (value === null) {
    return null;
  }

  if (typeof value !== "string") {
    throw new Error(
      `Schedule field ${fieldName} is malformed`,
    );
  }

  return value;
}

function parseNullableNumber(
  value: unknown,
  fieldName: string,
): number | null {
  if (value === null) {
    return null;
  }

  if (typeof value !== "number") {
    throw new Error(
      `Schedule field ${fieldName} is malformed`,
    );
  }

  return value;
}

function parseStringArray(
  value: unknown,
  fieldName: string,
): string[] {
  if (
    !Array.isArray(value) ||
    !value.every(
      (item) => typeof item === "string",
    )
  ) {
    throw new Error(
      `Schedule field ${fieldName} is malformed`,
    );
  }

  return value;
}

function parseSourceClassification(
  value: unknown,
): ScheduleSourceClassification {
  if (
    typeof value !== "string" ||
    !sourceClassifications.includes(
      value as ScheduleSourceClassification,
    )
  ) {
    throw new Error(
      "Schedule source classification is malformed",
    );
  }

  return value as ScheduleSourceClassification;
}

function parseFlow(
  value: unknown,
): ScheduleFlow {
  if (
    typeof value !== "string" ||
    !scheduleFlows.includes(
      value as ScheduleFlow,
    )
  ) {
    throw new Error(
      "Schedule flow is malformed",
    );
  }

  return value as ScheduleFlow;
}

function parseFreshness(
  value: unknown,
): Freshness {
  if (
    typeof value !== "string" ||
    !freshnessValues.includes(
      value as Freshness,
    )
  ) {
    throw new Error(
      "Schedule freshness is malformed",
    );
  }

  return value as Freshness;
}

function parseLaunchEvent(
  value: unknown,
): ScheduleLaunchEvent {
  if (
    !isRecord(value) ||
    typeof value.id !== "string" ||
    typeof value.product_id !== "string" ||
    typeof value.launch_at !== "string" ||
    typeof value.flow_template !== "string" ||
    typeof value.status !== "string" ||
    typeof value.template_id !== "string" ||
    typeof value.version !== "string" ||
    typeof value.timezone !== "string"
  ) {
    throw new Error(
      "Backend schedule launch event is malformed",
    );
  }

  return {
    id: value.id,
    product_id: value.product_id,
    launch_at: value.launch_at,
    flow_template: value.flow_template,
    status: value.status,
    flow: parseFlow(value.flow),
    template_id: value.template_id,
    version: value.version,
    timezone: value.timezone,
    as_of: parseNullableString(
      value.as_of,
      "as_of",
    ),
    freshness: parseFreshness(
      value.freshness,
    ),
    source_classification:
      parseSourceClassification(
        value.source_classification,
      ),
    evidence_ids:
      value.evidence_ids === undefined
        ? undefined
        : parseStringArray(
            value.evidence_ids,
            "evidence_ids",
          ),
  };
}

function parseTask(
  value: unknown,
): ScheduleTask | ReservationShortageTask {
  if (isRecord(value) && value.task_type === "RESERVATION_SHORTAGE") return parseReservationShortageTask(value);
  if (
    !isRecord(value) ||
    typeof value.id !== "string" ||
    typeof value.type !== "string" ||
    typeof value.title !== "string" ||
    typeof value.source_reason !== "string" ||
    typeof value.priority !== "string" ||
    !riskLevels.includes(
      value.priority as RiskLevel,
    ) ||
    typeof value.status !== "string" ||
    !taskStatuses.includes(
      value.status as TaskStatus,
    )
  ) {
    throw new Error(
      "Backend schedule task is malformed",
    );
  }

  return {
    id: value.id,
    type: value.type,
    title: value.title,
    deadline: parseNullableString(
      value.deadline,
      "deadline",
    ),
    priority: value.priority as RiskLevel,
    status: value.status as TaskStatus,
    source_reason: value.source_reason,
    owner: parseNullableString(
      value.owner,
      "owner",
    ),
    duration_hours: parseNullableNumber(
      value.duration_hours,
      "duration_hours",
    ),
    flow: parseFlow(value.flow),
    as_of: parseNullableString(
      value.as_of,
      "as_of",
    ),
    freshness: parseFreshness(
      value.freshness,
    ),
    source_classification:
      parseSourceClassification(
        value.source_classification,
      ),
    evidence_ids:
      value.evidence_ids === undefined
        ? undefined
        : parseStringArray(
            value.evidence_ids,
            "evidence_ids",
          ),
  };
}

function parseReservationShortageTask(value: Record<string, unknown>): ReservationShortageTask {
  if (typeof value.id !== "string" || typeof value.tenant_id !== "string" ||
      typeof value.reservation_id !== "string" || typeof value.sku_id !== "string" ||
      typeof value.title !== "string" || typeof value.priority !== "number" ||
      typeof value.priority_rule_score !== "number" || value.priority !== value.priority_rule_score ||
      typeof value.source_reason !== "string" || typeof value.source_classification !== "string" ||
      typeof value.status !== "string" || !taskStatuses.includes(value.status as TaskStatus) ||
      !isRecord(value.priority_breakdown) ||
      typeof value.replay_count !== "number" || typeof value.priority_coverage_weight !== "number" ||
      typeof value.priority_rule_version !== "string" || typeof value.priority_provenance !== "string" ||
      typeof value.priority_calibration_status !== "string" ||
      !(value.task_id === undefined || typeof value.task_id === "string")) throw new Error("Backend reservation shortage task is malformed");
  const breakdown = {} as ReservationShortageTask["priority_breakdown"];
  for (const key of ["deadline", "risk", "business_impact", "aging"] as const) {
    const feature = value.priority_breakdown[key];
    if (!isRecord(feature) ||
        !(feature.raw === null || typeof feature.raw === "string" || typeof feature.raw === "number") ||
        !(feature.normalized === null || typeof feature.normalized === "number") ||
        typeof feature.weight !== "number" ||
        !(feature.contribution === null || typeof feature.contribution === "number") ||
        !(feature.reason === null || typeof feature.reason === "string")) throw new Error(`Backend priority ${key} is malformed`);
    breakdown[key] = feature as unknown as ReservationShortageTask["priority_breakdown"][typeof key];
  }
  return {
    id: value.id, task_id: value.task_id,
    tenant_id: value.tenant_id, reservation_id: value.reservation_id, sku_id: value.sku_id,
    task_type: "RESERVATION_SHORTAGE", title: value.title,
    deadline: parseNullableString(value.deadline, "deadline"),
    risk_level: parseNullableString(value.risk_level, "risk_level"),
    affected_count: parseNullableNumber(value.affected_count, "affected_count"),
    aging_hours: parseNullableNumber(value.aging_hours, "aging_hours"),
    priority: value.priority, priority_reason: parseNullableString(value.priority_reason, "priority_reason"),
    status: value.status as TaskStatus, source_reason: value.source_reason,
    source_classification: value.source_classification,
    evidence_ids: parseStringArray(value.evidence_ids, "evidence_ids"),
    as_of: parseNullableString(value.as_of, "as_of"),
    replay_count: value.replay_count, priority_rule_score: value.priority_rule_score,
    priority_breakdown: breakdown, priority_rule_version: value.priority_rule_version,
    priority_provenance: value.priority_provenance,
    priority_calibration_status: value.priority_calibration_status,
    priority_missing_features: parseStringArray(value.priority_missing_features, "priority_missing_features"),
    priority_coverage_weight: value.priority_coverage_weight,
    priority_as_of: parseNullableString(value.priority_as_of, "priority_as_of"),
  };
}

function parseDependency(
  value: unknown,
): ScheduleDependency {
  if (
    !isRecord(value) ||
    typeof value.predecessor_id !== "string" ||
    typeof value.successor_id !== "string"
  ) {
    throw new Error(
      "Backend schedule dependency is malformed",
    );
  }

  return {
    predecessor_id: value.predecessor_id,
    successor_id: value.successor_id,
    lag_hours: parseNullableNumber(
      value.lag_hours,
      "lag_hours",
    ),
    as_of: parseNullableString(
      value.as_of,
      "as_of",
    ),
    source_classification:
      parseSourceClassification(
        value.source_classification,
      ),
    evidence_ids:
      value.evidence_ids === undefined
        ? undefined
        : parseStringArray(
            value.evidence_ids,
            "evidence_ids",
          ),
  };
}

function parseEnvelope<T>(
  value: unknown,
  parseItem: (item: unknown) => T,
): ApiEnvelope<T[]> {
  if (
    !isRecord(value) ||
    value.schema_version !== "1.0" ||
    typeof value.tenant_id !== "string" ||
    typeof value.request_id !== "string" ||
    typeof value.trace_id !== "string" ||
    !Array.isArray(value.data) ||
    !Array.isArray(value.evidence_ids) ||
    !Array.isArray(value.warnings) ||
    typeof value.as_of !== "string"
  ) {
    throw new Error(
      "Backend schedule envelope is malformed",
    );
  }

  return {
    schema_version: value.schema_version,
    tenant_id: value.tenant_id,
    request_id: value.request_id,
    trace_id: value.trace_id,
    data: value.data.map(parseItem),
    evidence_ids: parseStringArray(
      value.evidence_ids,
      "evidence_ids",
    ),
    warnings: parseStringArray(
      value.warnings,
      "warnings",
    ),
    as_of: value.as_of,
  };
}

export function parseDay10LaunchEventsResponse(
  value: unknown,
): ApiEnvelope<ScheduleLaunchEvent[]> {
  return parseEnvelope(
    value,
    parseLaunchEvent,
  );
}

export function parseDay10TasksResponse(
  value: unknown,
): ApiEnvelope<(ScheduleTask | ReservationShortageTask)[]> {
  return parseEnvelope(
    value,
    parseTask,
  );
}

export function parseDay10DependenciesResponse(
  value: unknown,
): ApiEnvelope<ScheduleDependency[]> {
  return parseEnvelope(
    value,
    parseDependency,
  );
}

function assertRealBackend(): void {
  if (!useRealBackend) {
    throw new Error(
      "Day 10 actual schedule adapter requires real backend mode",
    );
  }
}

export async function getDay10LaunchEvents(
  signal?: AbortSignal,
): Promise<ApiEnvelope<ScheduleLaunchEvent[]>> {
  assertRealBackend();

  return parseDay10LaunchEventsResponse(
    await realApiGet(
      "/api/v1/launch-events",
      signal,
    ),
  );
}

export async function getDay10Tasks(
  signal?: AbortSignal,
): Promise<ApiEnvelope<(ScheduleTask | ReservationShortageTask)[]>> {
  assertRealBackend();

  return parseDay10TasksResponse(
    await realApiGet(
      "/api/v1/tasks",
      signal,
    ),
  );
}

export async function getDay10Dependencies(
  signal?: AbortSignal,
): Promise<ApiEnvelope<ScheduleDependency[]>> {
  assertRealBackend();

  return parseDay10DependenciesResponse(
    await realApiGet(
      "/api/v1/schedule/dependencies",
      signal,
    ),
  );
}

function parseScheduleImpactItem(
  value: unknown,
): ScheduleDelayImpactItem {
  if (
    !isRecord(value) ||
    typeof value.target_type !== "string" ||
    ![
      "TASK",
      "RESERVATION_ORDER",
      "LAUNCH_EVENT",
    ].includes(value.target_type) ||
    typeof value.target_id !== "string"
  ) {
    throw new Error(
      "Backend schedule delay impact item is malformed",
    );
  }

  return {
    target_type:
      value.target_type as ScheduleDelayImpactItem["target_type"],

    target_id: value.target_id,

    before: parseNullableString(
      value.before,
      "before",
    ),

    after: parseNullableString(
      value.after,
      "after",
    ),

    lag_hours: parseNullableNumber(
      value.lag_hours,
      "lag_hours",
    ),

    reason:
      value.reason === undefined
        ? null
        : parseNullableString(
            value.reason,
            "reason",
          ),

    evidence_ids:
      value.evidence_ids === undefined
        ? undefined
        : parseStringArray(
            value.evidence_ids,
            "evidence_ids",
          ),
    source_id: value.source_id === undefined ? null : parseNullableString(value.source_id, "source_id"),
  };
}

function parseC08Impact(value: Record<string, unknown>): ScheduleDelayImpact {
  if (typeof value.incoming_id !== "string" || typeof value.source_id !== "string" ||
      !["CONTRACT_ONLY", "CALCULATED", "BLOCKED"].includes(String(value.status)) ||
      typeof value.actual_delay_confirmed !== "boolean" ||
      !Array.isArray(value.impact_path) ||
      !Array.isArray(value.impacted_task_ids) || !Array.isArray(value.impacted_reservation_ids) ||
      !Array.isArray(value.impacted_launch_event_ids) ||
      (value.data_mode !== undefined && value.data_mode !== "SYNTHETIC_DEMO")) {
    throw new Error("Backend C08 delay impact is malformed");
  }
  const paths = value.impact_path.map((path) => {
    if (!isRecord(path) || typeof path.source_id !== "string") {
      throw new Error("Backend C08 impact path is malformed");
    }
    return parseScheduleImpactItem({ ...path, target_type: path.target_type === "RESERVATION" ? "RESERVATION_ORDER" : path.target_type });
  });
  const targets = (ids: unknown[], type: ScheduleDelayImpactItem["target_type"]) => {
    const checked = parseStringArray(ids, `impacted_${type}_ids`);
    return checked.map((id) => {
      const path = paths.find((item) => item.target_type === type && item.target_id === id);
      return path ?? { target_type: type, target_id: id, before: null, after: null,
        lag_hours: null, reason: null, source_id: null, evidence_ids: [] };
    });
  };
  return {
    incoming_id: value.incoming_id,
    expected_at_before: null, expected_at_after: null,
    impact_state: value.status === "BLOCKED" ? "BLOCKED" :
      (value.impacted_task_ids.length + value.impacted_reservation_ids.length + value.impacted_launch_event_ids.length > 0 ? "KNOWN" : "UNKNOWN"),
    affected_tasks: targets(value.impacted_task_ids, "TASK"),
    affected_reservations: targets(value.impacted_reservation_ids, "RESERVATION_ORDER"),
    affected_launch_events: targets(value.impacted_launch_event_ids, "LAUNCH_EVENT"),
    critical_path_affected: Array.isArray(value.critical_path) ? value.critical_path.length > 0 : null,
    as_of: parseNullableString(value.as_of, "as_of"),
    freshness: parseFreshness(value.freshness),
    quality: parseNullableString(value.quality, "quality"),
    source_classification: parseSourceClassification(value.source_classification),
    evidence_ids: parseStringArray(value.evidence_ids, "evidence_ids"),
    request_id: "", trace_id: "",
    data_mode: value.data_mode as "SYNTHETIC_DEMO" | undefined,
    status: value.status as ScheduleDelayImpact["status"],
    actual_delay_confirmed: value.actual_delay_confirmed,
    delay_hours: parseNullableNumber(value.delay_hours, "delay_hours"),
    source_id: value.source_id,
    critical_path: parseStringArray(value.critical_path, "critical_path"),
    reason: typeof value.reason === "string" ? value.reason : undefined,
  };
}

function parseScheduleImpactItems(
  value: unknown,
  fieldName: string,
): ScheduleDelayImpactItem[] {
  if (!Array.isArray(value)) {
    throw new Error(
      `Schedule field ${fieldName} is malformed`,
    );
  }

  return value.map(
    parseScheduleImpactItem,
  );
}

function parseImpactState(
  value: unknown,
): ScheduleDelayImpact["impact_state"] {
  if (
    typeof value !== "string" ||
    ![
      "KNOWN",
      "NONE",
      "UNKNOWN",
      "BLOCKED",
    ].includes(value)
  ) {
    throw new Error(
      "Schedule impact state is malformed",
    );
  }

  return value as ScheduleDelayImpact["impact_state"];
}

function parseNullableBoolean(
  value: unknown,
  fieldName: string,
): boolean | null {
  if (value === null) {
    return null;
  }

  if (typeof value !== "boolean") {
    throw new Error(
      `Schedule field ${fieldName} is malformed`,
    );
  }

  return value;
}

function parseDelayImpact(
  value: unknown,
): ScheduleDelayImpact {
  if (isRecord(value) && "impact_path" in value) return parseC08Impact(value);
  if (
    !isRecord(value) ||
    typeof value.incoming_id !== "string" ||
    typeof value.request_id !== "string" ||
    typeof value.trace_id !== "string"
  ) {
    throw new Error(
      "Backend schedule delay impact is malformed",
    );
  }

  return {
    incoming_id: value.incoming_id,

    expected_at_before:
      parseNullableString(
        value.expected_at_before,
        "expected_at_before",
      ),

    expected_at_after:
      parseNullableString(
        value.expected_at_after,
        "expected_at_after",
      ),

    impact_state:
      parseImpactState(
        value.impact_state,
      ),

    affected_tasks:
      parseScheduleImpactItems(
        value.affected_tasks,
        "affected_tasks",
      ),

    affected_reservations:
      parseScheduleImpactItems(
        value.affected_reservations,
        "affected_reservations",
      ),

    affected_launch_events:
      parseScheduleImpactItems(
        value.affected_launch_events,
        "affected_launch_events",
      ),

    critical_path_affected:
      parseNullableBoolean(
        value.critical_path_affected,
        "critical_path_affected",
      ),

    as_of:
      parseNullableString(
        value.as_of,
        "as_of",
      ),

    freshness:
      parseFreshness(
        value.freshness,
      ),

    quality:
      value.quality === undefined
        ? null
        : parseNullableString(
            value.quality,
            "quality",
          ),

    source_classification:
      parseSourceClassification(
        value.source_classification,
      ),

    evidence_ids:
      value.evidence_ids === undefined
        ? undefined
        : parseStringArray(
            value.evidence_ids,
            "evidence_ids",
          ),

    request_id: value.request_id,
    trace_id: value.trace_id,
  };
}

export function parseDay10DelayImpactsResponse(
  value: unknown,
): ApiEnvelope<ScheduleDelayImpact[]> {
  return parseEnvelope(
    value,
    parseDelayImpact,
  );
}

export function parseDay10DelayImpactResponse(
  value: unknown,
): ScheduleDelayImpact {
  return parseDelayImpact(value);
}

export async function getDay10DelayImpacts(
  signal?: AbortSignal,
): Promise<ApiEnvelope<ScheduleDelayImpact[]>> {
  assertRealBackend();

  return parseDay10DelayImpactsResponse(
    await realApiGet(
      "/api/v1/schedule/delay-impacts",
      signal,
    ),
  );
}

export async function getDay10DelayImpact(
  incomingId: string,
  signal?: AbortSignal,
): Promise<ScheduleDelayImpact> {
  assertRealBackend();

  return parseDay10DelayImpactResponse(
    (await realApiGet(
      `/api/v1/schedule/delay-impacts/${encodeURIComponent(
        incomingId,
      )}`,
      signal,
    ) as { data: unknown }).data,
  );
}

function parseReplanValue(
  value: unknown,
): ScheduleReplanValue {
  if (
    !isRecord(value) ||
    typeof value.target_type !== "string" ||
    ![
      "TASK",
      "RESERVATION_ORDER",
      "LAUNCH_EVENT",
    ].includes(value.target_type) ||
    typeof value.target_id !== "string"
  ) {
    throw new Error(
      "Backend schedule replan value is malformed",
    );
  }

  return {
    target_type:
      value.target_type as ScheduleReplanValue["target_type"],

    target_id:
      value.target_id,

    scheduled_at:
      parseNullableString(
        value.scheduled_at,
        "scheduled_at",
      ),

    evidence_ids:
      value.evidence_ids === undefined
        ? undefined
        : parseStringArray(
            value.evidence_ids,
            "evidence_ids",
          ),
  };
}

function parseReplanValues(
  value: unknown,
  fieldName: string,
): ScheduleReplanValue[] {
  if (!Array.isArray(value)) {
    throw new Error(
      `Schedule field ${fieldName} is malformed`,
    );
  }

  return value.map(
    parseReplanValue,
  );
}

function parseReplanStatus(
  value: unknown,
): ScheduleReplanProposal["status"] {
  if (
    typeof value !== "string" ||
    ![
      "PROPOSED",
      "APPROVED",
      "EDITED",
      "REJECTED",
      "EXPIRED",
    ].includes(value)
  ) {
    throw new Error(
      "Schedule replan status is malformed",
    );
  }

  return value as ScheduleReplanProposal["status"];
}

function parseNullableConfidence(
  value: unknown,
): number | null {
  if (value === null) {
    return null;
  }

  if (
    typeof value !== "number" ||
    value < 0 ||
    value > 1
  ) {
    throw new Error(
      "Schedule replan confidence is malformed",
    );
  }

  return value;
}

function parseReplanProposal(
  value: unknown,
): ScheduleReplanProposal {
  if (isRecord(value) && "before_schedule" in value) {
    if (typeof value.proposal_id !== "string" || typeof value.source_incoming_id !== "string" ||
        typeof value.reason !== "string" || value.external_execution_allowed !== false ||
        !Array.isArray(value.before_schedule) || !Array.isArray(value.proposed_schedule) ||
        !Array.isArray(value.downstream_impact)) throw new Error("Backend C08 replan proposal is malformed");
    const values = (items: unknown[]): ScheduleReplanValue[] => items.map((item) => {
      if (!isRecord(item)) throw new Error("Backend C08 replan value is malformed");
      return parseReplanValue({ target_type: item.item_type === "RESERVATION" ? "RESERVATION_ORDER" : item.item_type,
        target_id: item.item_id, scheduled_at: item.scheduled_at });
    });
    return {
      proposal_id: value.proposal_id, incoming_id: value.source_incoming_id,
      source_incoming_id: value.source_incoming_id, status: parseReplanStatus(value.status),
      before: values(value.before_schedule), proposed_after: values(value.proposed_schedule),
      reason: value.reason, confidence: parseNullableConfidence(value.confidence),
      downstream_impact: parseStringArray(value.downstream_impact, "downstream_impact").join(", "),
      conflict: null, as_of: null, freshness: "UNKNOWN", source_classification: "UNKNOWN",
      evidence_ids: parseStringArray(value.evidence_ids, "evidence_ids"),
      request_id: "", trace_id: "", external_execution_allowed: false,
    };
  }
  if (
    !isRecord(value) ||
    typeof value.proposal_id !== "string" ||
    typeof value.reason !== "string" ||
    typeof value.request_id !== "string" ||
    typeof value.trace_id !== "string" ||
    value.external_execution_allowed !== false
  ) {
    throw new Error(
      "Backend schedule replan proposal is malformed",
    );
  }

  return {
    proposal_id:
      value.proposal_id,

    incoming_id:
      parseNullableString(
        value.incoming_id,
        "incoming_id",
      ),

    status:
      parseReplanStatus(
        value.status,
      ),

    before:
      parseReplanValues(
        value.before,
        "before",
      ),

    proposed_after:
      parseReplanValues(
        value.proposed_after,
        "proposed_after",
      ),

    reason:
      value.reason,

    confidence:
      parseNullableConfidence(
        value.confidence,
      ),

    downstream_impact:
      parseNullableString(
        value.downstream_impact,
        "downstream_impact",
      ),

    conflict:
      parseNullableString(
        value.conflict,
        "conflict",
      ),

    as_of:
      parseNullableString(
        value.as_of,
        "as_of",
      ),

    freshness:
      parseFreshness(
        value.freshness,
      ),

    source_classification:
      parseSourceClassification(
        value.source_classification,
      ),

    evidence_ids:
      value.evidence_ids === undefined
        ? undefined
        : parseStringArray(
            value.evidence_ids,
            "evidence_ids",
          ),

    request_id:
      value.request_id,

    trace_id:
      value.trace_id,

    external_execution_allowed:
      false,
  };
}

export function parseDay10ReplanProposalsResponse(
  value: unknown,
): ApiEnvelope<ScheduleReplanProposal[]> {
  return parseEnvelope(
    value,
    parseReplanProposal,
  );
}

export function parseDay10ReplanProposalResponse(
  value: unknown,
): ScheduleReplanProposal {
  return parseReplanProposal(value);
}

export async function getDay10ReplanProposals(
  signal?: AbortSignal,
): Promise<ApiEnvelope<ScheduleReplanProposal[]>> {
  assertRealBackend();

  return parseDay10ReplanProposalsResponse(
    await realApiGet(
      "/api/v1/schedule/replan-proposals",
      signal,
    ),
  );
}

export async function getDay10ReplanProposal(
  proposalId: string,
  signal?: AbortSignal,
): Promise<ScheduleReplanProposal> {
  assertRealBackend();

  return parseDay10ReplanProposalResponse(
    (await realApiGet(
      `/api/v1/schedule/replan-proposals/${encodeURIComponent(
        proposalId,
      )}`,
      signal,
    ) as { data: unknown }).data,
  );
}

export interface DemoSchedulePrepareResult {
  status: "READY" | "ALREADY_READY";
  data_mode: "SYNTHETIC_DEMO";
  created_count: number;
  row_count: number;
  snapshot_id: string;
  snapshot_sha256: string;
}

export async function prepareDay10DemoSchedule(): Promise<DemoSchedulePrepareResult> {
  assertRealBackend();
  const value = await realApiPost("/api/v1/demo/schedule/prepare", undefined);
  if (!isRecord(value) || !["READY", "ALREADY_READY"].includes(String(value.status)) ||
      value.data_mode !== "SYNTHETIC_DEMO" || typeof value.created_count !== "number" ||
      typeof value.row_count !== "number" || typeof value.snapshot_id !== "string" ||
      typeof value.snapshot_sha256 !== "string" ||
      value.snapshot_id !== "c08-r08-synthetic-v1" ||
      value.snapshot_sha256 !== "aefc694a5c3364752934f2a33616500b464f3e1e21a27413b6f7420a56b45d40")
    throw new Error("Backend C08 prepare response is malformed");
  return value as unknown as DemoSchedulePrepareResult;
}

export async function draftDay10DemoReplan(impact: ScheduleDelayImpact): Promise<ScheduleReplanProposal> {
  assertRealBackend();
  if (impact.data_mode !== "SYNTHETIC_DEMO" || impact.status !== "CONTRACT_ONLY" ||
      impact.actual_delay_confirmed !== false || impact.source_classification !== "FIXTURE" ||
      impact.as_of === null || impact.delay_hours === undefined || impact.source_id == null ||
      impact.reason === undefined || impact.critical_path === undefined) {
    throw new Error("C08 합성 예시 영향만 제안할 수 있습니다.");
  }
  const path = [...impact.affected_tasks, ...impact.affected_reservations, ...impact.affected_launch_events];
  if (path.some((item) => item.source_id == null || item.reason == null || item.lag_hours == null)) {
    throw new Error("C08 영향 경로의 필수 값이 확인되지 않았습니다.");
  }
  const current_schedule = path.filter((item) => item.before !== null && item.target_type !== "RESERVATION_ORDER")
    .map((item) => ({ item_type: item.target_type, item_id: item.target_id, scheduled_at: item.before }));
  const body = { current_schedule, created_at: new Date().toISOString(), confidence: 0.8,
    impact: { status: impact.status, actual_delay_confirmed: impact.actual_delay_confirmed,
      incoming_id: impact.incoming_id, delay_hours: impact.delay_hours, source_id: impact.source_id,
      source_classification: impact.source_classification, as_of: impact.as_of,
      freshness: impact.freshness, quality: impact.quality, evidence_ids: impact.evidence_ids ?? [],
      impacted_task_ids: impact.affected_tasks.map((item) => item.target_id),
      impacted_reservation_ids: impact.affected_reservations.map((item) => item.target_id),
      impacted_launch_event_ids: impact.affected_launch_events.map((item) => item.target_id),
      critical_path: impact.critical_path,
      impact_path: path.map((item) => ({ target_type: item.target_type === "RESERVATION_ORDER" ? "RESERVATION" : item.target_type,
        target_id: item.target_id, source_id: item.source_id, before: item.before, after: item.after,
        lag_hours: item.lag_hours, reason: item.reason, evidence_ids: item.evidence_ids ?? [] })),
      reason: impact.reason } };
  const response = await realApiPost("/api/v1/demo/schedule/replan-proposals/draft", body);
  if (!isRecord(response)) throw new Error("Backend C08 draft envelope is malformed");
  return parseDay10ReplanProposalResponse(response.data);
}

function parseFeedback(value: unknown): TaskFeedback {
  if (!isRecord(value) || typeof value.id !== "string" || typeof value.task_id !== "string" ||
      typeof value.feedback_version !== "number" || typeof value.reason !== "string" ||
      (value.decision !== "EDIT" && value.decision !== "REJECT")) throw new Error("Backend task feedback is malformed");
  return value as unknown as TaskFeedback;
}

export async function getTaskFeedback(taskId: string): Promise<ApiEnvelope<TaskFeedback[]>> {
  assertRealBackend();
  return parseEnvelope(await realApiGet(`/api/v1/tasks/${encodeURIComponent(taskId)}/feedback`), parseFeedback);
}

export async function postTaskFeedback(taskId: string, body: {
  decision: "EDIT" | "REJECT"; target_field: "title" | "deadline" | null;
  after_value: unknown; reason: string; idempotency_key: string; expected_version: number;
}): Promise<TaskFeedback> {
  assertRealBackend();
  if (!body.reason.trim() || body.reason.length > 500) throw new Error("의견 사유를 1~500자로 입력하세요.");
  const raw = await realApiPost(`/api/v1/tasks/${encodeURIComponent(taskId)}/feedback`, body);
  if (!isRecord(raw)) throw new Error("Backend task feedback envelope is malformed");
  return parseFeedback(raw.data);
}

async function backendError(response: Response): Promise<Error> {
  const body = await response.json().catch(() => null);
  const code = body?.detail?.code ?? body?.error?.code;
  return new Error(`${response.status} ${typeof code === "string" ? code : "Backend request failed"}`);
}

async function realApiPost(path: string, body: unknown): Promise<unknown> {
  const response = await fetch(`${backendBaseUrl}${path}`, {
    method: "POST",
    headers: { Accept: "application/json", ...(body === undefined ? {} : { "Content-Type": "application/json" }) },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  if (!response.ok) throw await backendError(response);
  return response.json();
}
