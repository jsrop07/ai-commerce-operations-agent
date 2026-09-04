import type {
  Freshness,
  RiskLevel,
  TaskStatus,
} from "../types/contracts";

export const taskStatusLabel: Record<TaskStatus, string> = {
  PROPOSED: "제안됨",
  APPROVED: "승인됨",
  IN_PROGRESS: "진행 중",
  DONE: "완료",
  BLOCKED: "차단됨",
  DISMISSED: "종료됨",
};

export const freshnessLabel: Record<Freshness, string> = {
  FRESH: "최신",
  STALE: "오래됨",
  UNKNOWN: "확인 불가",
};

export const riskLabel: Record<RiskLevel, string> = {
  LOW: "낮음",
  MEDIUM: "보통",
  HIGH: "높음",
  PROHIBITED: "실행 금지",
};

const insightTypeLabels: Record<string, string> = {
  RESERVATION_SHORTAGE: "예약 재고 부족",
  INVENTORY_DISCREPANCY: "재고 불일치",
  SCHEDULE_CONFLICT: "일정 충돌",
};

export function getInsightTypeLabel(type: string): string {
  return insightTypeLabels[type] ?? "알 수 없는 분석 유형";
}
const providerLabels: Record<string, string> = {
  CAFE24: "CAFE24",
  TOSS_POS: "TOSS_POS",
  ECOUNT: "ECOUNT",
  DEMO: "DEMO",
};

const providerFailureReasonLabels: Record<string, string> = {
  TIMEOUT: "응답 시간 초과",
};

export function getProviderLabel(provider: string): string {
  return providerLabels[provider] ?? "알 수 없는 연동사";
}

export function getProviderFailureReasonLabel(reason: string): string {
  return providerFailureReasonLabels[reason] ?? "확인되지 않은 연동 오류";
}