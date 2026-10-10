import { afterEach, describe, expect, it, vi } from "vitest";
import {
  getCatalogProducts,
  parseCatalogCategories,
  parseCatalogProducts,
  parseCatalogSummary,
} from "../src/api/catalog";

const asOf = "2026-09-11T06:00:00Z";

function envelope(data: unknown) {
  return {
    schema_version: "1.0",
    tenant_id: "demo_store",
    request_id: "req_catalog_test",
    trace_id: "tr_catalog_test",
    evidence_ids: [],
    warnings: [],
    as_of: asOf,
    data,
  };
}

const summary = {
  product_count: 1,
  category_count: 2,
  product_category_count: 2,
  source: "commerce_ops_v2",
  source_as_of: null,
};

const product = {
  id: "73dca1bd-c65a-431b-9eeb-54cdb5111c36",
  cafe24_product_no: 101,
  product_name: "Sample product",
  product_code: "P101",
  custom_product_code: null,
  sale_price: null,
  display_status: "T",
  selling_status: "T",
  sold_out: false,
  operational: true,
  source_as_of: null,
  category_nos: [3, 8],
  categories: [
    { cafe24_category_no: 3, category_name: "Games" },
    { cafe24_category_no: 8, category_name: "Miniatures" },
  ],
};

const page = { items: [product], total: 1, limit: 50, offset: 0, source_as_of: null };

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("C13 catalog API boundary", () => {
  it("parses summary counts and preserves null source timestamp", () => {
    const result = parseCatalogSummary(envelope(summary));
    expect(result.data).toEqual(summary);
    expect(result.data.source_as_of).toBeNull();
    expect(result.as_of).toBe(asOf);
  });

  it("parses product page and Decimal price without treating codes as SKUs", () => {
    const result = parseCatalogProducts(envelope({
      ...page,
      items: [{ ...product, sale_price: "12900.50" }],
    }));
    expect(result.data.items[0]).toEqual({ ...product, sale_price: 12900.5 });
    expect(result.data.items[0].custom_product_code).toBeNull();
    expect(result.data.source_as_of).toBeNull();
  });

  it("preserves null price and accepts an empty items page", () => {
    expect(parseCatalogProducts(envelope(page)).data.items[0].sale_price).toBeNull();
    expect(parseCatalogProducts(envelope({ ...page, items: [], offset: 200 })).data.items).toEqual([]);
  });

  it("parses hierarchy categories and rejects guessed parent relationships", () => {
    const root = { id: "root-id", cafe24_category_no: 3, category_name: "Games",
      category_depth: 1, parent_category_id: null };
    expect(parseCatalogCategories(envelope([root])).data).toEqual([root]);
    expect(() => parseCatalogCategories(envelope([{ ...root, category_depth: 2 }]))).toThrow("category is malformed");
    expect(() => parseCatalogProducts(envelope({ ...page, items: [{ ...product,
      categories: [{ cafe24_category_no: 7, category_name: "Wrong" }] }] }))).toThrow("product is malformed");
  });

  it("rejects malformed summary and envelope", () => {
    expect(() => parseCatalogSummary(envelope({ ...summary, product_count: -1 }))).toThrow("summary is malformed");
    expect(() => parseCatalogSummary(envelope({ ...summary, source: "inventory" }))).toThrow("summary is malformed");
    expect(() => parseCatalogSummary(envelope({ ...summary, source_as_of: "not a timestamp" }))).toThrow("summary is malformed");
    expect(() => parseCatalogSummary(envelope({ ...summary, source_as_of: "2026-02-30T06:00:00Z" }))).toThrow("summary is malformed");
    expect(() => parseCatalogSummary({ ...envelope(summary), evidence_ids: [42] })).toThrow("envelope is malformed");
  });

  it("rejects malformed products and paging response", () => {
    expect(() => parseCatalogProducts(envelope({ ...page, items: [{ ...product, sold_out: "F" }] }))).toThrow("product is malformed");
    expect(() => parseCatalogProducts(envelope({ ...page, items: [{ ...product, category_nos: [-1] }] }))).toThrow("product is malformed");
    expect(() => parseCatalogProducts(envelope({ ...page, items: [{ ...product, sale_price: 12 }] }))).toThrow("product is malformed");
    expect(() => parseCatalogProducts(envelope({ ...page, items: "bad" }))).toThrow("products page is malformed");
    expect(() => parseCatalogProducts(envelope({ ...page, limit: 201 }))).toThrow("products page is malformed");
  });

  it("rejects invalid client paging before a request", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    await expect(getCatalogProducts(0)).rejects.toThrow(RangeError);
    await expect(getCatalogProducts(201)).rejects.toThrow(RangeError);
    await expect(getCatalogProducts(1.5)).rejects.toThrow(RangeError);
    await expect(getCatalogProducts(50, -1)).rejects.toThrow(RangeError);
    await expect(getCatalogProducts(50, 1.5)).rejects.toThrow(RangeError);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("uses C13 paths, configured base URL, and AbortSignal", async () => {
    vi.stubEnv("VITE_USE_REAL_BACKEND", "true");
    vi.stubEnv("VITE_BACKEND_BASE_URL", "https://backend.example");
    vi.resetModules();
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => envelope(summary) })
      .mockResolvedValueOnce({ ok: true, json: async () => envelope(page) })
      .mockResolvedValueOnce({ ok: true, json: async () => envelope(page) })
      .mockResolvedValueOnce({ ok: true, json: async () => envelope([]) });
    vi.stubGlobal("fetch", fetchMock);
    const client = await import("../src/api/catalog");
    const signal = new AbortController().signal;

    expect((await client.getCatalogSummary(signal)).data).toEqual(summary);
    expect((await client.getCatalogProducts(50, 0, signal)).data.items[0].sale_price).toBeNull();
    expect(fetchMock).toHaveBeenNthCalledWith(1, "https://backend.example/api/v1/catalog/summary", {
      method: "GET", headers: { Accept: "application/json" }, signal,
    });
    expect(fetchMock).toHaveBeenNthCalledWith(2, "https://backend.example/api/v1/catalog/products?limit=50&offset=0", {
      method: "GET", headers: { Accept: "application/json" }, signal,
    });
    await client.getCatalogProducts(50, 50, signal, { q: "Warhammer", category_no: 3,
      display_status: "T", sold_out: false, sort_by: "sale_price", sort_dir: "asc" });
    const queryUrl = new URL(fetchMock.mock.calls[2][0] as string);
    expect(queryUrl.searchParams.get("offset")).toBe("50");
    expect(queryUrl.searchParams.get("q")).toBe("Warhammer");
    expect(queryUrl.searchParams.get("category_no")).toBe("3");
    expect(queryUrl.searchParams.get("sold_out")).toBe("false");
    expect(queryUrl.searchParams.get("sort_by")).toBe("sale_price");
    expect(queryUrl.searchParams.get("sort_dir")).toBe("asc");
    expect((await client.getCatalogCategories(2, "parent-uuid", signal)).data).toEqual([]);
    expect(fetchMock).toHaveBeenNthCalledWith(4,
      "https://backend.example/api/v1/catalog/categories?depth=2&parent_category_id=parent-uuid",
      { method: "GET", headers: { Accept: "application/json" }, signal });
  });
});
