import type { ApiEnvelope } from "../types/contracts";

const useRealBackend = import.meta.env.VITE_USE_REAL_BACKEND === "true";
const backendBaseUrl = import.meta.env.VITE_BACKEND_BASE_URL ?? "";

export interface CatalogSummary {
  product_count: number;
  category_count: number;
  product_category_count: number;
  source: "commerce_ops_v2";
  source_as_of: string | null;
}

export interface CatalogProduct {
  id: string;
  cafe24_product_no: number;
  product_name: string;
  product_code: string;
  custom_product_code: string | null;
  sale_price: number | null;
  display_status: string;
  selling_status: string;
  sold_out: boolean;
  operational: boolean;
  category_nos: number[];
  categories: CatalogCategory[];
}

export interface CatalogCategory {
  cafe24_category_no: number;
  category_name: string;
}

export interface CatalogHierarchyCategory extends CatalogCategory {
  id: string;
  category_depth: 1 | 2 | 3;
  parent_category_id: string | null;
}

export interface CatalogProductsQuery {
  q?: string;
  display_status?: "T" | "F";
  selling_status?: "T" | "F";
  sold_out?: boolean;
  price_min?: number;
  price_max?: number;
  product_no_min?: number;
  product_no_max?: number;
  category_no?: number;
  sort_by?: "cafe24_product_no" | "sale_price";
  sort_dir?: "asc" | "desc";
}

export interface CatalogProductsPage {
  items: CatalogProduct[];
  total: number;
  limit: number;
  offset: number;
  source_as_of: string | null;
}

function requireCatalog(condition: unknown, part: string): asserts condition {
  if (!condition) throw new Error(`Backend catalog ${part} is malformed`);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function nonNegativeInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}

function timestamp(value: unknown): value is string {
  if (typeof value !== "string") return false;
  const parts = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.exec(value);
  if (!parts || !Number.isFinite(Date.parse(value))) return false;
  const [, yearText, monthText, dayText, hourText, minuteText, secondText] = parts;
  const year = Number(yearText);
  const month = Number(monthText);
  const day = Number(dayText);
  const leapYear = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const days = [31, leapYear ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  return month >= 1 && month <= 12 && day >= 1 && day <= days[month - 1] &&
    Number(hourText) <= 23 && Number(minuteText) <= 59 && Number(secondText) <= 59;
}

function sourceTimestamp(value: unknown): value is string | null {
  return value === null || timestamp(value);
}

function parseEnvelope(value: unknown): ApiEnvelope<unknown> {
  requireCatalog(isRecord(value), "envelope");
  requireCatalog(
    value.schema_version === "1.0" &&
      typeof value.tenant_id === "string" && value.tenant_id.length > 0 &&
      typeof value.request_id === "string" && value.request_id.length > 0 &&
      typeof value.trace_id === "string" && value.trace_id.length > 0 &&
      Array.isArray(value.evidence_ids) && value.evidence_ids.every((id) => typeof id === "string") &&
      Array.isArray(value.warnings) && value.warnings.every((warning) => typeof warning === "string") &&
      timestamp(value.as_of) && isRecord(value.data),
    "envelope",
  );
  return value as unknown as ApiEnvelope<unknown>;
}

export function parseCatalogSummary(value: unknown): ApiEnvelope<CatalogSummary> {
  const envelope = parseEnvelope(value);
  const data = envelope.data as Record<string, unknown>;
  requireCatalog(
    nonNegativeInteger(data.product_count) &&
      nonNegativeInteger(data.category_count) &&
      nonNegativeInteger(data.product_category_count) &&
      data.source === "commerce_ops_v2" && sourceTimestamp(data.source_as_of),
    "summary",
  );
  return envelope as ApiEnvelope<CatalogSummary>;
}

function parseSalePrice(value: unknown): number | null {
  if (value === null) return null;
  // C13 serializes Decimal as a string; keep the UI model numeric.
  requireCatalog(typeof value === "string" && /^-?\d+(?:\.\d+)?$/.test(value), "product");
  const price = Number(value);
  requireCatalog(Number.isFinite(price), "product");
  return price;
}

function parseProduct(value: unknown): CatalogProduct {
  requireCatalog(isRecord(value), "product");
  const categoryNos = value.category_nos;
  requireCatalog(Array.isArray(categoryNos) && categoryNos.every(nonNegativeInteger), "product");
  requireCatalog(
    typeof value.id === "string" && value.id.length > 0 &&
      nonNegativeInteger(value.cafe24_product_no) &&
      typeof value.product_name === "string" &&
      typeof value.product_code === "string" &&
      (value.custom_product_code === null || typeof value.custom_product_code === "string") &&
      typeof value.display_status === "string" &&
      typeof value.selling_status === "string" &&
      typeof value.sold_out === "boolean" &&
      typeof value.operational === "boolean" &&
      Array.isArray(value.categories),
    "product",
  );
  const categories = value.categories.map(parseCategory);
  requireCatalog(
    categories.length === categoryNos.length &&
      categories.every((category, index) => category.cafe24_category_no === categoryNos[index]),
    "product",
  );
  return {
    id: value.id,
    cafe24_product_no: value.cafe24_product_no,
    product_name: value.product_name,
    product_code: value.product_code,
    custom_product_code: value.custom_product_code,
    sale_price: parseSalePrice(value.sale_price),
    display_status: value.display_status,
    selling_status: value.selling_status,
    sold_out: value.sold_out,
    operational: value.operational,
    category_nos: categoryNos,
    categories,
  };
}

function parseCategory(value: unknown): CatalogCategory {
  requireCatalog(isRecord(value) && nonNegativeInteger(value.cafe24_category_no) &&
    typeof value.category_name === "string" && value.category_name.length > 0, "category");
  return { cafe24_category_no: value.cafe24_category_no, category_name: value.category_name };
}

export function parseCatalogCategories(value: unknown): ApiEnvelope<CatalogHierarchyCategory[]> {
  requireCatalog(isRecord(value) && value.schema_version === "1.0" &&
    typeof value.tenant_id === "string" && value.tenant_id.length > 0 &&
    typeof value.request_id === "string" && value.request_id.length > 0 &&
    typeof value.trace_id === "string" && value.trace_id.length > 0 &&
    Array.isArray(value.evidence_ids) && value.evidence_ids.every((item) => typeof item === "string") &&
    Array.isArray(value.warnings) && value.warnings.every((item) => typeof item === "string") &&
    timestamp(value.as_of) && Array.isArray(value.data), "envelope");
  const categories = value.data.map((item: unknown) => {
    const category = parseCategory(item);
    requireCatalog(isRecord(item) && typeof item.id === "string" && item.id.length > 0 &&
      (item.category_depth === 1 || item.category_depth === 2 || item.category_depth === 3) &&
      (item.category_depth === 1 ? item.parent_category_id === null :
        typeof item.parent_category_id === "string" && item.parent_category_id.length > 0), "category");
    return { ...category, id: item.id, category_depth: item.category_depth,
      parent_category_id: item.parent_category_id };
  });
  return { ...value, data: categories } as ApiEnvelope<CatalogHierarchyCategory[]>;
}

export function parseCatalogProducts(value: unknown): ApiEnvelope<CatalogProductsPage> {
  const envelope = parseEnvelope(value);
  const data = envelope.data as Record<string, unknown>;
  requireCatalog(
    Array.isArray(data.items) && nonNegativeInteger(data.total) &&
      nonNegativeInteger(data.limit) && data.limit >= 1 && data.limit <= 200 &&
      nonNegativeInteger(data.offset) && sourceTimestamp(data.source_as_of),
    "products page",
  );
  return {
    ...envelope,
    data: {
      items: data.items.map(parseProduct),
      total: data.total,
      limit: data.limit,
      offset: data.offset,
      source_as_of: data.source_as_of,
    },
  };
}

async function realApiGet(path: string, signal?: AbortSignal): Promise<unknown> {
  if (!useRealBackend) throw new Error("Catalog requires real backend mode");
  const response = await fetch(`${backendBaseUrl}${path}`, {
    method: "GET",
    headers: { Accept: "application/json" },
    signal,
  });
  if (!response.ok) throw new Error(`Backend GET failed: ${response.status}`);
  return response.json() as Promise<unknown>;
}

export async function getCatalogSummary(signal?: AbortSignal): Promise<ApiEnvelope<CatalogSummary>> {
  return parseCatalogSummary(await realApiGet("/api/v1/catalog/summary", signal));
}

export async function getCatalogProducts(
  limit = 50,
  offset = 0,
  signal?: AbortSignal,
  query: CatalogProductsQuery = {},
): Promise<ApiEnvelope<CatalogProductsPage>> {
  if (!nonNegativeInteger(limit) || limit < 1 || limit > 200) {
    throw new RangeError("Catalog limit must be an integer from 1 to 200");
  }
  if (!nonNegativeInteger(offset)) {
    throw new RangeError("Catalog offset must be a non-negative integer");
  }
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== "") params.set(key, String(value));
  }
  return parseCatalogProducts(await realApiGet(`/api/v1/catalog/products?${params}`, signal));
}

export async function getCatalogCategories(
  depth: 1 | 2 | 3,
  parentCategoryId?: string,
  signal?: AbortSignal,
): Promise<ApiEnvelope<CatalogHierarchyCategory[]>> {
  if (depth !== 1 && depth !== 2 && depth !== 3) throw new RangeError("Invalid catalog category depth");
  if (depth === 1 ? parentCategoryId !== undefined : !parentCategoryId) {
    throw new Error("Catalog category parent is malformed");
  }
  const params = new URLSearchParams({ depth: String(depth) });
  if (parentCategoryId) params.set("parent_category_id", parentCategoryId);
  return parseCatalogCategories(await realApiGet(`/api/v1/catalog/categories?${params}`, signal));
}
