import type {
  ApiEnvelope, ApiError, DashboardData, Freshness, HealthData, InquirySummary, InsightSummary,
  InventorySnapshot, LaunchEventSummary, OrderSummary, ProductSummary, SkuSummary, TaskSummary,ReservationRiskItem,
  ReservationTimeline,ReservationTimelineStep,ScheduleDelayImpact,ScheduleReplanProposal,ScheduleDependency,
  ScheduleLaunchEvent,ScheduleTask,
} from "../../types/contracts";
import type { InquiryListItem } from "../../features/inquiries/inquiryViewModels";

const asOf = "2026-09-02T06:30:00Z";

export const reservationRiskSanitizedRealFixture: ApiEnvelope<
  ReservationRiskItem[]
> = envelope(
  [
    {
      reservation_id: "reservation_actual_001",
      product_name: "Warhammer Pre-Order Product",
      sku_id: "sku_reservation_actual_001",

      required_qty: 8,
      secured_qty: null,
      confirmed_incoming: null,
      tentative_incoming: null,
      shortage: null,

      aging: null,
      priority: null,

      as_of: asOf,

      source_classification: "SANITIZED_REAL",

      required_state: "KNOWN",
      secured_state: "BLOCKED",
      confirmed_incoming_state: "BLOCKED",
      tentative_incoming_state: "UNKNOWN",
      shortage_state: "BLOCKED",

      evidence_ids: [
        "evidence_reservation_actual_001",
      ],
    },
  ],
  "reservation_risk_actual_001",
  ["evidence_reservation_actual_001"],
  [
    "secured_qty, confirmed_incoming, shortage는 authoritative source 미확보로 확정할 수 없습니다.",
  ],
);

export const reservationRiskUiFixture: ApiEnvelope<
  ReservationRiskItem[]
> = envelope(
  [
    {
      reservation_id: "reservation_fixture_shortage",
      product_name:
        "매우 긴 합성 예약 상품명 - UI 줄바꿈 및 좁은 화면 검증용 상품",
      sku_id: "sku_fixture_shortage",

      required_qty: 10,
      secured_qty: 4,
      confirmed_incoming: 2,
      tentative_incoming: 1,
      shortage: 4,

      aging: 6,
      priority: "HIGH",

      as_of: asOf,

      source_classification: "FIXTURE",

      required_state: "KNOWN",
      secured_state: "KNOWN",
      confirmed_incoming_state: "KNOWN",
      tentative_incoming_state: "KNOWN",
      shortage_state: "KNOWN",

      evidence_ids: [
        "fixture_evidence_reservation_shortage",
      ],
    },

    {
      reservation_id: "reservation_fixture_sufficient",
      product_name: "합성 예약 상품 - 충분",
      sku_id: "sku_fixture_sufficient",

      required_qty: 5,
      secured_qty: 5,
      confirmed_incoming: 2,
      tentative_incoming: null,
      shortage: 0,

      aging: 2,
      priority: "LOW",

      as_of: asOf,

      source_classification: "FIXTURE",

      required_state: "KNOWN",
      secured_state: "KNOWN",
      confirmed_incoming_state: "KNOWN",
      tentative_incoming_state: "UNKNOWN",
      shortage_state: "KNOWN",

      evidence_ids: [
        "fixture_evidence_reservation_sufficient",
      ],
    },

    {
      reservation_id: "reservation_fixture_unknown",
      product_name: "합성 예약 상품 - 입고 확인 필요",
      sku_id: "sku_fixture_unknown",

      required_qty: 7,
      secured_qty: null,
      confirmed_incoming: null,
      tentative_incoming: null,
      shortage: null,

      aging: 9,
      priority: null,

      as_of: asOf,

      source_classification: "FIXTURE",

      required_state: "KNOWN",
      secured_state: "UNKNOWN",
      confirmed_incoming_state: "BLOCKED",
      tentative_incoming_state: "UNKNOWN",
      shortage_state: "BLOCKED",

      evidence_ids: [
        "fixture_evidence_reservation_unknown",
      ],
    },
  ],
  "reservation_risk_ui_001",
  [
    "fixture_evidence_reservation_shortage",
    "fixture_evidence_reservation_sufficient",
    "fixture_evidence_reservation_unknown",
  ],
  [
    "FIXTURE_ONLY: 실제 Backend 통합 증거로 사용하지 않습니다.",
  ],
);

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
  {
    provider: "ECOUNT",
    sku_id: "sku_demo_001",
    on_hand: 3,
    reserved: 4,
    as_of: "2026-09-02T05:43:00Z",
    freshness: "STALE",
    quality_status: "STALE",
    confirmed_for_total: false,
  },
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

export const mappingReviewItems = [
  {
    id: "mapping_review_demo_001",
    source: "TOSS_POS",
    originalName: "Synthetic Game Korean Edition",
    candidates: [
      {
        sku_id: "sku_demo_001",
        label: "sku_demo_001 / KOREAN",
        confidence: 0.91,
        rule: "normalized-name + option",
      },
      {
        sku_id: "sku_demo_002",
        label: "sku_demo_002 / STANDARD",
        confidence: 0.63,
        rule: "normalized-name",
      },
    ],
  },
  {
    id: "mapping_review_demo_002",
    source: "CAFE24",
    originalName: "Synthetic Card Game Standard",
    candidates: [
      {
        sku_id: "sku_demo_002",
        label: "sku_demo_002 / STANDARD",
        confidence: 0.98,
        rule: "external-code + option",
      },
    ],
  },
  {
    id: "mapping_review_demo_003",
    source: "TOSS_POS",
    originalName: "Unknown Synthetic Product",
    candidates: [],
  },
] as const;

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

export const inventoryQualityItems = [
  {
    id: "quality_demo_001",
    provider: "CAFE24",
    sku_id: "sku_demo_001",
    quality_status: "USABLE",
    on_hand: 12,
  },
  {
    id: "quality_demo_002",
    provider: "TOSS_POS",
    sku_id: "sku_demo_002",
    quality_status: "UNMAPPED",
    on_hand: 18,
  },
  {
    id: "quality_demo_003",
    provider: "DEMO",
    sku_id: "sku_demo_quarantined",
    quality_status: "QUARANTINED",
    on_hand: 7,
  },
  {
    id: "quality_demo_004",
    provider: "ECOUNT",
    sku_id: "sku_demo_001",
    quality_status: "SOURCE_QUALITY_BLOCKED",
    on_hand: null,
  },
] as const;

export const inquiryWorkbenchItems: InquiryListItem[] = [
  {
    inquiry: {
      id: "inq_day07_low",
      channel: "DEMO",
      sanitized_text:
        "이 확장팩을 본판 없이 사용할 수 있는지 궁금합니다.",
      intent: "PRODUCT_INFO",
      entities: {
        product_id: "prd_demo_001",
      },
      risk: "LOW",
    },

    status: "NEW",
    ageLabel: "10분 전",
    relatedProductRef: "prd_demo_001",

    workbench: {
      confidence: 0.94,
      warnings: [],
      answerStatus: "DRAFT",
    },

    retrieval: {
      request_id: "req_day07_low",
      trace_id: "tr_day07_low",
      query:
        "이 확장팩은 본판 없이 사용할 수 있는가?",
      method: "BM25",
      confidence: 0.94,
      index_version: "demo-index-v1",

      citations: [
        {
          source_type: "product",
          source_id: "prd_demo_001",
          title: "합성 확장팩 상품 정보",
          record_or_field: "compatibility",
          as_of: "2026-09-07T06:00:00Z",
          score: 0.92,
        },
      ],

      warnings: [],
      answer_status: "DRAFT",
    },

    draft: {
      text:
        "확인된 상품 정보에 따르면 해당 확장팩의 사용 조건을 별도로 확인해야 합니다. 아래 근거를 검토한 뒤 답변해 주세요.",
      status: "DRAFT",
      provenance: "AI",
    },
  },

  {
    inquiry: {
      id: "inq_day07_high",
      channel: "DEMO",
      sanitized_text:
        "주문 취소와 환불 처리를 요청합니다.",
      intent: "REFUND_REQUEST",
      entities: {
        order_id: "ord_demo_002",
      },
      risk: "HIGH",
    },

    status: "REVIEW",
    ageLabel: "25분 전",
    relatedOrderRef: "ord_demo_002",

    workbench: {
      confidence: 0.91,
      warnings: [
        "고위험 문의입니다. 운영 시스템에서 사람이 직접 확인해야 합니다.",
      ],
      answerStatus: "HOLD",
    },

    retrieval: {
      request_id: "req_day07_high",
      trace_id: "tr_day07_high",
      query:
        "주문 취소와 환불 처리 기준을 확인한다.",
      method: "BM25",
      confidence: 0.91,
      index_version: "demo-index-v1",

      citations: [
        {
          source_type: "policy",
          source_id: "policy_demo_refund_001",
          title: "합성 취소·환불 정책",
          record_or_field: "refund_review_policy",
          as_of: "2026-09-07T06:00:00Z",
          score: 0.89,
        },
      ],

      warnings: [
        "고위험 문의이므로 검색 근거가 있어도 자동 답변 확정이 허용되지 않습니다.",
      ],

      answer_status: "HOLD",
    },
    draft: {
      text:
        "취소 및 환불 요청은 운영 시스템에서 담당자가 주문 상태와 정책을 직접 확인해야 합니다.",
      status: "HOLD",
      provenance: "AI",
    },

  },

  {
    inquiry: {
      id: "inq_day07_low_confidence",
      channel: "DEMO",
      sanitized_text:
        "이 상품이 제가 가진 제품과 호환되는지 잘 모르겠습니다.",
      intent: "PRODUCT_INFO",
      entities: {},
      risk: "LOW",
    },

    status: "HOLD",
    ageLabel: "1시간 전",

    workbench: {
      confidence: 0.54,
      warnings: [
        "신뢰도가 낮아 추가 근거 확인이 필요합니다.",
      ],
      answerStatus: "HOLD",
    },

    retrieval: {
      request_id: "req_day07_low_confidence",
      trace_id: "tr_day07_low_confidence",
      query:
        "이 상품이 보유 제품과 호환되는가?",
      method: "BM25",
      confidence: 0.54,
      index_version: "demo-index-v1",

      citations: [],

      warnings: [
        "검색 근거가 부족합니다.",
      ],

      answer_status: "HOLD",
    },
    draft: {
      text: "",
      status: "INSUFFICIENT_EVIDENCE",
    },
  },
];

export const reservationTimelineFixture: ReservationTimeline = {
  reservation_id: "reservation_fixture_timeline_001",

  product_name:
    "합성 예약 상품 - Timeline 상태 검증용",

  as_of: "2026-09-10T10:00:00Z",

  evidence_ids: [
    "evidence_reservation_created",
  ],

  steps: [
    {
      id: "timeline_step_reservation",

      stage: "RESERVATION",

      status: "CONFIRMED",

      title: "예약 접수",

      as_of: "2026-09-08T09:00:00Z",

      source_classification:
        "SANITIZED_REAL",

      source_event_id:
        "evt_reservation_created_001",

      evidence: [
        {
          source_type: "order",
          source_id:
            "reservation_fixture_timeline_001",
          as_of:
            "2026-09-08T09:00:00Z",
        },
      ],

      note:
        "Cafe24 예약주문에서 확인된 예약 접수 단계입니다.",
    },

    {
      id: "timeline_step_purchase_order",

      stage: "PURCHASE_ORDER",

      status: "CONTRACT_ONLY",

      title: "발주",

      as_of: null,

      source_classification:
        "CONTRACT_ONLY",

      source_event_id: null,

      evidence: [],

      note:
        "발주 단계 계약은 존재하지만 실제 발주 여부를 확인할 authoritative source가 없습니다.",
    },

    {
      id: "timeline_step_incoming",

      stage: "INCOMING",

      status: "BLOCKED",

      title: "입고",

      as_of: null,

      source_classification:
        "BLOCKED",

      source_event_id: null,

      evidence: [],

      note:
        "eCount/Gmail 입고 확정 source가 확보되지 않아 실제 입고 여부를 확인할 수 없습니다.",
    },

    {
      id: "timeline_step_fulfillment",

      stage: "FULFILLMENT",

      status: "UNKNOWN",

      title: "출고",

      as_of: null,

      source_classification:
        "SANITIZED_REAL",

      source_event_id: null,

      evidence: [],

      note:
        "현재 확인 가능한 근거만으로 출고 여부를 확정할 수 없습니다.",
    },
  ],
};

export const day10DelayImpacts: ScheduleDelayImpact[] = [
  {
    incoming_id: "incoming_day10_001",

    expected_at_before:
      "2026-09-20T01:00:00Z",
    expected_at_after:
      "2026-09-22T01:00:00Z",

    impact_state: "KNOWN",

    affected_tasks: [
      {
        target_type: "TASK",
        target_id: "task_day10_002",

        before:
          "2026-09-18T09:00:00Z",
        after:
          "2026-09-20T09:00:00Z",

        lag_hours: 48,

        reason:
          "입고 일정 지연에 따른 Task 검토 필요",

        evidence_ids: [
          "ev_impact_task_001",
        ],
      },
    ],

    affected_reservations: [
      {
        target_type:
          "RESERVATION_ORDER",
        target_id:
          "reservation_demo_001",

        before: null,
        after: null,

        lag_hours: null,

        reason:
          "예약주문 실제 일정 Source 미연결",

        evidence_ids: [],
      },
    ],

    affected_launch_events: [
      {
        target_type:
          "LAUNCH_EVENT",
        target_id:
          "launch_day10_001",

        before:
          "2026-09-20T01:00:00Z",
        after:
          "2026-09-22T01:00:00Z",

        lag_hours: 48,

        reason:
          "입고 지연에 따른 출시 일정 영향",

        evidence_ids: [
          "ev_impact_launch_001",
        ],
      },
    ],

    critical_path_affected: true,

    as_of:
      "2026-09-11T06:00:00Z",

    freshness: "FRESH",

    quality:
      "FIXTURE_VALIDATED",

    source_classification:
      "FIXTURE",

    evidence_ids: [
      "ev_impact_day10_001",
    ],

    request_id:
      "req_impact_day10_001",

    trace_id:
      "trace_impact_day10_001",
  },
];

export const day10DelayImpactsFixture =
  envelope(
    day10DelayImpacts,
    "day10_delay_impacts",
    ["ev_impact_day10_001"],
  );

  export const day10ReplanProposals:
  ScheduleReplanProposal[] = [
  {
    proposal_id:
      "replan_day10_001",

    incoming_id:
      "incoming_day10_001",

    status: "PROPOSED",

    before: [
      {
        target_type:
          "LAUNCH_EVENT",

        target_id:
          "launch_day10_001",

        scheduled_at:
          "2026-09-20T01:00:00Z",

        evidence_ids: [
          "ev_replan_before_001",
        ],
      },
    ],

    proposed_after: [
      {
        target_type:
          "LAUNCH_EVENT",

        target_id:
          "launch_day10_001",

        scheduled_at:
          "2026-09-22T01:00:00Z",

        evidence_ids: [
          "ev_replan_after_001",
        ],
      },
    ],

    reason:
      "입고 지연 Fixture 기반 재계획 검토",

    confidence: 0.82,

    downstream_impact:
      "출시 준비 Task 및 예약주문 검토 필요",

    conflict: null,

    as_of:
      "2026-09-11T06:00:00Z",

    freshness: "FRESH",

    source_classification:
      "FIXTURE",

    evidence_ids: [
      "ev_replan_day10_001",
    ],

    request_id:
      "req_replan_day10_001",

    trace_id:
      "trace_replan_day10_001",

    external_execution_allowed:
      false,
  },
];

export const day10ReplanProposalsFixture =
  envelope(
    day10ReplanProposals,
    "day10_replans",
    ["ev_replan_day10_001"],
  );

export const day10Dependencies: ScheduleDependency[] = [
  {
    predecessor_id: "task_day10_001",
    successor_id: "task_day10_002",

    lag_hours: null,

    as_of: null,

    source_classification:
      "CONTRACT_ONLY",

    evidence_ids: [],
  },
];

export const day10DependenciesFixture =
  envelope(
    day10Dependencies,
    "day10_dependencies",
    [],
  );

// Day 10 — 출시 일정 Fixture
export const day10LaunchEvents: ScheduleLaunchEvent[] = [
  {
    id: "launch_day10_001",
    product_id: "prd_demo_002",
    launch_at: "2026-09-20T01:00:00Z",
    flow_template: "STANDARD_LAUNCH",
    status: "PLANNED",

    flow: "FLOW_A",
    template_id: "launch-flow-a",
    version: "1.0",
    timezone: "Asia/Seoul",

    as_of: "2026-09-11T06:00:00Z",
    freshness: "FRESH",
    source_classification: "FIXTURE",

    evidence_ids: [
      "ev_launch_day10_001",
    ],
  },
];
export const day10Tasks: ScheduleTask[] = [
  {
    /*
     * 기존 InventoryPage가 사용하던 Task를 유지한다.
     * Day 10 일정 Projection 필드만 추가한다.
     */
    id: "task_demo_001",
    type: "INVENTORY_REVIEW",
    title: "합성 SKU 재고 차이 확인",

    deadline: "2026-09-02T09:00:00Z",
    priority: "HIGH",
    status: "PROPOSED",

    source_reason:
      "inventory discrepancy",

    owner: null,
    duration_hours: null,

    flow: "FLOW_A",

    as_of:
      "2026-09-11T06:00:00Z",

    freshness: "FRESH",

    source_classification:
      "FIXTURE",

    evidence_ids: [
      "task_demo_001",
    ],
  },

  {
    /*
     * 기존 Inquiry 관련 Task도 유지한다.
     */
    id: "task_demo_002",
    type: "INQUIRY_REVIEW",
    title: "합성 문의 초안 검토",

    deadline: "2026-09-02T10:00:00Z",
    priority: "MEDIUM",
    status: "IN_PROGRESS",

    source_reason:
      "draft ready",

    owner: null,
    duration_hours: null,

    flow: "FLOW_B",

    as_of:
      "2026-09-11T06:00:00Z",

    freshness: "FRESH",

    source_classification:
      "FIXTURE",

    evidence_ids: [
      "task_demo_002",
    ],
  },

  {
    /*
     * Day 10 일정 화면 검증용 Task.
     */
    id: "task_day10_001",
    type: "LAUNCH_PREPARATION",
    title: "출시 준비 상태 검토",

    deadline: null,
    priority: "MEDIUM",
    status: "PROPOSED",

    source_reason:
      "Day 10 Fixture 일정 검토",

    owner: null,
    duration_hours: null,

    flow: "FLOW_A",

    as_of: null,
    freshness: "UNKNOWN",

    source_classification:
      "FIXTURE",

    evidence_ids: [],
  },
];

export const day10TasksFixture =
  envelope(
    day10Tasks,
    "day10_tasks",
    [
      "task_demo_001",
      "task_demo_002",
    ],
  );

export const day10LaunchEventsFixture =
  envelope(
    day10LaunchEvents,
    "day10_launch_events",
    ["ev_launch_day10_001"],
  );
