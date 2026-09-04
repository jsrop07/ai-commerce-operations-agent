import type {
  ApiEnvelope, ApiError, DashboardData, Freshness, HealthData, InquirySummary, InsightSummary,
  InventorySnapshot, LaunchEventSummary, OrderSummary, ProductSummary, SkuSummary, TaskSummary,
} from "../../types/contracts";

const asOf = "2026-09-02T06:30:00Z";

function envelope<T>(data: T, suffix: string, evidenceIds: string[] = [], warnings: string[] = []): ApiEnvelope<T> {
  return {
    schema_version: "1.0",
    tenant_id: "demo_store",
    request_id: `req_demo_${suffix}`,
    trace_id: `tr_demo_${suffix}`,
    data,
    evidence_ids: evidenceIds,
    warnings,
    as_of: asOf,
  };
}

export const products: ProductSummary[] = [
  { id: "prd_demo_001", name: "합성 레드 보드게임", brand_id: "brand_demo_001", category: "STRATEGY" },
  { id: "prd_demo_002", name: "합성 그린 카드게임", brand_id: "brand_demo_001", category: "CARD_GAME" },
];

export const skus: SkuSummary[] = [
  { id: "sku_demo_001", product_id: "prd_demo_001", option: "KOREAN", barcode: null, status: "ACTIVE" },
  { id: "sku_demo_002", product_id: "prd_demo_002", option: "STANDARD", barcode: null, status: "ACTIVE" },
];

export const inventory: InventorySnapshot[] = [
  { provider: "CAFE24", sku_id: "sku_demo_001", on_hand: 12, reserved: 4, as_of: asOf, freshness: "FRESH" },
  { provider: "ECOUNT", sku_id: "sku_demo_001", on_hand: 3, reserved: 4, as_of: "2026-09-02T05:43:00Z", freshness: "STALE" },
  { provider: "TOSS_POS", sku_id: "sku_demo_002", on_hand: 18, reserved: 2, as_of: asOf, freshness: "FRESH" },
];

export const orders: OrderSummary[] = [
  { id: "ord_demo_001", provider: "CAFE24", external_id: "ext_demo_order_001", type: "STANDARD", status: "PREPARING", ordered_at: asOf, customer_ref: "customer_ref_demo_001" },
  { id: "ord_demo_002", provider: "CAFE24", external_id: "ext_demo_order_002", type: "RESERVATION", status: "CONFIRMED", ordered_at: asOf, customer_ref: "customer_ref_demo_002" },
  { id: "ord_demo_003", provider: "TOSS_POS", external_id: "ext_demo_sale_001", type: "STANDARD", status: "DONE", ordered_at: asOf, customer_ref: "customer_ref_demo_walkin" },
];

export const inquiries: InquirySummary[] = [
  { id: "inq_demo_001", channel: "CAFE24", sanitized_text: "합성 주문의 배송 일정을 확인하고 싶습니다.", intent: "DELIVERY_STATUS", entities: { order_id: "ord_demo_001" }, risk: "MEDIUM" },
  { id: "inq_demo_002", channel: "DEMO", sanitized_text: "합성 상품의 구성 정보를 알려주세요.", intent: "PRODUCT_INFO", entities: { product_id: "prd_demo_002" }, risk: "LOW" },
];

export const tasks: TaskSummary[] = [
  { id: "task_demo_001", type: "INVENTORY_REVIEW", title: "합성 SKU 재고 차이 확인", deadline: "2026-09-02T09:00:00Z", priority: "HIGH", status: "PROPOSED", source_reason: "inventory discrepancy" },
  { id: "task_demo_002", type: "INQUIRY_REVIEW", title: "합성 문의 초안 검토", deadline: "2026-09-02T10:00:00Z", priority: "MEDIUM", status: "IN_PROGRESS", source_reason: "draft ready" },
];

export const insights: InsightSummary[] = [
  {
    insight_id: "ins_demo_001",
    type: "RESERVATION_SHORTAGE",
    severity: "HIGH",
    confidence: 0.97,
    summary: "예약 수량 대비 확정 재고가 2개 부족합니다.",
    calculation: { reserved: 5, available: 1, confirmed_incoming: 2, shortage: 2 },
    evidence: [
      { source_type: "order", source_id: "ord_demo_002", as_of: asOf },
      { source_type: "inventory_snapshot", source_id: "sku_demo_001", as_of: asOf },
    ],
    proposal: { action: "CREATE_TASK", risk_level: "LOW", requires_approval: false },
    model_run_id: null,
    rule_version: "reservation-risk-v1",
  },
  {
    insight_id: "ins_demo_002",
    type: "INVENTORY_DISCREPANCY",
    severity: "MEDIUM",
    confidence: 0.88,
    summary: "두 provider의 합성 SKU 재고 수량에 차이가 있습니다.",
    evidence: [{ source_type: "inventory_snapshot", source_id: "sku_demo_001", as_of: asOf }],
    proposal: { action: "CREATE_TASK", risk_level: "LOW", requires_approval: false },
    model_run_id: null,
    rule_version: "inventory-discrepancy-v1",
  },
];

export const launchEvents: LaunchEventSummary[] = [
  { id: "launch_demo_001", product_id: "prd_demo_002", launch_at: "2026-09-07T01:00:00Z", flow_template: "STANDARD_LAUNCH", status: "PLANNED" },
];

export const dashboardFixture = envelope<DashboardData>(
  { orders, inventory, inquiries, tasks, insights },
  "dashboard_001",
  ["ord_demo_002", "sku_demo_001"],
  ["ECOUNT inventory snapshot is stale"],
);
export const healthFixture: HealthData = {
  status: "ok",
  environment: "DEMO",
  contract_version: "1.0",
  write_mode: "disabled",
  global_write_kill: true,
};
export const productsFixture = envelope({ products, skus }, "products_001");
export const inventoryFixture = envelope(inventory, "inventory_001", ["sku_demo_001"]);
export const ordersFixture = envelope(orders, "orders_001", ["ord_demo_001", "ord_demo_002"]);
export const inquiriesFixture = envelope(inquiries, "inquiries_001", ["inq_demo_001"]);
export const launchEventsFixture = envelope(launchEvents, "launch_001", ["launch_demo_001"]);
export const tasksFixture = envelope(tasks, "tasks_001", ["task_demo_001"]);
export const insightsFixture = envelope(insights, "insights_001", insights.flatMap((item) => item.evidence.map((entry) => entry.source_id)));

export const freshnessFixtures: Record<Freshness, ApiEnvelope<InventorySnapshot[]>> = {
  FRESH: envelope([inventory[0]], "fresh_001", ["sku_demo_001"]),
  STALE: envelope([inventory[1]], "stale_001", ["sku_demo_001"], ["Inventory data is stale"]),
  UNKNOWN: envelope([], "unknown_001", [], ["Inventory freshness is unknown"]),
};

function errorFixture(code: string, message: string, retryable: boolean, details: Record<string, unknown>): ApiError {
  return {
    error: { code, message, retryable, details },
    request_id: `req_demo_error_${code.toLowerCase()}`,
    trace_id: `tr_demo_error_${code.toLowerCase()}`,
  };
}

export const partialProviderFailureFixture = errorFixture(
  "PARTIAL_PAGE", "One synthetic provider page could not be processed", true,
  { failed_providers: ["ECOUNT"], available_providers: ["CAFE24", "TOSS_POS"] },
);
export const ambiguousSkuMappingFixture = errorFixture(
  "AMBIGUOUS_SKU_MAPPING", "Human mapping required", false,
  { candidate_ids: ["sku_demo_001", "sku_demo_002"] },
);
export const policyDeniedFixture = errorFixture(
  "PROVIDER_WRITE_BLOCKED", "Provider write is blocked by policy", false,
  { environment: "PRODUCTION_READ" },
);
export const lowConfidenceFixture = envelope<InsightSummary[]>(
  [{ ...insights[1], insight_id: "ins_demo_low_confidence_001", confidence: 0.62 }],
  "low_confidence_001", ["sku_demo_001"], ["Low confidence requires human review"],
);
export const agentWaitingApprovalFixture = envelope<TaskSummary[]>(
  [{ ...tasks[0], id: "task_demo_waiting_001", status: "PROPOSED", source_reason: "human approval required" }],
  "agent_waiting_001", ["task_demo_waiting_001"], ["Agent is waiting for approval"],
);
