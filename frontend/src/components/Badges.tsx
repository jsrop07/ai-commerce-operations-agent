export function RiskBadge({ level }: { level: "critical" | "warning" | "ok" }) {
  const label = level === "critical" ? "● 위험" : level === "warning" ? "▲ 주의" : "✓ 정상";
  return <span className={`badge ${level === "ok" ? "success" : level}`}>{label}</span>;
}

export function SourceBadge({ children }: { children: string }) {
  return <span className="badge source">{children}</span>;
}

export function AIBadge({ children = "AI" }: { children?: string }) {
  return <span className="badge ai">✦ {children}</span>;
}

export function StatusBadge({ children }: { children: string }) {
  const state = ["완료", "배송중", "정상"].includes(children) ? "success" : ["지연", "보류"].includes(children) ? "warning" : "source";
  return <span className={`badge ${state}`}>{children}</span>;
}
