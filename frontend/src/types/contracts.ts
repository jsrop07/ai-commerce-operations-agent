export type Environment = "LOCAL" | "TEST" | "DEMO" | "PRODUCTION_READ" | "PILOT_SHADOW" | "PILOT_APPROVED";
export type Provider = "CAFE24" | "TOSS_POS" | "ECOUNT" | "DEMO";
export type Freshness = "FRESH" | "STALE" | "UNKNOWN";
export type InventoryQualityStatus =
  | "USABLE"
  | "STALE"
  | "UNMAPPED"
  | "QUARANTINED"
  | "SOURCE_QUALITY_BLOCKED";
export type RiskLevel = "LOW" | "MEDIUM" | "HIGH" | "PROHIBITED";
export type TaskStatus = "PROPOSED" | "APPROVED" | "IN_PROGRESS" | "DONE" | "BLOCKED" | "DISMISSED";

export interface ApiEnvelope<T> {
  schema_version: "1.0";
  tenant_id: string;
  request_id: string;
  trace_id: string;
  data: T;
  evidence_ids: string[];
  warnings: string[];
  as_of: string;
}

export interface ErrorBody {
  code: string;
  message: string;
  retryable: boolean;
  details: Record<string, unknown>;
}

export interface HealthData {
  status: string;
  environment: Environment;
  contract_version: string;
  write_mode: string;
  global_write_kill: boolean;
}

export interface ApiError {
  error: ErrorBody;
  request_id: string;
  trace_id: string;
}

export interface EvidenceReference {
  source_type: string;
  source_id: string;
  as_of: string;
}

export interface ProductSummary {
  id: string;
  name: string;
  brand_id: string;
  category: string;
}

export interface SkuSummary {
  id: string;
  product_id: string;
  option: string;
  barcode: string | null;
  status: string;
}

export interface InventorySnapshot {
  provider: Provider;
  sku_id: string;
  on_hand: number;
  reserved: number;
  as_of: string;
  freshness: Freshness;

  expected_inventory?: number | null;
  confirmed_incoming?: number | null;
  risk_level?: RiskLevel | null;
  calculation?: Record<string, number> | null;
  evidence?: EvidenceReference[];
  quality_status?: InventoryQualityStatus;
  ttl_seconds?: number;
  age_seconds?: number;
  freshness_reason?: string;
  confirmed_for_total?: boolean;
}

export interface OrderSummary {
  id: string;
  provider: Provider;
  external_id: string;
  type: "STANDARD" | "RESERVATION";
  status: string;
  ordered_at: string;
  customer_ref: string;
}

export interface InquirySummary {
  id: string;
  channel: string;
  sanitized_text: string;
  intent: string;
  entities: Record<string, string>;
  risk: RiskLevel;
}

export interface TaskSummary {
  id: string;
  type: string;
  title: string;
  deadline: string;
  priority: RiskLevel;
  status: TaskStatus;
  source_reason: string;
}

export interface InsightProposal {
  action: "CREATE_TASK";
  risk_level: RiskLevel;
  requires_approval: boolean;
}

export interface InsightSummary {
  insight_id: string;
  type: string;
  severity: RiskLevel;
  confidence: number;
  summary: string;
  calculation?: Record<string, number>;
  evidence: EvidenceReference[];
  proposal: InsightProposal;
  model_run_id: string | null;
  rule_version: string;
}

export interface LaunchEventSummary {
  id: string;
  product_id: string;
  launch_at: string;
  flow_template: string;
  status: string;
}

/** UI model that only groups entities defined by the v1 data specification. */
export interface DashboardData {
  orders: OrderSummary[];
  inventory: InventorySnapshot[];
  inquiries: InquirySummary[];
  tasks: TaskSummary[];
  insights: InsightSummary[];
}

export type ReservationSourceClassification =
  | "SANITIZED_REAL"
  | "FIXTURE"
  | "CONTRACT_ONLY"
  | "BLOCKED";

export type ReservationValueState =
  | "KNOWN"
  | "UNKNOWN"
  | "BLOCKED";

export interface ReservationRiskItem {
  reservation_id: string;
  product_name: string;
  sku_id?: string | null;

  required_qty: number | null;
  secured_qty: number | null;
  confirmed_incoming: number | null;
  tentative_incoming: number | null;
  shortage: number | null;

  aging?: number | null;
  priority?: RiskLevel | number | null;

  as_of: string;

  source_classification:
    ReservationSourceClassification;

  required_state?: ReservationValueState;
  secured_state?: ReservationValueState;
  confirmed_incoming_state?: ReservationValueState;
  tentative_incoming_state?: ReservationValueState;
  shortage_state?: ReservationValueState;

  evidence_ids?: string[];
  quality_status?: InventoryQualityStatus;
  confirmed_incoming_qty?: number | null;
  tentative_incoming_qty?: number | null;
  calculation_status?: string;
}

export type ReservationTimelineStage =
  | "RESERVATION"
  | "PURCHASE_ORDER"
  | "INCOMING"
  | "FULFILLMENT";

export type ReservationTimelineStatus =
  | "CONFIRMED"
  | "PENDING"
  | "UNKNOWN"
  | "BLOCKED"
  | "CONTRACT_ONLY";

export interface ReservationTimelineStep {
  id: string;

  stage: ReservationTimelineStage;
  status: ReservationTimelineStatus;

  title: string;

  as_of: string | null;

  source_classification:
    ReservationSourceClassification;

  source_event_id?: string | null;

  evidence?: EvidenceReference[];

  note?: string | null;
}

export interface ReservationTimeline {
  reservation_id: string;

  product_name: string;

  steps: ReservationTimelineStep[];

  as_of: string;

  evidence_ids?: string[];
}

export type TaskProposalStatus =
  | "PROPOSED"
  | "UNDER_REVIEW"
  | "EDITED"
  | "DISMISSED";

export interface TaskProposal {
  proposal_id: string;
  task_type: string;
  title: string;

  status: TaskProposalStatus;

  source_reason: string;

  priority?: RiskLevel | null;

  as_of: string;

  evidence_ids?: string[];

  external_execution_allowed: false;
}

// Day 10 — 운영 일정 화면용 Source 검증 수준
export type ScheduleSourceClassification =
  | "SANITIZED_REAL"
  | "FIXTURE"
  | "CONTRACT_ONLY"
  | "BLOCKED"
  | "SOURCE_QUALITY_BLOCKED";

// Day 10 — Flow A / Flow B
export type ScheduleFlow = "FLOW_A" | "FLOW_B";

// Day 10 — 일정 보드에서 사용하는 Launch Event Projection
export interface ScheduleLaunchEvent
  extends LaunchEventSummary {
  flow: ScheduleFlow;
  template_id: string;
  version: string;
  timezone: string;

  as_of: string | null;
  freshness: Freshness;
  source_classification: ScheduleSourceClassification;

  evidence_ids?: string[];
}

// Day 10 — 일정 보드에서 사용하는 Task Projection
//
// 기존 TaskSummary의 deadline은 과거 화면 계약상 string이므로
// Day 10 nullable 계약을 별도 Projection으로 유지한다.
export interface ScheduleTask
  extends Omit<TaskSummary, "deadline"> {
  deadline: string | null;

  owner: string | null;
  duration_hours: number | null;

  flow: ScheduleFlow;

  as_of: string | null;
  freshness: Freshness;
  source_classification: ScheduleSourceClassification;

  evidence_ids?: string[];
}

export interface ReservationShortageTask {
  id: string;
  owner?: null;
  duration_hours?: null;
  task_id?: string;
  tenant_id: string;
  reservation_id: string;
  sku_id: string;
  task_type: "RESERVATION_SHORTAGE";
  title: string;
  deadline: string | null;
  risk_level: string | null;
  affected_count: number | null;
  aging_hours: number | null;
  priority: number;
  priority_reason: string | null;
  status: TaskStatus;
  source_reason: string;
  source_classification: string;
  evidence_ids: string[];
  as_of: string | null;
  replay_count: number;
  priority_rule_score: number;
  priority_breakdown: Record<"deadline" | "risk" | "business_impact" | "aging", {
    raw: string | number | null;
    normalized: number | null;
    weight: number;
    contribution: number | null;
    reason: string | null;
  }>;
  priority_rule_version: string;
  priority_provenance: string;
  priority_calibration_status: string;
  priority_missing_features: string[];
  priority_coverage_weight: number;
  priority_as_of: string | null;
}

export interface C03Reservation {
  reservation_id: string;
  sku_id: string;
  required_qty: number | null;
  secured_qty: number | null;
  confirmed_incoming_qty: number | null;
  tentative_incoming_qty: number | null;
  shortage: number | null;
  calculation_status: string;
}

export interface TaskFeedback {
  id: string;
  tenant_id: string;
  task_id: string;
  decision: "EDIT" | "REJECT";
  target_field: "title" | "deadline" | null;
  before_value: unknown;
  after_value: unknown;
  reason: string;
  actor: string;
  idempotency_key: string;
  feedback_version: number;
  schema_version: string;
  created_at: string;
}

// Day 10 — Task 선후행 관계
export interface ScheduleDependency {
  predecessor_id: string;
  successor_id: string;

  lag_hours: number | null;

  as_of: string | null;
  source_classification: ScheduleSourceClassification;

  evidence_ids?: string[];
}

// Day 10 — 일정 지연 영향 상태
export type ScheduleImpactState =
  | "KNOWN"
  | "NONE"
  | "UNKNOWN"
  | "BLOCKED";

// Day 10 — 지연 영향 대상 종류
export type ScheduleImpactTargetType =
  | "TASK"
  | "RESERVATION_ORDER"
  | "LAUNCH_EVENT";

// Day 10 — 일정 지연 영향 상세
export interface ScheduleDelayImpactItem {
  target_type: ScheduleImpactTargetType;
  target_id: string;

  before: string | null;
  after: string | null;

  lag_hours: number | null;

  reason: string | null;

  evidence_ids?: string[];
}

// Day 10 — 입고 지연 영향 Projection
export interface ScheduleDelayImpact {
  incoming_id: string;

  expected_at_before: string | null;
  expected_at_after: string | null;

  impact_state: ScheduleImpactState;

  affected_tasks: ScheduleDelayImpactItem[];
  affected_reservations: ScheduleDelayImpactItem[];
  affected_launch_events: ScheduleDelayImpactItem[];

  critical_path_affected: boolean | null;

  as_of: string | null;
  freshness: Freshness;
  quality: string | null;

  source_classification:
    ScheduleSourceClassification;

  evidence_ids?: string[];

  request_id: string;
  trace_id: string;
}

// Day 10 — 재계획 검토 상태
export type ScheduleReplanStatus =
  | "PROPOSED"
  | "APPROVED"
  | "EDITED"
  | "REJECTED"
  | "EXPIRED";

// Day 10 — 기존 일정 / 제안 일정 값
export interface ScheduleReplanValue {
  target_type:
    | "TASK"
    | "RESERVATION_ORDER"
    | "LAUNCH_EVENT";

  target_id: string;

  scheduled_at: string | null;

  evidence_ids?: string[];
}

// Day 10 — 재계획 제안 Projection
export interface ScheduleReplanProposal {
  proposal_id: string;

  incoming_id: string | null;

  status: ScheduleReplanStatus;

  before: ScheduleReplanValue[];
  proposed_after: ScheduleReplanValue[];

  reason: string;

  confidence: number | null;

  downstream_impact: string | null;

  conflict: string | null;

  as_of: string | null;

  freshness: Freshness;

  source_classification:
    ScheduleSourceClassification;

  evidence_ids?: string[];

  request_id: string;
  trace_id: string;

  external_execution_allowed: false;
}
