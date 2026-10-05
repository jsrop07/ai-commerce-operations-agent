import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import InventoryPage, { CatalogPagination } from "../src/app/pages/InventoryPage";
import { CommonAiDrawerHost } from "../src/app/CommonAiDrawerContext";
import { getCatalogCategories, getCatalogProducts, getCatalogSummary } from "../src/api/catalog";
import { getDay08Inventory } from "../src/api/day08";
import { mockApiGet } from "../src/mocks/handlers";
import { catalogPageNumbers } from "../src/features/catalog/catalogState";
import type { CatalogHierarchyCategory, CatalogProductsPage } from "../src/api/catalog";
import type { ApiEnvelope, InventorySnapshot } from "../src/types/contracts";

vi.mock("../src/api/catalog", () => ({
  getCatalogSummary: vi.fn(), getCatalogProducts: vi.fn(), getCatalogCategories: vi.fn(),
}));
vi.mock("../src/api/day08", () => ({ getDay08Inventory: vi.fn() }));

function envelope<T>(data: T): ApiEnvelope<T> {
  return { schema_version: "1.0", tenant_id: "demo_store", request_id: "req_test",
    trace_id: "tr_test", evidence_ids: [], warnings: [], as_of: "2026-09-11T06:00:00Z", data };
}
const summary = { product_count: 2167, category_count: 123, product_category_count: 2165,
  source: "commerce_ops_v2" as const, source_as_of: null };
const baseProduct = {
  id: "product-1", cafe24_product_no: 1, product_name: "C13 sample product",
  product_code: "P1", custom_product_code: null, sale_price: null,
  display_status: "T", selling_status: "T", sold_out: false, operational: true,
  category_nos: [10, 11], categories: [
    { cafe24_category_no: 10, category_name: "Games" },
    { cafe24_category_no: 11, category_name: "Miniatures" },
  ],
};
function productsPage(offset = 0, total = 1): CatalogProductsPage {
  return { items: Array.from({ length: Math.min(50, Math.max(0, total - offset)) }, (_, index) => ({
    ...baseProduct, id: `product-${offset + index + 1}`, cafe24_product_no: offset + index + 1,
    product_name: `Catalog product ${offset + index + 1}`,
  })), total, limit: 50, offset, source_as_of: null };
}
const rootA: CatalogHierarchyCategory = { id: "root-a", cafe24_category_no: 10,
  category_name: "Games", category_depth: 1, parent_category_id: null };
const rootB: CatalogHierarchyCategory = { id: "root-b", cafe24_category_no: 20,
  category_name: "Books", category_depth: 1, parent_category_id: null };
const midA: CatalogHierarchyCategory = { id: "mid-a", cafe24_category_no: 11,
  category_name: "Miniatures", category_depth: 2, parent_category_id: rootA.id };
const midEmpty: CatalogHierarchyCategory = { id: "mid-empty", cafe24_category_no: 12,
  category_name: "No children", category_depth: 2, parent_category_id: rootA.id };
const midB: CatalogHierarchyCategory = { id: "mid-b", cafe24_category_no: 21,
  category_name: "Comics", category_depth: 2, parent_category_id: rootB.id };
const leafA: CatalogHierarchyCategory = { id: "leaf-a", cafe24_category_no: 111,
  category_name: "Figures", category_depth: 3, parent_category_id: midA.id };

beforeEach(() => {
  vi.mocked(getCatalogSummary).mockResolvedValue(envelope(summary));
  vi.mocked(getCatalogProducts).mockImplementation((_limit, offset) => Promise.resolve(envelope(productsPage(offset))));
  vi.mocked(getCatalogCategories).mockImplementation((depth, parent) => Promise.resolve(envelope(
    depth === 1 ? [rootA, rootB] : depth === 2 ?
      parent === rootA.id ? [midA, midEmpty] : parent === rootB.id ? [midB] : [] :
      parent === midA.id ? [leafA] : [],
  )));
  vi.mocked(getDay08Inventory).mockImplementation(() =>
    mockApiGet<ApiEnvelope<InventorySnapshot[]>>("/api/v1/inventory"));
});
afterEach(() => { cleanup(); vi.resetAllMocks(); });
const catalog = () => screen.getByTestId("catalog-section");
const inventory = () => screen.getByTestId("inventory-snapshot-section");

describe("InventoryPage C13 Catalog Browser", () => {
  it("opens the AI drawer with Cafe24 product_no and does not analyze on open", async () => {
    vi.mocked(getCatalogProducts).mockResolvedValue(envelope({
      ...productsPage(), items: [{ ...baseProduct, cafe24_product_no: 245,
        product_name: "IMPERIAL KNIGHTS: KNIGHT QUESTORIS" }],
    }));
    render(<CommonAiDrawerHost><InventoryPage /></CommonAiDrawerHost>);
    const open = await within(catalog()).findByRole("button", {
      name: "IMPERIAL KNIGHTS: KNIGHT QUESTORIS 운영 AI 열기",
    });
    fireEvent.click(open);
    const drawer = screen.getByRole("dialog", { name: "운영 AI" });
    expect(within(drawer).getByText("245")).toBeInTheDocument();
    expect(within(drawer).getByText("아직 분석을 실행하지 않았습니다.")).toBeInTheDocument();
    expect(within(drawer).getByText("상품정보 · 실제 Catalog")).toBeInTheDocument();
  });

  it("opens a VIEW scope from structured catalog filters", async () => {
    render(<CommonAiDrawerHost><InventoryPage /></CommonAiDrawerHost>);
    await within(catalog()).findByRole("button", { name: "상품·재고 화면 운영 AI 열기" });
    fireEvent.change(within(catalog()).getByRole("combobox", { name: "판매 필터" }), {
      target: { value: "T" },
    });
    fireEvent.change(within(catalog()).getByRole("combobox", { name: "품절 필터" }), {
      target: { value: "false" },
    });
    fireEvent.click(within(catalog()).getByRole("button", { name: "상품·재고 화면 운영 AI 열기" }));
    const drawer = screen.getByRole("dialog", { name: "운영 AI" });
    expect(within(drawer).getByText("PRODUCT_INVENTORY", { selector: "dd" })).toBeInTheDocument();
    expect(within(drawer).getByText(/selling: true/)).toBeInTheDocument();
    expect(within(drawer).getByText(/sold_out: false/)).toBeInTheDocument();
    expect(within(drawer).getByText("아직 분석을 실행하지 않았습니다.")).toBeInTheDocument();
  });

  it("does not send a phone-like catalog search into VIEW context", async () => {
    render(<CommonAiDrawerHost><InventoryPage /></CommonAiDrawerHost>);
    const search = within(catalog()).getByRole("textbox", { name: "Catalog 검색어" });
    fireEvent.change(search, { target: { value: "010-1234-5678" } });
    fireEvent.submit(search.closest("form")!);
    const viewButton = within(catalog()).getByRole("button", { name: "상품·재고 화면 운영 AI 열기" });
    expect(viewButton).toBeDisabled();
    expect(screen.queryByRole("dialog", { name: "운영 AI" })).not.toBeInTheDocument();
  });
  it("keeps Catalog master separate, shows real category names, and hides operational", async () => {
    render(<InventoryPage />);
    expect(await within(catalog()).findByText(/상품 2167건 · 카테고리 123건/)).toBeInTheDocument();
    expect(within(catalog()).getByText("원본 기준시각 미확인")).toBeInTheDocument();
    const row = (await within(catalog()).findByText("Catalog product 1")).closest("tr")!;
    expect(within(row).getByText("Games · Miniatures")).toBeInTheDocument();
    expect(within(row).getAllByText("미확인")).toHaveLength(2);
    expect(within(catalog()).queryByRole("columnheader", { name: "운영" })).not.toBeInTheDocument();
    expect(within(catalog()).queryByRole("columnheader", { name: "카테고리 번호" })).not.toBeInTheDocument();
    expect(await within(inventory()).findByText("sku_demo_002")).toBeInTheDocument();
    expect(getCatalogProducts).toHaveBeenCalledWith(50, 0, expect.any(AbortSignal),
      { sort_by: "cafe24_product_no", sort_dir: "desc" });
  });

  it("does not guess category names when no relation exists", async () => {
    vi.mocked(getCatalogProducts).mockResolvedValue(envelope({ ...productsPage(), items: [{
      ...baseProduct, category_nos: [], categories: [],
    }] }));
    render(<InventoryPage />);
    const row = (await within(catalog()).findByText("C13 sample product")).closest("tr")!;
    expect(within(row).getAllByText("미확인")).toHaveLength(3);
    expect(within(row).queryByText("Games")).not.toBeInTheDocument();
  });

  it("submits q by Enter without a search button, resets page, and restores q from URL", async () => {
    window.history.replaceState({}, "", "/inventory?page=3&q=old&sort_by=sale_price&sort_dir=asc");
    vi.mocked(getCatalogProducts).mockImplementation((_limit, offset) => Promise.resolve(envelope(productsPage(offset, 120))));
    render(<InventoryPage />);
    const input = within(catalog()).getByRole("textbox", { name: "Catalog 검색어" });
    expect(input).toHaveValue("old");
    expect(input).toHaveAttribute("placeholder", "상품 번호 · 코드 · 판매가 · 카테고리 검색");
    expect(within(catalog()).queryByRole("button", { name: "검색" })).not.toBeInTheDocument();
    await waitFor(() => expect(getCatalogProducts).toHaveBeenCalledWith(50, 100, expect.any(AbortSignal),
      { q: "old", sort_by: "sale_price", sort_dir: "asc" }));
    fireEvent.change(input, { target: { value: "warhammer" } });
    expect(getCatalogProducts).toHaveBeenCalledTimes(1);
    fireEvent.keyDown(input, { key: "Enter" });
    fireEvent.submit(input.closest("form")!);
    await waitFor(() => expect(getCatalogProducts).toHaveBeenLastCalledWith(50, 0, expect.any(AbortSignal),
      { q: "warhammer", sort_by: "sale_price", sort_dir: "asc" }));
    expect(window.location.search).toContain("page=1");
  });

  it("restores, applies, and clears price range through URL and server query", async () => {
    window.history.replaceState({}, "", "/inventory?page=3&price_min=100&price_max=250");
    vi.mocked(getCatalogProducts).mockImplementation((_limit, offset) => Promise.resolve(envelope(productsPage(offset, 120))));
    render(<InventoryPage />);
    await waitFor(() => expect(getCatalogProducts).toHaveBeenCalledWith(50, 100, expect.any(AbortSignal),
      { price_min: 100, price_max: 250, sort_by: "cafe24_product_no", sort_dir: "desc" }));
    fireEvent.click(within(catalog()).getByRole("button", { name: /^판매가$/ }));
    const popover = within(catalog()).getByRole("group", { name: "판매가 범위" });
    const min = within(popover).getByRole("textbox", { name: "최소 가격" });
    const max = within(popover).getByRole("textbox", { name: "최대 가격" });
    expect(min).toHaveValue("100"); expect(max).toHaveValue("250");
    fireEvent.change(min, { target: { value: "150" } });
    fireEvent.change(max, { target: { value: "300" } });
    fireEvent.click(within(popover).getByRole("button", { name: "적용" }));
    await waitFor(() => expect(getCatalogProducts).toHaveBeenLastCalledWith(50, 0, expect.any(AbortSignal),
      { price_min: 150, price_max: 300, sort_by: "cafe24_product_no", sort_dir: "desc" }));
    expect(window.location.search).toContain("price_min=150");
    expect(window.location.search).toContain("price_max=300");
    expect(window.location.search).toContain("page=1");
    window.history.pushState({}, "", "/inventory?page=2&price_min=100&price_max=250");
    fireEvent(window, new PopStateEvent("popstate"));
    await waitFor(() => expect(getCatalogProducts).toHaveBeenLastCalledWith(50, 50, expect.any(AbortSignal),
      { price_min: 100, price_max: 250, sort_by: "cafe24_product_no", sort_dir: "desc" }));
    fireEvent.click(within(catalog()).getByRole("button", { name: /^판매가$/ }));
    const restored = within(catalog()).getByRole("group", { name: "판매가 범위" });
    expect(within(restored).getByRole("textbox", { name: "최소 가격" })).toHaveValue("100");
    fireEvent.click(within(restored).getByRole("button", { name: "초기화" }));
    await waitFor(() => expect(getCatalogProducts).toHaveBeenLastCalledWith(50, 0, expect.any(AbortSignal),
      { sort_by: "cafe24_product_no", sort_dir: "desc" }));
    expect(window.location.search).not.toContain("price_min");
    expect(window.location.search).not.toContain("price_max");
  });

  it("blocks invalid price ranges and closes the popover on Escape and outside click", async () => {
    render(<InventoryPage />);
    await waitFor(() => expect(getCatalogProducts).toHaveBeenCalledTimes(1));
    const priceButton = within(catalog()).getByRole("button", { name: /^판매가$/ });
    fireEvent.click(priceButton);
    const popover = within(catalog()).getByRole("group", { name: "판매가 범위" });
    fireEvent.change(within(popover).getByRole("textbox", { name: "최소 가격" }), { target: { value: "300" } });
    fireEvent.change(within(popover).getByRole("textbox", { name: "최대 가격" }), { target: { value: "100" } });
    fireEvent.click(within(popover).getByRole("button", { name: "적용" }));
    expect(within(popover).getByRole("alert")).toHaveTextContent("최소 가격은 최대 가격보다 클 수 없습니다.");
    expect(getCatalogProducts).toHaveBeenCalledTimes(1);
    fireEvent.change(within(popover).getByRole("textbox", { name: "최소 가격" }), { target: { value: "abc" } });
    fireEvent.click(within(popover).getByRole("button", { name: "적용" }));
    expect(within(popover).getByRole("alert")).toHaveTextContent("가격은 0 이상의 숫자로 입력해 주세요.");
    fireEvent.keyDown(document, { key: "Escape" });
    expect(within(catalog()).queryByRole("group", { name: "판매가 범위" })).not.toBeInTheDocument();
    fireEvent.click(priceButton);
    fireEvent.pointerDown(within(catalog()).getByRole("heading", { name: "상품 목록" }));
    expect(within(catalog()).queryByRole("group", { name: "판매가 범위" })).not.toBeInTheDocument();
  });

  it("maps display, selling, and sold-out filters and resets page", async () => {
    window.history.replaceState({}, "", "/inventory?page=2&display_status=T&selling_status=F&sold_out=false");
    vi.mocked(getCatalogProducts).mockImplementation((_limit, offset) => Promise.resolve(envelope(productsPage(offset, 120))));
    render(<InventoryPage />);
    const display = within(catalog()).getByRole("combobox", { name: "진열 필터" });
    const selling = within(catalog()).getByRole("combobox", { name: "판매 필터" });
    const soldOut = within(catalog()).getByRole("combobox", { name: "품절 필터" });
    expect(display).toHaveValue("T"); expect(selling).toHaveValue("F"); expect(soldOut).toHaveValue("false");
    await waitFor(() => expect(getCatalogProducts).toHaveBeenCalledWith(50, 50, expect.any(AbortSignal),
      { display_status: "T", selling_status: "F", sold_out: false,
        sort_by: "cafe24_product_no", sort_dir: "desc" }));
    fireEvent.change(display, { target: { value: "" } });
    fireEvent.change(selling, { target: { value: "T" } });
    fireEvent.change(soldOut, { target: { value: "true" } });
    await waitFor(() => expect(getCatalogProducts).toHaveBeenLastCalledWith(50, 0, expect.any(AbortSignal),
      { selling_status: "T", sold_out: true, sort_by: "cafe24_product_no", sort_dir: "desc" }));
    expect(window.location.search).not.toContain("display_status");
  });

  it("loads hierarchy by parent UUID and uses the deepest selected category number", async () => {
    render(<InventoryPage />);
    await waitFor(() => expect(getCatalogCategories).toHaveBeenCalledWith(1, undefined, expect.any(AbortSignal)));
    await waitFor(() => expect(within(catalog()).getByRole("combobox", { name: "대주제" })).toBeEnabled());
    const root = within(catalog()).getByRole("combobox", { name: "대주제" });
    const middle = within(catalog()).getByRole("combobox", { name: "중간주제" });
    const leaf = within(catalog()).getByRole("combobox", { name: "소주제" });
    expect(middle).toBeDisabled(); expect(leaf).toBeDisabled();
    fireEvent.change(root, { target: { value: "10" } });
    await waitFor(() => expect(getCatalogCategories).toHaveBeenCalledWith(2, rootA.id, expect.any(AbortSignal)));
    await waitFor(() => expect(middle).toBeEnabled());
    expect(getCatalogProducts).toHaveBeenLastCalledWith(50, 0, expect.any(AbortSignal), expect.objectContaining({ category_no: 10 }));
    fireEvent.change(middle, { target: { value: "11" } });
    await waitFor(() => expect(getCatalogCategories).toHaveBeenCalledWith(3, midA.id, expect.any(AbortSignal)));
    await waitFor(() => expect(leaf).toBeEnabled());
    expect(getCatalogProducts).toHaveBeenLastCalledWith(50, 0, expect.any(AbortSignal), expect.objectContaining({ category_no: 11 }));
    fireEvent.change(leaf, { target: { value: "111" } });
    await waitFor(() => expect(getCatalogProducts).toHaveBeenLastCalledWith(50, 0, expect.any(AbortSignal), expect.objectContaining({ category_no: 111 })));
    fireEvent.change(root, { target: { value: "20" } });
    expect(middle).toHaveValue(""); expect(leaf).toHaveValue("");
    expect(window.location.search).not.toContain("category_3");
    await waitFor(() => expect(getCatalogCategories).toHaveBeenCalledWith(2, rootB.id, expect.any(AbortSignal)));
  });

  it("disables leaf select when the actual middle category has no children", async () => {
    render(<InventoryPage />);
    const root = within(catalog()).getByRole("combobox", { name: "대주제" });
    const middle = within(catalog()).getByRole("combobox", { name: "중간주제" });
    await waitFor(() => expect(root).toBeEnabled());
    fireEvent.change(root, { target: { value: "10" } });
    await waitFor(() => expect(middle).toBeEnabled());
    fireEvent.change(middle, { target: { value: "12" } });
    await waitFor(() => expect(getCatalogCategories).toHaveBeenCalledWith(3, midEmpty.id, expect.any(AbortSignal)));
    await waitFor(() => expect(within(catalog()).getByRole("combobox", { name: "소주제" })).toBeDisabled());
  });

  it("restores category path and page from URL and popstate", async () => {
    window.history.replaceState({}, "", "/inventory?page=2&category_1=10&category_2=11&category_3=111");
    vi.mocked(getCatalogProducts).mockImplementation((_limit, offset) => Promise.resolve(envelope(productsPage(offset, 120))));
    render(<InventoryPage />);
    await waitFor(() => expect(getCatalogProducts).toHaveBeenCalledWith(50, 50, expect.any(AbortSignal), expect.objectContaining({ category_no: 111 })));
    expect(within(catalog()).getByRole("combobox", { name: "대주제" })).toHaveValue("10");
    expect(within(catalog()).getByRole("combobox", { name: "중간주제" })).toHaveValue("11");
    expect(within(catalog()).getByRole("combobox", { name: "소주제" })).toHaveValue("111");
    window.history.pushState({}, "", "/inventory?page=1&category_1=20");
    fireEvent(window, new PopStateEvent("popstate"));
    await waitFor(() => expect(getCatalogProducts).toHaveBeenLastCalledWith(50, 0, expect.any(AbortSignal), expect.objectContaining({ category_no: 20 })));
  });

  it("toggles server sort, active arrows, and resets page", async () => {
    window.history.replaceState({}, "", "/inventory?page=2");
    vi.mocked(getCatalogProducts).mockImplementation((_limit, offset) => Promise.resolve(envelope(productsPage(offset, 120))));
    render(<InventoryPage />);
    const productNo = await within(catalog()).findByRole("button", { name: "카페24 상품 번호 ↓" });
    expect(productNo.closest("th")).toHaveAttribute("aria-sort", "descending");
    expect(within(catalog()).getByRole("button", { name: "판매가 ↕" }).closest("th")).toHaveAttribute("aria-sort", "none");
    fireEvent.click(productNo);
    await waitFor(() => expect(getCatalogProducts).toHaveBeenLastCalledWith(50, 0, expect.any(AbortSignal), { sort_by: "cafe24_product_no", sort_dir: "asc" }));
    expect(within(catalog()).getByRole("button", { name: "카페24 상품 번호 ↑" })).toBeInTheDocument();
    fireEvent.click(within(catalog()).getByRole("button", { name: "판매가 ↕" }));
    await waitFor(() => expect(getCatalogProducts).toHaveBeenLastCalledWith(50, 0, expect.any(AbortSignal), { sort_by: "sale_price", sort_dir: "desc" }));
    expect(within(catalog()).getByRole("button", { name: "판매가 ↓" }).closest("th")).toHaveAttribute("aria-sort", "descending");
    expect(within(catalog()).getByRole("button", { name: "카페24 상품 번호 ↕" }).closest("th")).toHaveAttribute("aria-sort", "none");
    fireEvent.click(within(catalog()).getByRole("button", { name: "판매가 ↓" }));
    await waitFor(() => expect(getCatalogProducts).toHaveBeenLastCalledWith(50, 0, expect.any(AbortSignal), { sort_by: "sale_price", sort_dir: "asc" }));
    expect(within(catalog()).getByRole("button", { name: "판매가 ↑" })).toBeInTheDocument();
  });

  it("renders numeric pagination, ellipses, range, and URL page changes", async () => {
    window.history.replaceState({}, "", "/inventory?page=6");
    vi.mocked(getCatalogProducts).mockImplementation((_limit, offset) => Promise.resolve(envelope(productsPage(offset, 2167))));
    render(<InventoryPage />);
    const paging = await within(catalog()).findByRole("navigation", { name: "Catalog 상품 페이지" });
    expect(within(paging).getByText("251–300 / 총 2167건")).toBeInTheDocument();
    expect(within(paging).getByRole("button", { name: "1 페이지" })).toBeInTheDocument();
    expect(within(paging).getByRole("button", { name: "44 페이지" })).toBeInTheDocument();
    expect(within(paging).getByRole("button", { name: "6 페이지" })).toHaveAttribute("aria-current", "page");
    expect(within(paging).getAllByText("…")).toHaveLength(2);
    fireEvent.click(within(paging).getByRole("button", { name: "7 페이지" }));
    await waitFor(() => expect(getCatalogProducts).toHaveBeenLastCalledWith(50, 300, expect.any(AbortSignal), { sort_by: "cafe24_product_no", sort_dir: "desc" }));
    expect(window.location.search).toContain("page=7");
  });

  it("tests the last page directly and handles invalid page safely", async () => {
    const onPageChange = vi.fn();
    const { unmount } = render(<CatalogPagination page={productsPage(2150, 2167)} currentPage={44} onPageChange={onPageChange} />);
    const paging = screen.getByRole("navigation", { name: "Catalog 상품 페이지" });
    expect(within(paging).getByText("2151–2167 / 총 2167건")).toBeInTheDocument();
    expect(within(paging).getByRole("button", { name: "다음 페이지" })).toBeDisabled();
    expect(catalogPageNumbers(6, 44)).toEqual([1, "ellipsis", 4, 5, 6, 7, 8, "ellipsis", 44]);
    unmount();
    window.history.replaceState({}, "", "/inventory?page=999");
    vi.mocked(getCatalogProducts).mockImplementation((_limit, offset) => Promise.resolve(envelope(productsPage(offset, 0))));
    render(<InventoryPage />);
    expect(await within(catalog()).findByText("표시할 Catalog 상품이 없습니다")).toBeInTheDocument();
    expect(window.location.search).toContain("page=1");
  });

  it("aborts stale product requests and keeps prior rows on an error", async () => {
    let resolveOld: ((value: ApiEnvelope<CatalogProductsPage>) => void) | undefined;
    const oldResponse = new Promise<ApiEnvelope<CatalogProductsPage>>((resolve) => { resolveOld = resolve; });
    vi.mocked(getCatalogProducts).mockImplementation((_limit, offset) =>
      offset === 50 ? oldResponse : Promise.resolve(envelope(productsPage(offset, 120))));
    render(<InventoryPage />);
    const paging = await within(catalog()).findByRole("navigation", { name: "Catalog 상품 페이지" });
    fireEvent.click(within(paging).getByRole("button", { name: "다음 페이지" }));
    expect(within(catalog()).getByText("Catalog product 1")).toBeInTheDocument();
    fireEvent.click(within(paging).getByRole("button", { name: "다음 페이지" }));
    await within(paging).findByText("101–120 / 총 120건");
    expect(vi.mocked(getCatalogProducts).mock.calls.find((call) => call[1] === 50)?.[2]?.aborted).toBe(true);
    await act(async () => { resolveOld?.(envelope(productsPage(50, 120))); });
    expect(within(catalog()).getByText("Catalog product 101")).toBeInTheDocument();
    expect(within(catalog()).queryByText("Catalog product 51")).not.toBeInTheDocument();
    vi.mocked(getCatalogProducts).mockRejectedValue(new Error("Page unavailable"));
    fireEvent.click(within(paging).getByRole("button", { name: "이전 페이지" }));
    expect(await within(catalog()).findByText("상품 페이지를 불러오지 못했습니다")).toBeInTheDocument();
    expect(within(catalog()).getByText("Catalog product 101")).toBeInTheDocument();
    expect(within(inventory()).getByText("sku_demo_002")).toBeInTheDocument();
  });

  it("ignores stale category children when the parent changes", async () => {
    let resolveOld: ((value: ApiEnvelope<CatalogHierarchyCategory[]>) => void) | undefined;
    const oldResponse = new Promise<ApiEnvelope<CatalogHierarchyCategory[]>>((resolve) => { resolveOld = resolve; });
    vi.mocked(getCatalogCategories).mockImplementation((depth, parent) =>
      depth === 2 && parent === rootA.id ? oldResponse :
        Promise.resolve(envelope(depth === 1 ? [rootA, rootB] : parent === rootB.id ? [midB] : [])));
    render(<InventoryPage />);
    const root = within(catalog()).getByRole("combobox", { name: "대주제" });
    await waitFor(() => expect(root).toBeEnabled());
    fireEvent.change(root, { target: { value: "10" } });
    fireEvent.change(root, { target: { value: "20" } });
    await waitFor(() => expect(within(catalog()).getByRole("combobox", { name: "중간주제" })).toBeEnabled());
    expect(vi.mocked(getCatalogCategories).mock.calls.find((call) => call[0] === 2 && call[1] === rootA.id)?.[2]?.aborted).toBe(true);
    await act(async () => { resolveOld?.(envelope([midA])); });
    expect(within(catalog()).getByRole("option", { name: "Comics" })).toBeInTheDocument();
    expect(within(catalog()).queryByRole("option", { name: "Miniatures" })).not.toBeInTheDocument();
  });

  it("keeps Catalog and Inventory failures independent", async () => {
    vi.mocked(getCatalogProducts).mockRejectedValue(new Error("Catalog unavailable"));
    render(<InventoryPage />);
    expect(await within(catalog()).findByText("상품 페이지를 불러오지 못했습니다")).toBeInTheDocument();
    expect(await within(inventory()).findByText("sku_demo_002")).toBeInTheDocument();
    cleanup();
    vi.mocked(getCatalogProducts).mockResolvedValue(envelope(productsPage()));
    vi.mocked(getDay08Inventory).mockRejectedValue(new Error("Inventory unavailable"));
    render(<InventoryPage />);
    expect(await within(catalog()).findByText("Catalog product 1")).toBeInTheDocument();
    expect(await within(inventory()).findByText("재고 데이터를 불러오지 못했습니다")).toBeInTheDocument();
  });
});
