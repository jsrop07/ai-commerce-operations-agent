export type EnvironmentVariant =
  | "DEMO"
  | "LOCAL_EVAL"
  | "PRODUCTION_READ";

export default function EnvironmentBanner({
  variant,
}: {
  variant: EnvironmentVariant;
}) {
  const production = variant === "PRODUCTION_READ";
  const localEval = variant === "LOCAL_EVAL";

  const label = production
    ? "Production Read-Only 환경"
    : localEval
      ? "Local Evaluation 환경"
      : "Demo 환경";

  const summary = production
    ? "실제 운영 데이터 · 읽기 전용"
    : localEval
      ? "비공개 actual-scale 평가 · 로컬 검증 전용"
      : "합성 데이터 · 실적·고객·주문·재고 정보가 아닙니다";

  const detail = production
    ? "외부 쓰기 없이 운영 데이터를 읽기 전용으로 확인합니다."
    : localEval
      ? "PRIVATE_ACTUAL_EVAL 집계 결과를 검증하며 Demo 공개용 데이터가 아닙니다."
      : "합성 운영 데이터를 사용하며 실제 운영 결과를 의미하지 않습니다.";

  return (
    <div
      className={`environment-banner ${
        production
          ? "production"
          : localEval
            ? "local-eval"
            : "demo"
      }`}
      role="banner"
      aria-label={label}
    >
      <span aria-hidden="true">
        {production ? "🔒" : localEval ? "◆" : "◆"}
      </span>

      <span>
        {label} · {summary}
      </span>

      <span className="environment-detail">
        {detail}
      </span>
    </div>
  );
}