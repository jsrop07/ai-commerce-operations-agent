export type EnvironmentVariant = "DEMO" | "PRODUCTION_READ";

export default function EnvironmentBanner({ variant }: { variant: EnvironmentVariant }) {
  const production = variant === "PRODUCTION_READ";
  return (
    <div
      className={`environment-banner ${production ? "production" : "demo"}`}
      role="banner"
      aria-label={production ? "Production Read-Only 환경" : "Demo 환경"}
    >
      <span aria-hidden="true">{production ? "🔒" : "◆"}</span>
      <span>{production ? "Production Read-Only · 운영환경 읽기 전용" : "Demo 환경 · 합성 데이터"}</span>
      <span className="environment-detail">
        {production ? "조회와 내부 확인 업무만 사용할 수 있습니다" : "실제 고객·주문·재고 정보가 아닙니다"}
      </span>
    </div>
  );
}
