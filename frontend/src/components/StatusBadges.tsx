import type { Freshness, RiskLevel } from "../types/contracts";
import { freshnessLabel, riskLabel } from "./statusLabels";

type FreshnessBadgeProps = {
  freshness?: Freshness | null;
};

type RiskLevelBadgeProps = {
  risk?: RiskLevel | null;
};

export function FreshnessBadge({ freshness }: FreshnessBadgeProps) {
  if (!freshness) {
    return (
      <span className="badge status-unknown">
        ? 확인 불가
      </span>
    );
  }

  const icon =
    freshness === "FRESH"
      ? "●"
      : freshness === "STALE"
        ? "▲"
        : "?";

  const state =
    freshness === "FRESH"
      ? "success"
      : freshness === "STALE"
        ? "warning"
        : "status-unknown";

  return (
    <span className={`badge ${state}`}>
      {icon} {freshnessLabel[freshness]}
    </span>
  );
}

export function RiskLevelBadge({ risk }: RiskLevelBadgeProps) {
  if (!risk) {
    return (
      <span className="badge status-unknown">
        ? 위험도 확인 불가
      </span>
    );
  }

  const icon =
    risk === "LOW"
      ? "✓"
      : risk === "MEDIUM"
        ? "▲"
        : risk === "HIGH"
          ? "●"
          : "⛔";

  const state =
    risk === "LOW"
      ? "success"
      : risk === "MEDIUM"
        ? "warning"
        : risk === "HIGH"
          ? "critical"
          : "prohibited";

  return (
    <span className={`badge ${state}`}>
      {icon} {riskLabel[risk]}
    </span>
  );
}

type ConfidenceBadgeProps = {
  confidence?: number | null;
};

export function ConfidenceBadge({ confidence }: ConfidenceBadgeProps) {
  if (
    confidence === null ||
    confidence === undefined ||
    !Number.isFinite(confidence)
  ) {
    return (
      <span className="badge status-unknown">
        ? 신뢰도 확인 불가
      </span>
    );
  }

  const normalized = Math.max(0, Math.min(1, confidence));
  const percentage = Math.round(normalized * 100);

  const state =
    normalized >= 0.8
      ? "success"
      : normalized >= 0.6
        ? "warning"
        : "critical";

  const icon =
    normalized >= 0.8
      ? "●"
      : normalized >= 0.6
        ? "▲"
        : "⚠";

  return (
    <span className={`badge ${state}`}>
      {icon} 신뢰도 {percentage}%
    </span>
  );
}