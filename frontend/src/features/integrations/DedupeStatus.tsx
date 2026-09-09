type DedupeStatusProps = {
  eventId: string;
  receivedCount: number;
  duplicateCount: number;
  appliedEffectCount: number;
};

export default function DedupeStatus({
  eventId,
  receivedCount,
  duplicateCount,
  appliedEffectCount,
}: DedupeStatusProps) {
  const dedupeSafe =
    receivedCount >= 1 &&
    duplicateCount >= 1 &&
    appliedEffectCount === 1;

  return (
    <section
      className="card card-body stack"
      aria-labelledby="dedupe-status-title"
      data-testid="dedupe-status"
    >
      <div>
        <strong id="dedupe-status-title">
          중복 이벤트 처리 상태
        </strong>

        <p className="muted">
          동일 이벤트가 여러 번 수신되더라도
          재고 효과는 한 번만 적용되어야 합니다.
        </p>
      </div>

      <dl>
        <div>
          <dt>Event ID</dt>
          <dd className="mono">{eventId}</dd>
        </div>

        <div>
          <dt>수신 횟수</dt>
          <dd>{receivedCount}</dd>
        </div>

        <div>
          <dt>중복 횟수</dt>
          <dd>{duplicateCount}</dd>
        </div>

        <div>
          <dt>적용된 Effect</dt>
          <dd>{appliedEffectCount}</dd>
        </div>
      </dl>

      <div
        role="status"
        data-testid="dedupe-result"
        className={
          dedupeSafe
            ? "notice"
            : "notice warning"
        }
      >
        {dedupeSafe
          ? "중복 이벤트가 재고에 추가 반영되지 않았습니다."
          : "중복 이벤트 처리 결과를 확인해야 합니다."}
      </div>
    </section>
  );
}