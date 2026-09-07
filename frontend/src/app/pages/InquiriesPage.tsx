import {
  useMemo,
  useState,
} from "react";

import {
  ConfidenceBadge,
  RiskLevelBadge,
} from "../../components/StatusBadges";

import CitationCard from "../../features/inquiries/CitationCard";

import {
  inquiryStatusLabels,
  requiresManualReview,
} from "../../features/inquiries/inquiryViewModels";

import {
  inquiryWorkbenchItems,
} from "../../mocks/fixtures";

import DraftPanel from "../../features/inquiries/DraftPanel";

export default function InquiriesPage() {
  const [
    selectedInquiryId,
    setSelectedInquiryId,
  ] = useState(
    inquiryWorkbenchItems[0]?.inquiry.id ?? "",
  );

  const selectedItem = useMemo(
    () =>
      inquiryWorkbenchItems.find(
        (item) =>
          item.inquiry.id ===
          selectedInquiryId,
      ) ?? inquiryWorkbenchItems[0],
    [selectedInquiryId],
  );

  if (!selectedItem) {
    return (
      <div
        className="page"
        data-testid="route-inquiries"
      >
        <p>표시할 문의가 없습니다.</p>
      </div>
    );
  }

  const {
    inquiry,
    workbench,
    retrieval,
  } = selectedItem;

  const manualReviewRequired =
    requiresManualReview(
      inquiry.risk,
      workbench.confidence,
    );

  const holdRequired =
    manualReviewRequired ||
    workbench.answerStatus === "HOLD" ||
    retrieval.answer_status === "HOLD" ||
    retrieval.citations.length === 0;

  return (
    <div
      className="page flush"
      data-testid="route-inquiries"
    >
      <div className="three-column inquiry-layout">
        {/* 1. Inquiry 목록 */}
        <section
          className="column"
          aria-labelledby="inquiry-list-title"
        >
          <div
            className="column-title"
            id="inquiry-list-title"
          >
            고객 문의
            <span className="tertiary">
              {inquiryWorkbenchItems.length}건
            </span>
          </div>

          <div
            className="inquiry-list"
            aria-label="고객 문의 목록"
          >
            {inquiryWorkbenchItems.map(
              (item) => {
                const isSelected =
                  item.inquiry.id ===
                  selectedInquiryId;

                return (
                  <button
                    key={item.inquiry.id}
                    type="button"
                    className={`list-item ${
                      isSelected
                        ? "active"
                        : ""
                    }`}
                    aria-pressed={isSelected}
                    onClick={() =>
                      setSelectedInquiryId(
                        item.inquiry.id,
                      )
                    }
                  >
                    <div className="badges">
                      <RiskLevelBadge
                        risk={
                          item.inquiry.risk
                        }
                      />

                      <span className="right mono tertiary">
                        {item.ageLabel}
                      </span>
                    </div>

                    <strong>
                      {item.inquiry.intent}
                    </strong>

                    <div className="tertiary">
                      {
                        inquiryStatusLabels[
                          item.status
                        ]
                      }
                    </div>
                  </button>
                );
              },
            )}
          </div>
        </section>

        {/* 2. Conversation */}
        <section
          className="column"
          aria-labelledby="conversation-title"
        >
          <div
            className="column-title"
            id="conversation-title"
          >
            Conversation
          </div>

          <div className="card-body stack">
            <div className="badges">
              <RiskLevelBadge
                risk={inquiry.risk}
              />

              <span className="badge source">
                {inquiry.channel}
              </span>
            </div>

            <div className="card card-body">
              <strong>
                비식별 문의 원문
              </strong>

              <p>
                {inquiry.sanitized_text}
              </p>

              <p className="mono tertiary">
                {inquiry.id}
              </p>
            </div>

            <div className="card card-body">
              <strong>
                관련 Reference
              </strong>

              {selectedItem.relatedProductRef ? (
                <p>
                  Product:{" "}
                  <span className="mono">
                    {
                      selectedItem.relatedProductRef
                    }
                  </span>
                </p>
              ) : null}

              {selectedItem.relatedOrderRef ? (
                <p>
                  Order:{" "}
                  <span className="mono">
                    {
                      selectedItem.relatedOrderRef
                    }
                  </span>
                </p>
              ) : null}

              {!selectedItem.relatedProductRef &&
              !selectedItem.relatedOrderRef ? (
                <p className="tertiary">
                  연결된 Product/Order
                  reference가 없습니다.
                </p>
              ) : null}
            </div>
          </div>
        </section>

        {/* 3. AI Workbench */}
        <section
          className="column"
          aria-labelledby="workbench-title"
        >
          <div
            className="column-title"
            id="workbench-title"
          >
            AI Workbench
          </div>

          <div className="page stack">
            {/* Structured Result */}
            <div className="card card-body">
              <strong>
                Structured Result
              </strong>

              <p>
                Intent:{" "}
                <span className="mono">
                  {inquiry.intent}
                </span>
              </p>

              <div>
                <strong>Entities</strong>

                {Object.keys(
                  inquiry.entities,
                ).length > 0 ? (
                  <ul>
                    {Object.entries(
                      inquiry.entities,
                    ).map(
                      ([key, value]) => (
                        <li key={key}>
                          <span className="mono">
                            {key}
                          </span>
                          :{" "}
                          <span className="mono">
                            {value}
                          </span>
                        </li>
                      ),
                    )}
                  </ul>
                ) : (
                  <p className="tertiary">
                    구조화된 Entity가 없습니다.
                  </p>
                )}
              </div>
            </div>

            {/* Workbench Confidence */}
            <div className="card card-body">
              <strong>
                Confidence
              </strong>

              <ConfidenceBadge
                confidence={
                  workbench.confidence
                }
              />
            </div>

            {/* Retrieval */}
            <div className="card card-body stack">
              <div className="workbench-section-header">
                <strong>
                  Retrieval Evidence
                </strong>

                <span className="tertiary">
                  {retrieval.method}
                  {" · "}
                  {retrieval.index_version}
                </span>
              </div>

              <p className="tertiary">
                Query: {retrieval.query}
              </p>

              <div className="tertiary">
                Retrieval confidence:{" "}
                <ConfidenceBadge
                  confidence={
                    retrieval.confidence
                  }
                />
              </div>

              <p className="tertiary">
                Retrieval answer status:{" "}
                <strong className="mono">
                  {retrieval.answer_status}
                </strong>
                {retrieval.answer_status === "HOLD"
                  ? " · 답변을 확정할 수 없어 보류합니다."
                  : " · 근거를 검토한 뒤 내부 Draft를 작성할 수 있습니다."}
              </p>

              {retrieval.citations.length >
              0 ? (
                <div className="stack">
                  {retrieval.citations.map(
                    (citation) => (
                      <CitationCard
                        key={`${citation.source_type}:${citation.source_id}:${citation.record_or_field}`}
                        citation={citation}
                      />
                    ),
                  )}
                </div>
              ) : (
                <div
                  className="notice warning"
                  role="note"
                >
                  <strong>
                    근거 부족
                  </strong>

                  <p>
                    검색된 Citation이 없어
                    답변을 확정할 수
                    없습니다.
                  </p>
                </div>
              )}

              {retrieval.warnings.length >
              0 ? (
                <div
                  className="notice warning"
                  role="note"
                >
                  <strong>
                    Retrieval Warnings
                  </strong>

                  <ul>
                    {retrieval.warnings.map(
                      (warning) => (
                        <li key={warning}>
                          {warning}
                        </li>
                      ),
                    )}
                  </ul>
                </div>
              ) : null}
            </div>

            {/* AI Workbench warnings */}
            {workbench.warnings.length >
            0 ? (
              <div
                className="notice warning"
                role="note"
              >
                <strong>
                  Warnings
                </strong>

                <ul>
                  {workbench.warnings.map(
                    (warning) => (
                      <li key={warning}>
                        {warning}
                      </li>
                    ),
                  )}
                </ul>
              </div>
            ) : null}

            <DraftPanel
              draft={selectedItem.draft}
              holdRequired={holdRequired}
              evidenceCount={
                retrieval.citations.length
              }
            />

          </div>
        </section>
      </div>
    </div>
  );
}