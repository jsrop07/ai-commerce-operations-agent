import { AIBadge, StatusBadge } from "../../components/Badges";
import InternalTaskAction from "../../components/InternalTaskAction";

const schedule = [
  ["9/4 (수)", "08:00", "생산", "오전 생산 배치 — 레드벨벳 12개", "완료"],
  ["9/4 (수)", "11:00", "입고", "생크림 원자재 입고 · 공급사 지연", "지연"],
  ["9/4 (수)", "14:00", "배송", "오후 배송 출고 — 32건", "진행중"],
  ["9/5 (목)", "08:00", "생산", "티라미수 생산 18개 · 원자재 확인 필요", "예정"],
  ["9/7 (토)", "10:00", "배송", "주말 예약 배송 24건 · 6건 부족 예상", "예정"],
];

export default function SchedulePage() {
  return (
    <div className="page" data-testid="route-schedule">
      <div className="toolbar"><h2 className="section-title">9월 4일–7일 운영 일정</h2><span className="badge warning">▲ 영향 일정 3건</span><span className="right tertiary">합성 일정 · 외부 캘린더 변경 없음</span></div>
      <div className="schedule-grid">
        <section className="card"><div className="card-header">운영 타임라인</div>{schedule.map((item) => <div className="timeline-item" key={`${item[0]}-${item[1]}`}><strong>{item[0]}</strong><span className="mono">{item[1]}</span><span><span className="badge source">{item[2]}</span> {item[3]}</span><StatusBadge>{item[4]}</StatusBadge></div>)}</section>
        <aside className="stack"><div className="notice"><strong>● 입고 지연 영향 요약</strong><p className="muted">생크림 입고가 3일 지연되어 생산 2개 배치와 예약 주문 6건에 영향이 예상됩니다.</p></div><section className="card"><div className="card-header"><AIBadge>AI 일정 재배치 제안</AIBadge></div><div className="card-body stack"><strong>기존 일정 vs. 제안 일정</strong>{[["9/5 생산", "9/8 검토"],["9/5 픽업", "9/8 이후 검토"],["배송 24건", "18건 가능 · 6건 확인"]].map(([before, after]) => <div className="diff" key={before}><span className="diff-before">{before}</span><span>→</span><span className="diff-after">{after}</span></div>)}<p className="tertiary">제안만 표시하며 실제 일정은 변경되지 않습니다.</p><InternalTaskAction /></div></section><div className="notice ai"><strong>⏸ 담당자 확인 대기</strong><br /><span className="muted">영향 주문 안내 초안 검토가 필요합니다.</span></div></aside>
      </div>
    </div>
  );
}
