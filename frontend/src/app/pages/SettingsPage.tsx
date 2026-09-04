import { SourceBadge } from "../../components/Badges";

const providers = [
  ["Cafe24", "정상", "2분 전", "주문 · 상품 · 재고", "5분"],
  ["Toss POS", "정상", "5분 전", "POS 매출 · 재고", "5분"],
  ["eCount", "지연", "47분 전", "재고 · 입고 · 품목", "30분"],
];

export default function SettingsPage() {
  return (
    <div className="page" data-testid="route-settings">
      <div className="toolbar"><button className="filter active">연동</button><button className="filter">알림</button><button className="filter">팀</button><span className="right readonly-label">🔒 Production 정책과 동일한 읽기 전용 UI</span></div>
      <div className="notice" style={{ marginBottom: 16 }}><strong>연동 상태와 데이터 범위만 확인할 수 있습니다.</strong><br /><span className="muted">자격증명과 비밀값은 표시하지 않으며 외부 시스템을 변경하는 동작은 제공하지 않습니다.</span></div>
      <section className="stack">{providers.map(([name,status,updated,scope,cycle]) => <article className="card provider-card" key={name}><div><SourceBadge>{name}</SourceBadge><h3>{name}</h3><span className={`badge ${status === "정상" ? "success" : "warning"}`}>{status === "정상" ? "●" : "▲"} {status}</span></div><div className="provider-details"><div><span className="tertiary">연동 방식</span><br /><strong>REST API</strong></div><div><span className="tertiary">인증</span><br /><strong>보안 값 미표시</strong></div><div><span className="tertiary">데이터 범위</span><br /><strong>{scope}</strong></div><div><span className="tertiary">확인 주기</span><br /><strong>{cycle}</strong></div></div><div className="mono tertiary">마지막 확인<br /><strong>{updated}</strong></div></article>)}</section>
      <div className="card card-body" style={{ marginTop: 16 }}><strong>🛡 권한 안전 원칙</strong><p className="muted">모든 역할은 외부 시스템에 대해 조회 전용입니다. 고객 응답은 초안 검토까지만 지원합니다.</p></div>
    </div>
  );
}
