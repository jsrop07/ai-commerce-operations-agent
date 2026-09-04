import { RiskBadge, SourceBadge, StatusBadge } from "../../components/Badges";
import InternalTaskAction from "../../components/InternalTaskAction";

const orders = [
  ["C24-0904-8821", "Cafe24", "데모고객 001", "레드벨벳 케이크", "1", "₩42,000", "준비중", "9월 6일", "재고 부족"],
  ["C24-0904-8820", "Cafe24", "데모고객 002", "티라미수 세트", "2", "₩116,000", "준비중", "9월 7일", ""],
  ["TP-0904-1043", "Toss POS", "현장방문 고객", "딸기 생크림 케이크", "1", "₩38,000", "완료", "—", ""],
  ["C24-0904-8819", "Cafe24", "데모고객 003", "말차 라떼 케이크", "1", "₩48,000", "보류", "9월 7일", "재고 없음"],
  ["C24-0904-8818", "Cafe24", "데모고객 004", "얼그레이 케이크", "1", "₩45,000", "배송중", "9월 5일", ""],
];

export default function OrdersPage() {
  return (
    <div className="page" data-testid="route-orders">
      <div className="toolbar"><strong>전체 주문 247건</strong><SourceBadge>Cafe24 189건</SourceBadge><SourceBadge>Toss POS 58건</SourceBadge><RiskBadge level="critical" /><span className="right tertiary">합성 주문 · 조회 전용</span></div>
      <div className="split">
        <section className="card"><table className="dense-table"><thead><tr><th>주문번호</th><th>소스</th><th>고객</th><th>상품</th><th>수량</th><th>금액</th><th>상태</th><th>배송 예정</th><th>위험</th></tr></thead>
          <tbody>{orders.map((row) => <tr key={row[0]} className={row[8] ? "risk-row" : ""}><td className="mono">{row[0]}</td><td><SourceBadge>{row[1]}</SourceBadge></td><td>{row[2]}</td><td>{row[3]}</td><td className="number">{row[4]}</td><td className="number">{row[5]}</td><td><StatusBadge>{row[6]}</StatusBadge></td><td>{row[7]}</td><td>{row[8] && <span className="badge critical">⚑ {row[8]}</span>}</td></tr>)}</tbody>
        </table></section>
        <aside className="card">
          <div className="card-header"><RiskBadge level="critical" /> 주문 위험 상세</div>
          <div className="card-body stack"><h3 style={{ margin: 0 }}>레드벨벳 케이크</h3><p className="mono tertiary">C24-0904-8821</p><div className="notice"><strong>예상 배송 영향</strong><br />확보 재고 부족으로 예정일 지연 가능성이 있습니다.</div><div className="card"><table className="dense-table"><tbody><tr><td>주문 수량</td><td className="number">1개</td></tr><tr><td>현재 확보</td><td className="number">0개</td></tr><tr><td>확정 입고</td><td className="number">6개 / 9월 6일</td></tr></tbody></table></div><p className="muted">담당자 확인 후 내부 후속 업무를 만들 수 있습니다.</p><InternalTaskAction /></div>
        </aside>
      </div>
    </div>
  );
}
