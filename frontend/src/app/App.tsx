import { useEffect, useState } from "react";
import EnvironmentBanner, { type EnvironmentVariant } from "../components/EnvironmentBanner";
import { resolveRoute, routes } from "./routes";

function currentPath() {
  return window.location.pathname;
}

export default function App({ environment }: { environment?: EnvironmentVariant }) {
  const [pathname, setPathname] = useState(currentPath);
  const activeRoute = resolveRoute(pathname);
  const queryEnvironment = new URLSearchParams(window.location.search).get("environment");
  const activeEnvironment = environment ?? (queryEnvironment === "production-read" ? "PRODUCTION_READ" : "DEMO");

  useEffect(() => {
    const handlePopState = () => setPathname(currentPath());
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  const navigate = (event: React.MouseEvent<HTMLAnchorElement>, path: string) => {
    event.preventDefault();
    if (path === pathname) return;
    window.history.pushState({}, "", path);
    setPathname(path);
  };

  return (
    <div className="app">
      <EnvironmentBanner variant={activeEnvironment} />
      <div className="app-frame">
        <aside className="sidebar">
          <div className="brand">
            <strong>AI Commerce</strong>
            <strong>Operations Agent</strong>
            <small>운영 의사결정 지원</small>
          </div>
          <nav className="nav-list" aria-label="주요 화면">
            {routes.map((route) => (
              <a
                key={route.path}
                href={route.path}
                className={`nav-link ${route.path === activeRoute.path ? "active" : ""}`}
                aria-current={route.path === activeRoute.path ? "page" : undefined}
                onClick={(event) => navigate(event, route.path)}
              >
                <span className="nav-icon" aria-hidden="true">{route.icon}</span>
                <span>{route.navLabel}</span>
                {"badge" in route && <span className="nav-badge">{route.badge}</span>}
              </a>
            ))}
          </nav>
          <div className="safety-card">🛡 안전 원칙<br />외부 주문·재고·결제 변경 없음<br />내부 확인 업무만 생성</div>
        </aside>
        <section className="workspace">
          <header className="header">
            <h1>{activeRoute.label}</h1>
            <div className="provider-row" role="status" aria-label="연동 상태">
              <span className="badge success">● Cafe24</span>
              <span className="badge success">● Toss POS</span>
              <span className="badge warning">▲ eCount 지연</span>
            </div>
            <time className="header-meta">합성 데이터 · 최근 확인 11:42 KST</time>
          </header>
          <main className="main">
            <activeRoute.Component />
          </main>
        </section>
      </div>
    </div>
  );
}
