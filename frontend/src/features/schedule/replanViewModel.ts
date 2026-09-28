import type {
  ScheduleReplanProposal,
  ScheduleReplanValue,
} from "../../types/contracts";

export interface ReplanValueViewModel {
  targetType:
    ScheduleReplanValue["target_type"];

  targetLabel: string;

  targetId: string;

  scheduledAt:
    string | null;

  scheduledAtLabel:
    string;

  evidenceIds:
    string[];
}

export interface ReplanReviewViewModel {
  proposalId: string;

  status:
    ScheduleReplanProposal["status"];

  statusLabel: string;

  before:
    ReplanValueViewModel[];

  proposedAfter:
    ReplanValueViewModel[];

  reason: string;

  confidence:
    number | null;

  confidenceLabel:
    string;

  downstreamImpact:
    string | null;

  downstreamImpactLabel:
    string;

  conflict:
    string | null;

  conflictLabel:
    string;

  asOf:
    string | null;

  asOfLabel:
    string;

  sourceLabel:
    string;

  evidenceIds:
    string[];

  requestId:
    string;

  traceId:
    string;

  externalExecutionAllowed:
    false;
}

function statusLabel(
  status:
    ScheduleReplanProposal["status"],
): string {
  switch (status) {
    case "PROPOSED":
      return "검토 제안";

    case "APPROVED":
      return "내부 승인";

    case "EDITED":
      return "수정됨";

    case "REJECTED":
      return "거절됨";

    case "EXPIRED":
      return "만료됨";
  }
}

function sourceLabel(
  source:
    ScheduleReplanProposal["source_classification"],
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

function targetLabel(
  type:
    ScheduleReplanValue["target_type"],
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

function valueViewModel(
  value:
    ScheduleReplanValue,
): ReplanValueViewModel {
  return {
    targetType:
      value.target_type,

    targetLabel:
      targetLabel(
        value.target_type,
      ),

    targetId:
      value.target_id,

    scheduledAt:
      value.scheduled_at,

    scheduledAtLabel:
      value.scheduled_at ??
      "일정 미확정",

    evidenceIds:
      value.evidence_ids ?? [],
  };
}

export function buildReplanReviewViewModel(
  proposal:
    ScheduleReplanProposal,
): ReplanReviewViewModel {
  return {
    proposalId:
      proposal.proposal_id,

    status:
      proposal.status,

    statusLabel:
      statusLabel(
        proposal.status,
      ),

    before:
      proposal.before.map(
        valueViewModel,
      ),

    proposedAfter:
      proposal.proposed_after.map(
        valueViewModel,
      ),

    reason:
      proposal.reason,

    confidence:
      proposal.confidence,

    confidenceLabel:
      proposal.confidence === null
        ? "신뢰도 미확정"
        : `${Math.round(
            proposal.confidence *
              100,
          )}%`,

    downstreamImpact:
      proposal.downstream_impact,

    downstreamImpactLabel:
      proposal.downstream_impact ??
      "후속 영향 미확정",

    conflict:
      proposal.conflict,

    conflictLabel:
      proposal.conflict ??
      "확인된 충돌 없음",

    asOf:
      proposal.as_of,

    asOfLabel:
      proposal.as_of ??
      "기준 시각 미확정",

    sourceLabel:
      sourceLabel(
        proposal.source_classification,
      ),

    evidenceIds:
      proposal.evidence_ids ?? [],

    requestId:
      proposal.request_id,

    traceId:
      proposal.trace_id,

    externalExecutionAllowed:
      false,
  };
}