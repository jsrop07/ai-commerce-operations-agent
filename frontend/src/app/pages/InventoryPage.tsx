import { RiskBadge, SourceBadge } from "../../components/Badges";
import InternalTaskAction from "../../components/InternalTaskAction";

const products = [
  ["레드벨벳 케이크 500g", "CAKE-RV-500", "12", "3", "-9", "20 / 9월 6일", "critical", "3분 전"],
  ["티라미수 케이크 세트", "CAKE-TM-SET", "24", "18", "-6", "30 / 9월 8일", "critical", "12분 전"],
  ["딸기 생크림 케이크", "CAKE-STR-WC", "15", "15", "0", "—", "ok", "5분 전"],
  ["초코 가나슈 롤케이크", "ROLL-CHO-GAN", "8", "6", "-2", "10 / 9월 5일", "warning", "47분 전"],
  ["말차 라떼 케이크", "CAKE-MT-LAT", "5", "0", "-5", "15 / 9월 7일", "critical", "47분 전"],
];

export default function InventoryPage() {
  return (
    <div className="page" data-testid="route-inventory">
      <div className="toolbar"><button className="filter active">재고 현황</button><button className="filter">상품 연결 <span className="badge warning">3</span></button><span className="right tertiary">행 기준 최신 확인 시각 표시</span></div>
      <div className="notice" style={{ marginBottom: 14 }}><strong>⚠ 데이터 지연 · 최신 정보가 아닐 수 있습니다</strong><br /><span className="muted">eCount 마지막 확인 47분 전 · 중요 의사결정 전 직접 확인하세요.</span></div>
      <div className="split">
        <section className="card">
          <table className="dense-table">
            <thead><tr><th>상품명</th><th>SKU</th><th>판매 재고</th><th>실재고</th><th>차이</th><th>입고 예정</th><th>상태</th><th>최종 확인</th></tr></thead>
            <tbody>{products.map(([name, sku, listed, actual, diff, incoming, level, updated]) => (
              <tr key={sku}>
                <td><strong>{name}</strong></td><td className="mono">{sku}</td>
                <td className="number"><SourceBadge>Cafe24</SourceBadge> {listed}</td><td className="number"><SourceBadge>eCount</SourceBadge> {actual}</td>
                <td className="number"><strong>{diff}</strong></td><td>{incoming}</td><td><RiskBadge level={level as "critical" | "warning" | "ok"} /></td><td><span className="badge">⏱ {updated}</span></td>
              </tr>
            ))}</tbody>
          </table>
        </section>
        <aside className="card">
          <div className="card-header">재고 비교 요약</div>
          <div className="card-body stack">
            <RiskBadge level="critical" />
            <h3 style={{ margin: 0 }}>레드벨 케이크 500g</h3>
            <div className="notice ai">✦ eCount 데이터 지연 또는 POS 판매 반영 시차로 차이가 생겼을 수 있습니다.</div>
            <div className="card"><table className="dense-table"><tbody><tr><td>판매 재고</td><td className="number">12개</td></tr><tr><td>실재고</td><td className="number">3개</td></tr><tr><td>시스템 간 차이</td><td className="number"><strong>-9개</strong></td></tr></tbody></table></div>
            <p className="muted">담당자가 원본 시스템에서 직접 확인한 뒤 판단합니다.</p>
            <InternalTaskAction />
          </div>
        </aside>
      </div>
    </div>
  );
}
