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
