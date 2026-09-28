import type {
  TaskProposal,
  TaskProposalStatus,
} from "../../types/contracts";

export function getTaskProposalStatusLabel(
  status: TaskProposalStatus,
): string {
  switch (status) {
    case "PROPOSED":
      return "제안됨";

    case "UNDER_REVIEW":
      return "검토 중";

    case "EDITED":
      return "수정됨";

    case "DISMISSED":
      return "거절됨";
  }
}

export function getTaskProposalSafetyLabel(
  proposal: TaskProposal,
): string {
  if (
    proposal.external_execution_allowed === false
  ) {
    return "내부 검토 제안 · 외부 실행 없음";
  }

  return "외부 실행 금지";
}