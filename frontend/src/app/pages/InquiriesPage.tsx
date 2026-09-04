import { AIBadge, SourceBadge, StatusBadge } from "../../components/Badges";

const inquiries = [
  ["배송이 언제 되나요?", "데모고객 001", "초안완료", "10분 전"],
  ["픽업 날짜 변경 가능한가요?", "데모고객 003", "검토중", "25분 전"],
  ["알레르기 성분 확인 부탁드립니다", "데모고객 002", "초안완료", "1시간 전"],
  ["처리 기준을 확인하고 싶습니다", "데모고객 004", "보류", "2시간 전"],
];

export default function InquiriesPage() {
  return (
    <div className="page flush" data-testid="route-inquiries">
      <div className="three-column">
        <section className="column"><div className="column-title">문의 목록 <span className="tertiary">· 전체 31건</span></div>{inquiries.map((item, index) => <button className={`list-item ${index === 0 ? "active" : ""}`} key={item[0]}><div className="badges"><StatusBadge>{item[2]}</StatusBadge><span className="right mono tertiary">{item[3]}</span></div><strong>{item[0]}</strong><div className="tertiary">{item[1]}</div></button>)}</section>
        <section className="column"><div className="column-title">문의 내용 · AI 분류</div><div className="card-body stack"><div className="badges"><span className="badge critical">● 긴급</span><SourceBadge>Cafe24 1:1 문의</SourceBadge></div><h3>주문한 케이크 배송이 언제 되나요?</h3><div className="card card-body"><strong>문의 정보</strong><p className="mono tertiary">INQ-DEMO-0231</p><p>고객이 주문 상품의 준비 상태와 배송 예정일을 문의했습니다.</p></div><div className="notice ai"><AIBadge>AI 분류</AIBadge><p><strong>의도:</strong> 배송 조회</p><p><strong>신뢰도:</strong> 96%</p></div><div className="card card-body"><strong>답변 참고 근거</strong><p>• 주문 상태: 준비중</p><p>• 배송 예정: 9월 6일</p><p>• 배송 정책: 출고 후 2~3영업일</p></div></div></section>
        <section className="column"><div className="column-title">AI 답변 초안 · 실제 전송 없음</div><div className="page stack"><div className="notice ai"><AIBadge>Draft only</AIBadge> 담당자 검토를 위한 합성 초안입니다.</div><textarea className="draft" aria-label="AI 답변 초안" defaultValue={"안녕하세요, 고객님. 주문하신 상품은 현재 준비 중이며 예정 배송일은 9월 6일입니다.\n\n출고가 시작되면 안내 정보를 확인하실 수 있습니다. 추가 문의 사항은 담당자가 검토하겠습니다."} /><div className="badges"><button className="filter active" type="button">검토 완료 표시</button><button className="filter" type="button">수정 필요</button><button className="filter" type="button">근거 부족</button></div><p className="tertiary">이 화면에서는 고객 메시지가 전송되지 않습니다.</p></div></section>
      </div>
    </div>
  );
}
