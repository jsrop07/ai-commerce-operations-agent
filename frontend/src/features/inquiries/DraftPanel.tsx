import {
  useEffect,
  useState,
} from "react";

import type {
  DraftStatus,
  InquiryDraftState,
} from "./inquiryViewModels";

import {
  draftStatusLabels,
} from "./inquiryViewModels";

type DraftPanelProps = {
  draft: InquiryDraftState;
  holdRequired: boolean;
  evidenceCount: number;
};

export default function DraftPanel({
  draft,
  holdRequired,
  evidenceCount,
}: DraftPanelProps) {
  const [text, setText] =
    useState(draft.text);

  const [status, setStatus] =
    useState<DraftStatus>(draft.status);

  useEffect(() => {
    setText(draft.text);
    setStatus(draft.status);
  }, [draft]);

  const insufficientEvidence =
    evidenceCount === 0;

  const effectiveStatus: DraftStatus =
    insufficientEvidence
      ? "INSUFFICIENT_EVIDENCE"
      : status === "REJECTED"
        ? "REJECTED"
        : holdRequired
          ? "HOLD"
          : status;

  const statusDescription: Record<
    DraftStatus,
    string
  > = {
    DRAFT:
      "근거를 검토하며 내부 초안을 수정할 수 있습니다.",
    REVIEW_PENDING:
      "내부 검토를 기다리는 초안이며 수정하면 다시 초안 상태가 됩니다.",
    HOLD:
      "위험도 또는 신뢰도 기준으로 보류되어 승인 대기를 요청할 수 없습니다.",
    INSUFFICIENT_EVIDENCE:
      "Citation이 없어 초안을 수정하거나 승인 대기를 요청할 수 없습니다.",
    REJECTED:
      "거절된 초안이므로 수정하거나 승인 대기를 요청할 수 없습니다.",
  };

  const canEdit =
    effectiveStatus !==
      "INSUFFICIENT_EVIDENCE" &&
    effectiveStatus !== "REJECTED";

  const canRequestReview =
    !holdRequired &&
    !insufficientEvidence &&
    text.trim().length > 0 &&
    effectiveStatus !== "REJECTED";

  return (
    <section
      className="draft-panel card card-body stack"
      aria-labelledby="draft-panel-title"
    >
      <div className="draft-panel-header">
        <div>
          <strong id="draft-panel-title">
            AI 답변 Draft
          </strong>

          <p className="tertiary">
            고객에게 전송된 답변이 아닙니다.
            운영자가 검토하는 내부 초안입니다.
          </p>
        </div>

        <span
          className={`badge ${
            effectiveStatus ===
              "INSUFFICIENT_EVIDENCE" ||
            effectiveStatus === "HOLD"
              ? "warning"
              : effectiveStatus ===
                  "REJECTED"
                ? "critical"
                : "ai"
          }`}
        >
          {draftStatusLabels[
            effectiveStatus
          ]}
        </span>
      </div>

      <p
        id="draft-status-description"
        className="tertiary"
        aria-live="polite"
      >
        현재 상태: {draftStatusLabels[effectiveStatus]}.{" "}
        {statusDescription[effectiveStatus]}
      </p>

      {draft.provenance ? (
        <p className="tertiary">
          생성 출처:{" "}
          <strong>
            {draft.provenance}
          </strong>
        </p>
      ) : (
        <p className="tertiary">
          생성 출처: 확인 불가
        </p>
      )}

      {insufficientEvidence ? (
        <div
          className="notice warning"
          role="note"
        >
          <strong>
            근거 부족
          </strong>

          <p>
            Citation이 없어 답변 초안을
            확정할 수 없습니다.
          </p>
        </div>
      ) : null}

      {holdRequired &&
      !insufficientEvidence ? (
        <div
          className="notice warning"
          role="note"
        >
          <strong>
            수동 검토 필요
          </strong>

          <p>
            위험도 또는 신뢰도 기준으로
            답변 진행이 보류되었습니다.
          </p>
        </div>
      ) : null}

      <label
        className="stack"
        htmlFor="inquiry-draft-text"
      >
        <strong>
          Draft 내용
        </strong>

        <textarea
          id="inquiry-draft-text"
          className="draft"
          value={text}
          disabled={!canEdit}
          aria-describedby="draft-status-description draft-safety-note"
          onChange={(event) => {
            setText(
              event.currentTarget.value,
            );

            if (
              effectiveStatus ===
              "REVIEW_PENDING"
            ) {
              setStatus("DRAFT");
            }
          }}
        />
      </label>

      <div
        className="draft-actions"
        aria-label="Draft 검토 상태"
      >
        <button
          type="button"
          className="filter"
          disabled={!canEdit}
          onClick={() =>
            setStatus("DRAFT")
          }
        >
          수정
        </button>

        <button
          type="button"
          className="filter active"
          disabled={!canRequestReview}
          onClick={() =>
            setStatus(
              "REVIEW_PENDING",
            )
          }
        >
          승인 대기
        </button>

        <button
          type="button"
          className="filter"
          disabled={insufficientEvidence}
          onClick={() =>
            setStatus("HOLD")
          }
        >
          보류
        </button>

        <button
          type="button"
          className="filter"
          disabled={
            !insufficientEvidence
          }
          onClick={() =>
            setStatus(
              "INSUFFICIENT_EVIDENCE",
            )
          }
        >
          근거 부족
        </button>

        <button
          type="button"
          className="filter"
          onClick={() =>
            setStatus("REJECTED")
          }
        >
          거절
        </button>
      </div>

      <p
        id="draft-safety-note"
        className="tertiary"
      >
        이 화면에는 실제 고객 전송
        기능이나 Provider write 요청이
        없습니다.
      </p>
    </section>
  );
}