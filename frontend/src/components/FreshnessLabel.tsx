import type {
  Freshness,
  Provider,
} from "../types/contracts";
import { useId } from "react";
import { FreshnessBadge } from "./StatusBadges";

type FreshnessLabelProps = {
  freshness: Freshness;
  asOf: string;
  source: Provider;
  showMetadata?: boolean;
};

const freshnessDescription: Record<Freshness, string> = {
  FRESH: "현재 최신성 기준을 만족하는 데이터입니다.",
  STALE:
    "최신성 기준을 초과한 데이터입니다. 최신 자료를 다시 확인하기 전까지 확정 판단에 사용하지 않습니다.",
  UNKNOWN:
    "최신성 판단 정보가 없습니다. 최신 데이터나 재고 0으로 간주하지 않습니다.",
};

export default function FreshnessLabel({
  freshness,
  asOf,
  source,
  showMetadata = true,
}: FreshnessLabelProps) {
  const description = freshnessDescription[freshness];
  const descriptionId = useId();

  return (
    <div className="freshness-label">
      <div className="freshness-label-main">
        <FreshnessBadge freshness={freshness} />

        <span
          className="freshness-help"
          title={description}
          role="note"
          aria-label="최신성 도움말"
          aria-describedby={descriptionId}
          tabIndex={0}
        >
          ?
        </span>
      </div>

      {showMetadata && (
        <div className="freshness-meta">
          <span>
            source: <strong>{source}</strong>
          </span>

          <span>
            as_of:{" "}
            <time dateTime={asOf}>
              {new Date(asOf).toLocaleString("ko-KR")}
            </time>
          </span>
        </div>
      )}

      <p
        id={descriptionId}
        className="muted freshness-description"
      >
        {description}
      </p>
    </div>
  );
}
