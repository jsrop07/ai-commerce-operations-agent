import DashboardPage from "./pages/DashboardPage";
import InquiriesPage from "./pages/InquiriesPage";
import InsightsPage from "./pages/InsightsPage";
import InventoryPage from "./pages/InventoryPage";
import OrdersPage from "./pages/OrdersPage";
import SchedulePage from "./pages/SchedulePage";
import SettingsPage from "./pages/SettingsPage";

export const routes = [
  { path: "/", label: "홈 / 운영 대시보드", navLabel: "홈 / 운영 대시보드", icon: "⌂", badge: "5", Component: DashboardPage },
  { path: "/inventory", label: "상품 & 재고", navLabel: "상품 & 재고", icon: "▦", Component: InventoryPage },
  { path: "/orders", label: "주문 & 매출", navLabel: "주문 & 매출", icon: "▤", Component: OrdersPage },
  { path: "/inquiries", label: "고객 문의 / AI 초안", navLabel: "고객 문의 / AI 초안", icon: "□", badge: "31", Component: InquiriesPage },
  { path: "/schedule", label: "운영 일정", navLabel: "운영 일정", icon: "◫", Component: SchedulePage },
  { path: "/insights", label: "AI 인사이트", navLabel: "AI 인사이트", icon: "✦", Component: InsightsPage },
  { path: "/settings", label: "연동 & 설정", navLabel: "연동 & 설정", icon: "⚙", Component: SettingsPage },
] as const;

export function resolveRoute(pathname: string) {
  return routes.find((route) => route.path === pathname) ?? routes[0];
}
