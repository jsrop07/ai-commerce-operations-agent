import {
  useState,
} from "react";

import type {
  TaskProposal as TaskProposalModel,
  TaskProposalStatus,
} from "../../types/contracts";

import {
  getTaskProposalSafetyLabel,
  getTaskProposalStatusLabel,
} from "./taskProposalViewModels";

type TaskProposalProps = {
  proposal: TaskProposalModel;
};

export default function TaskProposal({
  proposal,
}: TaskProposalProps) {
  const [
    status,
    setStatus,
  ] = useState<TaskProposalStatus>(
    proposal.status,
  );

  const [
    title,
    setTitle,
  ] = useState(
    proposal.title,
  );

  const [
    isEditing,
    setIsEditing,
  ] = useState(false);

  function startReview() {
    if (
      status === "DISMISSED"
    ) {
      return;
    }

    setStatus("UNDER_REVIEW");
  }

  function saveEdit() {
    if (
      status === "DISMISSED"
    ) {
      return;
    }

    setStatus("EDITED");
    setIsEditing(false);
  }

  function dismissProposal() {
    setStatus("DISMISSED");
    setIsEditing(false);
  }

  return (
    <section
      className="card"
      aria-labelledby={`task-proposal-${proposal.proposal_id}`}
      data-testid="task-proposal"
      data-status={status}
    >
      <div className="card-header">
        <div>
          <strong
            id={`task-proposal-${proposal.proposal_id}`}
          >
            Task 제안
          </strong>

          <div className="tertiary">
            {getTaskProposalStatusLabel(
              status,
            )}
          </div>
        </div>
      </div>

      <div className="card-body stack">
        {isEditing ? (
          <label>
            <span>
              제안 제목
            </span>

            <input
              type="text"
              value={title}
              onChange={(event) =>
                setTitle(
                  event.target.value,
                )
              }
            />
          </label>
        ) : (
          <h3>
            {title}
          </h3>
        )}

        <div>
          <strong>
            제안 사유
          </strong>

          <p>
            {proposal.source_reason}
          </p>
        </div>

        <dl>
          <div>
            <dt>Task Type</dt>
            <dd className="mono">
              {proposal.task_type}
            </dd>
          </div>

          <div>
            <dt>Priority</dt>
            <dd>
              {proposal.priority ??
                "확인 필요"}
            </dd>
          </div>

          <div>
            <dt>기준 시각</dt>
            <dd>
              {proposal.as_of}
            </dd>
          </div>
        </dl>

        <div
          className="notice"
          role="note"
          data-testid="task-proposal-safety"
        >
          <strong>
            {
              getTaskProposalSafetyLabel(
                proposal,
              )
            }
          </strong>

          <p>
            이 화면의 검토·수정·거절은
            내부 제안 상태만 변경합니다.
            외부 Provider의 발주·주문·재고를
            실행하지 않습니다.
          </p>
        </div>

        {proposal.evidence_ids &&
        proposal.evidence_ids.length >
          0 ? (
          <div>
            <strong>
              Evidence
            </strong>

            <ul>
              {proposal.evidence_ids.map(
                (evidenceId) => (
                  <li
                    key={evidenceId}
                    className="mono"
                  >
                    {evidenceId}
                  </li>
                ),
              )}
            </ul>
          </div>
        ) : null}

        <div
          className="toolbar"
          aria-label="Task 제안 검토"
        >
          <button
            type="button"
            className="filter"
            onClick={startReview}
            disabled={
              status ===
              "DISMISSED"
            }
          >
            검토
          </button>

          <button
            type="button"
            className="filter"
            onClick={() =>
              setIsEditing(true)
            }
            disabled={
              status ===
              "DISMISSED"
            }
          >
            수정
          </button>

          {isEditing ? (
            <button
              type="button"
              className="filter active"
              onClick={saveEdit}
            >
              수정 저장
            </button>
          ) : null}

          <button
            type="button"
            className="filter"
            onClick={
              dismissProposal
            }
            disabled={
              status ===
              "DISMISSED"
            }
          >
            거절
          </button>
        </div>
      </div>
    </section>
  );
}