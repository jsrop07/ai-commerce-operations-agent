export default function InternalTaskAction({ compact = false }: { compact?: boolean }) {
  return (
    <button className="internal-action" type="button" aria-label="내부 확인 업무 만들기" style={compact ? { padding: "5px 10px", fontSize: 11 } : undefined}>
      📋 확인 업무 만들기
    </button>
  );
}
