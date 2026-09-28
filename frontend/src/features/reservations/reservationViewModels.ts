import type {
  ReservationRiskItem,
  ReservationValueState,
} from "../../types/contracts";

export type ReservationRiskDisplayState =
  | "SHORTAGE"
  | "SUFFICIENT"
  | "UNCERTAIN";

export function formatReservationQuantity(
  value: number | null,
  state?: ReservationValueState,
): string {
  if (value !== null) {
    return String(value);
  }

  if (state === "BLOCKED") {
    return "확인 불가";
  }

  if (state === "UNKNOWN") {
    return "미확인";
  }

  return "미제공";
}

export function getReservationRiskDisplayState(
  item: ReservationRiskItem,
): ReservationRiskDisplayState {
  if (
    item.shortage_state !== "KNOWN" ||
    item.shortage === null
  ) {
    return "UNCERTAIN";
  }

  if (item.shortage > 0) {
    return "SHORTAGE";
  }

  return "SUFFICIENT";
}

export function getReservationRiskLabel(
  item: ReservationRiskItem,
): string {
  const state = getReservationRiskDisplayState(
    item,
  );

  if (state === "SHORTAGE") {
    return "▲ 부족";
  }

  if (state === "SUFFICIENT") {
    return "✓ 충분";
  }

  return "● 확인 필요";
}

export function getSourceClassificationLabel(
  value: ReservationRiskItem["source_classification"],
): string {
  switch (value) {
    case "SANITIZED_REAL":
      return "실제 데이터 · 비식별 처리";
    case "FIXTURE":
      return "테스트 Fixture";
    case "CONTRACT_ONLY":
      return "계약만 확인됨";
    case "BLOCKED":
      return "연결 차단";
  }
}