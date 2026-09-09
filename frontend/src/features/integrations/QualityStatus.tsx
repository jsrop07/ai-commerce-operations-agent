type QualityStatusValue =
  | "USABLE"
  | "STALE"
  | "UNMAPPED"
  | "QUARANTINED"
  | "SOURCE_QUALITY_BLOCKED";

type QualityStatusProps = {
  status: QualityStatusValue;
  provider: string;
  confirmedForTotal?: boolean;
};

const qualityContent: Record<
  QualityStatusValue,
  {
    label: string;
    description: string;
    className: string;
  }
> = {
  USABLE: {
    label: "업무 사용 가능",
    description:
      "현재 데이터는 확정 재고 계산에 사용할 수 있습니다.",
    className: "success",
  },

  STALE: {
    label: "오래된 데이터",
    description:
      "데이터는 존재하지만 최신성 기준을 초과했습니다. 최신 자료 확인 전까지 주의가 필요합니다.",
    className: "warning",
  },

  UNMAPPED: {
    label: "상품 연결 필요",
    description:
      "원천 상품이 내부 SKU에 연결되지 않았습니다. 확정 재고 합계에서 제외합니다.",
    className: "warning",
  },

  QUARANTINED: {
    label: "격리됨",
    description:
      "검증이 필요한 데이터로 격리되었습니다. 확정 재고 합계에서 제외합니다.",
    className: "critical",
  },

  SOURCE_QUALITY_BLOCKED: {
    label: "원천 품질 차단",
    description:
      "원천 데이터 품질 문제로 업무 기준값으로 사용할 수 없습니다. 재고 0으로 간주하지 않고 확정 재고 합계에서 제외합니다.",
    className: "critical",
  },
};

export default function QualityStatus({
  status,
  provider,
  confirmedForTotal,
}: QualityStatusProps) {
  const content = qualityContent[status];
  const confirmedUsage =
    confirmedForTotal === true
      ? {
          value: "true",
          label: "확정 재고 합계에 포함",
        }
      : confirmedForTotal === false
        ? {
            value: "false",
            label: "확정 재고 합계에서 제외",
          }
        : {
            value: "unknown",
            label: "확정 재고 합계 포함 여부 미제공",
          };
  return (
    <div className="quality-status">
      <div className="quality-status-main">
        <span className={`badge ${content.className}`}>
          {content.label}
        </span>

        <span className="muted">
          {provider}
        </span>
      </div>

      <p className="muted quality-status-description">
        {content.description}
      </p>

    <p
      className="quality-status-usage"
      data-usable-for-confirmed-inventory={
        confirmedUsage.value
      }
    >
      {confirmedUsage.label}
    </p>
    </div>
  );
}

export type { QualityStatusValue };
