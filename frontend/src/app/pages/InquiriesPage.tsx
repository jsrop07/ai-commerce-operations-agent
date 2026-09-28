import SystemState from "../../components/SystemStates";

export default function InquiriesPage() {
  return (
    <div className="page" data-testid="route-inquiries">
      <SystemState
        state="empty"
        title="고객문의 AI 기능은 현재 사용하지 않습니다"
        description="문의 목록, 새 문의, 내부 읽음 연결은 후속 R11 범위입니다. 외부 고객답변 전송 기능은 없습니다."
      />
    </div>
  );
}
