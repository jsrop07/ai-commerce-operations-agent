import type {
  ReservationRiskItem,
} from "../../types/contracts";
import { useState } from "react";
import PolicyExplanation from "./PolicyExplanation";

import {
  formatReservationQuantity,
  getReservationRiskDisplayState,
  getReservationRiskLabel,
  getSourceClassificationLabel,
} from "./reservationViewModels";

type ReservationListProps = {
  items: ReservationRiskItem[];
  showPolicyExplanation?: boolean;
};

function displayOptionalNumber(
  value: number | null | undefined,
): string {
  return value === null || value === undefined
    ? "미제공"
    : String(value);
}

export default function ReservationList({
  items,
  showPolicyExplanation = false,
}: ReservationListProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = items.find((item) =>
    item.reservation_id === selectedId &&
    item.source_classification === "SYNTHETIC_DEMO" &&
    getReservationRiskDisplayState(item) !== "UNCERTAIN",
  );
  if (items.length === 0) {
    return (
      <section
        className="card card-body"
        data-testid="reservation-list-empty"
      >
        <strong>예약 위험 정보가 없습니다</strong>
        <p className="muted">
          현재 확정 가능한 예약 위험 Projection이 없습니다.
          확인되지 않은 값을 0으로 표시하지 않습니다.
        </p>
      </section>
    );
  }

  return (
    <section
      className="card"
      aria-labelledby="reservation-risk-title"
      data-testid="reservation-list"
    >
      <div className="card-header">
        <strong id="reservation-risk-title">
          예약주문 위험 목록
        </strong>
      </div>

      <div className="table-scroll">
        <table className="dense-table">
          <thead>
            <tr>
              <th scope="col">상태</th>
              <th scope="col">상품</th>
              <th scope="col">필요 수량</th>
              <th scope="col">확보 수량</th>
              <th scope="col">확정 입고</th>
              <th scope="col">예정 입고</th>
              <th scope="col">부족 수량</th>
              <th scope="col">경과</th>
              <th scope="col">우선순위</th>
              <th scope="col">데이터 출처</th>
            </tr>
          </thead>

          <tbody>
            {items.map((item) => {
              const displayState =
                getReservationRiskDisplayState(item);

              return (
                <tr
                  key={item.reservation_id}
                  data-testid="reservation-risk-row"
                  data-risk-state={displayState}
                >
                  <td>
                    <strong>
                      {getReservationRiskLabel(item)}
                    </strong>
                  </td>

                  <td>
                    <div>
                      <strong>
                        {item.product_name}
                      </strong>
                    </div>

                    <div className="mono tertiary">
                      {item.reservation_id}
                    </div>

                    {item.sku_id ? (
                      <div className="mono tertiary">
                        {item.sku_id}
                      </div>
                    ) : null}
                    {showPolicyExplanation &&
                      item.source_classification === "SYNTHETIC_DEMO" &&
                      displayState !== "UNCERTAIN" && (
                        <button
                          type="button"
                          className="filter"
                          aria-label={`${item.product_name} 예약상품 출고 정책 선택`}
                          aria-pressed={selectedId === item.reservation_id}
                          onClick={() => setSelectedId(item.reservation_id)}
                        >
                          출고 정책
                        </button>
                      )}
                  </td>

                  <td className="number">
                    {formatReservationQuantity(
                      item.required_qty,
                      item.required_state,
                    )}
                  </td>

                  <td className="number">
                    {formatReservationQuantity(
                      item.secured_qty,
                      item.secured_state,
                    )}
                  </td>

                  <td className="number">
                    {formatReservationQuantity(
                      item.confirmed_incoming,
                      item.confirmed_incoming_state,
                    )}
                  </td>

                  <td className="number">
                    {formatReservationQuantity(
                      item.tentative_incoming,
                      item.tentative_incoming_state,
                    )}
                  </td>

                  <td className="number">
                    {formatReservationQuantity(
                      item.shortage,
                      item.shortage_state,
                    )}
                  </td>

                  <td className="number">
                    {displayOptionalNumber(item.aging)}
                  </td>

                  <td>
                    {item.priority ?? "확인 필요"}
                  </td>

                  <td>
                    {getSourceClassificationLabel(
                      item.source_classification,
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {showPolicyExplanation && selected &&
        <PolicyExplanation key={selected.reservation_id} targetId={selected.reservation_id} productName={selected.product_name} />}
    </section>
  );
}
