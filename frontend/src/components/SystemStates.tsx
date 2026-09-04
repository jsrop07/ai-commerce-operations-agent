import { useId } from "react";

type SystemStateKind = "loading" | "empty" | "stale" | "denied";

type SystemStateProps = {
  state: SystemStateKind;
  title?: string;
  description?: string;
  onAction?: () => void;
};

const defaultContent: Record<
  SystemStateKind,
  {
    icon: string;
    title: string;
    description: string;
    actionLabel?: string;
  }
> = {
  loading: {
    icon: "…",
    title: "데이터를 불러오는 중입니다",
    description: "최신 운영 데이터를 확인하고 있습니다.",
  },

  empty: {
    icon: "○",
    title: "표시할 데이터가 없습니다",
    description: "현재 조건에 해당하는 운영 데이터가 없습니다.",
  },

  stale: {
    icon: "▲",
    title: "정보가 오래되었습니다",
    description:
      "최신 정보가 아닐 수 있습니다. 기준 시각을 확인한 뒤 직접 검토하세요.",
    actionLabel: "다시 확인",
  },

  denied: {
    icon: "⛔",
    title: "안전 정책으로 실행할 수 없습니다",
    description:
      "현재 환경에서는 외부 시스템 변경이 차단되어 있습니다. 내부 확인 업무 또는 제안만 사용할 수 있습니다.",
  },
};

export default function SystemState({
  state,
  title,
  description,
  onAction,
}: SystemStateProps) {
  const content = defaultContent[state];
  const titleId = useId();

  return (
    <section
      className={`system-state system-state-${state}`}
      role={state === "loading" ? "status" : "region"}
      aria-labelledby={titleId}
      aria-live={state === "loading" ? "polite" : undefined}
      data-testid={`system-state-${state}`}
    >
      <div className="system-state-icon" aria-hidden="true">
        {content.icon}
      </div>

      <div className="system-state-content">
        <h3 id={titleId}>{title ?? content.title}</h3>
        <p>{description ?? content.description}</p>

        {content.actionLabel && onAction && (
          <button
            type="button"
            className="system-state-action"
            onClick={onAction}
          >
            {content.actionLabel}
          </button>
        )}
      </div>
    </section>
  );
}

export type { SystemStateKind };
