export type CatalogSortBy = "cafe24_product_no" | "sale_price";
export type CatalogSortDir = "asc" | "desc";

export interface CatalogUrlState {
  page: number;
  q: string;
  display_status: "" | "T" | "F";
  selling_status: "" | "T" | "F";
  sold_out: "" | "true" | "false";
  price_min: number | null;
  price_max: number | null;
  category_1: number | null;
  category_2: number | null;
  category_3: number | null;
  sort_by: CatalogSortBy;
  sort_dir: CatalogSortDir;
}

function categoryNumber(value: string | null): number | null {
  if (value === null || !/^\d+$/.test(value)) return null;
  const number = Number(value);
  return Number.isSafeInteger(number) && number >= 0 ? number : null;
}

function priceNumber(value: string | null): number | null {
  if (value === null || !/^\d+(?:\.\d+)?$/.test(value)) return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

export function readCatalogUrl(search: string): CatalogUrlState {
  const params = new URLSearchParams(search);
  const rawPage = params.get("page");
  const pageNumber = rawPage && /^\d+$/.test(rawPage) ? Number(rawPage) : 1;
  const page = Number.isSafeInteger(pageNumber) && pageNumber > 0 ? pageNumber : 1;
  const display = params.get("display_status");
  const selling = params.get("selling_status");
  const soldOut = params.get("sold_out");
  const sortBy = params.get("sort_by");
  const sortDir = params.get("sort_dir");
  return {
    page,
    q: params.get("q") ?? "",
    display_status: display === "T" || display === "F" ? display : "",
    selling_status: selling === "T" || selling === "F" ? selling : "",
    sold_out: soldOut === "true" || soldOut === "false" ? soldOut : "",
    price_min: priceNumber(params.get("price_min")),
    price_max: priceNumber(params.get("price_max")),
    category_1: categoryNumber(params.get("category_1")),
    category_2: categoryNumber(params.get("category_2")),
    category_3: categoryNumber(params.get("category_3")),
    sort_by: sortBy === "sale_price" ? sortBy : "cafe24_product_no",
    sort_dir: sortDir === "asc" ? sortDir : "desc",
  };
}

export function writeCatalogUrl(state: CatalogUrlState, mode: "push" | "replace" = "push"): void {
  const url = new URL(window.location.href);
  const params = url.searchParams;
  params.set("page", String(state.page));
  for (const key of ["q", "display_status", "selling_status", "sold_out"] as const) {
    if (state[key]) params.set(key, state[key]);
    else params.delete(key);
  }
  for (const key of ["category_1", "category_2", "category_3"] as const) {
    if (state[key] !== null) params.set(key, String(state[key]));
    else params.delete(key);
  }
  for (const key of ["price_min", "price_max"] as const) {
    if (state[key] !== null) params.set(key, String(state[key]));
    else params.delete(key);
  }
  params.set("sort_by", state.sort_by);
  params.set("sort_dir", state.sort_dir);
  window.history[mode === "push" ? "pushState" : "replaceState"]({}, "", url);
}

export function catalogPageNumbers(current: number, total: number): Array<number | "ellipsis"> {
  if (total <= 0) return [];
  const pages = new Set([1, total]);
  for (let page = Math.max(1, current - 2); page <= Math.min(total, current + 2); page += 1) {
    pages.add(page);
  }
  const ordered = [...pages].sort((a, b) => a - b);
  const result: Array<number | "ellipsis"> = [];
  ordered.forEach((page, index) => {
    if (index > 0) {
      const gap = page - ordered[index - 1];
      if (gap === 2) result.push(page - 1);
      else if (gap > 2) result.push("ellipsis");
    }
    result.push(page);
  });
  return result;
}
