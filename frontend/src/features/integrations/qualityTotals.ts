import type { QualityStatusValue } from "./QualityStatus";

type QualityInventoryItem = {
  quality_status: QualityStatusValue;
  on_hand: number | null;
};

const excludedStatuses = new Set<QualityStatusValue>([
  "UNMAPPED",
  "QUARANTINED",
  "SOURCE_QUALITY_BLOCKED",
]);

export function confirmedInventoryTotal(
  items: readonly QualityInventoryItem[],
) {
  return items.reduce((total, item) => {
    if (
      excludedStatuses.has(item.quality_status) ||
      item.on_hand === null ||
      !Number.isFinite(item.on_hand)
    ) {
      return total;
    }

    return total + item.on_hand;
  }, 0);
}
