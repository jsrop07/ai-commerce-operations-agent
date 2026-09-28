import { RiskBadge, SourceBadge, StatusBadge } from "../../components/Badges";
import InternalTaskAction from "../../components/InternalTaskAction";
import {
  useEffect,
  useState,
} from "react";

import ReservationList from "../../features/reservations/ReservationList";

import {
  getDay09Reservations,
} from "../../api/day09";

import type {
  ReservationRiskItem,
} from "../../types/contracts";

const orders = [
  ["C24-0904-8821", "Cafe24", "데모고객 001", "레드벨벳 케이크", "1", "₩42,000", "준비중", "9월 6일", "재고 부족"],
  ["C24-0904-8820", "Cafe24", "데모고객 002", "티라미수 세트", "2", "₩116,000", "준비중", "9월 7일", ""],
  ["TP-0904-1043", "Toss POS", "현장방문 고객", "딸기 생크림 케이크", "1", "₩38,000", "완료", "—", ""],
  ["C24-0904-8819", "Cafe24", "데모고객 003", "말차 라떼 케이크", "1", "₩48,000", "보류", "9월 7일", "재고 없음"],
  ["C24-0904-8818", "Cafe24", "데모고객 004", "얼그레이 케이크", "1", "₩45,000", "배송중", "9월 5일", ""],
];

export default function OrdersPage() {
  const useRealBackend =
    import.meta.env.VITE_USE_REAL_BACKEND === "true";

  const [
    reservationItems,
    setReservationItems,
  ] = useState<ReservationRiskItem[] | null>(
    null,
  );

  const [
    reservationError,
    setReservationError,
  ] = useState<string | null>(null);

  const [
    reservationWarnings,
    setReservationWarnings,
  ] = useState<string[]>([]);
  useEffect(() => {
  if (!useRealBackend) {
    return;
  }

  const controller =
    new AbortController();

  getDay09Reservations(
    controller.signal,
  )
    .then((response) => {
      setReservationItems(
        response.data,
      );

      setReservationWarnings(
        response.warnings,
      );

      setReservationError(null);
    })
    .catch(() => {
      setReservationError(
        "예약 위험 Backend Projection을 불러오지 못했습니다.",
      );
    });

  return () => {
    controller.abort();
  };
}, [useRealBackend]);
  return (
    <div className="page" data-testid="route-orders">
      <div className="toolbar"><strong>전체 주문 247건</strong><SourceBadge>Cafe24 189건</SourceBadge><SourceBadge>Toss POS 58건</SourceBadge><RiskBadge level="critical" /><span className="right tertiary">합성 주문 · 조회 전용</span></div>
      <div className="split">
        <section className="card"><table className="dense-table"><thead><tr><th>주문번호</th><th>소스</th><th>고객</th><th>상품</th><th>수량</th><th>금액</th><th>상태</th><th>배송 예정</th><th>위험</th></tr></thead>
          <tbody>{orders.map((row) => <tr key={row[0]} className={row[8] ? "risk-row" : ""}><td className="mono">{row[0]}</td><td><SourceBadge>{row[1]}</SourceBadge></td><td>{row[2]}</td><td>{row[3]}</td><td className="number">{row[4]}</td><td className="number">{row[5]}</td><td><StatusBadge>{row[6]}</StatusBadge></td><td>{row[7]}</td><td>{row[8] && <span className="badge critical">⚑ {row[8]}</span>}</td></tr>)}</tbody>
        </table></section>
<aside className="stack">
  {useRealBackend ? (
    <>
      {reservationError ? (
        <section
          className="card card-body"
          data-testid="reservation-error"
        >
          <strong>
            예약 위험 정보를 불러오지 못했습니다
          </strong>

          <p className="muted">
            {reservationError}
          </p>
        </section>
      ) : reservationItems === null ? (
        <section
          className="card card-body"
          data-testid="reservation-loading"
        >
          <strong>
            예약 위험 정보를 불러오는 중입니다
          </strong>
        </section>
      ) : (
        <>
          {reservationWarnings.length > 0 ? (
            <section
              className="notice warning"
              data-testid="reservation-warning"
            >
              <strong>
                예약 위험 Projection 안내
              </strong>

              <ul>
                {reservationWarnings.map(
                  (warning) => (
                    <li key={warning}>
                      {warning}
                    </li>
                  ),
                )}
              </ul>
            </section>
          ) : null}

          <ReservationList
            items={reservationItems}
          />
        </>
      )}
    </>
  ) : (
    <section
      className="card card-body"
      data-testid="reservation-fixture-placeholder"
    >
      <strong>
        예약 위험 테스트 화면
      </strong>

      <p className="muted">
        현재 Mock 모드에서는 Day 9 Fixture를
        실제 Backend 데이터로 표시하지 않습니다.
      </p>
    </section>
  )}
</aside>
      </div>
    </div>
  );
}
