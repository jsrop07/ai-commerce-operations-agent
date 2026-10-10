import {
  useEffect,
  useState,
} from "react";
import EnvironmentBanner, { type EnvironmentVariant } from "../components/EnvironmentBanner";
import FloatingAiLauncher from "../components/FloatingAiLauncher";
import {
  CommonAiDrawerHost,
} from "./CommonAiDrawerContext";
import { resolveRoute, routes } from "./routes";



function currentPath() {
  return window.location.pathname;
}

export default function App({ environment }: { environment?: EnvironmentVariant }) {
  const [pathname, setPathname] = useState(currentPath);
  const publicDemo = import.meta.env.VITE_USE_REAL_BACKEND === "true";
  const queryEnvironment = new URLSearchParams(window.location.search).get("environment");
  const activeEnvironment =
    publicDemo ? "DEMO" : environment ??
    (queryEnvironment === "production-read"
      ? "PRODUCTION_READ"
      : queryEnvironment === "local-eval"
        ? "LOCAL_EVAL"
        : "DEMO");
  const visibleRoutes = publicDemo ? routes.filter((route) => route.path !== "/inquiries") : routes;
  const activeRoute = resolveRoute(pathname, publicDemo);

  const headerDataLabel =
    activeEnvironment === "LOCAL_EVAL"
      ? "로컬 평가 데이터"
      : activeEnvironment === "PRODUCTION_READ"
        ? "운영 데이터 · 읽기 전용"
        : "합성 데이터";

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
    <CommonAiDrawerHost sessionRequired={publicDemo} currentPage={pathname}>
      <div className="app commerce-app">
        {activeEnvironment !== "DEMO" && (
          <EnvironmentBanner variant={activeEnvironment} />
        )}

        <div className="app-frame commerce-frame">
          <section className="workspace commerce-workspace">
            <header className="commerce-topbar">
              <div className="commerce-topbar-brand">
                <strong>AI COMMERCE</strong>
                <span>/ OPERATIONS</span>
              </div>

              <nav
                className="commerce-topnav"
                aria-label="주요 화면"
              >
                {visibleRoutes.map((route) => (
                  <a
                    key={route.path}
                    href={route.path}
                    className={`commerce-nav-link ${
                      route.path === activeRoute.path ? "active" : ""
                    }`}
                    aria-current={
                      route.path === activeRoute.path
                        ? "page"
                        : undefined
                    }
                    onClick={(event) => navigate(event, route.path)}
                  >
                    <span>{route.navLabel}</span>
                    {"badge" in route && (
                      <span className="nav-badge">
                        {route.badge}
                      </span>
                    )}
                  </a>
                ))}
              </nav>
            </header>
            <main className="main commerce-main">
              <activeRoute.Component />
            </main>
          </section>
        </div>

        {publicDemo && <FloatingAiLauncher />}
      </div>
    </CommonAiDrawerHost>
  );
}
