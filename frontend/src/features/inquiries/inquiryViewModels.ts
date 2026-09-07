import type {
  InquirySummary,
  RiskLevel,
} from "../../types/contracts";

import type {
  CitationItem,
} from "./CitationCard";

export type InquiryUiStatus =
  | "NEW"
  | "REVIEW"
  | "HOLD";

export type InquiryWorkbenchState = {
  confidence: number;
  warnings: string[];
  answerStatus: "DRAFT" | "HOLD";
};

export type InquiryRetrievalResult = {
  request_id: string;
  trace_id: string;
  query: string;
  method: string;
  confidence: number;
  index_version: string;
  citations: CitationItem[];
  warnings: string[];
  answer_status: "DRAFT" | "HOLD";
};

export type InquiryListItem = {
  inquiry: InquirySummary;

  // Day 7 Frontend Mock/View Model 전용 상태.
  // shared InquirySummary 계약 필드가 아니다.
  status: InquiryUiStatus;
  ageLabel: string;

  relatedProductRef?: string;
  relatedOrderRef?: string;

  workbench: InquiryWorkbenchState;
  retrieval: InquiryRetrievalResult;

  draft: InquiryDraftState;
};

export const inquiryStatusLabels: Record<
  InquiryUiStatus,
  string
> = {
  NEW: "새 문의",
  REVIEW: "검토 필요",
  HOLD: "보류",
};

export function requiresManualReview(
  risk: RiskLevel,
  confidence: number,
) {
  return (
    risk === "HIGH" ||
    risk === "PROHIBITED" ||
    confidence < 0.7
  );
}

export type DraftStatus =
  | "DRAFT"
  | "REVIEW_PENDING"
  | "HOLD"
  | "INSUFFICIENT_EVIDENCE"
  | "REJECTED";

export type InquiryDraftState = {
  text: string;
  status: DraftStatus;
  provenance?: "AI" | "RULE" | "HUMAN";
};

export const draftStatusLabels: Record<
  DraftStatus,
  string
> = {
  DRAFT: "초안",
  REVIEW_PENDING: "승인 대기",
  HOLD: "보류",
  INSUFFICIENT_EVIDENCE: "근거 부족",
  REJECTED: "거절",
};