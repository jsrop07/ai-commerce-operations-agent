import type {
  ApiEnvelope,
  InsightSummary,
} from "../../types/contracts";

function urgentEnvelope(
  insight: InsightSummary,
  requestId: string,
  traceId: string,
  evidenceIds: string[],
  asOf: string,
): ApiEnvelope<InsightSummary> {
  return {
    schema_version: "1.0",
    tenant_id: "demo_store",
    request_id: requestId,
    trace_id: traceId,
    data: insight,
    evidence_ids: evidenceIds,
    warnings: [],
    as_of: asOf,
  };
}

export const urgentQueueFixtures: ApiEnvelope<InsightSummary>[] = [
  urgentEnvelope(
    {
      insight_id: "ins_demo_urgent_001",
      type: "RESERVATION_SHORTAGE",
      severity: "HIGH",
      confidence: 0.97,
      summary:
        "예약 수량 대비 확정 재고가 부족하여 출고 전 확인이 필요합니다.",
      calculation: {
        reserved: 5,
        available: 1,
        confirmed_incoming: 2,
        shortage: 2,
      },
      evidence: [
        {
          source_type: "order",
          source_id: "ord_demo_reservation_001",
          as_of: "2026-09-03T04:40:00Z",
        },
        {
          source_type: "inventory_snapshot",
          source_id: "sku_demo_urgent_001",
          as_of: "2026-09-03T04:40:00Z",
        },
      ],
      proposal: {
        action: "CREATE_TASK",
        risk_level: "LOW",
        requires_approval: false,
      },
      model_run_id: null,
      rule_version: "reservation-risk-v1",
    },
    "req_demo_urgent_001",
    "tr_demo_urgent_001",
    ["ord_demo_reservation_001", "sku_demo_urgent_001"],
    "2026-09-03T04:40:00Z",
  ),

  urgentEnvelope(
    {
      insight_id: "ins_demo_urgent_002",
      type: "SCHEDULE_CONFLICT",
      severity: "HIGH",
      confidence: 0.91,
      summary:
        "같은 시간대에 처리해야 할 운영 일정이 겹쳐 담당자 확인이 필요합니다.",
      evidence: [
        {
          source_type: "launch_event",
          source_id: "launch_demo_conflict_001",
          as_of: "2026-09-03T04:35:00Z",
        },
      ],
      proposal: {
        action: "CREATE_TASK",
        risk_level: "LOW",
        requires_approval: true,
      },
      model_run_id: null,
      rule_version: "schedule-conflict-v1",
    },
    "req_demo_urgent_002",
    "tr_demo_urgent_002",
    ["launch_demo_conflict_001"],
    "2026-09-03T04:35:00Z",
  ),

  urgentEnvelope(
    {
      insight_id: "ins_demo_urgent_003",
      type: "INVENTORY_DISCREPANCY",
      severity: "MEDIUM",
      confidence: 0.88,
      summary:
        "온라인·오프라인 재고 수량에 차이가 있어 실제 수량 확인이 필요합니다.",
      evidence: [
        {
          source_type: "inventory_snapshot",
          source_id: "sku_demo_urgent_002",
          as_of: "2026-09-03T04:30:00Z",
        },
      ],
      proposal: {
        action: "CREATE_TASK",
        risk_level: "LOW",
        requires_approval: false,
      },
      model_run_id: null,
      rule_version: "inventory-discrepancy-v1",
    },
    "req_demo_urgent_003",
    "tr_demo_urgent_003",
    ["sku_demo_urgent_002"],
    "2026-09-03T04:30:00Z",
  ),
];

export const emptyUrgentQueueFixture: ApiEnvelope<InsightSummary>[] = [];